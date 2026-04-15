from __future__ import annotations

from copy import deepcopy
from random import randint
from threading import RLock
from typing import Any

from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ..avge_abstracts.AVGEEnvironment import GamePhase
from ..avge_abstracts.AVGECards import (
    AVGECard,
    AVGECharacterCard,
    AVGEStadiumCard,
    AVGEItemCard,
    AVGESupporterCard,
    AVGEToolCard,
)
from ..constants import Pile
from ..constants import (
    ALLOW_NONE,
    ALLOW_REPEAT,
    DISPLAY_FLAG,
    InputType,
    LABEL_FLAG,
    MESSAGE_KEY,
    REVEAL_KEY,
    Response,
    ResponseType,
    TARGETS_FLAG,
    AVGEPlayerAttribute,
    PlayerID,
    ActionTypes,
    AVGEEngineID,
)
from ..internal_events import (
    AtkPhase,
    AVGECardHPChange,
    AVGECardMaxHPChange,
    AVGECardStatusChange,
    AVGECardTypeChange,
    AVGEEnergyTransfer,
    AVGEPlayerAttributeChange,
    EmptyEvent,
    InputEvent,
    Phase2,
    PhasePickCard,
    PlayCharacterCard,
    PlayNonCharacterCard,
    ReorderCardholder,
    TransferCard,
    TurnEnd,
)
from ..avge_abstracts.AVGEEvent import AVGEPacket
from .frontend_formatter import environment_to_setup_json as format_environment_to_setup_json
from .frontend_formatter import environment_to_setup_payload as format_environment_to_setup_payload
from .logging import log_ack_wait
from .logging import log_ack_trace_bridge
from .logging import log_energy_move
from .logging import log_engine_response
from card_game.catalog import *
from card_game.constants import *

start_round = 1
p1_setup_default: dict[Pile, list[type[AVGECard]]] = {
    Pile.ACTIVE: [KeiWatanabe],
    Pile.BENCH: [RobertoGonzales],
    Pile.HAND: [RobertoGonzales, DavidMan, BenCherekIII, Lucas, Bucket, AVGETShirt, Richard, Victoria],
    Pile.DISCARD: [MainHall, Johann, IceSkates],
    Pile.DECK: [MainHall, AVGEBirb, IceSkates, FionaLi, DavidMan, JennieWang,LukeXu, Johann, DanielYang, ],
    Pile.STADIUM: [],
}

p2_setup_default: dict[Pile, list[type[AVGECard]]] = {
    Pile.ACTIVE: [MatthewWang],
    Pile.BENCH: [DavidMan],
    Pile.HAND: [AVGEBirb, SteinertPracticeRoom,  JennieWang, ConcertTicket, FoldingStand],
    Pile.DISCARD: [VideoCamera, JuliaCiacerelli, MaggieLi],
    Pile.DECK: [AVGEBirb, SteinertPracticeRoom,  JennieWang, ConcertTicket, FoldingStand],
}

# Backwards-compatible aliases for older references.
p1_setup = p1_setup_default
p2_setup = p2_setup_default


def build_environment_from_default_setups(
    start_turn: PlayerID = PlayerID.P1,
    starting_stadium: type[AVGEStadiumCard] | None = None,
    starting_stadium_player: PlayerID | None = None,
    round_number: int = start_round,
) -> AVGEEnvironment:
    """Build an AVGEEnvironment from p1_setup_default and p2_setup_default."""
    return AVGEEnvironment(
        deepcopy(p1_setup_default),
        deepcopy(p2_setup_default),
        start_turn,
        starting_stadium=starting_stadium,
        starting_stadium_player=starting_stadium_player,
        start_round=round_number,
    )


def build_default_setup_payload_from_environment(
    start_turn: PlayerID = PlayerID.P1,
    starting_stadium: type[AVGEStadiumCard] | None = None,
    starting_stadium_player: PlayerID | None = None,
    round_number: int = start_round,
) -> dict[str, Any]:
    """Build a frontend/router-compatible setup payload from the default environment."""
    env = build_environment_from_default_setups(
        start_turn=start_turn,
        starting_stadium=starting_stadium,
        starting_stadium_player=starting_stadium_player,
        round_number=round_number,
    )
    return environment_to_setup_payload(env)

def environment_to_setup_payload(env: AVGEEnvironment) -> dict[str, Any]:
    """Convert an AVGEEnvironment into frontend setup payload format."""
    return format_environment_to_setup_payload(env)


def environment_to_setup_json(env: AVGEEnvironment, indent: int = 2) -> str:
    """Return a pretty JSON string for the converted setup payload."""
    return format_environment_to_setup_json(env, indent=indent)


class FrontendGameBridge:
    """Translate frontend events to engine actions and engine responses back to frontend commands."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.env = build_environment_from_default_setups()
        self._max_forward_steps = 5000
        self._pending_packet_commands: list[str] = []
        self._outbound_command_queue: list[str] = []
        self._awaiting_frontend_ack = False
        self._awaiting_frontend_ack_command: str | None = None
        self._last_emitted_phase_token: str | None = None
        self._pending_engine_input_args: dict[str, Any] | None = None
        self._pending_frontend_events: list[tuple[str, dict[str, Any]]] = []
        self._last_emitted_input_query_signature: tuple[str, str, str] | None = None
        self._force_environment_sync_pending = False
        self._bootstrap_phase_cycle()
        self._prime_engine_for_frontend_inputs()
        self._last_emitted_phase_token = self._frontend_phase_token(self.env.game_phase)

    def get_setup_payload(self) -> dict[str, Any]:
        with self._lock:
            return environment_to_setup_payload(self.env)

    def _accept_frontend_ack(self, payload: dict[str, Any]) -> bool:
        if not self._awaiting_frontend_ack:
            if str(payload.get('line', '')).strip().lower() == 'ack backend_update_processed':
                log_ack_trace_bridge('unexpected_ack_no_wait')
            return False

        ack_line = str(payload.get('line', '')).strip().lower()
        if ack_line != 'ack backend_update_processed':
            return False

        expected = self._awaiting_frontend_ack_command
        ack_command = payload.get('command')

        # Strict ACK mode: every emitted backend command must be explicitly
        # acknowledged with a matching command payload.
        if expected is not None and (
            not isinstance(ack_command, str)
            or ack_command.strip() != expected.strip()
        ):
            log_ack_trace_bridge(
                'ack_rejected_command_mismatch',
                expected=expected,
                actual=ack_command,
            )
            return False

        log_ack_trace_bridge('ack_accepted', command=expected)
        self._awaiting_frontend_ack = False
        self._awaiting_frontend_ack_command = None
        return True

    def _emit_next_command_if_ready(self) -> list[str]:
        if self._awaiting_frontend_ack:
            return []
        if not self._outbound_command_queue:
            return []

        next_command = self._outbound_command_queue.pop(0)
        self._awaiting_frontend_ack = True
        self._awaiting_frontend_ack_command = next_command
        log_ack_trace_bridge(
            'emit_command_waiting_ack',
            command=next_command,
            remaining_queue=len(self._outbound_command_queue),
        )
        return [next_command]

    def _append_phase_command_if_changed(self, commands: list[str], phase: GamePhase) -> None:
        phase_token = self._frontend_phase_token(phase)
        if self._last_emitted_phase_token == phase_token:
            return
        commands.append(f'phase {phase_token}')
        self._last_emitted_phase_token = phase_token

    def _response_source_summary(self, source: Any) -> str:
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

    def _log_engine_response(self, response: Response, step: int, stage: str, input_args: dict[str, Any] | None) -> None:
        response_type = getattr(response.response_type, 'value', str(response.response_type))
        source = getattr(response, 'source', None)
        source_type = type(source).__name__ if source is not None else 'None'
        response_data = response.data if isinstance(response.data, dict) else None
        data_keys = list(response_data.keys()) if response_data is not None else []

        # Skip noisy accept-without-payload steps; keep all meaningful responses.
        if response.response_type == ResponseType.ACCEPT and not data_keys:
            return

        log_engine_response(
            stage=stage,
            step=step,
            response_type=response_type,
            source_type=source_type,
            source=self._response_source_summary(source),
            data_keys=data_keys,
            has_input_args=input_args is not None,
        )

    def _enqueue_frontend_event_work(self, event_name: str, payload: dict[str, Any]) -> None:
        commands, used_input = self._apply_frontend_event(event_name, payload)
        self._outbound_command_queue.extend(commands)

        if used_input is not None:
            self._pending_engine_input_args = used_input

        if not self._outbound_command_queue:
            drain_input = self._pending_engine_input_args
            self._pending_engine_input_args = None
            self._outbound_command_queue.extend(self._drain_engine(input_args=drain_input, stop_after_command_batch=True))

    def _pump_outbound_until_next_command(self) -> None:
        if self._outbound_command_queue:
            return

        # Process at most one queued frontend event per ACK cycle.
        if self._pending_frontend_events:
            queued_event_name, queued_payload = self._pending_frontend_events.pop(0)
            self._enqueue_frontend_event_work(queued_event_name, queued_payload)
            return

        running_event = self.env._engine.event_running
        if isinstance(running_event, InputEvent) and self._pending_engine_input_args is None:
            # InputEvent is waiting for user/admin input, so draining now would
            # only re-observe the same unresolved query boundary.
            log_ack_trace_bridge(
                'waiting_for_input_result',
                input_keys=getattr(running_event, 'input_keys', None),
                input_type=getattr(running_event, 'input_type', None),
            )
            return

        # Perform one deterministic drain pass per ACK cycle.
        drain_input = self._pending_engine_input_args
        self._pending_engine_input_args = None
        drained = self._drain_engine(input_args=drain_input, stop_after_command_batch=True)
        if drained:
            self._outbound_command_queue.extend(drained)
            return

        log_ack_trace_bridge(
            'post_ack_no_commands',
            phase=self._frontend_phase_token(self.env.game_phase),
            event_running=(
                type(self.env._engine.event_running).__name__
                if self.env._engine.event_running is not None
                else None
            ),
            pending_input=self._pending_engine_input_args is not None,
        )

    def handle_frontend_event(
        self,
        event_type: str,
        response_data: dict[str, Any] | None,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with self._lock:
            payload = response_data or {}
            event_name = self._canonical_event_name(event_type)

            if event_name == 'terminal_log':
                if self._accept_frontend_ack(payload):
                    self._pump_outbound_until_next_command()

                    return {
                        'commands': self._emit_next_command_if_ready(),
                        'setup_payload': environment_to_setup_payload(self.env),
                        'force_environment_sync': self._consume_force_environment_sync_flag(),
                    }

                return {
                    'commands': [],
                    'setup_payload': environment_to_setup_payload(self.env),
                    'force_environment_sync': self._consume_force_environment_sync_flag(),
                }

            if event_name in {'setup_loaded', 'surrender_result', 'surrender_timeout'}:
                return {
                    'commands': [],
                    'setup_payload': environment_to_setup_payload(self.env),
                    'force_environment_sync': self._consume_force_environment_sync_flag(),
                }

            # Command-level flow control: do not advance engine while waiting for
            # frontend ACK of the last emitted backend command.
            if self._awaiting_frontend_ack:
                self._pending_frontend_events.append((event_name, dict(payload)))

                log_ack_wait(
                    queued_event=event_name,
                    awaiting_command=self._awaiting_frontend_ack_command,
                    queued_events=len(self._pending_frontend_events),
                )

                return {
                    'commands': [],
                    'setup_payload': environment_to_setup_payload(self.env),
                    'force_environment_sync': self._consume_force_environment_sync_flag(),
                }

            self._enqueue_frontend_event_work(event_name, payload)

            return {
                'commands': self._emit_next_command_if_ready(),
                'setup_payload': environment_to_setup_payload(self.env),
                'force_environment_sync': self._consume_force_environment_sync_flag(),
            }

    def _bootstrap_phase_cycle(self) -> None:
        self.env.propose(
            AVGEPacket([
                Phase2(self.env.player_turn, ActionTypes.ENV, None)
            ], AVGEEngineID(None, ActionTypes.ENV, None))
        )
        self.env.force_flush()

    def _prime_engine_for_frontend_inputs(self) -> None:
        """Advance startup packets so the bridge can accept immediate frontend phase actions."""
        for step in range(1, 129):
            response = self.env.forward()
            self._log_engine_response(response, step=step, stage='prime', input_args=None)
            if response.response_type in {ResponseType.REQUIRES_QUERY, ResponseType.GAME_END}:
                return
            if response.response_type == ResponseType.NO_MORE_EVENTS:
                if not self._auto_advance_when_idle():
                    return

    def _apply_frontend_event(
        self,
        event_name: str,
        data: dict[str, Any],
    ) -> tuple[list[str], dict[str, Any] | None]:
        commands: list[str] = []
        engine = self.env._engine
        running = engine.event_running

        # Backend state is authoritative for phase navigation.
        if event_name in {'phase2_attack_button_clicked', 'phase_2_attack_button_clicked'}:
            if self.env.game_phase == GamePhase.PHASE_2:
                commands.extend(self._notify_both('Phase2 attack request received.'))
                return commands, {'next': 'atk'}
            commands.extend(self._notify_both(f'Ignored phase2 attack request: backend phase is {self._frontend_phase_token(self.env.game_phase)}'))
            return commands, None

        if event_name in {'atk_skip_button_clicked', 'atk_phase_skip_button_clicked'}:
            if self.env.game_phase == GamePhase.ATK_PHASE:
                commands.extend(self._notify_both('Attack phase skip request received.'))
                return commands, {'type': ActionTypes.SKIP}
            commands.extend(self._notify_both(f'Ignored attack skip request: backend phase is {self._frontend_phase_token(self.env.game_phase)}'))
            return commands, None

        if isinstance(running, InputEvent) and event_name == 'input_result':
            input_args = self._parse_frontend_input_result(running, data)
            if input_args is not None:
                return commands, input_args
            commands.extend(self._notify_both('Input result rejected by backend parser.'))
            return commands, None

        if event_name == 'energy_moved':
            running_name = type(running).__name__ if running is not None else 'None'
            game_phase = self._frontend_phase_token(self.env.game_phase)
            in_phase2 = isinstance(running, Phase2) or (running is None and self.env.game_phase == GamePhase.PHASE_2)
            if not in_phase2:
                log_energy_move(
                    status='ignored',
                    reason='not_phase2',
                    running=running_name,
                    game_phase=game_phase,
                    payload=data,
                )
                commands.extend(self._notify_both(f'Ignored energy move request: backend phase is {self._frontend_phase_token(self.env.game_phase)}'))
                return commands, None

            phase_args = self._phase2_args_from_frontend_event(event_name, data)
            if phase_args is not None:
                attach_to = phase_args.get('attach_to') if isinstance(phase_args, dict) else None
                token = phase_args.get('token') if isinstance(phase_args, dict) else None
                log_energy_move(
                    status='accepted',
                    reason='valid_phase2_attach',
                    running=running_name,
                    game_phase=game_phase,
                    payload=data,
                    attach_to=str(getattr(attach_to, 'unique_id', None)),
                    token=str(getattr(token, 'unique_id', None)),
                )
                return commands, phase_args

            log_energy_move(
                status='ignored',
                reason='invalid_target_or_token',
                running=running_name,
                game_phase=game_phase,
                payload=data,
            )
            commands.extend(self._notify_both('Ignored energy move request: missing/invalid energy target or token.'))
            return commands, None

        if event_name in {'card_played', 'card_action'}:
            action = self._normalize_action_name(data.get('action'))
            card_id = self._card_id_from_payload(data)
            card = self._get_character_card(card_id)
            if action in {'activate-ability', 'activate_ability', 'active'}:
                if card is not None:
                    self._queue_active_ability_interrupt(card, running)
                return commands, None

            if isinstance(running, AtkPhase) or (running is None and self.env.game_phase == GamePhase.ATK_PHASE):
                active = self.env.get_active_card(self.env.player_turn.unique_id)
                if isinstance(active, AVGECharacterCard) and card is not None and active.unique_id == card.unique_id:
                    if action in {'atk1', 'atk_1', 'attack1'}:
                        return commands, {'type': ActionTypes.ATK_1}
                    if action in {'atk2', 'atk_2', 'attack2'}:
                        return commands, {'type': ActionTypes.ATK_2}

        if isinstance(running, Phase2) or (running is None and self.env.game_phase == GamePhase.PHASE_2):
            phase_args = self._phase2_args_from_frontend_event(event_name, data)
            if phase_args is not None:
                return commands, phase_args

        return commands, None

    def _drain_engine(self, input_args: dict[str, Any] | None, stop_after_command_batch: bool = False) -> list[str]:
        commands_to_emit: list[str] = []
        steps = 0
        next_args = input_args

        while steps < self._max_forward_steps:
            steps += 1
            response = self.env.forward(next_args)
            self._log_engine_response(response, step=steps, stage='drain', input_args=next_args)

            # Keep pending args through transition responses (NEXT_PACKET/NEXT_EVENT/NO_MORE_EVENTS)
            # so the intended action reaches the actual phase event core call.
            if next_args is not None and response.response_type not in {
                ResponseType.NEXT_PACKET,
                ResponseType.NEXT_EVENT,
                ResponseType.NO_MORE_EVENTS,
            }:
                next_args = None

            response_commands = self._commands_from_response(response)

            # Keep command updates packet-scoped until packet completion/interruption.
            if response.response_type == ResponseType.NEXT_PACKET:
                # New packet boundary; clear stale buffer defensively.
                self._pending_packet_commands = []

            should_buffer_response_commands = response.response_type not in {
                ResponseType.SKIP,
                ResponseType.REQUIRES_QUERY,
            }

            if response_commands and should_buffer_response_commands:
                self._pending_packet_commands.extend(response_commands)

            if response.response_type in {
                ResponseType.FINISHED_PACKET,
                ResponseType.INTERRUPT,
                ResponseType.NO_MORE_EVENTS,
            }:
                if self._pending_packet_commands:
                    commands_to_emit.extend(self._pending_packet_commands)
                    self._pending_packet_commands = []
                    if stop_after_command_batch:
                        break

            if response.response_type == ResponseType.SKIP:
                # Packet rolled back; discard accumulated mid-packet state commands
                # and emit SKIP rollback/sync commands immediately.
                self._pending_packet_commands = []
                if response_commands:
                    commands_to_emit.extend(response_commands)
                    if stop_after_command_batch:
                        break

            if response.response_type == ResponseType.REQUIRES_QUERY:
                # A query can arrive before packet-completion signals. In incremental
                # (ACK-gated) draining, flush buffered packet commands first so phase
                # transitions (for example, no-input -> phase2) are not starved behind
                # an immediate query boundary.
                if self._pending_packet_commands:
                    commands_to_emit.extend(self._pending_packet_commands)
                    self._pending_packet_commands = []
                    if stop_after_command_batch:
                        break

                # Query prompts should be sent immediately, but packet state should remain buffered.
                if response_commands:
                    commands_to_emit.extend(response_commands)
                    if stop_after_command_batch:
                        break

            if response.response_type == ResponseType.REQUIRES_QUERY:
                break

            if response.response_type == ResponseType.GAME_END:
                winner = getattr(self.env.winner, 'unique_id', None)
                if winner == PlayerID.P1:
                    commands_to_emit.append('winner player-1')
                elif winner == PlayerID.P2:
                    commands_to_emit.append('winner player-2')
                break

            if response.response_type == ResponseType.NO_MORE_EVENTS:
                if not self._auto_advance_when_idle():
                    break

        # Safety fallback: if we hit step cap mid-packet, treat it as interruption
        # so frontend is not starved waiting for any update.
        if steps >= self._max_forward_steps and self._pending_packet_commands:
            commands_to_emit.extend(self._pending_packet_commands)
            self._pending_packet_commands = []

        # In ACK-gated incremental mode, we may emit one command batch and return
        # before the engine fully consumes query/input args. Persist remaining args
        # for the next drain invocation after frontend ACK.
        if next_args is not None:
            self._pending_engine_input_args = next_args

        return commands_to_emit

    def _auto_advance_when_idle(self) -> bool:
        # Recovery path: if engine reports idle while still in transitional/no-input
        # phases, explicitly enqueue Phase2 for the current turn so frontend does
        # not remain stuck on no-input after pick-card transfer.
        if self.env.game_phase in {GamePhase.INIT, GamePhase.TURN_END, GamePhase.PICK_CARD}:
            self.env.propose(
                AVGEPacket([
                    Phase2(self.env.player_turn, ActionTypes.ENV, None)
                ], AVGEEngineID(None, ActionTypes.ENV, None))
            )
            self.env.force_flush()
            log_ack_trace_bridge(
                'idle_recover_proposed_phase2',
                phase=self._frontend_phase_token(self.env.game_phase),
                player=getattr(self.env.player_turn, 'unique_id', None),
            )
            return True

        if self.env.game_phase == GamePhase.ATK_PHASE:
            attacks_left = int(self.env.player_turn.attributes.get(AVGEPlayerAttribute.ATTACKS_LEFT, 0))
            next_event = AtkPhase(self.env.player_turn, ActionTypes.ENV, None) if attacks_left > 0 else TurnEnd(self.env, ActionTypes.ENV, None)
            self.env.propose(AVGEPacket([next_event], AVGEEngineID(None, ActionTypes.ENV, None)))
            self.env.force_flush()
            return True

        if self.env.game_phase == GamePhase.PHASE_2:
            self.env.propose(
                AVGEPacket([
                    Phase2(self.env.player_turn, ActionTypes.ENV, None)
                ], AVGEEngineID(None, ActionTypes.ENV, None))
            )
            self.env.force_flush()
            return True

        return False

    def _consume_force_environment_sync_flag(self) -> bool:
        should_sync = self._force_environment_sync_pending
        self._force_environment_sync_pending = False
        return should_sync

    def _commands_from_response(self, response: Response) -> list[str]:
        commands: list[str] = []
        response_data = response.data if isinstance(response.data, dict) else {}

        if response.response_type == ResponseType.ACCEPT:
            message = response_data.get(MESSAGE_KEY)
            if isinstance(message, str) and message.strip():
                commands.extend(self._notify_for_source_player(response.source, message.strip()))
            return commands

        if response.response_type == ResponseType.SKIP:
            message = response_data.get(MESSAGE_KEY)
            skip_message = message if isinstance(message, str) and message.strip() else 'EVENT SKIPPED'
            if bool(getattr(response.source, 'internal', False)):
                commands.extend(self._notify_current_turn_player(skip_message))
            else:
                commands.extend(self._notify_both(skip_message))
            self._force_environment_sync_pending = True
            return commands

        if response.response_type == ResponseType.FAST_FORWARD:
            message = response_data.get(MESSAGE_KEY)
            commands.extend(self._notify_both(message if isinstance(message, str) and message.strip() else 'EVENT FAST FORWARDED'))
            return commands

        if response.response_type == ResponseType.REQUIRES_QUERY:
            source = response.source
            if isinstance(source, (PhasePickCard, Phase2, AtkPhase)):
                # Phase events may surface as REQUIRES_QUERY (for example Phase2
                # waiting for player action) without emitting a CORE response.
                # Keep frontend phase HUD/state in sync in this path too.
                self._append_phase_command_if_changed(commands, self.env.game_phase)
            if isinstance(source, InputEvent):
                query_label = str(response_data.get(LABEL_FLAG, ''))
                input_keys = ','.join(str(key) for key in getattr(source, 'input_keys', []))
                player_id = str(getattr(getattr(source, 'player_for', None), 'unique_id', ''))
                query_signature = (player_id, query_label, input_keys)

                if self._last_emitted_input_query_signature == query_signature:
                    log_ack_trace_bridge(
                        'duplicate_input_query_suppressed',
                        signature=query_signature,
                    )
                    return commands

                input_command = self._build_input_command(source, response_data)
                if input_command:
                    commands.append(input_command)
                    self._last_emitted_input_query_signature = query_signature
                return commands

            message = response_data.get(MESSAGE_KEY)
            if isinstance(message, str) and message.strip():
                commands.extend(self._notify_for_source_player(response.source, message.strip()))
            return commands

        if response.response_type != ResponseType.CORE:
            return commands

        source = response.source

        if isinstance(source, AVGECardHPChange):
            commands.append(f'hp {source.target_card.unique_id} {int(source.target_card.hp)} {int(source.target_card.max_hp)}')
            return commands

        if isinstance(source, AVGECardMaxHPChange):
            commands.append(f'maxhp {source.target_card.unique_id} {int(source.target_card.max_hp)}')
            return commands

        if isinstance(source, AVGECardTypeChange):
            card_type = self._card_type_command_token(source.target_card.card_type)
            commands.append(f'changetype {source.target_card.unique_id} {card_type}')
            return commands

        if isinstance(source, AVGECardStatusChange):
            status_key = str(source.status_effect).split('.')[-1]
            status_name = {
                'ARR': 'Arranger',
                'GOON': 'Goon',
                'MAID': 'Maid',
            }.get(status_key, status_key.title())
            count = len(source.target.statuses_attached[source.status_effect])
            commands.append(f'set_status {source.target.unique_id} {status_name} {count}')
            return commands

        if isinstance(source, AVGEEnergyTransfer):
            energy_target = self._energy_target_command_arg(source.target)
            if energy_target:
                commands.append(f'mv-energy {source.token.unique_id} {energy_target}')
            return commands

        if isinstance(source, AVGEPlayerAttributeChange):
            player_token = self._player_id_to_frontend(source.target_player.unique_id)
            commands.append(f'stat {player_token} {source.attribute} {int(source.target_player.attributes[source.attribute])}')
            return commands

        if isinstance(source, TransferCard):
            move_target = self._transfer_target_command_arg(source)
            if move_target:
                commands.append(f'mv {source.card.unique_id} {move_target}')
            return commands

        if isinstance(source, ReorderCardholder):
            commands.append('shuffle-animation')
            return commands

        if isinstance(source, (PlayCharacterCard, PlayNonCharacterCard)):
            return commands

        if isinstance(source, PhasePickCard):
            self._append_phase_command_if_changed(commands, self.env.game_phase)
            return commands

        if isinstance(source, Phase2):
            self._append_phase_command_if_changed(commands, self.env.game_phase)
            return commands

        if isinstance(source, AtkPhase):
            self._append_phase_command_if_changed(commands, self.env.game_phase)
            return commands

        if isinstance(source, InputEvent):
            # Successful input application has no direct frontend mutation command.
            return commands

        if isinstance(source, TurnEnd):
            next_turn = self._player_id_to_frontend(self.env.player_turn.unique_id)
            commands.extend(self._notify_both(f'TURN SWITCHED: {next_turn.upper()}'))
            self._force_environment_sync_pending = True
            return commands

        if isinstance(source, EmptyEvent):
            reveal_data = response_data.get(REVEAL_KEY)
            if isinstance(reveal_data, list) and reveal_data:
                card_ids = [getattr(card, 'unique_id', str(card)) for card in reveal_data]
                cards_csv = ','.join(card_ids)
                commands.append(f'reveal player-1 [{cards_csv}]')
                commands.append(f'reveal player-2 [{cards_csv}]')
            return commands

        message = response_data.get(MESSAGE_KEY)
        if isinstance(message, str) and message.strip():
            commands.extend(self._notify_for_source_player(response.source, message.strip()))

        return commands

    def _phase2_args_from_frontend_event(self, event_name: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if event_name in {'phase2_attack_button_clicked', 'phase_2_attack_button_clicked'}:
            return {'next': 'atk'}

        if event_name in {'attach_tool', 'tool_attached'}:
            tool_id = self._pick_str(data, 'tool_card_id', 'card_id')
            target_id = self._pick_str(data, 'attached_to_card_id', 'target_card_id')
            tool = self._get_card(tool_id)
            attach_to = self._get_character_card(target_id)
            if isinstance(tool, AVGEToolCard) and isinstance(attach_to, AVGECharacterCard):
                return {'next': 'tool', 'tool': tool, 'attach_to': attach_to}

        if event_name == 'item_supporter_use':
            card_id = self._card_id_from_payload(data)
            card = self._get_card(card_id)
            if isinstance(card, AVGEItemCard):
                return {'next': 'item', 'item_card': card}
            if isinstance(card, AVGESupporterCard):
                return {'next': 'supporter', 'supporter_card': card}

        if event_name == 'card_moved':
            card = self._get_card(self._card_id_from_payload(data))
            to_zone = self._pick_str(data, 'to_zone', 'to_zone_id', 'toZone', 'toZoneId')
            if card is None or not to_zone:
                return None

            to_zone = self._normalize_zone_id(to_zone)
            current_zone = self._card_zone_id(card)
            if not current_zone:
                return None

            if to_zone == 'stadium' and isinstance(card, AVGEStadiumCard):
                return {'next': 'stadium', 'stadium_card': card}

            if isinstance(card, AVGECharacterCard):
                if current_zone.endswith('-bench') and to_zone.endswith('-active'):
                    return {'next': 'swap', 'bench_card': card}
                if current_zone.endswith('-hand') and to_zone.endswith('-bench'):
                    return {'next': 'hand2bench', 'hand2bench': card}

        if event_name == 'energy_moved':
            to_attached = self._pick_str(data, 'to_attached_to_card_id', 'toAttachedToCardId', 'attached_to_card_id')
            to_zone = self._pick_str(data, 'to_zone_id', 'to_zone', 'toZoneId', 'toZone')
            energy_id = self._pick_str(data, 'energy_id', 'id', 'energyId')
            target_card: AVGECharacterCard | None = None
            if to_attached:
                target_card = self._get_character_card(to_attached)
            elif isinstance(to_zone, str):
                normalized_to_zone = self._normalize_zone_id(to_zone)
                if normalized_to_zone.endswith('-bench') or normalized_to_zone.endswith('-active'):
                    target_card = self._get_character_card(self._pick_str(data, 'to_card_id', 'toCardId'))

            if isinstance(target_card, AVGECharacterCard):
                selected_token = self._get_energy_token(energy_id)
                if selected_token is not None:
                    return {'next': 'energy', 'attach_to': target_card, 'token': selected_token}
                return {'next': 'energy', 'attach_to': target_card}

        # Allow card_action active ability in phase2.
        if event_name in {'card_played', 'card_action'}:
            action = self._normalize_action_name(data.get('action'))
            if action in {'activate-ability', 'activate_ability', 'active'}:
                card = self._get_character_card(self._card_id_from_payload(data))
                if card is not None:
                    self._queue_active_ability_interrupt(card, self.env._engine.event_running)

        return None

    def _build_input_command(self, event: InputEvent, response_data: dict[str, Any]) -> str | None:
        player_token = self._player_id_to_frontend(event.player_for.unique_id)
        message = self._command_token(str(response_data.get(MESSAGE_KEY, 'input_required')))
        query_label = str(response_data.get(LABEL_FLAG, ''))

        if query_label in {'kei_watanabe_drumkidworkshop'}:
            display = response_data.get(DISPLAY_FLAG, [])
            display_ids = self._csv_from_display_entries(display)
            if display_ids:
                return f'input kei_watanabe_drumkidworkshop {player_token} {message} [{display_ids}]'

        input_type = response_data.get('input_type')
        num_inputs = int(response_data.get('num_inputs', len(event.input_keys)))

        if input_type == InputType.SELECTION:
            display = response_data.get(DISPLAY_FLAG, [])
            targets = response_data.get(TARGETS_FLAG, [])
            allow_repeat = bool(response_data.get(ALLOW_REPEAT, False))
            allow_none = bool(response_data.get(ALLOW_NONE, response_data.get('allow_none', False)))
            display_ids = self._csv_from_display_entries(display)
            highlight_ids = self._csv_from_display_entries(targets)
            return (
                f'input selection {player_token} {message} '
                f'[{display_ids}], [{highlight_ids}], {num_inputs} '
                f'{str(allow_repeat).lower()} {str(allow_none).lower()}'
            )

        if isinstance(input_type, list):
            flat_type = input_type[0] if len(input_type) > 0 else InputType.DETERMINISTIC
        else:
            flat_type = input_type

        if flat_type == InputType.D6:
            value = randint(1, 6)
            return f'input d6 {player_token} {message} {value}'

        if flat_type == InputType.COIN:
            value = randint(0, 1)
            return f'input coin {player_token} {message} {value}'

        if flat_type == InputType.BINARY:
            return f'input binary {player_token} {message}'

        if query_label in {'daniel_redirect', 'ryan_lee_atk1'} or flat_type == InputType.DETERMINISTIC:
            return f'input numerical-entry {player_token} {message}'

        return f'input numerical-entry {player_token} {message}'

    def _parse_frontend_input_result(self, event: InputEvent, data: dict[str, Any]) -> dict[str, Any] | None:
        # Frontend supplied an input answer, so allow the next query cycle to emit.
        self._last_emitted_input_query_signature = None

        query_label = str(event.query_data.get(LABEL_FLAG, ''))
        if query_label == 'kei_watanabe_drumkidworkshop':
            card_id = self._pick_str(data, 'card_id', 'cardId')
            attack = self._normalize_action_name(data.get('attack'))
            card = self._get_character_card(card_id)
            if card is None:
                return None
            if attack == 'atk1':
                return {'input_result': [card, ActionTypes.ATK_1]}
            if attack == 'atk2':
                return {'input_result': [card, ActionTypes.ATK_2]}
            return None

        if query_label in {'daniel_redirect', 'ryan_lee_atk1'}:
            value = data.get('value')
            if isinstance(value, (int, float)):
                return {'input_result': [int(value)]}
            return None

        input_type = event.input_type
        if input_type == InputType.SELECTION:
            ordered = data.get('ordered_selections', [])
            if not isinstance(ordered, list):
                return None
            parsed: list[Any] = []
            for raw in ordered:
                if raw is None or (isinstance(raw, str) and raw.strip().lower() in {'none', 'null', '-1'}):
                    parsed.append(None)
                    continue
                if not isinstance(raw, str):
                    return None
                normalized_raw = self._sanitize_identifier_token(raw)
                card = self._get_card(normalized_raw)
                parsed.append(card if card is not None else raw)
            if len(parsed) != len(event.input_keys):
                return None
            return {'input_result': parsed}

        if isinstance(input_type, list):
            normalized_types = input_type
        else:
            normalized_types = [input_type] * len(event.input_keys)

        if len(normalized_types) != len(event.input_keys):
            return None

        results: list[Any] = []
        for t in normalized_types:
            if t == InputType.D6:
                value = data.get('result')
                if not isinstance(value, (int, float)):
                    return None
                results.append(int(value))
            elif t == InputType.COIN:
                value = data.get('result_value', data.get('result'))
                if not isinstance(value, (int, float)):
                    return None
                results.append(int(value))
            elif t == InputType.BINARY:
                value = data.get('result_value', data.get('result'))
                if not isinstance(value, (int, float, bool)):
                    return None
                results.append(bool(value))
            else:
                value = data.get('value')
                if value is None:
                    return None
                results.append(value)

        return {'input_result': results}

    def _sync_environment_commands(self) -> list[str]:
        payload = environment_to_setup_payload(self.env)
        commands: list[str] = []

        for player_token, player_data in sorted(payload.get('players', {}).items()):
            frontend_player = self._player_id_to_frontend(player_token)
            attributes = player_data.get('attributes', {}) if isinstance(player_data, dict) else {}
            for attr_key, attr_value in attributes.items():
                if isinstance(attr_value, (int, float)):
                    commands.append(f'stat {frontend_player} {attr_key} {int(attr_value)}')

        cards = payload.get('cards', []) if isinstance(payload.get('cards', []), list) else []
        base_cards: list[dict[str, Any]] = []
        attached_tools: list[dict[str, Any]] = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            if card.get('cardType') == 'tool' and isinstance(card.get('attachedToCardId'), str):
                attached_tools.append(card)
            else:
                base_cards.append(card)

        for card in base_cards + attached_tools:
            card_id = card.get('id')
            holder_id = card.get('holderId')
            if not isinstance(card_id, str):
                continue

            avge_card_type = card.get('AVGECardType')
            if isinstance(avge_card_type, str) and avge_card_type.strip():
                commands.append(f'changetype {card_id} {self._card_type_command_token(avge_card_type)}')

            attached_to = card.get('attachedToCardId')
            if isinstance(attached_to, str) and card.get('cardType') == 'tool':
                commands.append(f'mv {card_id} {attached_to}')
            elif isinstance(holder_id, str):
                commands.append(f'mv {card_id} {holder_id}')

            if card.get('cardType') == 'character':
                hp = card.get('hp')
                max_hp = card.get('maxHp')
                if isinstance(hp, (int, float)) and isinstance(max_hp, (int, float)):
                    commands.append(f'hp {card_id} {int(hp)} {int(max_hp)}')
                statuses = card.get('statusEffect', {})
                if isinstance(statuses, dict):
                    for status_name in ('Arranger', 'Goon', 'Maid'):
                        count = statuses.get(status_name)
                        if isinstance(count, int):
                            commands.append(f'set_status {card_id} {status_name} {count}')

        energy_tokens = payload.get('energyTokens', []) if isinstance(payload.get('energyTokens', []), list) else []
        for token in energy_tokens:
            if not isinstance(token, dict):
                continue
            token_id = token.get('id')
            if not isinstance(token_id, str):
                continue
            attached_to = token.get('attachedToCardId')
            if isinstance(attached_to, str):
                commands.append(f'mv-energy {token_id} {attached_to}')
            else:
                holder_id = token.get('holderId')
                if isinstance(holder_id, str):
                    commands.append(f'mv-energy {token_id} {holder_id}')

        commands.append(f'turn {self._player_id_to_frontend(self.env.player_turn.unique_id)}')
        self._append_phase_command_if_changed(commands, self.env.game_phase)
        return commands

    def _queue_active_ability_interrupt(self, card: AVGECharacterCard, running_event: Any) -> None:
        if not isinstance(running_event, (Phase2, AtkPhase)):
            return
        try:
            if not bool(card.can_play_active(card)):
                return
        except Exception:
            return
        p : PacketType = [
            PlayCharacterCard(card, ActionTypes.ACTIVATE_ABILITY, ActionTypes.PLAYER_CHOICE, card)
        ]
        packet = AVGEPacket(p, AVGEEngineID(card, ActionTypes.PLAYER_CHOICE, type(card)))
        self.env._engine.external_interrupt(packet)

    def _notify_for_source_player(self, source: Any, message: str) -> list[str]:
        player = getattr(source, 'player', None)
        if player is None:
            player = getattr(source, 'player_for', None)
        if player is not None and hasattr(player, 'unique_id'):
            token = self._player_id_to_frontend(player.unique_id)
            return [f'notify {token} {self._command_token(message)}']
        return self._notify_both(message)

    def _notify_both(self, message: str) -> list[str]:
        msg = self._command_token(message)
        return [f'notify both {msg}']

    def _notify_current_turn_player(self, message: str) -> list[str]:
        turn_player = getattr(self.env, 'player_turn', None)
        turn_player_id = getattr(turn_player, 'unique_id', None)
        if turn_player_id is None:
            return self._notify_both(message)
        token = self._player_id_to_frontend(turn_player_id)
        return [f'notify {token} {self._command_token(message)}']

    def _card_type_command_token(self, card_type: Any) -> str:
        lookup = {
            'ALL': 'NONE',
            'NONE': 'NONE',
            'WW': 'WW',
            'PERC': 'PERC',
            'PIANO': 'PIANO',
            'STRING': 'STRING',
            'GUITAR': 'GUITAR',
            'CHOIR': 'CHOIR',
            'BRASS': 'BRASS',
        }
        key = str(getattr(card_type, 'value', card_type)).upper()
        return lookup.get(key, 'NONE')

    def _energy_target_command_arg(self, target: Any) -> str | None:
        if isinstance(target, AVGECharacterCard):
            return target.unique_id
        if hasattr(target, 'unique_id'):
            uid = str(target.unique_id)
            if uid in {'p1', 'p2'}:
                return f'{uid}-energy'
        if target is self.env or target is None:
            return 'energy-discard'
        return None

    def _transfer_target_command_arg(self, event: TransferCard) -> str | None:
        if event.pile_to == self.env.stadium_cardholder:
            return 'stadium'

        player = getattr(event.pile_to, 'player', None)
        pile_type = getattr(event.pile_to, 'pile_type', None)

        # Tool cardholders are card-attached slots and should be targeted by parent card id,
        # not by synthetic pile ids like p1-tool/p2-tool.
        if pile_type == Pile.TOOL:
            parent = getattr(event.pile_to, 'parent_card', None)
            if parent is not None:
                return parent.unique_id
            return None

        if player is None or pile_type is None:
            return None
        return f'{player.unique_id}-{pile_type}'

    def _card_zone_id(self, card: AVGECard | None) -> str | None:
        if card is None:
            return None

        holder = getattr(card, 'cardholder', None)
        if holder is None:
            return None

        if holder == self.env.stadium_cardholder:
            return 'stadium'

        player = getattr(holder, 'player', None)
        pile_type = getattr(holder, 'pile_type', None)
        if player is None or pile_type is None:
            return None
        return f'{player.unique_id}-{pile_type}'

    def _frontend_phase_token(self, phase: GamePhase) -> str:
        if phase == GamePhase.PHASE_2:
            return 'phase2'
        if phase == GamePhase.ATK_PHASE:
            return 'atk'
        return 'no-input'

    def _player_id_to_frontend(self, player_id: Any) -> str:
        value = str(getattr(player_id, 'value', player_id)).lower()
        return 'player-1' if value == 'p1' else 'player-2'

    def _card_id_from_payload(self, data: dict[str, Any]) -> str | None:
        return self._pick_str(data, 'card_id', 'id', 'cardId')

    def _pick_str(self, data: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return self._sanitize_identifier_token(value)
        return None

    def _get_card(self, card_id: str | None) -> AVGECard | None:
        if not card_id:
            return None

        direct = self.env.cards.get(card_id)
        if direct is not None:
            return direct

        target = card_id.lower()
        for key, card in self.env.cards.items():
            if key.lower() == target:
                return card
        return None

    def _get_character_card(self, card_id: str | None) -> AVGECharacterCard | None:
        card = self._get_card(card_id)
        if isinstance(card, AVGECharacterCard):
            return card
        return None

    def _get_energy_token(self, token_id: str | None):
        if not token_id:
            return None

        normalized_token_id = token_id.lower()

        for player in self.env.players.values():
            for token in player.energy:
                token_uid = str(getattr(token, 'unique_id', ''))
                if token_uid.lower() == normalized_token_id:
                    return token

            for holder in player.cardholders.values():
                for card in holder:
                    if isinstance(card, AVGECharacterCard):
                        for token in card.energy:
                            token_uid = str(getattr(token, 'unique_id', ''))
                            if token_uid.lower() == normalized_token_id:
                                return token

        for token in self.env.energy:
            token_uid = str(getattr(token, 'unique_id', ''))
            if token_uid.lower() == normalized_token_id:
                return token

        return None

    def _csv_from_display_entries(self, values: Any) -> str:
        if not isinstance(values, list):
            return ''
        result: list[str] = []
        for value in values:
            if value is None:
                result.append('none')
                continue
            uid = getattr(value, 'unique_id', None)
            if isinstance(uid, str):
                result.append(uid)
            else:
                result.append(str(value))
        return ','.join(result)

    def _command_token(self, raw: str) -> str:
        normalized = (raw or '').strip()
        if not normalized:
            return 'message'
        return normalized.replace(' ', '_')

    def _canonical_event_name(self, raw_event_type: Any) -> str:
        base = str(raw_event_type or '').strip().lower()
        normalized = base.replace('-', '_').replace(' ', '_')
        aliases = {
            'phase_2_attack_button_clicked': 'phase2_attack_button_clicked',
            'atk_phase_skip_button_clicked': 'atk_skip_button_clicked',
            'tool_attached': 'tool_attached',
            'attach_tool': 'tool_attached',
            'card_action': 'card_action',
            'card_played': 'card_played',
            'item_supporter_use': 'item_supporter_use',
            'card_moved': 'card_moved',
            'energy_moved': 'energy_moved',
            'input_result': 'input_result',
            'terminal_log': 'terminal_log',
            'setup_loaded': 'setup_loaded',
            'surrender_result': 'surrender_result',
            'surrender_timeout': 'surrender_timeout',
        }
        return aliases.get(normalized, normalized)

    def _normalize_action_name(self, raw_action: Any) -> str:
        return str(raw_action or '').strip().lower().replace(' ', '_').replace('-', '_')

    def _sanitize_identifier_token(self, raw: str) -> str:
        cleaned = raw.strip()
        cleaned = cleaned.replace('[', '').replace(']', '')
        cleaned = cleaned.replace('"', '').replace("'", '')
        cleaned = cleaned.rstrip(',')
        return cleaned.strip()

    def _normalize_zone_id(self, raw_zone: str) -> str:
        return self._sanitize_identifier_token(raw_zone).lower()

