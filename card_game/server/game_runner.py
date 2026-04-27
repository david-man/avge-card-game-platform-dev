from __future__ import annotations

from copy import deepcopy
from random import randint, sample
from threading import RLock
from typing import Any, NoReturn
import json
import os

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
    Data,
    Notify,
    RevealCards,
    RevealStr,
    CardSelectionQuery,
    StrSelectionQuery,
    OrderingQuery,
    Phase2Data,
    AtkPhaseData,
    IntegerInputData,
    CoinflipData,
    D6Data,
    Response,
    ResponseType,
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
from .logging import log_input_trace
from card_game.catalog import *
from card_game.constants import *

p1_username = os.getenv("P1_USERNAME", "Ash")
starting_round = 0
p2_username = os.getenv("P2_USERNAME", "Misty")

_DEFAULT_P1_SELECTED_CARDS: list[type[AVGECard]] = [
    KeiWatanabe,
    RobertoGonzales,
    DavidMan,
    BenCherekIII,
    Lucas,
    Bucket,
    AVGETShirt,
    Richard,
    Victoria,
    MainHall,
    Johann,
    IceSkates,
    AVGEBirb,
    FionaLi,
    JennieWang,
    LukeXu,
    DanielYang,
]

_DEFAULT_P2_SELECTED_CARDS: list[type[AVGECard]] = [
    MatthewWang,
    DavidMan,
    AVGEBirb,
    SteinertPracticeRoom,
    JennieWang,
    ConcertTicket,
    FoldingStand,
    VideoCamera,
    JuliaCeccarelli,
    MaggieLi,
]


def _blank_player_setup() -> dict[Pile, list[type[AVGECard]]]:
    return {
        Pile.ACTIVE: [],
        Pile.BENCH: [],
        Pile.HAND: [],
        Pile.DISCARD: [],
        Pile.DECK: [],
        Pile.TOOL: [],
        Pile.STADIUM: [],
    }


def _resolve_catalog_card_class(card_id: str) -> type[AVGECard] | None:
    symbol = globals().get(card_id)
    if not isinstance(symbol, type):
        return None
    if not issubclass(symbol, AVGECard):
        return None
    return symbol


def _selected_cards_from_env(env_name: str) -> list[type[AVGECard]]:
    raw_payload = os.getenv(env_name, '')
    if not raw_payload:
        return []

    try:
        parsed = json.loads(raw_payload)
    except Exception:
        return []

    if not isinstance(parsed, list):
        return []

    resolved: list[type[AVGECard]] = []
    for raw_card_id in parsed:
        if not isinstance(raw_card_id, str) or not raw_card_id.strip():
            continue
        resolved_class = _resolve_catalog_card_class(raw_card_id.strip())
        if resolved_class is not None:
            resolved.append(resolved_class)
    return resolved


def _apply_selected_cards_to_setup(
    selected_cards: list[type[AVGECard]],
) -> dict[Pile, list[type[AVGECard]]]:

    resolved_setup = _blank_player_setup()
    remaining_cards = list(selected_cards)

    character_cards = [card for card in remaining_cards if issubclass(card, AVGECharacterCard)]
    if not character_cards:
        return resolved_setup

    active_card = sample(character_cards, 1)[0]
    remaining_cards.remove(active_card)
    resolved_setup[Pile.ACTIVE] = [active_card]

    hand_count = min(initial_hand_size, len(remaining_cards))
    initial_hand = sample(remaining_cards, hand_count) if hand_count > 0 else []
    for card in initial_hand:
        remaining_cards.remove(card)

    resolved_setup[Pile.HAND] = initial_hand
    resolved_setup[Pile.DECK] = remaining_cards
    return resolved_setup


_p1_selected_cards = _selected_cards_from_env('P1_DECK_CARDS_JSON')
if len(_p1_selected_cards) == 0:
    _p1_selected_cards = list(_DEFAULT_P1_SELECTED_CARDS)

_p2_selected_cards = _selected_cards_from_env('P2_DECK_CARDS_JSON')
if len(_p2_selected_cards) == 0:
    _p2_selected_cards = list(_DEFAULT_P2_SELECTED_CARDS)

p1_setup = _apply_selected_cards_to_setup(_p1_selected_cards)
p2_setup = _apply_selected_cards_to_setup(_p2_selected_cards)
# Backwards-compatible aliases for older references.


def build_environment_from_default_setups(
    start_turn: PlayerID = PlayerID.P1,
    starting_stadium: type[AVGEStadiumCard] | None = None,
    starting_stadium_player: PlayerID | None = None,
    round_number: int = starting_round,
) -> AVGEEnvironment:
    """Build an AVGEEnvironment from configured p1/p2 setups."""
    return AVGEEnvironment(
        deepcopy(p1_setup),
        deepcopy(p2_setup),
        start_turn,
        p1_username=p1_username,
        p2_username=p2_username,
        starting_stadium=starting_stadium,
        starting_stadium_player=starting_stadium_player,
        start_round=round_number,
    )


def build_default_setup_payload_from_environment(
    start_turn: PlayerID = PlayerID.P1,
    starting_stadium: type[AVGEStadiumCard] | None = None,
    starting_stadium_player: PlayerID | None = None,
    round_number: int = starting_round,
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
    payload = format_environment_to_setup_payload(env)
    players = payload.get('players')
    if isinstance(players, dict):
        p1_payload = players.get('p1')
        p2_payload = players.get('p2')
        if isinstance(p1_payload, dict):
            p1_payload['username'] = p1_username
        if isinstance(p2_payload, dict):
            p2_payload['username'] = p2_username
    return payload


def environment_to_setup_json(env: AVGEEnvironment, indent: int = 2) -> str:
    """Return a pretty JSON string for the converted setup payload."""
    return format_environment_to_setup_json(env, indent=indent)


class BridgeEngineRuntimeError(RuntimeError):
    """Raised when bridge-driven engine execution fails."""


class FrontendGameBridge:
    """Translate frontend events to engine actions and engine responses back to frontend commands."""

    def __init__(self, env: AVGEEnvironment | None = None) -> None:
        self._lock = RLock()
        self.env = env if isinstance(env, AVGEEnvironment) else build_environment_from_default_setups()
        self._max_forward_steps = 5000
        self._pending_packet_commands: list[str] = []
        self._outbound_command_queue: list[str] = []
        self._awaiting_frontend_ack = False
        self._awaiting_frontend_ack_command: str | None = None
        self._last_emitted_phase_token: str | None = None
        self._pending_engine_input_args: dict[str, Any] | None = None
        self._pending_frontend_events: list[tuple[str, dict[str, Any]]] = []
        self._pending_input_query_event: InputEvent | None = None
        self._pending_input_query_command: str | None = None
        self._pending_ordering_listener_by_token: dict[str, Any] | None = None
        self._last_emitted_ordering_query_signature: tuple[str, ...] | None = None
        self._force_environment_sync_pending = False
        self._bootstrap_phase_cycle()
        self._prime_engine_for_frontend_inputs()
        self._last_emitted_phase_token = self._frontend_phase_token(self.env.game_phase)

    def clone_with_init_setup(self, setup_by_slot: dict[str, dict[str, Any]]) -> 'FrontendGameBridge':
        with self._lock:
            p1_setup = self._build_player_setup_for_init('p1', setup_by_slot.get('p1', {}))
            p2_setup = self._build_player_setup_for_init('p2', setup_by_slot.get('p2', {}))
            next_env = AVGEEnvironment(
                deepcopy(p1_setup),
                deepcopy(p2_setup),
                self.env.player_turn.unique_id,
                p1_username=self.env.players['p1'].username,
                p2_username=self.env.players['p2'].username,
                start_round=self.env.round_id,
            )

        return FrontendGameBridge(env=next_env)

    def _build_player_setup_for_init(self, slot: str, setup: dict[str, Any]) -> dict[Pile, list[type[AVGECard]]]:
        if slot not in {'p1', 'p2'}:
            raise ValueError('init setup slot is invalid')

        player = self.env.players[slot]
        hand_holder = player.cardholders[Pile.HAND]
        bench_holder = player.cardholders[Pile.BENCH]
        active_holder = player.cardholders[Pile.ACTIVE]
        deck_holder = player.cardholders[Pile.DECK]
        discard_holder = player.cardholders[Pile.DISCARD]

        active_card_id_raw = setup.get('active_card_id')
        bench_card_ids_raw = setup.get('bench_card_ids')
        active_card_id = active_card_id_raw.strip() if isinstance(active_card_id_raw, str) else ''
        bench_card_ids = [
            card_id.strip()
            for card_id in bench_card_ids_raw
            if isinstance(card_id, str) and card_id.strip()
        ] if isinstance(bench_card_ids_raw, list) else []

        if not active_card_id:
            raise ValueError(f'{slot} init setup missing active card id')

        if len(bench_card_ids) > max_bench_size:
            raise ValueError(f'{slot} init setup exceeds bench size cap')

        selected_ids = [active_card_id, *bench_card_ids]
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError(f'{slot} init setup has duplicate selected card ids')

        candidate_by_id: dict[str, AVGECharacterCard] = {}
        for holder in (hand_holder, bench_holder, active_holder):
            for card in holder:
                if isinstance(card, AVGECharacterCard):
                    candidate_by_id[card.unique_id] = card

        if active_card_id not in candidate_by_id:
            raise ValueError(f'{slot} init setup active card is not selectable')

        for bench_id in bench_card_ids:
            if bench_id not in candidate_by_id:
                raise ValueError(f'{slot} init setup bench card is not selectable')

        selected_id_set = set(selected_ids)

        resolved_setup = _blank_player_setup()
        resolved_setup[Pile.ACTIVE] = [type(candidate_by_id[active_card_id])]
        resolved_setup[Pile.BENCH] = [type(candidate_by_id[bench_id]) for bench_id in bench_card_ids]

        hand_cards: list[type[AVGECard]] = []
        for card in hand_holder:
            if isinstance(card, AVGECharacterCard) and card.unique_id in selected_id_set:
                continue
            hand_cards.append(type(card))

        for holder in (bench_holder, active_holder):
            for card in holder:
                if not isinstance(card, AVGECharacterCard):
                    continue
                if card.unique_id in selected_id_set:
                    continue
                hand_cards.append(type(card))

        resolved_setup[Pile.HAND] = hand_cards
        resolved_setup[Pile.DECK] = [type(card) for card in deck_holder]
        resolved_setup[Pile.DISCARD] = [type(card) for card in discard_holder]
        return resolved_setup

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

    def _current_response_source(self, response: Response) -> Any:
        source = getattr(response, 'source', None)
        if source is not None:
            return source
        return getattr(self.env._engine, 'event_running', None)

    def _response_data_keys(self, data: Any) -> list[str]:
        if isinstance(data, Data):
            try:
                return [str(key) for key in vars(data).keys()]
            except Exception:
                return []
        return []

    def _should_emit_core_commands_before_reactors(self, response: Response, commands: list[str]) -> bool:
        if response.response_type != ResponseType.CORE:
            return False
        if len(commands) == 0:
            return False

        source = self._current_response_source(response)
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

    def _is_plain_data_payload(self, payload: Any) -> bool:
        return isinstance(payload, Data) and type(payload) is Data

    def _has_nonempty_payload(self, payload: Any) -> bool:
        if self._is_plain_data_payload(payload):
            return False
        return isinstance(payload, Data)

    def _notify_targets_from_players(self, players: list[PlayerID]) -> list[str]:
        targets: list[str] = []
        for player in players:
            token = self._player_id_to_frontend(player)
            if token not in targets:
                targets.append(token)
        return targets

    def _normalize_notify_timeout(self, timeout: int | None) -> int:
        if timeout is None:
            return -1
        try:
            parsed = int(timeout)
        except Exception:
            return -1
        return parsed if parsed >= -1 else -1

    def _notify_from_notify(self, notify_data: Notify) -> list[str]:
        timeout = self._normalize_notify_timeout(notify_data.timeout)
        targets = self._notify_targets_from_players(notify_data.players)
        if not targets or len(targets) >= 2:
            return self._notify_both(notify_data.message, timeout=timeout)
        return [
            f'notify {target} {self._command_token(notify_data.message)} {timeout}'
            for target in targets
        ]

    def _reveal_commands_for_players(
        self,
        players: list[PlayerID],
        card_ids: list[str],
        message: str | None = None,
        timeout: int | None = None,
    ) -> list[str]:
        if len(card_ids) == 0:
            return []
        cards_csv = ','.join(card_ids)
        message_token = self._command_token(message) if isinstance(message, str) and message.strip() else None
        timeout_token = self._normalize_notify_timeout(timeout)
        targets = self._notify_targets_from_players(players)
        target_token = 'both' if len(targets) >= 2 or len(targets) == 0 else targets[0]
        if isinstance(message_token, str):
            return [f'reveal {target_token} [{cards_csv}] {message_token} {timeout_token}']
        return [f'reveal {target_token} [{cards_csv}] {timeout_token}']

    def _notification_commands_from_payload(self, payload: Any) -> list[str]:
        if isinstance(payload, RevealCards):
            card_ids = [getattr(card, 'unique_id', str(card)) for card in payload.cards]
            return self._reveal_commands_for_players(payload.players, card_ids, payload.message, payload.timeout)
        if isinstance(payload, RevealStr):
            msg = f"{payload.message}: {', '.join(payload.items)}" if len(payload.items) > 0 else payload.message
            return self._notify_from_notify(Notify(msg, payload.players, payload.timeout))
        if isinstance(payload, Notify):
            return self._notify_from_notify(payload)
        return []

    def _fallback_payload_command(self, response: Response, payload: Any) -> list[str]:
        if response.response_type in {ResponseType.GAME_END, ResponseType.INTERRUPT}:
            return []
        if isinstance(payload, RevealCards):
            card_ids = [getattr(card, 'unique_id', str(card)) for card in payload.cards]
            return self._reveal_commands_for_players(payload.players, card_ids, payload.message, payload.timeout)
        if isinstance(payload, RevealStr):
            msg = f"{payload.message}: {', '.join(payload.items)}" if len(payload.items) > 0 else payload.message
            return self._notify_from_notify(Notify(msg, payload.players, payload.timeout))
        if isinstance(payload, Notify):
            return self._notify_from_notify(payload)
        if self._has_nonempty_payload(payload):
            payload_name = type(payload).__name__
            log_ack_trace_bridge(
                'uncovered_nonempty_payload',
                response_type=str(response.response_type),
                payload_type=payload_name,
            )
            return self._notify_both(f'UNHANDLED_{payload_name}')
        return []

    def _log_engine_response(self, response: Response, step: int, stage: str, input_args: dict[str, Any] | None) -> None:
        response_type = getattr(response.response_type, 'value', str(response.response_type))
        source = self._current_response_source(response)
        source_type = type(source).__name__ if source is not None else 'None'
        data_keys = self._response_data_keys(response.data)

        # Skip noisy accept-without-payload steps; keep all meaningful responses.
        if response.response_type == ResponseType.ACCEPT and self._is_plain_data_payload(response.data):
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

    def _clear_pending_input_query_state(self) -> None:
        self._pending_input_query_event = None
        self._pending_input_query_command = None

    def _is_waiting_for_pending_input_query(self) -> bool:
        pending_event = self._pending_input_query_event
        if not isinstance(pending_event, InputEvent):
            return False

        running_event = getattr(self.env._engine, 'event_running', None)
        if running_event is pending_event:
            return True

        self._clear_pending_input_query_state()
        return False

    def _queue_pending_input_query_resend(self) -> bool:
        if not self._is_waiting_for_pending_input_query():
            return False

        pending_command = self._pending_input_query_command
        if not isinstance(pending_command, str) or not pending_command.strip():
            self._clear_pending_input_query_state()
            return False

        normalized_pending_command = pending_command.strip()
        if (
            self._awaiting_frontend_ack
            and isinstance(self._awaiting_frontend_ack_command, str)
            and self._awaiting_frontend_ack_command.strip() == normalized_pending_command
        ):
            log_ack_trace_bridge(
                'pending_input_query_resend_skipped_in_flight',
                command=normalized_pending_command,
            )
            return False

        if any(
            isinstance(command, str) and command.strip() == normalized_pending_command
            for command in self._outbound_command_queue
        ):
            return False

        # Intentional resend path for reconnect/resync flows.
        self._outbound_command_queue.insert(0, normalized_pending_command)
        log_ack_trace_bridge(
            'pending_input_query_resent',
            command=normalized_pending_command,
        )
        return True

    def _pump_outbound_until_next_command(self) -> None:
        if self._outbound_command_queue:
            return

        # Process at most one queued frontend event per ACK cycle.
        if self._pending_frontend_events:
            queued_event_name, queued_payload = self._pending_frontend_events.pop(0)
            self._enqueue_frontend_event_work(queued_event_name, queued_payload)
            return

        pending_ordering_map = getattr(self, '_pending_ordering_listener_by_token', None)
        if isinstance(pending_ordering_map, dict) and pending_ordering_map and self._pending_engine_input_args is None:
            log_ack_trace_bridge(
                'waiting_for_ordering_result',
                pending_tokens=len(pending_ordering_map),
            )
            return

        if self._pending_engine_input_args is None and self._is_waiting_for_pending_input_query():
            running_event = self._pending_input_query_event
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

            if event_name in {'setup_loaded', 'resync_requested'}:
                self._queue_pending_input_query_resend()

                return {
                    'commands': self._emit_next_command_if_ready(),
                    'setup_payload': environment_to_setup_payload(self.env),
                    'force_environment_sync': self._consume_force_environment_sync_flag(),
                }

            if event_name == 'surrender_timeout':
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
        try:
            self.env.propose(
                AVGEPacket([
                    Phase2(self.env, ActionTypes.ENV, self.env)
                ], AVGEEngineID(self.env, ActionTypes.ENV, None))
            )
            self.env.force_flush()
        except Exception as exc:
            self._raise_engine_runtime_error('bootstrap', exc)

    def _prime_engine_for_frontend_inputs(self) -> None:
        """Advance startup packets so the bridge can accept immediate frontend phase actions."""
        for step in range(1, 129):
            try:
                response = self.env.forward()
            except Exception as exc:
                self._raise_engine_runtime_error('prime', exc)

            self._log_engine_response(response, step=step, stage='prime', input_args=None)
            if response.response_type in {ResponseType.REQUIRES_QUERY, ResponseType.GAME_END}:
                return
            if response.response_type == ResponseType.NO_MORE_EVENTS:
                try:
                    should_continue = self._auto_advance_when_idle()
                except Exception as exc:
                    self._raise_engine_runtime_error('prime', exc)

                if not should_continue:
                    return

    def _apply_frontend_event(
        self,
        event_name: str,
        data: dict[str, Any],
    ) -> tuple[list[str], dict[str, Any] | None]:
        commands: list[str] = []
        engine = self.env._engine
        running = engine.event_running

        if event_name == 'input_result':
            log_input_trace(
                'bridge_apply_input_result_start',
                running_type=type(running).__name__ if running is not None else 'None',
                payload_keys=sorted(data.keys()),
            )
            ordering_args = self._parse_ordering_query_result(data)
            if ordering_args is not None:
                log_input_trace(
                    'bridge_apply_input_result_ordering_query',
                    result_keys=sorted(ordering_args.keys()),
                )
                return commands, ordering_args

        # Backend state is authoritative for phase navigation.
        if event_name in {'phase2_attack_button_clicked', 'phase_2_attack_button_clicked'}:
            if self.env.game_phase == GamePhase.PHASE_2:
                return commands, {'next': 'atk'}
            return commands, None

        if event_name in {'atk_skip_button_clicked', 'atk_phase_skip_button_clicked'}:
            if self.env.game_phase == GamePhase.ATK_PHASE:
                return commands, {'type': ActionTypes.SKIP}
            return commands, None

        if event_name == 'surrender_result':
            winner_command = self._winner_command_from_surrender_payload(data)
            if winner_command is not None:
                commands.append(winner_command)
            return commands, None

        if isinstance(running, InputEvent) and event_name == 'input_result':
            input_args = self._parse_frontend_input_result(running, data)
            if input_args is not None:
                self._clear_pending_input_query_state()
                log_input_trace(
                    'bridge_apply_input_result_accepted',
                    input_keys=sorted(input_args.keys()),
                )
                return commands, input_args
            log_input_trace('bridge_apply_input_result_rejected')
            commands.extend(self._notify_both('Input result rejected by backend parser.'))
            return commands, None

        if event_name == 'input_result':
            log_input_trace(
                'bridge_apply_input_result_no_running_input_event',
                running_type=type(running).__name__ if running is not None else 'None',
            )
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
                    commands.extend(self._queue_active_ability_interrupt(card, running))
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
            try:
                response = self.env.forward(next_args)
            except Exception as exc:
                self._raise_engine_runtime_error('drain', exc)

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

            # In incremental ACK-gated mode, emit core state-mutation commands
            # immediately so frontend can apply the visual change before any
            # follow-up reactors/listeners are processed.
            if (
                stop_after_command_batch
                and self._should_emit_core_commands_before_reactors(response, response_commands)
            ):
                if self._pending_packet_commands:
                    commands_to_emit.extend(self._pending_packet_commands)
                    self._pending_packet_commands = []
                commands_to_emit.extend(response_commands)
                break

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
                        # Do not drop the query command when an input boundary
                        # follows a packet command in the same drain pass.
                        if response_commands:
                            commands_to_emit.extend(response_commands)
                        break

                # Query prompts should be sent immediately, but packet state should remain buffered.
                if response_commands:
                    commands_to_emit.extend(response_commands)
                    if stop_after_command_batch:
                        break

            if response.response_type == ResponseType.REQUIRES_QUERY:
                break

            if response.response_type == ResponseType.GAME_END:
                # Preserve already-buffered packet updates (for example a lethal
                # HP change) so frontend can animate them before winner overlay.
                if self._pending_packet_commands:
                    commands_to_emit.extend(self._pending_packet_commands)
                    self._pending_packet_commands = []

                winner_command = self._winner_command_from_environment()
                if winner_command is not None:
                    commands_to_emit.append(winner_command)
                break

            if response.response_type == ResponseType.NO_MORE_EVENTS:
                try:
                    should_continue = self._auto_advance_when_idle()
                except Exception as exc:
                    self._raise_engine_runtime_error('drain', exc)

                if not should_continue:
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
                    Phase2(self.env, ActionTypes.ENV, self.env)
                ], AVGEEngineID(self.env, ActionTypes.ENV, None))
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
            next_event = AtkPhase(self.env, ActionTypes.ENV, self.env) if attacks_left > 0 else TurnEnd(self.env, ActionTypes.ENV, self.env)
            self.env.propose(AVGEPacket([next_event], AVGEEngineID(self.env, ActionTypes.ENV, None)))
            self.env.force_flush()
            return True

        if self.env.game_phase == GamePhase.PHASE_2:
            self.env.propose(
                AVGEPacket([
                    Phase2(self.env, ActionTypes.ENV, self.env)
                ], AVGEEngineID(self.env, ActionTypes.ENV, None))
            )
            self.env.force_flush()
            return True

        return False

    def _consume_force_environment_sync_flag(self) -> bool:
        should_sync = self._force_environment_sync_pending
        self._force_environment_sync_pending = False
        return should_sync

    def _raise_engine_runtime_error(self, stage: str, exc: Exception) -> NoReturn:
        message = f'engine runtime error during {stage}: {exc}'
        print(f'[GAME_RUNNER_ERROR] {message}')
        log_ack_trace_bridge(
            'engine_runtime_error',
            stage=stage,
            error=str(exc),
        )
        raise BridgeEngineRuntimeError(message) from exc

    def _commands_from_response(self, response: Response) -> list[str]:
        commands: list[str] = []
        response_data = response.data
        source = self._current_response_source(response)

        if response.response_type != ResponseType.REQUIRES_QUERY:
            self._clear_pending_ordering_query_state()

        if response.response_type == ResponseType.ACCEPT:
            commands.extend(self._notification_commands_from_payload(response_data))
            return commands

        if response.response_type == ResponseType.SKIP:
            commands.extend(self._notification_commands_from_payload(response_data))
            commands.append('resync')
            self._force_environment_sync_pending = True
            return commands

        if response.response_type == ResponseType.FAST_FORWARD:
            commands.extend(self._notification_commands_from_payload(response_data))
            return commands

        if response.response_type == ResponseType.GAME_END:
            if len(commands) == 0:
                commands.extend(self._fallback_payload_command(response, response_data))
            return commands

        if response.response_type == ResponseType.REQUIRES_QUERY:
            if isinstance(response_data, OrderingQuery):
                ordering_command = self._build_ordering_query_command(response_data)
                if ordering_command is not None:
                    commands.append(ordering_command)
                return commands

            self._clear_pending_ordering_query_state()

            if isinstance(response_data, Phase2Data):
                self._append_phase_command_if_changed(commands, GamePhase.PHASE_2)
                return commands

            if isinstance(response_data, AtkPhaseData):
                self._append_phase_command_if_changed(commands, GamePhase.ATK_PHASE)
                return commands

            if isinstance(source, (PhasePickCard, Phase2, AtkPhase)) or isinstance(response_data, (Phase2Data, AtkPhaseData)):
                # Phase events may surface as REQUIRES_QUERY (for example Phase2
                # waiting for player action) without emitting a CORE response.
                # Keep frontend phase HUD/state in sync in this path too.
                self._append_phase_command_if_changed(commands, self.env.game_phase)
            if isinstance(source, InputEvent):
                query_data = getattr(source, 'query_data', Data())
                if not isinstance(query_data, Data):
                    log_ack_trace_bridge(
                        'uncovered_input_query_data',
                        payload_type=type(query_data).__name__,
                    )
                    commands.extend(self._notify_both('UNHANDLED_QUERY_DATA'))
                    return commands

                if self._pending_input_query_event is source:
                    pending_command = self._pending_input_query_command
                    if isinstance(pending_command, str) and pending_command.strip():
                        log_ack_trace_bridge('duplicate_input_query_blocked_by_latch')
                        return commands
                    self._clear_pending_input_query_state()

                input_command = self._build_input_command(source, query_data)
                if input_command:
                    normalized_input_command = input_command.strip()
                    commands.append(normalized_input_command)
                    self._pending_input_query_event = source
                    self._pending_input_query_command = normalized_input_command
                else:
                    payload_name = type(query_data).__name__
                    log_ack_trace_bridge(
                        'uncovered_input_query_data',
                        payload_type=payload_name,
                    )
                    if not self._is_plain_data_payload(query_data):
                        commands.extend(self._notify_both(f'UNHANDLED_{payload_name}'))
                return commands

            if isinstance(response_data, Notify):
                commands.extend(self._notify_from_notify(response_data))
            if len(commands) == 0:
                commands.extend(self._fallback_payload_command(response, response_data))
            return commands

        if response.response_type != ResponseType.CORE:
            if len(commands) == 0:
                commands.extend(self._fallback_payload_command(response, response_data))
            return commands

        payload_notification_commands = self._notification_commands_from_payload(response_data)

        def _return_core_commands() -> list[str]:
            commands.extend(payload_notification_commands)
            return commands

        if isinstance(source, AVGECardHPChange):
            commands.append(f'hp {source.target_card.unique_id} {int(source.target_card.hp)} {int(source.target_card.max_hp)}')
            return _return_core_commands()

        if isinstance(source, AVGECardMaxHPChange):
            commands.append(f'maxhp {source.target_card.unique_id} {int(source.target_card.max_hp)}')
            return _return_core_commands()

        if isinstance(source, AVGECardTypeChange):
            card_type = self._card_type_command_token(source.target_card.card_type)
            commands.append(f'changetype {source.target_card.unique_id} {card_type}')
            return _return_core_commands()

        if isinstance(source, AVGECardStatusChange):
            status_key = str(source.status_effect).split('.')[-1]
            status_name = {
                'ARR': 'Arranger',
                'GOON': 'Goon',
                'MAID': 'Maid',
            }.get(status_key, status_key.title())
            count = len(source.target.statuses_attached[source.status_effect])
            commands.append(f'set_status {source.target.unique_id} {status_name} {count}')
            return _return_core_commands()

        if isinstance(source, AVGEEnergyTransfer):
            energy_target = self._energy_target_command_arg(source.target)
            if energy_target:
                commands.append(f'mv-energy {source.token.unique_id} {energy_target}')
            return _return_core_commands()

        if isinstance(source, AVGEPlayerAttributeChange):
            player_token = self._player_id_to_frontend(source.target_player.unique_id)
            commands.append(f'stat {player_token} {source.attribute} {int(source.target_player.attributes[source.attribute])}')
            return _return_core_commands()

        if isinstance(source, TransferCard):
            move_target = self._transfer_target_command_arg(source)
            if move_target:
                same_holder_transfer = source.pile_from == source.pile_to
                pile_to_type = getattr(source.pile_to, 'pile_type', None)
                if same_holder_transfer and pile_to_type == Pile.DECK:
                    commands.append(f'shuffle-animation {self._normalize_zone_id(move_target)}')
                else:
                    commands.append(f'mv {source.card.unique_id} {move_target}')
            return _return_core_commands()

        if isinstance(source, ReorderCardholder):
            target_holder_id = self._reorder_target_command_arg(source)
            if target_holder_id:
                commands.append(f'shuffle-animation {target_holder_id}')
            else:
                commands.append('shuffle-animation')
            return _return_core_commands()

        if isinstance(source, PlayCharacterCard):
            if len(commands) == 0 and len(payload_notification_commands) == 0:
                commands.extend(self._fallback_payload_command(response, response_data))

            return _return_core_commands()

        if isinstance(source, PhasePickCard):
            self._append_phase_command_if_changed(commands, self.env.game_phase)
            return _return_core_commands()

        if isinstance(source, Phase2):
            self._append_phase_command_if_changed(commands, self.env.game_phase)
            return _return_core_commands()

        if isinstance(source, AtkPhase):
            self._append_phase_command_if_changed(commands, self.env.game_phase)
            return _return_core_commands()

        if isinstance(source, InputEvent):
            # Successful input application has no direct frontend mutation command.
            return _return_core_commands()

        if isinstance(source, TurnEnd):
            self._force_environment_sync_pending = True
            return _return_core_commands()

        if isinstance(source, EmptyEvent):
            return _return_core_commands()

        if len(commands) == 0 and len(payload_notification_commands) == 0:
            commands.extend(self._fallback_payload_command(response, response_data))

        return _return_core_commands()

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

    def _build_input_command(self, event: InputEvent, query_data: Data) -> str | None:
        player_token = self._player_id_to_frontend(event.player_for.unique_id)
        message_source = 'input_required'

        if isinstance(query_data, CardSelectionQuery):
            message_source = query_data.header_msg
            display_ids = self._csv_from_display_entries(list(query_data.display))
            highlight_ids = self._csv_from_display_entries(list(query_data.targets))
            return (
                f'input selection {player_token} {self._command_token(message_source)} '
                f'[{display_ids}], [{highlight_ids}], {len(event.input_keys)} '
                f'{str(query_data.allows_repeat).lower()} {str(query_data.allows_none).lower()}'
            )

        if isinstance(query_data, StrSelectionQuery):
            message_source = query_data.header_msg
            display_ids = self._csv_from_display_entries(list(query_data.display))
            highlight_ids = self._csv_from_display_entries(list(query_data.targets))
            return (
                f'input selection {player_token} {self._command_token(message_source)} '
                f'[{display_ids}], [{highlight_ids}], {len(event.input_keys)} '
                f'{str(query_data.allows_repeat).lower()} {str(query_data.allows_none).lower()}'
            )

        if isinstance(query_data, IntegerInputData):
            message_source = query_data.header_msg
            return f'input numerical-entry {player_token} {self._command_token(message_source)}'

        if isinstance(query_data, CoinflipData):
            message_source = query_data.header_msg
            roll_count = max(1, len(event.input_keys))
            values = [randint(0, 1) for _ in range(roll_count)]
            value_token = str(values[0]) if roll_count == 1 else f'[{",".join(str(value) for value in values)}]'
            return f'input coin {player_token} {self._command_token(message_source)} {value_token}'

        if isinstance(query_data, D6Data):
            message_source = query_data.header_msg
            roll_count = max(1, len(event.input_keys))
            values = [randint(1, 6) for _ in range(roll_count)]
            value_token = str(values[0]) if roll_count == 1 else f'[{",".join(str(value) for value in values)}]'
            return f'input d6 {player_token} {self._command_token(message_source)} {value_token}'

        if isinstance(query_data, OrderingQuery):
            return f'input numerical-entry {player_token} order_listeners'

        return None

    def _parse_frontend_input_result(self, event: InputEvent, data: dict[str, Any]) -> dict[str, Any] | None:
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

        def _reject(reason: str, **extra: Any) -> None:
            log_input_trace(
                'bridge_parse_input_result_rejected',
                reason=reason,
                query_type=query_type,
                payload_keys=payload_keys,
                expected_input_count=expected_input_count,
                **extra,
            )

        def _accept(parsed_values: list[Any]) -> dict[str, Any]:
            preview: list[Any] = []
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

        def _ordered_entries(*keys: str) -> list[Any] | None:
            for key in keys:
                raw_value = data.get(key)
                if isinstance(raw_value, list):
                    return list(raw_value)
                if isinstance(raw_value, tuple):
                    return list(raw_value)
                if isinstance(raw_value, str) and raw_value.strip():
                    text = raw_value.strip()
                    if text.startswith('[') and text.endswith(']'):
                        text = text[1:-1]
                    parts = [part.strip() for part in text.split(',')]
                    cleaned = [part for part in parts if part]
                    return cleaned if cleaned else [text]
            return None

        def _int_from_any(raw_value: Any, *, coin_mode: bool) -> int | None:
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
            ordered = _ordered_entries('ordered_selections', 'orderedSelections')
            if ordered is None:
                _reject('missing_ordered_selections')
                return None
            parsed: list[Any] = []
            for raw in ordered:
                if raw is None or (isinstance(raw, str) and raw.strip().lower() in {'none', 'null', '-1'}):
                    parsed.append(None)
                    continue
                if not isinstance(raw, str):
                    _reject('invalid_card_selection_entry_type', entry_type=type(raw).__name__)
                    return None
                normalized_raw = self._sanitize_identifier_token(raw)
                card = self._get_card(normalized_raw)
                parsed.append(card if card is not None else normalized_raw)
            if len(parsed) != len(event.input_keys):
                _reject('card_selection_length_mismatch', parsed_count=len(parsed))
                return None
            return _accept(parsed)

        if isinstance(query_data, StrSelectionQuery):
            ordered = _ordered_entries('ordered_selections', 'orderedSelections')
            if ordered is None:
                _reject('missing_ordered_selections')
                return None
            parsed: list[Any] = []
            for raw in ordered:
                if raw is None or (isinstance(raw, str) and raw.strip().lower() in {'none', 'null', '-1'}):
                    parsed.append(None)
                    continue
                if not isinstance(raw, str):
                    _reject('invalid_str_selection_entry_type', entry_type=type(raw).__name__)
                    return None
                parsed.append(raw)
            if len(parsed) != len(event.input_keys):
                _reject('str_selection_length_mismatch', parsed_count=len(parsed))
                return None
            return _accept(parsed)

        if isinstance(query_data, IntegerInputData):
            value = data.get('value', data.get('result'))
            if not isinstance(value, (int, float)):
                _reject('invalid_integer_value', received_type=type(value).__name__ if value is not None else 'None')
                return None
            return _accept([int(value)])

        if isinstance(query_data, CoinflipData):
            entries = _ordered_entries('result_values', 'resultValues', 'ordered_results', 'orderedResults')
            parsed_values: list[int] = []
            if isinstance(entries, list):
                for raw_value in entries:
                    parsed_value = _int_from_any(raw_value, coin_mode=True)
                    if parsed_value is None:
                        _reject('invalid_coinflip_entry', entry_type=type(raw_value).__name__)
                        return None
                    parsed_values.append(parsed_value)
            else:
                single_value = data.get('result_value', data.get('resultValue', data.get('result')))
                parsed_value = _int_from_any(single_value, coin_mode=True)
                if parsed_value is None:
                    _reject('invalid_coinflip_value', received_type=type(single_value).__name__ if single_value is not None else 'None')
                    return None
                parsed_values = [parsed_value]

            if len(parsed_values) == 1 and expected_input_count > 1:
                parsed_values.extend(randint(0, 1) for _ in range(expected_input_count - 1))

            if len(parsed_values) != expected_input_count:
                _reject('coinflip_length_mismatch', parsed_count=len(parsed_values))
                return None

            if any(value not in {0, 1} for value in parsed_values):
                _reject('invalid_coinflip_range', parsed_preview=parsed_values)
                return None

            return _accept(parsed_values)

        if isinstance(query_data, D6Data):
            entries = _ordered_entries('result_values', 'resultValues', 'ordered_results', 'orderedResults')
            parsed_values: list[int] = []
            if isinstance(entries, list):
                for raw_value in entries:
                    parsed_value = _int_from_any(raw_value, coin_mode=False)
                    if parsed_value is None:
                        _reject('invalid_d6_entry', entry_type=type(raw_value).__name__)
                        return None
                    parsed_values.append(parsed_value)
            else:
                single_value = data.get('result_value', data.get('resultValue', data.get('result')))
                parsed_value = _int_from_any(single_value, coin_mode=False)
                if parsed_value is None:
                    _reject('invalid_d6_value', received_type=type(single_value).__name__ if single_value is not None else 'None')
                    return None
                parsed_values = [parsed_value]

            if len(parsed_values) == 1 and expected_input_count > 1:
                parsed_values.extend(randint(1, 6) for _ in range(expected_input_count - 1))

            if len(parsed_values) != expected_input_count:
                _reject('d6_length_mismatch', parsed_count=len(parsed_values))
                return None

            if any(value < 1 or value > 6 for value in parsed_values):
                _reject('invalid_d6_range', parsed_preview=parsed_values)
                return None

            return _accept(parsed_values)

        _reject('unsupported_query_type')
        return None

    def _clear_pending_ordering_query_state(self) -> None:
        self._pending_ordering_listener_by_token = None
        self._last_emitted_ordering_query_signature = None

    def _build_ordering_query_command(self, query_data: OrderingQuery) -> str | None:
        unordered = list(getattr(query_data, 'unordered_listeners', []) or [])
        if len(unordered) == 0:
            self._clear_pending_ordering_query_state()
            return None

        listener_by_token: dict[str, Any] = {}
        ordered_tokens: list[str] = []
        for idx, listener in enumerate(unordered):
            package_fn = getattr(listener, 'package', None)
            package_name = package_fn() if callable(package_fn) else type(listener).__name__
            if not isinstance(package_name, str) or not package_name.strip():
                package_name = type(listener).__name__
            token = f'l{idx}_{self._command_token(package_name)}'
            listener_by_token[token] = listener
            ordered_tokens.append(token)

        signature = tuple(ordered_tokens)
        if (
            self._last_emitted_ordering_query_signature == signature
            and isinstance(self._pending_ordering_listener_by_token, dict)
            and len(self._pending_ordering_listener_by_token) == len(listener_by_token)
        ):
            return None

        self._pending_ordering_listener_by_token = listener_by_token
        self._last_emitted_ordering_query_signature = signature

        player_token = self._player_id_to_frontend(self.env.player_turn.unique_id)
        token_csv = ','.join(ordered_tokens)
        return (
            f'input selection {player_token} order_listeners '
            f'[{token_csv}], [{token_csv}], {len(ordered_tokens)} false false'
        )

    def _parse_ordering_query_result(self, data: dict[str, Any]) -> dict[str, Any] | None:
        pending_map = getattr(self, '_pending_ordering_listener_by_token', None)
        if not isinstance(pending_map, dict) or len(pending_map) == 0:
            return None

        ordered_tokens = None
        for key in ('ordered_selections', 'orderedSelections', 'ordered_listener_tokens', 'orderedListenerTokens'):
            raw_value = data.get(key)
            if isinstance(raw_value, list):
                ordered_tokens = list(raw_value)
                break
            if isinstance(raw_value, tuple):
                ordered_tokens = list(raw_value)
                break
            if isinstance(raw_value, str) and raw_value.strip():
                text = raw_value.strip()
                if text.startswith('[') and text.endswith(']'):
                    text = text[1:-1]
                ordered_tokens = [part.strip() for part in text.split(',') if part.strip()]
                if len(ordered_tokens) == 0:
                    ordered_tokens = [text]
                break
        if not isinstance(ordered_tokens, list):
            return None
        if len(ordered_tokens) != len(pending_map):
            return None

        seen_tokens: set[str] = set()
        resolved_listeners: list[Any] = []
        for raw_token in ordered_tokens:
            if not isinstance(raw_token, str):
                return None
            token = self._sanitize_identifier_token(raw_token)
            if token in seen_tokens:
                return None
            listener = pending_map.get(token)
            if listener is None:
                return None
            seen_tokens.add(token)
            resolved_listeners.append(listener)

        if len(resolved_listeners) != len(pending_map):
            return None

        self._clear_pending_ordering_query_state()
        return {'group_ordering': resolved_listeners}

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

    def _queue_active_ability_interrupt(self, card: AVGECharacterCard, running_event: Any) -> list[str]:
        if not isinstance(running_event, (Phase2, AtkPhase)):
            return []

        try:
            if not bool(card.can_play_active()):
                return self._notify_for_source_player(card, "Can't play this ability right now!", timeout=default_timeout)
        except Exception:
            return self._notify_for_source_player(card, "Can't play this ability right now!", timeout=default_timeout)

        p : PacketType = [
            PlayCharacterCard(card, ActionTypes.ACTIVATE_ABILITY, ActionTypes.PLAYER_CHOICE, card)
        ]
        packet = AVGEPacket(p, AVGEEngineID(card, ActionTypes.PLAYER_CHOICE, type(card)))
        self.env._engine.external_interrupt(packet)
        return []

    def _notify_for_source_player(self, source: Any, message: str, timeout: int | None = -1) -> list[str]:
        player = getattr(source, 'player', None)
        if player is None:
            player = getattr(source, 'player_for', None)
        normalized_timeout = self._normalize_notify_timeout(timeout)
        if player is not None and hasattr(player, 'unique_id'):
            token = self._player_id_to_frontend(player.unique_id)
            return [f'notify {token} {self._command_token(message)} {normalized_timeout}']
        return self._notify_both(message, timeout=normalized_timeout)

    def _notify_both(self, message: str, timeout: int | None = -1) -> list[str]:
        msg = self._command_token(message)
        normalized_timeout = self._normalize_notify_timeout(timeout)
        return [f'notify both {msg} {normalized_timeout}']

    def _notify_current_turn_player(self, message: str, timeout: int | None = -1) -> list[str]:
        turn_player = getattr(self.env, 'player_turn', None)
        turn_player_id = getattr(turn_player, 'unique_id', None)
        if turn_player_id is None:
            return self._notify_both(message, timeout=timeout)
        token = self._player_id_to_frontend(turn_player_id)
        normalized_timeout = self._normalize_notify_timeout(timeout)
        return [f'notify {token} {self._command_token(message)} {normalized_timeout}']

    def _winner_command_from_surrender_payload(self, data: dict[str, Any]) -> str | None:
        loser_token = self._frontend_player_token(data.get('loser_view'))
        if loser_token is not None:
            winner_token = 'player-2' if loser_token == 'player-1' else 'player-1'
        else:
            winner_token = self._frontend_player_token(data.get('winner_view'))

        if winner_token is not None:
            winner_player = self._player_from_frontend_token(winner_token)
            if winner_player is not None:
                self.env.winner = winner_player
            winner_label = self._winner_label_for_token(winner_token)
            return f'winner {winner_token} {winner_label}'

        fallback_winner = data.get('winner')
        if isinstance(fallback_winner, str) and fallback_winner.strip():
            return f'winner {self._normalize_winner_label(fallback_winner)}'

        return None

    def _winner_command_from_environment(self) -> str | None:
        winner = getattr(self.env, 'winner', None)
        winner_token = self._frontend_player_token(getattr(winner, 'unique_id', winner))
        if winner_token is None:
            return None
        winner_label = self._winner_label_for_token(winner_token)
        return f'winner {winner_token} {winner_label}'

    def _frontend_player_token(self, raw: Any) -> str | None:
        value = str(getattr(raw, 'value', raw)).strip().lower()
        if value in {'p1', 'player-1', 'player1'}:
            return 'player-1'
        if value in {'p2', 'player-2', 'player2'}:
            return 'player-2'
        return None

    def _player_from_frontend_token(self, token: str):
        target_id = 'p1' if token == 'player-1' else 'p2'
        for player in self.env.players.values():
            player_id = str(getattr(getattr(player, 'unique_id', None), 'value', getattr(player, 'unique_id', ''))).lower()
            if player_id == target_id:
                return player
        return None

    def _winner_label_for_token(self, token: str) -> str:
        if token == 'player-1':
            return self._normalize_winner_label(p1_username)
        if token == 'player-2':
            return self._normalize_winner_label(p2_username)
        player = self._player_from_frontend_token(token)
        username = getattr(player, 'username', None) if player is not None else None
        if isinstance(username, str) and username.strip():
            return self._normalize_winner_label(username)
        return 'PLAYER 1' if token == 'player-1' else 'PLAYER 2'

    def _normalize_winner_label(self, raw: str) -> str:
        return ' '.join(raw.strip().split())

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

    def _reorder_target_command_arg(self, event: ReorderCardholder) -> str | None:
        holder = getattr(event, 'cardholder', None)
        if holder is None:
            return None

        if holder == self.env.stadium_cardholder:
            return 'stadium'

        player = getattr(holder, 'player', None)
        pile_type = getattr(holder, 'pile_type', None)
        if player is None or pile_type is None:
            return None

        return self._normalize_zone_id(f'{player.unique_id}-{pile_type}')

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
            'resync_requested': 'resync_requested',
            'resync_request': 'resync_requested',
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

