from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from ..avge_abstracts.AVGECard import AVGECard
from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ..avge_abstracts.AVGEPlayer import AVGEPlayer
from ..engine.engine_io import IOException
from ..engine.event import Event, IOEvent
from . import config
from . import event_broadcasting
from . import serialization

if TYPE_CHECKING:
    from .io_adapter import NetworkIO


_MAX_DEPTH = 6


def _safe_json(value: Any, _depth: int = 0) -> Any:
    '''Best-effort recursive conversion of ANY value into something json.dumps can handle. This
    backs a debug/archival log, not the wire protocol - "good enough for a human to read" beats
    perfect typing, so unrecognized objects fall back to a shallow field dump (or str()) rather
    than raising. Enum members are always rendered via `.name` (not `.value`) uniformly, since not
    every Enum in this codebase is a StrEnum with a readable value - e.g. DeckType is a plain
    Enum with int values, unlike most others - and `.name` is always a safe, readable identifier
    regardless of which kind a given field happens to be.'''
    if _depth > _MAX_DEPTH:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, AVGECard):
        return serialization.card_to_wire(value)
    if isinstance(value, AVGEPlayer):
        return value.id.name
    if isinstance(value, AVGEEnvironment):
        return "ENV"
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (list, tuple, set)):
        items = cast("list[Any] | tuple[Any, ...] | set[Any]", value)
        return [_safe_json(v, _depth + 1) for v in items]
    if isinstance(value, dict):
        mapping = cast("dict[Any, Any]", value)
        return {str(k): _safe_json(v, _depth + 1) for k, v in mapping.items()}
    try:
        raw_fields = cast("dict[str, Any]", vars(value))
    except TypeError:
        return str(value)
    fields = {k: v for k, v in raw_fields.items() if not k.startswith("_")}
    return {"_type": type(value).__name__, **{k: _safe_json(v, _depth + 1) for k, v in fields.items()}}


def _serialize_event(event: Event, io: "NetworkIO") -> dict[str, Any]:
    update_io = event_broadcasting.event_to_update_io(event)
    if update_io is not None:
        try:
            return {
                "kind": "event", "event_type": type(event).__name__,
                "payload": io.build_request_payload(update_io),
            }
        except IOException:
            pass
    fields = {k: v for k, v in vars(event).items() if not k.startswith("_")}
    return {"kind": "event", "event_type": type(event).__name__, "fields": _safe_json(fields)}


def _serialize_io_event(event: IOEvent, io: "NetworkIO") -> dict[str, Any]:
    try:
        request = io.build_request_payload(event.io_obj)
    except IOException:
        fields = {k: v for k, v in vars(event.io_obj).items() if not k.startswith("_")}
        request = _safe_json(fields)
    return {
        "kind": "io", "io_type": type(event.io_obj).__name__,
        "request": request, "response": _safe_json(event.result),
    }


def serialize_history_records(env: AVGEEnvironment, io: "NetworkIO") -> list[dict[str, Any]]:
    '''Flattens env.engine.history.records (every chapter, in order) into one JSON-safe dict per
    (HistoricalStatus, Event | IOEvent) record. Deliberately reuses event_to_update_io() and
    NetworkIO.build_request_payload() - the exact same, already-resolved-field logic that drives
    live broadcasts to clients - rather than duplicating per-event-type field extraction here.'''
    out: list[dict[str, Any]] = []
    for chapter in env.engine.history.records:
        for status, event in chapter:
            entry = _serialize_io_event(event, io) if isinstance(event, IOEvent) else _serialize_event(event, io)
            entry["status"] = status.name
            out.append(entry)
    return out


def write_match_log(game_id: str, payload: dict[str, Any]) -> None:
    config.MATCH_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = config.MATCH_LOG_DIR / f"{game_id}.json"
    path.write_text(json.dumps(payload, indent=2))
