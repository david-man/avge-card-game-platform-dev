from __future__ import annotations

from collections.abc import Mapping
from typing import Callable
from card_game.server.server_types import JsonObject, CommandPayload

from ...avge_abstracts.AVGECards import AVGECard
from ...internal_events import InputEvent
from ...constants import (
    CardSelectionQuery,
    CoinflipData,
    D6Data,
    Data,
    IntegerInputData,
    OrderingQuery,
    StrSelectionQuery,
)


def build_input_command(
    event: InputEvent,
    query_data: Data,
    *,
    player_id_to_frontend: Callable[[object], str],
    command_token: Callable[[str], str],
    csv_from_display_entries: Callable[[list[object]], str],
    random_int: Callable[[int, int], int],
) -> str | None:
    player_token = player_id_to_frontend(event.player_for.unique_id)
    message_source = 'input_required'

    if isinstance(query_data, CardSelectionQuery):
        message_source = query_data.header_msg
        display_ids = csv_from_display_entries(list(query_data.display))
        highlight_ids = csv_from_display_entries(list(query_data.targets))
        return (
            f'input selection {player_token} {command_token(message_source)} '
            f'[{display_ids}], [{highlight_ids}], {len(event.input_keys)} '
            f'{str(query_data.allows_repeat).lower()} {str(query_data.allows_none).lower()}'
        )

    if isinstance(query_data, StrSelectionQuery):
        message_source = query_data.header_msg
        display_ids = csv_from_display_entries(list(query_data.display))
        highlight_ids = csv_from_display_entries(list(query_data.targets))
        return (
            f'input selection {player_token} {command_token(message_source)} '
            f'[{display_ids}], [{highlight_ids}], {len(event.input_keys)} '
            f'{str(query_data.allows_repeat).lower()} {str(query_data.allows_none).lower()}'
        )

    if isinstance(query_data, IntegerInputData):
        message_source = query_data.header_msg
        return f'input numerical-entry {player_token} {command_token(message_source)}'

    if isinstance(query_data, CoinflipData):
        message_source = query_data.header_msg
        roll_count = max(1, len(event.input_keys))
        values = [random_int(0, 1) for _ in range(roll_count)]
        value_token = str(values[0]) if roll_count == 1 else f'[{",".join(str(value) for value in values)}]'
        return f'input coin {player_token} {command_token(message_source)} {value_token}'

    if isinstance(query_data, D6Data):
        message_source = query_data.header_msg
        roll_count = max(1, len(event.input_keys))
        values = [random_int(1, 6) for _ in range(roll_count)]
        value_token = str(values[0]) if roll_count == 1 else f'[{",".join(str(value) for value in values)}]'
        return f'input d6 {player_token} {command_token(message_source)} {value_token}'

    if isinstance(query_data, OrderingQuery):
        return f'input numerical-entry {player_token} order_listeners'

    return None


def parse_frontend_input_result(
    event: InputEvent,
    data: JsonObject,
    *,
    get_card: Callable[[str], object | None],
    random_int: Callable[[int, int], int],
    log_input_trace: Callable[..., None],
) -> JsonObject | None:
    query_data = getattr(event, 'query_data', Data())
    query_type = type(query_data).__name__
    payload_keys = sorted(data.keys())
    expected_input_count = len(event.input_keys)

    log_input_trace(
        'bridge_parse_input_result_start',
        query_type=query_type,
        payload_keys=payload_keys,
        expected_input_count=expected_input_count,
    )

    def _reject(reason: str, **extra: object) -> None:
        log_input_trace(
            'bridge_parse_input_result_rejected',
            reason=reason,
            query_type=query_type,
            payload_keys=payload_keys,
            expected_input_count=expected_input_count,
            **extra,
        )

    def _accept(parsed_values: list[object]) -> JsonObject:
        preview: list[object] = []
        for value in parsed_values:
            if isinstance(value, AVGECard):
                preview.append(value.unique_id)
            else:
                preview.append(value)
        log_input_trace(
            'bridge_parse_input_result_accepted',
            query_type=query_type,
            parsed_count=len(parsed_values),
            parsed_preview=preview,
        )
        return {'input_result': parsed_values}

    def _int_from_any(raw_value: object, *, coin_mode: bool) -> int | None:
        if isinstance(raw_value, bool):
            return int(raw_value)
        if isinstance(raw_value, (int, float)):
            return int(raw_value)
        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if coin_mode:
                if normalized in {'heads', 'head', 'h', 'true', 'yes', '1'}:
                    return 1
                if normalized in {'tails', 'tail', 't', 'false', 'no', '0'}:
                    return 0
            if normalized.lstrip('-').isdigit():
                return int(normalized)
        return None

    if isinstance(query_data, CardSelectionQuery):
        ordered = data.get('ordered_selections')
        if not isinstance(ordered, list):
            _reject('missing_ordered_selections')
            return None
        parsed: list[object] = []
        for raw in ordered:
            if raw is None or (isinstance(raw, str) and raw.strip().lower() in {'none', 'null', '-1'}):
                parsed.append(None)
                continue
            if not isinstance(raw, str):
                _reject('invalid_card_selection_entry_type', entry_type=type(raw).__name__)
                return None
            normalized_raw = raw.strip()
            card = get_card(normalized_raw)
            parsed.append(card if card is not None else normalized_raw)
        if len(parsed) < len(event.input_keys) and query_data.allows_none:
            parsed.extend([None] * (len(event.input_keys) - len(parsed)))
        if len(parsed) != len(event.input_keys):
            _reject('card_selection_length_mismatch', parsed_count=len(parsed))
            return None
        return _accept(parsed)

    if isinstance(query_data, StrSelectionQuery):
        ordered = data.get('ordered_selections')
        if not isinstance(ordered, list):
            _reject('missing_ordered_selections')
            return None
        parsed: list[object] = []
        for raw in ordered:
            if raw is None or (isinstance(raw, str) and raw.strip().lower() in {'none', 'null', '-1'}):
                parsed.append(None)
                continue
            if not isinstance(raw, str):
                _reject('invalid_str_selection_entry_type', entry_type=type(raw).__name__)
                return None
            parsed.append(raw)
        if len(parsed) < len(event.input_keys) and query_data.allows_none:
            parsed.extend([None] * (len(event.input_keys) - len(parsed)))
        if len(parsed) != len(event.input_keys):
            _reject('str_selection_length_mismatch', parsed_count=len(parsed))
            return None
        return _accept(parsed)

    if isinstance(query_data, IntegerInputData):
        value = data.get('value')
        if not isinstance(value, (int, float)):
            _reject('invalid_integer_value', received_type=type(value).__name__ if value is not None else 'None')
            return None
        return _accept([int(value)])

    if isinstance(query_data, CoinflipData):
        entries = data.get('result_values')
        parsed_values: list[int] = []
        if isinstance(entries, list) and len(entries) > 0:
            for raw_value in entries:
                parsed_value = _int_from_any(raw_value, coin_mode=True)
                if parsed_value is None:
                    _reject('invalid_coinflip_entry', entry_type=type(raw_value).__name__)
                    return None
                parsed_values.append(parsed_value)
        else:
            single_value = data.get('result_value')
            parsed_value = _int_from_any(single_value, coin_mode=True)
            if parsed_value is None:
                _reject('invalid_coinflip_value', received_type=type(single_value).__name__ if single_value is not None else 'None')
                return None
            parsed_values = [parsed_value]

        if len(parsed_values) == 1 and expected_input_count > 1:
            parsed_values.extend(random_int(0, 1) for _ in range(expected_input_count - 1))

        if len(parsed_values) != expected_input_count:
            _reject('coinflip_length_mismatch', parsed_count=len(parsed_values))
            return None

        if any(value not in {0, 1} for value in parsed_values):
            _reject('invalid_coinflip_range', parsed_preview=parsed_values)
            return None

        return _accept(parsed_values)

    if isinstance(query_data, D6Data):
        entries = data.get('result_values')
        parsed_values: list[int] = []
        if isinstance(entries, list) and len(entries) > 0:
            for raw_value in entries:
                parsed_value = _int_from_any(raw_value, coin_mode=False)
                if parsed_value is None:
                    _reject('invalid_d6_entry', entry_type=type(raw_value).__name__)
                    return None
                parsed_values.append(parsed_value)
        else:
            single_value = data.get('result_value')
            parsed_value = _int_from_any(single_value, coin_mode=False)
            if parsed_value is None:
                _reject('invalid_d6_value', received_type=type(single_value).__name__ if single_value is not None else 'None')
                return None
            parsed_values = [parsed_value]

        if len(parsed_values) == 1 and expected_input_count > 1:
            parsed_values.extend(random_int(1, 6) for _ in range(expected_input_count - 1))

        if len(parsed_values) != expected_input_count:
            _reject('d6_length_mismatch', parsed_count=len(parsed_values))
            return None

        if any(value < 1 or value > 6 for value in parsed_values):
            _reject('invalid_d6_range', parsed_preview=parsed_values)
            return None

        return _accept(parsed_values)

    _reject('unsupported_query_type')
    return None


def build_ordering_listener_state(
    query_data: OrderingQuery,
    *,
    command_token: Callable[[str], str],
) -> tuple[JsonObject, list[str], tuple[str, ...]]:
    unordered = list(getattr(query_data, 'unordered_listeners', []) or [])

    listener_by_token: JsonObject = {}
    ordered_tokens: list[str] = []

    for idx, listener in enumerate(unordered):
        package_fn = getattr(listener, 'package', None)
        package_name = package_fn() if callable(package_fn) else type(listener).__name__
        if not isinstance(package_name, str) or not package_name.strip():
            package_name = type(listener).__name__

        token = f'l{idx}_{command_token(package_name)}'
        listener_by_token[token] = listener
        ordered_tokens.append(token)

    return listener_by_token, ordered_tokens, tuple(ordered_tokens)


def should_skip_duplicate_ordering_query(
    *,
    signature: tuple[str, ...],
    last_emitted_signature: tuple[str, ...] | None,
    pending_listener_by_token: Mapping[str, object] | None,
    next_listener_by_token: Mapping[str, object],
) -> bool:
    return (
        last_emitted_signature == signature
        and isinstance(pending_listener_by_token, Mapping)
        and len(pending_listener_by_token) == len(next_listener_by_token)
    )


def build_ordering_query_command(*, player_token: str, ordered_tokens: list[str]) -> str:
    token_csv = ','.join(ordered_tokens)
    return (
        f'input selection {player_token} order_listeners '
        f'[{token_csv}], [{token_csv}], {len(ordered_tokens)} false false'
    )


def parse_ordered_selection_tokens(data: JsonObject) -> list[object] | None:
    raw_value = data.get('ordered_selections')
    if isinstance(raw_value, list):
        return list(raw_value)
    return None


def resolve_ordered_listeners(
    ordered_tokens: list[object],
    *,
    pending_map: Mapping[str, object],
) -> list[object] | None:
    if len(ordered_tokens) != len(pending_map):
        return None

    seen_tokens: set[str] = set()
    resolved_listeners: list[object] = []
    for raw_token in ordered_tokens:
        if not isinstance(raw_token, str):
            return None
        token = raw_token
        if token in seen_tokens:
            return None

        listener = pending_map.get(token)
        if listener is None:
            return None

        seen_tokens.add(token)
        resolved_listeners.append(listener)

    if len(resolved_listeners) != len(pending_map):
        return None

    return resolved_listeners
