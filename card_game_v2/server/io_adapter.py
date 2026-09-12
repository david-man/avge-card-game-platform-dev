from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any, Awaitable, Callable, cast

from ..avge_abstracts.AVGECard import (
    AVGECard, AVGECharacterCard, AVGEItemCard, AVGESupporterCard, AVGEToolCard, AVGEStadiumCard,
)
from ..avge_abstracts.AVGEPlayer import AVGEPlayer
from ..constants import ActionTypes, User
from ..core.AVGEIOManager import (
    AVGEIO, BroadcastIO, Phase2IO, AtkPhaseIO, GameEndIO, Notification, EndOfTurn, RevealCards,
    ShowBoxedStrings, CardSelectionQuery, StringSelectionQuery, IntInput, D6Input, CoinflipData,
    Phase2Finish, Phase2EnergyAttach, Phase2CardMovement, Phase2ActivateAbility, Phase2PlayCard,
    HPChangeUpdate, MaxHPChangeUpdate, CardTypeChangeUpdate, StatusChangeUpdate,
    EnergyTransferUpdate, PlayerAttributeUpdate, CardMovedUpdate, DeckReorderedUpdate,
    CharacterActionUpdate, NonCharacterPlayUpdate, TurnEndUpdate, PhaseChangedUpdate,
    ActionRejectedUpdate,
)
from ..engine.engine_io import IOException, IOType, ListenerReorderIO, IOListenerReorderIO
from . import config
from . import protocol
from . import serialization

if TYPE_CHECKING:
    from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ..avge_abstracts.AVGEDeck import AVGEDeck


_ACK_ONLY_TYPES: tuple[type, ...] = (
    BroadcastIO, Notification, EndOfTurn, RevealCards, ShowBoxedStrings,
)
'''GameEndIO is deliberately NOT here - see the dedicated branch in send()/build_request_payload
below, which gives it the same "game_over" wire shape (and fire-and-forget, no-ack delivery) as
GameSession.force_end's synthetic ending, so the frontend has exactly one game-over message shape
regardless of whether the game ended naturally (real KOs) or was forced (concede/disconnect).'''

_FIRE_AND_FORGET_UPDATE_TYPES: tuple[type, ...] = (
    HPChangeUpdate, MaxHPChangeUpdate, CardTypeChangeUpdate, StatusChangeUpdate,
    EnergyTransferUpdate, PlayerAttributeUpdate, CardMovedUpdate, DeckReorderedUpdate,
    CharacterActionUpdate, NonCharacterPlayUpdate, TurnEndUpdate, PhaseChangedUpdate,
    ActionRejectedUpdate,
)
'''The 13 per-event update IOTypes from "Individualized event updates" (core/AVGEIOManager.py) -
genuinely one-way, fire-and-forget state-sync notices, distinct even from the 6 acknowledgment-
only types above (which still require *some* eventual ack, just with a backstop). Nothing will
ever send a matching response for these, so send() self-resolves them immediately - waiting for a
client here would mean the engine blocks on a full round trip for every single incremental HP
change / card move / etc., defeating the point of "live" updates.'''


def _wire_endpoint(obj: AVGECard | AVGEPlayer | AVGEEnvironment) -> dict[str, Any] | int | str:
    '''Shared wire-encoding for the AVGECard | AVGEPlayer | AVGEEnvironment unions used by
    giver/token_from/token_to fields (AVGECardStatusChange, AVGEEnergyTransfer, Phase2EnergyAttach).'''
    if isinstance(obj, AVGECard):
        return serialization.card_to_wire(obj)
    if isinstance(obj, AVGEPlayer):
        return obj.id.name
    return "ENV"


def _wire_deck_ref(deck: AVGEDeck) -> dict[str, Any]:
    # AVGEDeck.deck_owner is declared as always AVGEPlayer, but avge_abstracts/AVGEEnvironment.py
    # actually constructs the single global stadium deck with deck_owner=None (its own
    # `# type: ignore` at that construction site) - this cast documents that the declared type is
    # known-inaccurate for that one case, rather than silencing the check on the comparison below.
    owner = cast("AVGEPlayer | None", deck.deck_owner)
    return {
        "owner": owner.id.name if owner is not None else None,
        "deck_type": deck.deck_type.name,
    }


class NetworkIO(AVGEIO):
    '''Concrete AVGEIO implementation backed by injected send/failure callbacks, deliberately
    decoupled from any specific transport (a real WebSocket, or a fake recording stub in tests).

    Three delivery shapes, by IOType:
    - The 5 acknowledgment-only types (BroadcastIO/Notification/EndOfTurn/RevealCards/
      ShowBoxedStrings) require a real client ack, plus a server-side backstop timer (the IOType's
      own `timeout` field if present, else config.ACK_BACKSTOP_SECONDS) so a hung-but-still-
      connected client can't stall the engine forever.
    - GameEndIO and the 13 per-event update IOTypes are fire-and-forget: sent once, then
      self-resolved immediately, no client response ever expected. GameEndIO gets its own
      "game_over" wire shape (matching GameSession.force_end's synthetic ending exactly) instead
      of the generic "event_update" shape the other 13 use.
    - Everything else (Phase2IO, AtkPhaseIO, the selection/input types, the 2 reorder types)
      requires a real client decision - no backstop, no self-resolution.'''

    def __init__(
        self,
        send_message: Callable[[User, dict[str, Any]], Awaitable[None]],
        on_transport_failure: Callable[[User], Awaitable[None]],
    ):
        super().__init__()
        self._send_message = send_message
        self._on_transport_failure = on_transport_failure
        self._pending_request_ids: dict[User, str] = {}
        self._backstop_tasks: dict[User, asyncio.Task[None]] = {}

    def current_request_id(self, user: User) -> str | None:
        '''Used by ws_routes.py to validate an incoming io_response's request_id before ever
        calling receive() - guards against a stale response satisfying an unrelated new prompt.'''
        return self._pending_request_ids.get(user)

    def _cancel_backstop(self, user: User) -> None:
        '''Cancels and discards this user's own outstanding backstop task, if any. Called at the
        top of send() so re-issuing a request to a user (e.g. resending their still-pending ack-
        only request on reconnect, per ws_routes.py) can never leave the previous send's backstop
        running alongside the new one - both would otherwise race against the same underlying
        pending/future_obj (resending doesn't create a new one), and the old backstop's timeout
        clock started earlier, so it could fire and silently auto-resolve the request out from
        under a client that just reconnected and hasn't actually answered it yet.'''
        task = self._backstop_tasks.pop(user, None)
        if task is not None:
            task.cancel()

    def cancel_backstops(self) -> None:
        '''Called by GameSession._cancel_all_timers() on every early-termination path (force_end,
        _abandon, _fail) so an outstanding ack-only request's backstop timer doesn't keep sleeping
        for up to its own timeout after the session is already torn down - harmless (the
        pending/future_obj.done() guards in _backstop() make it a no-op either way), but there's
        no reason to leave it running.'''
        for task in self._backstop_tasks.values():
            task.cancel()
        self._backstop_tasks.clear()

    async def receive(self, user: User, data: Any) -> None:
        '''Overrides the base IOManager.receive(): the base implementation only calls
        `future_obj.set_result(...)` when `deserialize()` returns non-None
        (`if deserialized_data is not None:`), which would silently swallow every real client
        ack for the 6 acknowledgment-only IOTypes, since their one legitimate answer IS `None`.
        Bypass that filter for exactly those types; fall through to the base behavior (and its
        automatic retry()-on-IOException handling) for everything else.'''
        pending = self.pending.get(user)
        if pending is None or pending.future_obj.done():
            return
        if isinstance(pending.io_obj, _ACK_ONLY_TYPES):
            pending.future_obj.set_result(None)
            return
        await super().receive(user, data)

    async def send[T](self, user: User, io: IOType[T]) -> None:
        assert self.env is not None
        self._cancel_backstop(user)

        if isinstance(io, _FIRE_AND_FORGET_UPDATE_TYPES):
            message = protocol.EventUpdateMessage(
                io_type=type(io).__name__, payload=self.build_request_payload(io),
            ).model_dump()
            try:
                await self._send_message(user, message)
            except Exception:
                await self._on_transport_failure(user)
            # Self-resolve unconditionally (even on transport failure) - nothing will ever answer
            # this, and a dead transport is handled by on_transport_failure/session-level detach,
            # not by leaving the engine hanging on a future nobody can ever complete.
            pending = self.pending.get(user)
            if pending is not None and not pending.future_obj.done():
                pending.future_obj.set_result(None)
            return

        if isinstance(io, GameEndIO):
            # Same "game_over" wire shape and fire-and-forget delivery as GameSession.force_end's
            # synthetic ending - see the _ACK_ONLY_TYPES docstring above for why. winner/reason
            # aren't guaranteed set here (GameEndIO can in principle be reported before
            # GameEnd.act() would normally set them, e.g. directly in isolation as
            # test_io_adapter.py's SendEnvelopeTests do) - fall back to None rather than assert.
            message = protocol.GameOverMessage(
                winner=self.env.winner.name if self.env.winner is not None else None,
                reason=self.env.win_reason.value if self.env.win_reason is not None else None,
            ).model_dump()
            try:
                await self._send_message(user, message)
            except Exception:
                await self._on_transport_failure(user)
            pending = self.pending.get(user)
            if pending is not None and not pending.future_obj.done():
                pending.future_obj.set_result(None)
            return

        request_id = str(uuid.uuid4())
        payload = self.build_request_payload(io)
        message = protocol.IoRequestMessage(
            request_id=request_id, io_type=type(io).__name__, payload=payload,
        ).model_dump(exclude_none=True)
        self._pending_request_ids[user] = request_id
        try:
            await self._send_message(user, message)
        except Exception:
            await self._on_transport_failure(user)
            return

        if isinstance(io, _ACK_ONLY_TYPES):
            timeout = getattr(io, "timeout", None) or config.ACK_BACKSTOP_SECONDS
            self._backstop_tasks[user] = asyncio.create_task(self._backstop(user, timeout))

    async def _backstop(self, user: User, timeout: float) -> None:
        await asyncio.sleep(timeout)
        pending = self.pending.get(user)
        if pending is not None and not pending.future_obj.done():
            pending.future_obj.set_result(None)

    async def retry[T](self, user: User, io: IOType[T], error: IOException) -> None:
        message = protocol.IoRequestMessage(
            request_id=self._pending_request_ids.get(user, str(uuid.uuid4())),
            io_type=type(io).__name__,
            payload=self.build_request_payload(io),
            retry_reason=str(error),
        ).model_dump(exclude_none=True)
        try:
            await self._send_message(user, message)
        except Exception:
            await self._on_transport_failure(user)

    # --- Request payload construction ---

    def build_request_payload(self, io: IOType[Any]) -> dict[str, Any]:
        '''Public (not underscore-prefixed) because server/match_log.py also calls this directly
        to reuse the exact same per-IOType payload-building logic when serializing a finished
        match's engine.history for the archival log, rather than duplicating it there.'''
        if isinstance(io, BroadcastIO):
            return {"message": io.message, "timeout": io.timeout}
        if isinstance(io, Notification):
            return {"message": io.message, "timeout": io.timeout}
        # GameEndIO never reaches here - send() returns early for it with its own "game_over"
        # wire shape, built directly (not via this function).
        if isinstance(io, EndOfTurn):
            return {}
        if isinstance(io, RevealCards):
            return {"cards": [serialization.card_to_wire(c) for c in io.cards_to_reveal]}
        if isinstance(io, ShowBoxedStrings):
            return {"strings": io.strings_to_show}
        if isinstance(io, Phase2IO):
            return {}
        if isinstance(io, AtkPhaseIO):
            return {}
        if isinstance(io, CardSelectionQuery):
            return {
                "header_msg": io.header_msg,
                "num_selections": io.num_selections,
                "allowed_selections": [c.cardID for c in io.allowed_selections],
                "displayed_cards": [serialization.card_to_wire(c) for c in io.displayed_cards],
                "allows_none": io.allows_none,
                "allows_repeat": io.allows_repeat,
            }
        if isinstance(io, StringSelectionQuery):
            return {
                "header_msg": io.header_msg,
                "num_selections": io.num_selections,
                "allowed_selections": io.allowed_selections,
                "displayed_cards": io.displayed_cards,
                "allows_none": io.allows_none,
                "allows_repeat": io.allows_repeat,
            }
        if isinstance(io, IntInput):
            return {"header_msg": io.header_msg, "min_num": io.min_num, "max_num": io.max_num}
        if isinstance(io, D6Input):
            return {"header_msg": io.header_msg}
        if isinstance(io, CoinflipData):
            return {"header_msg": io.header_msg}
        if isinstance(io, (ListenerReorderIO, IOListenerReorderIO)):
            return {"count": len(io.listeners)}

        if isinstance(io, HPChangeUpdate):
            return {
                "target_card": serialization.card_to_wire(io.target_card),
                "magnitude": io.magnitude,
                "modifier_type": io.modifier_type.value,
                "change_type": io.change_type.value,
                "original_hp": io.original_hp,
                "final_change": io.final_change,
                "is_crit": io.is_crit,
            }
        if isinstance(io, MaxHPChangeUpdate):
            return {
                "target_card": serialization.card_to_wire(io.target_card),
                "magnitude": io.magnitude,
                "modifier_type": io.modifier_type.value,
                "change_type": io.change_type.value,
                "original_hp": io.original_hp,
                "original_max_hp": io.original_max_hp,
                "final_hp": io.final_hp,
                "final_max_hp": io.final_max_hp,
            }
        if isinstance(io, CardTypeChangeUpdate):
            return {
                "target": serialization.card_to_wire(io.target),
                "original_type": io.original_type.value,
                "new_type": io.new_type.value,
            }
        if isinstance(io, StatusChangeUpdate):
            return {
                "target": serialization.card_to_wire(io.target),
                "giver": _wire_endpoint(io.giver),
                "status": io.status.value,
                "change": io.change.value,
                "made_modification": io.made_modification,
            }
        if isinstance(io, EnergyTransferUpdate):
            return {
                "token_from": _wire_endpoint(io.token_from),
                "token_to": _wire_endpoint(io.token_to),
            }
        if isinstance(io, PlayerAttributeUpdate):
            return {
                "player": io.player.id.name,
                "attribute": io.attribute.value,
                "modifier_type": io.modifier_type.value,
                "magnitude": io.magnitude,
                "new_value": io.new_value,
            }
        if isinstance(io, CardMovedUpdate):
            return {
                "card": serialization.card_to_wire(io.card),
                "deck_from": _wire_deck_ref(io.deck_from),
                "deck_to": _wire_deck_ref(io.deck_to),
            }
        if isinstance(io, DeckReorderedUpdate):
            return {
                **_wire_deck_ref(io.deck),
                "new_order": [serialization.card_to_wire(c) for c in io.new_order],
            }
        if isinstance(io, CharacterActionUpdate):
            return {
                "target_card": serialization.card_to_wire(io.target_card),
                "action": io.action.value,
                "cost": io.cost,
                "calling_card": serialization.card_to_wire(io.calling_card) if io.calling_card is not None else None,
            }
        if isinstance(io, NonCharacterPlayUpdate):
            return {
                "target_card": serialization.card_to_wire(io.target_card),
                "action": io.action.value,
            }
        if isinstance(io, TurnEndUpdate):
            return {"new_turn": io.new_turn.name, "new_round": io.new_round}
        if isinstance(io, PhaseChangedUpdate):
            return {"phase": io.phase}
        if isinstance(io, ActionRejectedUpdate):
            # Computed at send time, which is always after Engine.flush() has already run this
            # packet's _rollback_all() - so the snapshot reflects the corrected state, not the
            # optimistic one the client already saw from the per-event updates that led up to
            # this rejection. Lets the client both learn why and resync in one message.
            assert self.env is not None
            return {
                "rejected_for": io.rejected_for.name,
                "reason": io.reason,
                "snapshot": serialization.snapshot(self.env),
            }

        raise IOException(f"No request payload builder for IOType {type(io).__name__!r}")

    # --- Response validation/deserialization ---

    def deserialize[T](self, io: IOType[T], data: dict[str, Any]) -> T:
        assert self.env is not None
        env = self.env

        if isinstance(io, _ACK_ONLY_TYPES):
            return None  # type: ignore[return-value]

        if isinstance(io, Phase2IO):
            return self._deserialize_phase2(env, data)  # type: ignore[return-value]

        if isinstance(io, AtkPhaseIO):
            action = data.get("action")
            if action not in (ActionTypes.ATK_1.value, ActionTypes.ATK_2.value, ActionTypes.SKIP.value):
                raise IOException(f"Invalid AtkPhaseIO action: {action!r}")
            return ActionTypes(action)  # type: ignore[return-value]

        if isinstance(io, CardSelectionQuery):
            return self._deserialize_card_selection(env, io, data)  # type: ignore[return-value]

        if isinstance(io, StringSelectionQuery):
            return self._deserialize_string_selection(io, data)  # type: ignore[return-value]

        if isinstance(io, IntInput):
            value = data.get("value")
            if not isinstance(value, int) or not (io.min_num <= value <= io.max_num):
                raise IOException(f"IntInput value {value!r} out of range [{io.min_num}, {io.max_num}]")
            return value  # type: ignore[return-value]

        if isinstance(io, D6Input):
            value = data.get("value")
            if not isinstance(value, int) or not (1 <= value <= 6):
                raise IOException(f"D6Input value {value!r} out of range [1, 6]")
            return value  # type: ignore[return-value]

        if isinstance(io, CoinflipData):
            value = data.get("value")
            if value not in (0, 1):
                raise IOException(f"CoinflipData value {value!r} must be 0 or 1")
            return value  # type: ignore[return-value]

        if isinstance(io, ListenerReorderIO):
            order = self._validate_reorder_indices(len(io.listeners), data)
            reordered = [io.listeners[i] for i in order]
            if not io.check_user_io(reordered):
                raise IOException("Reordered listener list failed check_user_io")
            return reordered  # type: ignore[return-value]

        if isinstance(io, IOListenerReorderIO):
            io_listeners = cast("IOListenerReorderIO[Any]", io)
            order = self._validate_reorder_indices(len(io_listeners.listeners), data)
            reordered_io = [io_listeners.listeners[i] for i in order]
            if not io_listeners.check_user_io(reordered_io):
                raise IOException("Reordered listener list failed check_user_io")
            return reordered_io  # type: ignore[return-value]

        raise IOException(f"No deserializer for IOType {type(io).__name__!r}")

    def _deserialize_phase2(self, env: AVGEEnvironment, data: dict[str, Any]):
        kind = data.get("kind")
        if kind == "finish":
            return Phase2Finish()
        if kind == "activate_ability":
            card = serialization.resolve_card(env, str(data.get("card_id")))
            if not isinstance(card, AVGECharacterCard):
                raise IOException(f"Invalid card_id for activate_ability: {data.get('card_id')!r}")
            return Phase2ActivateAbility(card=card)
        if kind == "energy_attach":
            token_from = self._resolve_energy_endpoint(env, data.get("token_from"))
            token_to = self._resolve_energy_endpoint(env, data.get("token_to"))
            return Phase2EnergyAttach(token_from=token_from, token_to=token_to)
        if kind == "card_movement":
            card = serialization.resolve_card(env, str(data.get("card_id")))
            if not isinstance(card, (AVGECharacterCard, AVGEToolCard, AVGEStadiumCard)):
                raise IOException(f"Invalid card_id for card_movement: {data.get('card_id')!r}")
            deck_from = self._resolve_deck_field(env, data.get("deck_from"))
            deck_to = self._resolve_deck_field(env, data.get("deck_to"))
            return Phase2CardMovement(card=card, deck_from=deck_from, deck_to=deck_to)
        if kind == "play_card":
            card = serialization.resolve_card(env, str(data.get("card_id")))
            if not isinstance(card, (AVGEItemCard, AVGESupporterCard)):
                raise IOException(f"Invalid card_id for play_card: {data.get('card_id')!r}")
            return Phase2PlayCard(card=card)
        raise IOException(f"Unknown Phase2IO response kind: {kind!r}")

    def _resolve_energy_endpoint(self, env: AVGEEnvironment, raw: Any) -> AVGECharacterCard | AVGEEnvironment:
        if raw == "ENV":
            return env
        card = serialization.resolve_card(env, str(raw))
        if not isinstance(card, AVGECharacterCard):
            raise IOException(f"Invalid energy_attach endpoint: {raw!r}")
        return card

    def _resolve_deck_field(self, env: AVGEEnvironment, raw_obj: Any):
        if not isinstance(raw_obj, dict) or "owner" not in raw_obj or "deck_type" not in raw_obj:
            raise IOException(f"Invalid deck reference: {raw_obj!r}")
        raw = cast("dict[str, Any]", raw_obj)
        # owner is None on the wire for the STADIUM deck (see _wire_deck_ref) - only parse it as
        # a User when it's actually present, so a stadium reference doesn't fail here before
        # resolve_deck() ever gets a chance to special-case it.
        owner: User | None = None
        if raw["owner"] is not None:
            try:
                owner = User[str(raw["owner"])]
            except KeyError as exc:
                raise IOException(f"Invalid deck owner: {raw['owner']!r}") from exc
        try:
            return serialization.resolve_deck(env, owner, str(raw["deck_type"]))
        except KeyError as exc:
            raise IOException(f"Invalid deck reference: {raw!r}") from exc

    def _deserialize_card_selection(self, env: AVGEEnvironment, io: CardSelectionQuery, data: dict[str, Any]) -> list[AVGECard]:
        raw_ids_obj = data.get("selected_ids")
        if not isinstance(raw_ids_obj, list):
            raise IOException("selected_ids must be a list")
        raw_ids_any = cast("list[Any]", raw_ids_obj)
        if not all(isinstance(r, str) for r in raw_ids_any):
            raise IOException("selected_ids must contain only card id strings")
        raw_ids = cast("list[str]", raw_ids_any)
        if len(raw_ids) == 0 and not io.allows_none:
            raise IOException("This selection does not allow an empty response")
        if len(raw_ids) > io.num_selections:
            raise IOException(f"Too many selections: {len(raw_ids)} > {io.num_selections}")
        if not io.allows_repeat and len(set(raw_ids)) != len(raw_ids):
            raise IOException("Duplicate selections are not allowed here")
        allowed_ids = {c.cardID for c in io.allowed_selections}
        resolved: list[AVGECard] = []
        for raw_id in raw_ids:
            if raw_id not in allowed_ids:
                raise IOException(f"Selected id {raw_id!r} is not an allowed selection")
            card = serialization.resolve_card(env, raw_id)
            if card is None:
                raise IOException(f"Unknown card id: {raw_id!r}")
            resolved.append(card)
        return resolved

    def _deserialize_string_selection(self, io: StringSelectionQuery, data: dict[str, Any]) -> list[str]:
        raw_obj = data.get("selected")
        if not isinstance(raw_obj, list):
            raise IOException("selected must be a list of strings")
        raw_any = cast("list[Any]", raw_obj)
        if not all(isinstance(item, str) for item in raw_any):
            raise IOException("selected must be a list of strings")
        raw = cast("list[str]", raw_any)
        if len(raw) == 0 and not io.allows_none:
            raise IOException("This selection does not allow an empty response")
        if len(raw) > io.num_selections:
            raise IOException(f"Too many selections: {len(raw)} > {io.num_selections}")
        if not io.allows_repeat and len(set(raw)) != len(raw):
            raise IOException("Duplicate selections are not allowed here")
        if not all(item in io.allowed_selections for item in raw):
            raise IOException("Selection includes a value outside allowed_selections")
        return raw

    def _validate_reorder_indices(self, count: int, data: dict[str, Any]) -> list[int]:
        order_obj = data.get("order")
        if not isinstance(order_obj, list):
            raise IOException("order must be a list of ints")
        order_any = cast("list[Any]", order_obj)
        if not all(isinstance(i, int) for i in order_any):
            raise IOException("order must be a list of ints")
        order = cast("list[int]", order_any)
        if sorted(order) != list(range(count)):
            raise IOException(f"order must be a permutation of 0..{count - 1}")
        return order
