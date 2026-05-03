from __future__ import annotations

from typing import Any, Callable
from card_game.server.server_types import JsonObject, CommandPayload

from ...constants import (
    Animation,
    Data,
    Notify,
    ParticleExplosion,
    Response,
    ResponseType,
    RevealCards,
    RevealStr,
    SoundEffect,
)
from ..logging import log_ack_trace_bridge
from ..protocol.command_codec import command_action


def animation_payload_from_response(
    response: Response,
    *,
    notify_targets_from_players_fn: Callable[[list[Any]], list[str]],
) -> JsonObject | None:
    animation = getattr(response, 'accompanying_animation', None)
    if not isinstance(animation, Animation):
        return None

    keyframes_payload: list[JsonObject] = []
    for keyframe in animation.keyframes:
        if isinstance(keyframe, SoundEffect):
            sound_key = keyframe.sound_key.strip() if isinstance(keyframe.sound_key, str) else ''
            if sound_key:
                keyframes_payload.append({
                    'key': sound_key,
                    'kind': 'sound',
                })
            continue

        if isinstance(keyframe, ParticleExplosion):
            particle_key = keyframe.particle_key.strip() if isinstance(keyframe.particle_key, str) else ''
            if not particle_key:
                continue

            payload: JsonObject = {
                'key': particle_key,
                'kind': 'particles',
            }
            card_id = getattr(keyframe.card, 'unique_id', None)
            if isinstance(card_id, str) and card_id.strip():
                payload['card_id'] = card_id.strip()
            keyframes_payload.append(payload)
            continue

        # Defensive compatibility: accept Effect-like objects from any
        # module identity so bridge output remains stable across reloads.
        sound_key_like = getattr(keyframe, 'sound_key', None)
        if isinstance(sound_key_like, str) and sound_key_like.strip():
            keyframes_payload.append({
                'key': sound_key_like.strip(),
                'kind': 'sound',
            })
            continue

        particle_key_like = getattr(keyframe, 'particle_key', None)
        if isinstance(particle_key_like, str) and particle_key_like.strip():
            payload = {
                'key': particle_key_like.strip(),
                'kind': 'particles',
            }
            card_like = getattr(keyframe, 'card', None)
            card_id_like = getattr(card_like, 'unique_id', None)
            if isinstance(card_id_like, str) and card_id_like.strip():
                payload['card_id'] = card_id_like.strip()
            keyframes_payload.append(payload)
            continue

        # Legacy compatibility: tuple[(asset key), (animation kind)].
        if isinstance(keyframe, tuple) and len(keyframe) == 2:
            raw_key, raw_type = keyframe
            if not isinstance(raw_key, str) or not raw_key.strip():
                continue

            if isinstance(raw_type, str):
                animation_type = raw_type.strip().lower()
            else:
                raw_type_value = getattr(raw_type, 'value', None)
                animation_type = raw_type_value.strip().lower() if isinstance(raw_type_value, str) else ''

            if animation_type not in {'sound', 'particles'}:
                continue

            keyframes_payload.append({
                'key': raw_key.strip(),
                'kind': animation_type,
            })

    if len(keyframes_payload) == 0:
        return None

    targets = notify_targets_from_players_fn(animation.players)
    target_token = 'both' if len(targets) != 1 else targets[0]
    return {
        'target': target_token,
        'keyframes': keyframes_payload,
    }


def response_payloads_for_commands(
    response: Response,
    commands: list[str],
    *,
    animation_payload_from_response_fn: Callable[[Response], JsonObject | None],
) -> list[CommandPayload]:
    payloads: list[CommandPayload] = [None] * len(commands)
    if len(commands) == 0:
        return payloads

    animation_payload = animation_payload_from_response_fn(response)
    if animation_payload is not None:
        target_index = 0
        for idx, command in enumerate(commands):
            action = command_action(command)
            if action not in {'notify', 'reveal', 'sound'}:
                target_index = idx
                break
        payloads[target_index] = {'animation': animation_payload}
    return payloads


def fallback_payload_command(
    response: Response,
    payload: Any,
    *,
    reveal_commands_for_players_fn: Callable[[list[Any], list[str], str | None, int | None], list[str]],
    notify_from_notify_fn: Callable[[Notify], list[str]],
    has_nonempty_payload_fn: Callable[[Any], bool],
    notify_both_fn: Callable[[str], list[str]],
) -> list[str]:
    if response.response_type in {ResponseType.GAME_END, ResponseType.INTERRUPT}:
        return []

    if isinstance(payload, RevealCards):
        card_ids = [getattr(card, 'unique_id', str(card)) for card in payload.cards]
        return reveal_commands_for_players_fn(payload.players, card_ids, payload.message, payload.timeout)

    if isinstance(payload, RevealStr):
        msg = f"{payload.message}: {', '.join(payload.items)}" if len(payload.items) > 0 else payload.message
        return notify_from_notify_fn(Notify(msg, payload.players, payload.timeout))

    if isinstance(payload, Notify):
        return notify_from_notify_fn(payload)

    if has_nonempty_payload_fn(payload):
        payload_name = type(payload).__name__
        log_ack_trace_bridge(
            'uncovered_nonempty_payload',
            response_type=str(response.response_type),
            payload_type=payload_name,
        )
        return notify_both_fn(f'UNHANDLED_{payload_name}')

    return []


def has_nonempty_payload(payload: Any) -> bool:
    if isinstance(payload, Data) and type(payload) is Data:
        return False
    return isinstance(payload, Data)
