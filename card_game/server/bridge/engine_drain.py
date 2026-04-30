from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ...avge_abstracts.AVGEEnvironment import GamePhase
from ...avge_abstracts.AVGEEvent import AVGEPacket
from ...constants import ActionTypes, AVGEEngineID, AVGEPlayerAttribute, ResponseType
from ...internal_events import AtkPhase, Phase2, TurnEnd
from ..logging import log_ack_trace_bridge


def drain_engine(
    bridge: Any,
    input_args: JsonObject | None,
    stop_after_command_batch: bool = False,
) -> tuple[list[str], list[CommandPayload]]:
    commands_to_emit: list[str] = []
    payloads_to_emit: list[CommandPayload] = []
    steps = 0
    next_args = input_args

    while steps < bridge._max_forward_steps:
        steps += 1
        try:
            response = bridge.env.forward(next_args)
        except Exception as exc:
            bridge._raise_engine_runtime_error('drain', exc)
            raise

        bridge._log_engine_response(response, step=steps, stage='drain', input_args=next_args)

        # Keep pending args through transition responses (NEXT_PACKET/NEXT_EVENT/NO_MORE_EVENTS)
        # so the intended action reaches the actual phase event core call.
        if next_args is not None and response.response_type not in {
            ResponseType.NEXT_PACKET,
            ResponseType.NEXT_EVENT,
            ResponseType.NO_MORE_EVENTS,
        }:
            next_args = None

        response_commands = bridge._commands_from_response(response)
        response_payloads = bridge._response_payloads_for_commands(response, response_commands)

        # In incremental ACK-gated mode, emit core state-mutation commands
        # immediately so frontend can apply the visual change before any
        # follow-up reactors/listeners are processed.
        if (
            stop_after_command_batch
            and bridge._should_emit_core_commands_before_reactors(response, response_commands)
        ):
            if bridge._pending_packet_commands:
                commands_to_emit.extend(bridge._pending_packet_commands)
                payloads_to_emit.extend(bridge._pending_packet_command_payloads)
                bridge._pending_packet_commands = []
                bridge._pending_packet_command_payloads = []
            commands_to_emit.extend(response_commands)
            payloads_to_emit.extend(response_payloads)
            break

        # Keep command updates packet-scoped until packet completion/interruption.
        if response.response_type == ResponseType.NEXT_PACKET:
            # New packet boundary; clear stale buffer defensively.
            bridge._pending_packet_commands = []
            bridge._pending_packet_command_payloads = []

        should_buffer_response_commands = response.response_type not in {
            ResponseType.SKIP,
            ResponseType.REQUIRES_QUERY,
        }

        if response_commands and should_buffer_response_commands:
            bridge._pending_packet_commands.extend(response_commands)
            bridge._pending_packet_command_payloads.extend(response_payloads)

        if response.response_type in {
            ResponseType.FINISHED_PACKET,
            ResponseType.INTERRUPT,
            ResponseType.NO_MORE_EVENTS,
        }:
            if bridge._pending_packet_commands:
                commands_to_emit.extend(bridge._pending_packet_commands)
                payloads_to_emit.extend(bridge._pending_packet_command_payloads)
                bridge._pending_packet_commands = []
                bridge._pending_packet_command_payloads = []
                if stop_after_command_batch:
                    break

        if response.response_type == ResponseType.SKIP:
            # Packet rolled back; discard accumulated mid-packet state commands
            # and emit SKIP rollback/sync commands immediately.
            bridge._pending_packet_commands = []
            bridge._pending_packet_command_payloads = []
            if response_commands:
                commands_to_emit.extend(response_commands)
                payloads_to_emit.extend(response_payloads)
                if stop_after_command_batch:
                    break

        if response.response_type == ResponseType.REQUIRES_QUERY:
            # A query can arrive before packet-completion signals. In incremental
            # (ACK-gated) draining, flush buffered packet commands first so phase
            # transitions (for example, no-input -> phase2) are not starved behind
            # an immediate query boundary.
            if bridge._pending_packet_commands:
                commands_to_emit.extend(bridge._pending_packet_commands)
                payloads_to_emit.extend(bridge._pending_packet_command_payloads)
                bridge._pending_packet_commands = []
                bridge._pending_packet_command_payloads = []
                if stop_after_command_batch:
                    # Do not drop the query command when an input boundary
                    # follows a packet command in the same drain pass.
                    if response_commands:
                        commands_to_emit.extend(response_commands)
                        payloads_to_emit.extend(response_payloads)
                    break

            # Query prompts should be sent immediately, but packet state should remain buffered.
            if response_commands:
                commands_to_emit.extend(response_commands)
                payloads_to_emit.extend(response_payloads)
                if stop_after_command_batch:
                    break

        if response.response_type == ResponseType.REQUIRES_QUERY:
            break

        if response.response_type == ResponseType.GAME_END:
            # Preserve already-buffered packet updates (for example a lethal
            # HP change) so frontend can animate them before winner overlay.
            if bridge._pending_packet_commands:
                commands_to_emit.extend(bridge._pending_packet_commands)
                payloads_to_emit.extend(bridge._pending_packet_command_payloads)
                bridge._pending_packet_commands = []
                bridge._pending_packet_command_payloads = []

            winner_command = bridge._winner_command_from_environment()
            if winner_command is not None:
                commands_to_emit.append(winner_command)
                payloads_to_emit.append(None)
            break

        if response.response_type == ResponseType.NO_MORE_EVENTS:
            try:
                should_continue = bridge._auto_advance_when_idle()
            except Exception as exc:
                bridge._raise_engine_runtime_error('drain', exc)
                raise

            if not should_continue:
                break

    # Safety fallback: if we hit step cap mid-packet, treat it as interruption
    # so frontend is not starved waiting for any update.
    if steps >= bridge._max_forward_steps and bridge._pending_packet_commands:
        commands_to_emit.extend(bridge._pending_packet_commands)
        payloads_to_emit.extend(bridge._pending_packet_command_payloads)
        bridge._pending_packet_commands = []
        bridge._pending_packet_command_payloads = []

    # In ACK-gated incremental mode, we may emit one command batch and return
    # before the engine fully consumes query/input args. Persist remaining args
    # for the next drain invocation after frontend ACK.
    if next_args is not None:
        bridge._pending_engine_input_args = next_args

    return commands_to_emit, payloads_to_emit


def auto_advance_when_idle(bridge: Any) -> bool:
    # Recovery path: if engine reports idle while still in transitional/no-input
    # phases, explicitly enqueue Phase2 for the current turn so frontend does
    # not remain stuck on no-input after pick-card transfer.
    if bridge.env.game_phase in {GamePhase.INIT, GamePhase.TURN_END, GamePhase.PICK_CARD}:
        bridge.env.propose(
            AVGEPacket([
                Phase2(bridge.env, ActionTypes.ENV, bridge.env)
            ], AVGEEngineID(bridge.env, ActionTypes.ENV, None))
        )
        bridge.env.force_flush()
        log_ack_trace_bridge(
            'idle_recover_proposed_phase2',
            phase=bridge._frontend_phase_token(bridge.env.game_phase),
            player=getattr(bridge.env.player_turn, 'unique_id', None),
        )
        return True

    if bridge.env.game_phase == GamePhase.ATK_PHASE:
        attacks_left = int(bridge.env.player_turn.attributes.get(AVGEPlayerAttribute.ATTACKS_LEFT, 0))
        next_event = AtkPhase(bridge.env, ActionTypes.ENV, bridge.env) if attacks_left > 0 else TurnEnd(bridge.env, ActionTypes.ENV, bridge.env)
        bridge.env.propose(AVGEPacket([next_event], AVGEEngineID(bridge.env, ActionTypes.ENV, None)))
        bridge.env.force_flush()
        return True

    if bridge.env.game_phase == GamePhase.PHASE_2:
        bridge.env.propose(
            AVGEPacket([
                Phase2(bridge.env, ActionTypes.ENV, bridge.env)
            ], AVGEEngineID(bridge.env, ActionTypes.ENV, None))
        )
        bridge.env.force_flush()
        return True

    return False
