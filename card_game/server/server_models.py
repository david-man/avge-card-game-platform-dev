from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Literal, cast
from uuid import uuid4

PlayerSlot = Literal['p1', 'p2']


@dataclass
class PendingCommandAck:
    command_id: int
    command: str
    required_slots: set[PlayerSlot]
    acked_slots: set[PlayerSlot] = field(default_factory=set)
    delivered_slots: set[PlayerSlot] = field(default_factory=set)


@dataclass
class ClientSession:
    sid: str
    slot: PlayerSlot
    reconnect_token: str
    connected: bool = True
    last_ack: int = 0
    next_seq: int = 0
    pending_commands: list[str] = field(default_factory=list)
    pending_packets: list[dict[str, Any]] = field(default_factory=list)
    environment_initialized: bool = False
    disconnected_at: float | None = None


@dataclass
class MultiplayerTransportState:
    sid_by_slot: dict[PlayerSlot, str | None] = field(default_factory=lambda: {'p1': None, 'p2': None})
    session_by_sid: dict[str, ClientSession] = field(default_factory=dict)
    reconnect_token_to_slot: dict[str, PlayerSlot] = field(default_factory=dict)
    reserved_session_by_slot: dict[PlayerSlot, ClientSession | None] = field(default_factory=lambda: {'p1': None, 'p2': None})
    grace_deadline_by_slot: dict[PlayerSlot, float | None] = field(default_factory=lambda: {'p1': None, 'p2': None})
    disconnect_grace_seconds: float = 5.0

    def both_players_connected(self) -> bool:
        return all(self.sid_by_slot[slot] is not None for slot in ('p1', 'p2'))

    def slot_for_sid(self, sid: str) -> PlayerSlot | None:
        self._expire_grace_slots()
        session = self.session_by_sid.get(sid)
        if session is None:
            return None
        return session.slot

    def assign_slot(
        self,
        sid: str,
        requested_slot: str | None = None,
        reconnect_token: str | None = None,
    ) -> ClientSession | None:
        self._expire_grace_slots()

        existing_session = self.session_by_sid.get(sid)
        if existing_session is not None:
            return existing_session

        reconnect_slot = self.reconnect_token_to_slot.get(reconnect_token or '')
        if reconnect_slot is not None:
            current_sid_for_slot = self.sid_by_slot[reconnect_slot]
            if current_sid_for_slot == sid:
                return self.session_by_sid.get(sid)
            if self.sid_by_slot[reconnect_slot] is None:
                reusable = self.reserved_session_by_slot[reconnect_slot]
                return self._bind_sid_to_slot(
                    sid,
                    reconnect_slot,
                    reconnect_token or '',
                    reusable_session=reusable,
                )
            return None

        normalized_requested: PlayerSlot | None = None
        if requested_slot in {'p1', 'p2'}:
            normalized_requested = cast(PlayerSlot, requested_slot)

        if (
            normalized_requested is not None
            and self.sid_by_slot[normalized_requested] is None
            and self.reserved_session_by_slot[normalized_requested] is None
        ):
            token = uuid4().hex
            return self._bind_sid_to_slot(sid, normalized_requested, token)

        for candidate in ('p1', 'p2'):
            if self.sid_by_slot[candidate] is None and self.reserved_session_by_slot[candidate] is None:
                token = uuid4().hex
                return self._bind_sid_to_slot(sid, candidate, token)

        return None

    def release_sid(self, sid: str) -> PlayerSlot | None:
        self._expire_grace_slots()
        session = self.session_by_sid.pop(sid, None)
        if session is None:
            return None
        slot = session.slot
        self.sid_by_slot[slot] = None
        session.connected = False
        session.disconnected_at = monotonic()
        session.environment_initialized = False
        self.reserved_session_by_slot[slot] = session
        self.grace_deadline_by_slot[slot] = session.disconnected_at + self.disconnect_grace_seconds
        return slot

    def grace_remaining_seconds(self, slot: PlayerSlot) -> int:
        self._expire_grace_slots()
        deadline = self.grace_deadline_by_slot.get(slot)
        if deadline is None:
            return 0
        return max(0, int(deadline - monotonic()))

    def set_reserved_pending_commands(self, slot: PlayerSlot, commands: list[str]) -> None:
        session = self.reserved_session_by_slot.get(slot)
        if session is None:
            return
        session.pending_commands = list(commands)

    def _bind_sid_to_slot(
        self,
        sid: str,
        slot: PlayerSlot,
        token: str,
        reusable_session: ClientSession | None = None,
    ) -> ClientSession:
        self._expire_grace_slots()
        previous_sid = self.sid_by_slot[slot]
        if previous_sid is not None and previous_sid != sid:
            self.session_by_sid.pop(previous_sid, None)

        self.sid_by_slot[slot] = sid
        self.reconnect_token_to_slot[token] = slot
        self.reserved_session_by_slot[slot] = None
        self.grace_deadline_by_slot[slot] = None

        if reusable_session is not None:
            session = reusable_session
            session.sid = sid
            session.connected = True
            session.disconnected_at = None
        else:
            session = ClientSession(
                sid=sid,
                slot=slot,
                reconnect_token=token,
            )

        self.session_by_sid[sid] = session
        return session

    def _expire_grace_slots(self) -> None:
        now = monotonic()
        for slot in ('p1', 'p2'):
            deadline = self.grace_deadline_by_slot.get(slot)
            if deadline is None or now < deadline:
                continue
            if self.sid_by_slot[slot] is not None:
                continue

            reserved = self.reserved_session_by_slot.get(slot)
            if reserved is not None:
                self.reconnect_token_to_slot.pop(reserved.reconnect_token, None)
            self.reserved_session_by_slot[slot] = None
            self.grace_deadline_by_slot[slot] = None
