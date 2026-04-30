from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ...constants import Data, Response, ResponseType
from ...internal_events import (
    AVGECardHPChange,
    AVGECardMaxHPChange,
    AVGECardStatusChange,
    AVGECardTypeChange,
    AVGEEnergyTransfer,
    AVGEPlayerAttributeChange,
    ReorderCardholder,
    TransferCard,
)
from ..logging import log_engine_response


def response_source_summary(source: Any) -> str:
    if source is None:
        return 'None'

    package_fn = getattr(source, 'package', None)
    if callable(package_fn):
        try:
            packaged = package_fn()
            if isinstance(packaged, str) and packaged.strip():
                return packaged.strip()
        except Exception:
            pass

    source_type = type(source).__name__
    source_id = getattr(source, 'unique_id', None)
    if source_id is not None:
        return f'{source_type}(unique_id={source_id})'
    return source_type


def current_response_source(bridge: Any, response: Response) -> Any:
    source = getattr(response, 'source', None)
    if source is not None:
        return source
    return getattr(bridge.env._engine, 'event_running', None)


def response_data_keys(data: Any) -> list[str]:
    if isinstance(data, Data):
        try:
            return [str(key) for key in vars(data).keys()]
        except Exception:
            return []
    return []


def is_plain_data_payload(payload: Any) -> bool:
    return isinstance(payload, Data) and type(payload) is Data


def has_nonempty_payload(payload: Any) -> bool:
    if is_plain_data_payload(payload):
        return False
    return isinstance(payload, Data)


def should_emit_core_commands_before_reactors(
    bridge: Any,
    response: Response,
    commands: list[str],
) -> bool:
    if response.response_type != ResponseType.CORE:
        return False
    if len(commands) == 0:
        return False

    source = current_response_source(bridge, response)
    return isinstance(source, (
        AVGECardHPChange,
        AVGECardMaxHPChange,
        AVGECardTypeChange,
        AVGECardStatusChange,
        AVGEEnergyTransfer,
        AVGEPlayerAttributeChange,
        TransferCard,
        ReorderCardholder,
    ))


def log_engine_response_entry(
    bridge: Any,
    response: Response,
    step: int,
    stage: str,
    input_args: JsonObject | None,
) -> None:
    response_type = getattr(response.response_type, 'value', str(response.response_type))
    source = current_response_source(bridge, response)
    source_type = type(source).__name__ if source is not None else 'None'
    data_keys = response_data_keys(response.data)

    # Skip noisy accept-without-payload steps; keep all meaningful responses.
    if response.response_type == ResponseType.ACCEPT and is_plain_data_payload(response.data):
        return

    log_engine_response(
        stage=stage,
        step=step,
        response_type=response_type,
        source_type=source_type,
        source=response_source_summary(source),
        data_keys=data_keys,
        has_input_args=input_args is not None,
    )
