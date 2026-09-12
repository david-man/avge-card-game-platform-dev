from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ..constants import User
from . import protocol
from . import serialization
from .accounts import Account, AccountStore
from .matchmaker import Matchmaker
from .session import GameSession, safe_send

logger = logging.getLogger(__name__)


async def websocket_endpoint(websocket: WebSocket, matchmaker: Matchmaker, accounts: AccountStore) -> None:
    await websocket.accept()

    try:
        first_raw = await websocket.receive_json()
        first_msg = protocol.parse_client_message(first_raw)
    except WebSocketDisconnect:
        return
    except (ValueError, ValidationError):
        await safe_send(websocket, protocol.ErrorMessage(message="First message must be login").model_dump())
        await websocket.close()
        return

    if not isinstance(first_msg, protocol.LoginMessage):
        await safe_send(websocket, protocol.ErrorMessage(message="First message must be login").model_dump())
        await websocket.close()
        return

    account: Account | None = None
    if first_msg.auth_token is not None:
        account = accounts.login_by_token(first_msg.auth_token)
    if account is None and first_msg.username is not None:
        # login_by_username() internally offloads only its blocking disk write
        # (AccountStore._persist()) to a thread the first time a username is seen, so it avoids
        # stalling every other concurrent match's websocket I/O for the duration of that write
        # without racing the check-then-insert itself across threads.
        account = await accounts.login_by_username(first_msg.username)
    if account is None:
        await safe_send(websocket, protocol.ErrorMessage(
            code="login_failed", message="Provide a username or a valid auth_token",
        ).model_dump())
        await websocket.close()
        return

    try:
        # Precedence: a newer login for the same account supersedes an older connection, which
        # gets notified and closed here - that flows into ITS OWN WebSocketDisconnect handling
        # below (session.detach(), account release), reusing all the existing disconnect machinery
        # rather than needing separate game-ending logic for this case.
        await matchmaker.claim(account.account_id, websocket)
        await safe_send(websocket, protocol.LoggedInMessage(
            account_id=account.account_id, username=account.username, auth_token=account.auth_token,
        ).model_dump())

        session: GameSession | None = None
        user: User | None = None
        found = matchmaker.find_active_game(account.account_id)
        if found is not None:
            session, user = found
            if not session.attach(user, websocket):
                # The session finished (game_over already sent, engine task torn down) in the
                # gap between find_active_game() reading a still-live registry entry and this
                # attach() call - see session.py's attach() docstring. Treat this connection as
                # if it had no active game rather than binding it to a dead one.
                session, user = None, None
                await safe_send(websocket, protocol.ErrorMessage(
                    code="game_already_ended", message="That game has already ended.",
                ).model_dump())
            else:
                # A reconnect never goes through the "join" flow again, but JoinedMessage is the
                # only message that ever tells the client which seat it holds - without resending
                # it here, a reconnecting client has no way to know its own `user`/`game_id`.
                await safe_send(websocket, protocol.JoinedMessage(
                    game_id=session.id, user=user.name,
                ).model_dump())

                if session.task is None:
                    # Reconnecting to a session that's still waiting for an opponent - prepare()/
                    # begin_running() haven't happened yet, so session.env has no dealt hands and
                    # there is nothing to resume. Re-send the same "still waiting" state instead of
                    # a game_start built from an unprepared (empty) environment.
                    await safe_send(websocket, protocol.WaitingForOpponentMessage().model_dump())
                else:
                    snapshot = serialization.snapshot(session.env)
                    await safe_send(websocket, protocol.GameStartMessage(snapshot=snapshot).model_dump())

                    other = session.seats[user.next]
                    if other.connected and other.websocket is not None:
                        await safe_send(other.websocket, protocol.OpponentReconnectedMessage(snapshot=snapshot).model_dump())

                    pending = session.io.pending.get(user)
                    if pending is not None:
                        await session.io.send(user, pending.io_obj)

        await _message_loop(websocket, matchmaker, account, session, user)
    except Exception:
        # The single place unexpected errors get logged - _message_loop() only ever catches
        # WebSocketDisconnect itself, so any real bug from in there surfaces here too.
        logger.exception("Unexpected error handling connection for account %s", account.account_id)
        raise
    finally:
        matchmaker.release(account.account_id, websocket)


async def _message_loop(
    websocket: WebSocket, matchmaker: Matchmaker, account: Account,
    session: GameSession | None, user: User | None,
) -> None:
    try:
        while True:
            try:
                raw = await websocket.receive_json()
                message = protocol.parse_client_message(raw)
            except (ValueError, ValidationError) as exc:
                await safe_send(websocket, protocol.ErrorMessage(message=str(exc)).model_dump())
                continue

            if session is None:
                if isinstance(message, protocol.JoinMessage):
                    joined_session, joined_user = await matchmaker.join(account.account_id)
                    if not joined_session.attach(joined_user, websocket):
                        # Narrow defense-in-depth window: joined_session.finished could in
                        # principle flip during the earlier `await joined_session.prepare()`
                        # inside matchmaker.join(). No extra matchmaker cleanup needed here - the
                        # session will still deregister itself normally via _finish().
                        await safe_send(websocket, protocol.ErrorMessage(
                            code="game_already_ended", message="That game has already ended.",
                        ).model_dump())
                        continue
                    session, user = joined_session, joined_user
                    await safe_send(websocket, protocol.JoinedMessage(
                        game_id=session.id, user=user.name,
                    ).model_dump())

                    if user == User.PLAYER_1:
                        await safe_send(websocket, protocol.WaitingForOpponentMessage().model_dump())
                    else:
                        # Pairing just happened and session.prepare() already ran inside
                        # matchmaker.join() - tell BOTH players, including the one who's been
                        # waiting on an earlier connection, before starting the engine running -
                        # otherwise its own event_update broadcasts could race ahead of game_start
                        # on the wire.
                        start_message = protocol.GameStartMessage(snapshot=serialization.snapshot(session.env)).model_dump()
                        for seat in session.seats.values():
                            if seat.websocket is not None:
                                await safe_send(seat.websocket, start_message)
                        session.begin_running()
                # Anything else while not yet in a game (a stray IoResponse/Concede, or a second
                # LoginMessage) is not a valid state - ignore and keep waiting for a join.
                continue
            assert user is not None  # always set together with session (both come from find_active_game/join)

            if isinstance(message, protocol.ConcedeMessage):
                await session.force_end(winner=user.next, reason="concede")
                return

            if isinstance(message, protocol.IoResponseMessage):
                current = session.io.current_request_id(user)
                if current is None or message.request_id != current:
                    await safe_send(websocket, protocol.ErrorMessage(
                        message="request_id does not match the currently pending request",
                    ).model_dump())
                    continue
                await session.io.receive(user, message.payload)
                continue

            # LoginMessage/JoinMessage after already being seated - not a valid state, ignore.
    except WebSocketDisconnect:
        pass
    finally:
        # Runs on every exit path - a real disconnect, concede's early return, or a genuine bug
        # propagating out of the loop (left uncaught here, on purpose: websocket_endpoint's own
        # except Exception is the single place unexpected errors get logged - catching and
        # re-logging them here too would just be the same traceback twice). detach() is a no-op
        # if this connection was already superseded or the session already finished.
        if session is not None and user is not None:
            session.detach(user, websocket)
