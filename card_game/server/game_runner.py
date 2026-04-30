from __future__ import annotations

from random import randint
from threading import RLock
from typing import NoReturn
from card_game.server.server_types import JsonObject, CommandPayload
import os

from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ..avge_abstracts.AVGEEnvironment import GamePhase
from ..avge_abstracts.AVGECards import (
    AVGECard,
    AVGECharacterCard,
    AVGEStadiumCard,
)
from ..constants import Pile
from ..constants import (
    Data,
    Notify,
    OrderingQuery,
    Response,
    PlayerID,
)
from ..internal_events import (
    InputEvent,
    ReorderCardholder,
    TransferCard,
)
from .formatting.frontend_formatter import environment_to_setup_json as format_environment_to_setup_json
from .formatting.frontend_formatter import environment_to_setup_payload as format_environment_to_setup_payload
from .logging import log_ack_trace_bridge
from .logging import log_input_trace
from .bridge.setup_defaults import (
    apply_selected_cards_to_setup as bridge_apply_selected_cards_to_setup,
    blank_player_setup as bridge_blank_player_setup,
    resolve_catalog_card_class as bridge_resolve_catalog_card_class,
    selected_cards_from_env as bridge_selected_cards_from_env,
)
from .bridge.setup_payload import (
    build_default_setup_payload_from_environment as bridge_build_default_setup_payload_from_environment,
    build_environment_from_default_setups as bridge_build_environment_from_default_setups,
    environment_to_setup_json as bridge_environment_to_setup_json,
    environment_to_setup_payload as bridge_environment_to_setup_payload,
)
from .bridge.notifications import (
    normalize_notify_timeout as bridge_normalize_notify_timeout,
    notify_from_notify as bridge_notify_from_notify,
    notify_targets_from_players as bridge_notify_targets_from_players,
    notification_commands_from_payload as bridge_notification_commands_from_payload,
    reveal_commands_for_players as bridge_reveal_commands_for_players,
)
from .bridge.input_queries import (
    build_input_command as bridge_build_input_command,
    parse_frontend_input_result as bridge_parse_frontend_input_result,
)
from .bridge.pending_input_query import (
    clear_pending_input_query_state as bridge_clear_pending_input_query_state,
    is_waiting_for_pending_input_query_for_bridge as bridge_is_waiting_for_pending_input_query_for_bridge,
    queue_pending_input_query_resend as bridge_queue_pending_input_query_resend,
)
from .bridge.response_commands import (
    commands_from_response as bridge_commands_from_response,
)
from .bridge.frontend_events import (
    apply_frontend_event as bridge_apply_frontend_event,
    phase2_args_from_frontend_event as bridge_phase2_args_from_frontend_event,
)
from .bridge.engine_drain import (
    auto_advance_when_idle as bridge_auto_advance_when_idle,
    drain_engine as bridge_drain_engine,
)
from .bridge.environment_sync import (
    sync_environment_commands as bridge_sync_environment_commands,
)
from .bridge.active_ability import (
    queue_active_ability_interrupt as bridge_queue_active_ability_interrupt,
)
from .bridge.winner_resolution import (
    frontend_player_token as bridge_frontend_player_token,
    normalize_winner_label as bridge_normalize_winner_label,
    player_from_frontend_token as bridge_player_from_frontend_token,
    winner_command_from_environment as bridge_winner_command_from_environment,
    winner_command_from_surrender_payload as bridge_winner_command_from_surrender_payload,
    winner_label_for_token as bridge_winner_label_for_token,
)
from .bridge.outbound_pump import (
    pump_outbound_until_next_command as bridge_pump_outbound_until_next_command,
)
from .bridge.frontend_router import (
    handle_frontend_event_locked as bridge_handle_frontend_event_locked,
)
from .bridge.response_payloads import (
    animation_payload_from_response as bridge_animation_payload_from_response,
    fallback_payload_command as bridge_fallback_payload_command,
    response_payloads_for_commands as bridge_response_payloads_for_commands,
)
from .bridge.startup_cycle import (
    bootstrap_phase_cycle as bridge_bootstrap_phase_cycle,
    prime_engine_for_frontend_inputs as bridge_prime_engine_for_frontend_inputs,
)
from .bridge.response_introspection import (
    current_response_source as bridge_current_response_source,
    has_nonempty_payload as bridge_has_nonempty_payload,
    is_plain_data_payload as bridge_is_plain_data_payload,
    log_engine_response_entry as bridge_log_engine_response,
    response_data_keys as bridge_response_data_keys,
    response_source_summary as bridge_response_source_summary,
    should_emit_core_commands_before_reactors as bridge_should_emit_core_commands_before_reactors,
)
from .bridge.command_utils import (
    canonical_event_name as bridge_canonical_event_name,
    card_id_from_payload as bridge_card_id_from_payload,
    card_type_command_token as bridge_card_type_command_token,
    card_zone_id as bridge_card_zone_id,
    command_token as bridge_command_token,
    csv_from_display_entries as bridge_csv_from_display_entries,
    energy_target_command_arg as bridge_energy_target_command_arg,
    frontend_phase_token as bridge_frontend_phase_token,
    get_card as bridge_get_card,
    get_character_card as bridge_get_character_card,
    get_energy_token as bridge_get_energy_token,
    normalize_action_name as bridge_normalize_action_name,
    normalize_zone_id as bridge_normalize_zone_id,
    pick_str as bridge_pick_str,
    player_id_to_frontend as bridge_player_id_to_frontend,
    reorder_target_command_arg as bridge_reorder_target_command_arg,
    transfer_target_command_arg as bridge_transfer_target_command_arg,
)
from .bridge.init_setup import (
    build_player_setup_for_init as bridge_build_player_setup_for_init,
)
from .bridge.ack_flow import (
    accept_frontend_ack as bridge_accept_frontend_ack,
    append_phase_command_if_changed as bridge_append_phase_command_if_changed,
    emit_next_command_if_ready as bridge_emit_next_command_if_ready,
)
from .bridge.ordering_query_flow import (
    build_ordering_query_command_for_bridge as bridge_build_ordering_query_command_for_bridge,
    parse_ordering_query_result_for_bridge as bridge_parse_ordering_query_result_for_bridge,
)
from .bridge.frontend_enqueue import (
    enqueue_frontend_event_work as bridge_enqueue_frontend_event_work,
)
from .bridge.clone_setup import (
    clone_with_init_setup as bridge_clone_with_init_setup,
)
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
    return bridge_blank_player_setup()


def _resolve_catalog_card_class(card_id: str) -> type[AVGECard] | None:
    return bridge_resolve_catalog_card_class(card_id, symbol_lookup=globals())


def _selected_cards_from_env(env_name: str) -> list[type[AVGECard]]:
    return bridge_selected_cards_from_env(env_name, resolver=_resolve_catalog_card_class)


def _apply_selected_cards_to_setup(
    selected_cards: list[type[AVGECard]],
) -> dict[Pile, list[type[AVGECard]]]:
    return bridge_apply_selected_cards_to_setup(
        selected_cards,
        initial_hand_size=initial_hand_size,
    )


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
    return bridge_build_environment_from_default_setups(
        p1_setup=p1_setup,
        p2_setup=p2_setup,
        p1_username=p1_username,
        p2_username=p2_username,
        start_turn=start_turn,
        starting_stadium=starting_stadium,
        starting_stadium_player=starting_stadium_player,
        round_number=round_number,
    )


def build_default_setup_payload_from_environment(
    start_turn: PlayerID = PlayerID.P1,
    starting_stadium: type[AVGEStadiumCard] | None = None,
    starting_stadium_player: PlayerID | None = None,
    round_number: int = starting_round,
) -> JsonObject:
    """Build a frontend/router-compatible setup payload from the default environment."""
    return bridge_build_default_setup_payload_from_environment(
        build_environment=build_environment_from_default_setups,
        environment_to_setup_payload=environment_to_setup_payload,
        start_turn=start_turn,
        starting_stadium=starting_stadium,
        starting_stadium_player=starting_stadium_player,
        round_number=round_number,
    )

def environment_to_setup_payload(env: AVGEEnvironment) -> JsonObject:
    """Convert an AVGEEnvironment into frontend setup payload format."""
    return bridge_environment_to_setup_payload(
        env,
        format_environment_to_setup_payload=format_environment_to_setup_payload,
        p1_username=p1_username,
        p2_username=p2_username,
    )


def environment_to_setup_json(env: AVGEEnvironment, indent: int = 2) -> str:
    """Return a pretty JSON string for the converted setup payload."""
    return bridge_environment_to_setup_json(
        env,
        format_environment_to_setup_json=format_environment_to_setup_json,
        indent=indent,
    )


class BridgeEngineRuntimeError(RuntimeError):
    """Raised when bridge-driven engine execution fails."""


class FrontendGameBridge:
    """Translate frontend events to engine actions and engine responses back to frontend commands."""

    def __init__(self, env: AVGEEnvironment | None = None) -> None:
        self._lock = RLock()
        self.env = env if isinstance(env, AVGEEnvironment) else build_environment_from_default_setups()
        self._max_forward_steps = 5000
        self._pending_packet_commands: list[str] = []
        self._pending_packet_command_payloads: list[CommandPayload] = []
        self._outbound_command_queue: list[str] = []
        self._outbound_command_payload_queue: list[CommandPayload] = []
        self._awaiting_frontend_ack = False
        self._awaiting_frontend_ack_command: str | None = None
        self._last_emitted_phase_token: str | None = None
        self._pending_engine_input_args: JsonObject | None = None
        self._pending_frontend_events: list[tuple[str, JsonObject]] = []
        self._pending_input_query_event: InputEvent | None = None
        self._pending_input_query_command: str | None = None
        self._pending_ordering_listener_by_token: JsonObject | None = None
        self._last_emitted_ordering_query_signature: tuple[str, ...] | None = None
        self._force_environment_sync_pending = False
        self._bootstrap_phase_cycle()
        self._prime_engine_for_frontend_inputs()
        self._last_emitted_phase_token = self._frontend_phase_token(self.env.game_phase)

    def clone_with_init_setup(self, setup_by_slot: dict[str, JsonObject]) -> 'FrontendGameBridge':
        return bridge_clone_with_init_setup(
            self,
            setup_by_slot,
            environment_factory=AVGEEnvironment,
            bridge_factory=FrontendGameBridge,
        )

    def _build_player_setup_for_init(self, slot: str, setup: JsonObject) -> dict[Pile, list[type[AVGECard]]]:
        return bridge_build_player_setup_for_init(
            self,
            slot,
            setup,
            blank_player_setup_fn=_blank_player_setup,
            max_bench_size=max_bench_size,
        )

    def get_setup_payload(self) -> JsonObject:
        with self._lock:
            return environment_to_setup_payload(self.env)

    def _accept_frontend_ack(self, payload: JsonObject) -> bool:
        return bridge_accept_frontend_ack(self, payload)

    def _emit_next_command_if_ready(self) -> tuple[list[str], list[CommandPayload]]:
        return bridge_emit_next_command_if_ready(self)

    def _append_phase_command_if_changed(self, commands: list[str], phase: GamePhase) -> None:
        bridge_append_phase_command_if_changed(self, commands, phase)

    def _response_source_summary(self, source: object) -> str:
        return bridge_response_source_summary(source)

    def _current_response_source(self, response: Response) -> object:
        return bridge_current_response_source(self, response)

    def _response_data_keys(self, data: object) -> list[str]:
        return bridge_response_data_keys(data)

    def _should_emit_core_commands_before_reactors(self, response: Response, commands: list[str]) -> bool:
        return bridge_should_emit_core_commands_before_reactors(self, response, commands)

    def _is_plain_data_payload(self, payload: object) -> bool:
        return bridge_is_plain_data_payload(payload)

    def _has_nonempty_payload(self, payload: object) -> bool:
        return bridge_has_nonempty_payload(payload)

    def _notify_targets_from_players(self, players: list[PlayerID]) -> list[str]:
        return bridge_notify_targets_from_players(
            players,
            player_id_to_frontend=self._player_id_to_frontend,
        )

    def _animation_payload_from_response(self, response: Response) -> JsonObject | None:
        return bridge_animation_payload_from_response(
            response,
            notify_targets_from_players_fn=self._notify_targets_from_players,
        )

    def _response_payloads_for_commands(self, response: Response, commands: list[str]) -> list[CommandPayload]:
        return bridge_response_payloads_for_commands(
            response,
            commands,
            animation_payload_from_response_fn=self._animation_payload_from_response,
        )

    def _normalize_notify_timeout(self, timeout: int | None) -> int:
        return bridge_normalize_notify_timeout(timeout)

    def _notify_from_notify(self, notify_data: Notify) -> list[str]:
        return bridge_notify_from_notify(
            notify_data,
            notify_targets_from_players_fn=self._notify_targets_from_players,
            notify_both=self._notify_both,
            command_token=self._command_token,
            normalize_timeout=self._normalize_notify_timeout,
        )

    def _reveal_commands_for_players(
        self,
        players: list[PlayerID],
        card_ids: list[str],
        message: str | None = None,
        timeout: int | None = None,
    ) -> list[str]:
        return bridge_reveal_commands_for_players(
            players,
            card_ids,
            message,
            timeout,
            notify_targets_from_players_fn=self._notify_targets_from_players,
            command_token=self._command_token,
            normalize_timeout=self._normalize_notify_timeout,
        )

    def _notification_commands_from_payload(self, payload: object) -> list[str]:
        return bridge_notification_commands_from_payload(
            payload,
            notify_from_notify_fn=self._notify_from_notify,
            reveal_commands_for_players_fn=self._reveal_commands_for_players,
        )

    def _fallback_payload_command(self, response: Response, payload: object) -> list[str]:
        return bridge_fallback_payload_command(
            response,
            payload,
            reveal_commands_for_players_fn=self._reveal_commands_for_players,
            notify_from_notify_fn=self._notify_from_notify,
            has_nonempty_payload_fn=self._has_nonempty_payload,
            notify_both_fn=self._notify_both,
        )

    def _log_engine_response(self, response: Response, step: int, stage: str, input_args: JsonObject | None) -> None:
        bridge_log_engine_response(self, response, step, stage, input_args)

    def _enqueue_frontend_event_work(self, event_name: str, payload: JsonObject) -> None:
        bridge_enqueue_frontend_event_work(self, event_name, payload)

    def _clear_pending_input_query_state(self) -> None:
        (
            self._pending_input_query_event,
            self._pending_input_query_command,
        ) = bridge_clear_pending_input_query_state()

    def _is_waiting_for_pending_input_query(self) -> bool:
        return bridge_is_waiting_for_pending_input_query_for_bridge(self)

    def _queue_pending_input_query_resend(self) -> bool:
        return bridge_queue_pending_input_query_resend(self)

    def _pump_outbound_until_next_command(self) -> None:
        bridge_pump_outbound_until_next_command(self)

    def _current_setup_payload(self) -> JsonObject:
        return environment_to_setup_payload(self.env)

    def handle_frontend_event(
        self,
        event_type: str,
        response_data: JsonObject | None,
        context: JsonObject | None,
    ) -> JsonObject:
        with self._lock:
            return bridge_handle_frontend_event_locked(self, event_type, response_data, context)

    def _bootstrap_phase_cycle(self) -> None:
        bridge_bootstrap_phase_cycle(self)

    def _prime_engine_for_frontend_inputs(self) -> None:
        bridge_prime_engine_for_frontend_inputs(self)

    def _apply_frontend_event(
        self,
        event_name: str,
        data: JsonObject,
    ) -> tuple[list[str], JsonObject | None]:
        return bridge_apply_frontend_event(self, event_name, data)

    def _drain_engine(
        self,
        input_args: JsonObject | None,
        stop_after_command_batch: bool = False,
    ) -> tuple[list[str], list[CommandPayload]]:
        return bridge_drain_engine(self, input_args, stop_after_command_batch)

    def _auto_advance_when_idle(self) -> bool:
        return bridge_auto_advance_when_idle(self)

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
        return bridge_commands_from_response(self, response)

    def _phase2_args_from_frontend_event(self, event_name: str, data: JsonObject) -> JsonObject | None:
        return bridge_phase2_args_from_frontend_event(self, event_name, data)

    def _build_input_command(self, event: InputEvent, query_data: Data) -> str | None:
        return bridge_build_input_command(
            event,
            query_data,
            player_id_to_frontend=self._player_id_to_frontend,
            command_token=self._command_token,
            csv_from_display_entries=self._csv_from_display_entries,
            random_int=randint,
        )

    def _parse_frontend_input_result(self, event: InputEvent, data: JsonObject) -> JsonObject | None:
        return bridge_parse_frontend_input_result(
            event,
            data,
            get_card=self._get_card,
            random_int=randint,
            log_input_trace=log_input_trace,
        )

    def _clear_pending_ordering_query_state(self) -> None:
        self._pending_ordering_listener_by_token = None
        self._last_emitted_ordering_query_signature = None

    def _build_ordering_query_command(self, query_data: OrderingQuery) -> str | None:
        return bridge_build_ordering_query_command_for_bridge(self, query_data)

    def _parse_ordering_query_result(self, data: JsonObject) -> JsonObject | None:
        return bridge_parse_ordering_query_result_for_bridge(self, data)

    def _sync_environment_commands(self) -> list[str]:
        return bridge_sync_environment_commands(self)

    def _queue_active_ability_interrupt(self, card: AVGECharacterCard, running_event: object) -> list[str]:
        return bridge_queue_active_ability_interrupt(self, card, running_event, default_timeout=default_timeout)

    def _notify_for_source_player(self, source: object, message: str, timeout: int | None = -1) -> list[str]:
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

    def _winner_command_from_surrender_payload(self, data: JsonObject) -> str | None:
        return bridge_winner_command_from_surrender_payload(
            self,
            data,
            p1_username=p1_username,
            p2_username=p2_username,
        )

    def _winner_command_from_environment(self) -> str | None:
        return bridge_winner_command_from_environment(
            self,
            p1_username=p1_username,
            p2_username=p2_username,
        )

    def _frontend_player_token(self, raw: object) -> str | None:
        return bridge_frontend_player_token(raw)

    def _player_from_frontend_token(self, token: str):
        return bridge_player_from_frontend_token(self, token)

    def _winner_label_for_token(self, token: str) -> str:
        return bridge_winner_label_for_token(
            self,
            token,
            p1_username=p1_username,
            p2_username=p2_username,
        )

    def _normalize_winner_label(self, raw: str) -> str:
        return bridge_normalize_winner_label(raw)

    def _card_type_command_token(self, card_type: object) -> str:
        return bridge_card_type_command_token(card_type)

    def _energy_target_command_arg(self, target: object) -> str | None:
        return bridge_energy_target_command_arg(self, target)

    def _transfer_target_command_arg(self, event: TransferCard) -> str | None:
        return bridge_transfer_target_command_arg(self, event)

    def _reorder_target_command_arg(self, event: ReorderCardholder) -> str | None:
        return bridge_reorder_target_command_arg(self, event)

    def _card_zone_id(self, card: AVGECard | None) -> str | None:
        return bridge_card_zone_id(self, card)

    def _frontend_phase_token(self, phase: GamePhase) -> str:
        return bridge_frontend_phase_token(phase)

    def _player_id_to_frontend(self, player_id: object) -> str:
        return bridge_player_id_to_frontend(player_id)

    def _card_id_from_payload(self, data: JsonObject) -> str | None:
        return bridge_card_id_from_payload(data)

    def _pick_str(self, data: JsonObject, *keys: str) -> str | None:
        return bridge_pick_str(data, *keys)

    def _get_card(self, card_id: str | None) -> AVGECard | None:
        return bridge_get_card(self, card_id)

    def _get_character_card(self, card_id: str | None) -> AVGECharacterCard | None:
        return bridge_get_character_card(self, card_id)

    def _get_energy_token(self, token_id: str | None):
        return bridge_get_energy_token(self, token_id)

    def _csv_from_display_entries(self, values: object) -> str:
        return bridge_csv_from_display_entries(values)

    def _command_token(self, raw: str) -> str:
        return bridge_command_token(raw)

    def _canonical_event_name(self, raw_event_type: object) -> str:
        return bridge_canonical_event_name(raw_event_type)

    def _normalize_action_name(self, raw_action: object) -> str:
        return bridge_normalize_action_name(raw_action)

    def _normalize_zone_id(self, raw_zone: str) -> str:
        return bridge_normalize_zone_id(raw_zone)

