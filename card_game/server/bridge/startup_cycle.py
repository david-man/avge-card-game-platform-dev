from __future__ import annotations

from typing import Any

from ...avge_abstracts.AVGEEvent import AVGEPacket
from ...constants import ActionTypes, AVGEEngineID, ResponseType
from ...internal_events import Phase2


def bootstrap_phase_cycle(bridge: Any) -> None:
    try:
        bridge.env.propose(
            AVGEPacket([
                Phase2(bridge.env, ActionTypes.ENV, bridge.env)
            ], AVGEEngineID(bridge.env, ActionTypes.ENV, None))
        )
        bridge.env.force_flush()
    except Exception as exc:
        bridge._raise_engine_runtime_error('bootstrap', exc)


def prime_engine_for_frontend_inputs(bridge: Any) -> None:
    """Advance startup packets so the bridge can accept immediate frontend phase actions."""
    for step in range(1, 129):
        try:
            response = bridge.env.forward()
        except Exception as exc:
            bridge._raise_engine_runtime_error('prime', exc)
            raise

        bridge._log_engine_response(response, step=step, stage='prime', input_args=None)
        if response.response_type in {ResponseType.REQUIRES_QUERY, ResponseType.GAME_END}:
            return
        if response.response_type == ResponseType.NO_MORE_EVENTS:
            try:
                should_continue = bridge._auto_advance_when_idle()
            except Exception as exc:
                bridge._raise_engine_runtime_error('prime', exc)
                raise

            if not should_continue:
                return
