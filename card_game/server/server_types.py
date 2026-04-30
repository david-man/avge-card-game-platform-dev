from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = object
JsonObject: TypeAlias = dict[str, JsonValue]
ReadonlyJsonObject: TypeAlias = Mapping[str, JsonValue]

CommandPayload: TypeAlias = JsonObject | None
CommandPayloadBatch: TypeAlias = list[CommandPayload]
