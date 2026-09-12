from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel


# --- Client -> Server ---

class LoginMessage(BaseModel):
    '''Always the first message on a fresh socket. Client sends `auth_token` if it has one cached
    (silent re-auth from localStorage); otherwise `username`, which creates the account on first
    use (open registration, no password).'''
    type: Literal["login"] = "login"
    username: str | None = None
    auth_token: str | None = None


class JoinMessage(BaseModel):
    type: Literal["join"] = "join"


class ConcedeMessage(BaseModel):
    type: Literal["concede"] = "concede"


class IoResponseMessage(BaseModel):
    '''A client's answer to a previously-sent IoRequestMessage. `payload`'s exact shape depends
    on which IOType `request_id` was pending for - validated by NetworkIO.deserialize(), not here,
    to avoid duplicating core/AVGEIOManager.py's dataclasses as a second, parallel set of models.'''
    type: Literal["io_response"] = "io_response"
    request_id: str
    payload: dict[str, Any]


ClientMessage = LoginMessage | JoinMessage | ConcedeMessage | IoResponseMessage

_CLIENT_MESSAGE_TYPES: dict[str, type[ClientMessage]] = {
    "login": LoginMessage,
    "join": JoinMessage,
    "concede": ConcedeMessage,
    "io_response": IoResponseMessage,
}


def parse_client_message(data: Any) -> ClientMessage:
    '''`data` is declared Any, not dict[str, Any], because it's whatever a client's raw JSON frame
    decoded to - which the type checker can't narrow for us, but a real client can send any JSON
    value (a bare number, string, list, ...), not just an object.
    Raises ValueError (unknown type, or not even a JSON object) or pydantic.ValidationError
    (known type, bad shape).'''
    if not isinstance(data, dict):
        raise ValueError(f"Client message must be a JSON object, got {type(data).__name__}")
    data = cast("dict[str, Any]", data)
    msg_type = data.get("type")
    if not isinstance(msg_type, str) or msg_type not in _CLIENT_MESSAGE_TYPES:
        raise ValueError(f"Unknown or missing client message type: {msg_type!r}")
    return _CLIENT_MESSAGE_TYPES[msg_type].model_validate(data)


# --- Server -> Client ---

class LoggedInMessage(BaseModel):
    type: Literal["logged_in"] = "logged_in"
    account_id: str
    username: str
    auth_token: str


class LoggedOutElsewhereMessage(BaseModel):
    '''Sent to a connection right before it's closed, because a newer login for the same account
    has taken precedence over it.'''
    type: Literal["logged_out_elsewhere"] = "logged_out_elsewhere"


class WaitingForOpponentMessage(BaseModel):
    type: Literal["waiting_for_opponent"] = "waiting_for_opponent"


class JoinedMessage(BaseModel):
    type: Literal["joined"] = "joined"
    game_id: str
    user: str


class GameStartMessage(BaseModel):
    type: Literal["game_start"] = "game_start"
    snapshot: dict[str, Any]


class IoRequestMessage(BaseModel):
    '''A request the server needs this specific client to answer - one of the 11 UserIOTypes or
    2 reorder types from core/AVGEIOManager.py. `payload`'s shape depends on `io_type`.
    `retry_reason` is present only when this is a re-send of a request the client's previous
    answer failed to satisfy (see NetworkIO.retry() in io_adapter.py).'''
    type: Literal["io_request"] = "io_request"
    request_id: str
    io_type: str
    payload: dict[str, Any]
    retry_reason: str | None = None


class EventUpdateMessage(BaseModel):
    '''A one-way, fire-and-forget state-change notice - one of the per-event update IOTypes added
    to core/AVGEIOManager.py (HPChangeUpdate, CardMovedUpdate, etc.). No request_id, no response
    expected - distinct from IoRequestMessage, which always requires a real client answer.'''
    type: Literal["event_update"] = "event_update"
    io_type: str
    payload: dict[str, Any]


class OpponentDisconnectedMessage(BaseModel):
    type: Literal["opponent_disconnected"] = "opponent_disconnected"
    grace_seconds: float


class OpponentReconnectedMessage(BaseModel):
    type: Literal["opponent_reconnected"] = "opponent_reconnected"
    snapshot: dict[str, Any]


class GameOverMessage(BaseModel):
    type: Literal["game_over"] = "game_over"
    winner: str | None
    reason: str | None


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str
    code: str | None = None
