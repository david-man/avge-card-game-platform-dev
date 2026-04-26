from __future__ import annotations

from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEEnvironment import *
from .avge_abstracts.AVGEPlayer import *
from .internal_events import *
import tkinter as tk
import threading
from typing import Any, Callable
from .catalog.characters.brass import *
from .catalog.characters.strings import *
from .catalog.characters.choir import *
from .catalog.characters.guitars import *
from .catalog.characters.percussion import *
from .catalog.characters.pianos import *
from .catalog.characters.woodwinds import *
from .catalog.items import *
from .catalog.stadiums import *
from .catalog.supporters import *
from .catalog.tools import *
STEP_LIMIT = 1000
MAIN_SCREEN_GEOMETRY = "1280x760+1280+80"
INSPECTOR_GEOMETRY = "520x300+0+0"
IO_GEOMETRY = "420x140+0+360"
_HIDDEN_RESPONSE_KEYS = {
    "num_inputs",
    TARGETS_FLAG,
    "allow_repeat",
    ALLOW_REPEAT,
    ALLOW_NONE,
    DISPLAY_FLAG,
}
start_round = 1
p1_setup_default: dict[Pile, list[type[AVGECard]]] = {
    Pile.ACTIVE: [KeiWatanabe],
    Pile.BENCH: [RobertoGonzales],
    Pile.HAND: [Lucas, Bucket, AVGETShirt, Richard, Victoria],
    Pile.DISCARD: [MainHall, Johann, IceSkates],
    Pile.DECK: [MainHall, AVGEBirb, IceSkates, FionaLi, DavidMan, JennieWang,LukeXu, Johann, DanielYang, ],
    Pile.STADIUM: [],
}

p2_setup_default: dict[Pile, list[type[AVGECard]]] = {
    Pile.ACTIVE: [MeyaGao],
    Pile.BENCH: [DavidMan],
    Pile.HAND: [AVGEBirb, SteinertPracticeRoom,  JennieWang, ConcertTicket, FoldingStand],
    Pile.DISCARD: [VideoCamera, JuliaCiacerelli, MaggieLi],
    Pile.DECK: [],
}

def _filtered_response_data(data: Data | None) -> Data:
    if(not isinstance(data, dict)):
        return {}
    return {k: v for k, v in data.items() if k not in _HIDDEN_RESPONSE_KEYS}


def _log_scanner_response(resp: Response) -> None:
    from .engine.event import Event
    from .engine.event_listener import AbstractEventListener

    source = resp.source
    if(source is None):
        return

    if(resp.response_type == ResponseType.CORE and isinstance(source, Event)):
        print(
            "CORE_RESPONSE "
            f"event={type(source).__name__} "
            f"data={_filtered_response_data(resp.data)}"
        )
        return

    if(isinstance(source, AbstractEventListener)):
        print(
            "LISTENER_RESPONSE "
            f"listener={type(source).__name__} "
            f"response={resp.response_type} "
            f"data={_filtered_response_data(resp.data)}"
        )


def _get_active_external_listener_names_by_player(env: AVGEEnvironment) -> dict[PlayerID | str, list[str]]:
    ignored = {
        "GoonStatusTransferModifier",
        "GoonStatusChangeReactor",
        "ArrangerStatusReactor",
    }
    active: dict[PlayerID | str, list[str]] = {
        PlayerID.P1: [],
        PlayerID.P2: [],
        "environment": []
    }
    for listener in env._engine._external_listeners:
        if(listener._invalidated):
            continue
        name = type(listener).__name__
        if(name in ignored):
            continue
        identifier = getattr(listener, "identifier", None)
        caller = getattr(identifier, "caller", None)
        caller_player = getattr(caller, "player", None)
        if(caller_player is None):
            active["environment"].append(name)
        if(isinstance(caller_player, AVGEPlayer) and caller_player.unique_id in [PlayerID.P1, PlayerID.P2]):
            active[caller_player.unique_id].append(name)
    return active


def _format_nonempty_env_cache(env: AVGEEnvironment) -> list[str]:
    lines: list[str] = []
    cache_by_card = env.cache.cache
    none_key = env.cache.empty_card.unique_id

    for card_key in sorted(cache_by_card.keys()):
        payload = cache_by_card.get(card_key, {})
        if(not isinstance(payload, dict) or len(payload) == 0):
            continue

        if(card_key == none_key):
            header = "None"
        else:
            card = env.cards.get(card_key)
            if(card is None):
                header = card_key
            else:
                header = f"{card.unique_id}<{type(card).__name__}>"

        lines.append(f"- {header}")
        for key in sorted(payload.keys()):
            lines.append(f"  {key}: {_truncate_repr(payload[key])}")

    if(len(lines) == 0):
        return ["(none)"]
    return lines


def _build_ui_text(env: AVGEEnvironment) -> str:
    grouped = _get_active_external_listener_names_by_player(env)
    p1_names = sorted(grouped[PlayerID.P1])
    p2_names = sorted(grouped[PlayerID.P2])
    env_names = sorted(grouped["environment"])
    p1_lines = ["- (none)"] if len(p1_names) == 0 else [f"- {name}" for name in p1_names]
    p2_lines = ["- (none)"] if len(p2_names) == 0 else [f"- {name}" for name in p2_names]
    env_lines = ["- (none)"] if len(env_names) == 0 else [f"- {name}" for name in env_names]
    env_cache_lines = _format_nonempty_env_cache(env)

    queue = env._engine.peek_n(len(env._engine._queue))
    event_running = str(env._engine.event_running)
    event_stack = list(env._engine.event_stack)
    queue_lines: list[str] = []
    for idx, packet in enumerate(queue):
        queue_lines.append(f"[{idx}] {packet} {packet.identifier.caller if isinstance(packet, AVGEPacket) else "??"}")
    if(len(queue_lines) == 0):
        queue_lines.append("(empty)")

    event_stack_lines: list[str] = []
    for idx, event in enumerate(event_stack):
        event_stack_lines.append(f"[{idx}] {event}")
    if(len(event_stack_lines) == 0):
        event_stack_lines.append("(empty)")

    return (
        str(env)
        + "\n\n"
        + "=" * 72
        + "\nSCANNER SUMMARY\n"
        + "=" * 72
        + "\nACTIVE EXTERNAL LISTENERS (P1):\n"
        + "\n".join(p1_lines)
        + "\n\nACTIVE EXTERNAL LISTENERS (P2):\n"
        + "\n".join(p2_lines)
        + "\n\nACTIVE EXTERNAL LISTENERS (ENVIRONMENT):\n"
        + "\n".join(env_lines)
        + "\n\nENV CACHE (NON-EMPTY):\n"
        + "\n".join(env_cache_lines)
        + "\n\nEVENT RUNNING:\n"
        + event_running
        + f"\n\nCURRENT QUEUE, len {len(queue)}:\n"
        + "\n".join(queue_lines)
        + f"\n\nEVENT STACK, len {len(event_stack)}:\n"
        + "\n".join(event_stack_lines)
    )

def build_demo_environment(
    p1_setup: dict[Pile, list[type[AVGECard]]] | None = None,
    p2_setup: dict[Pile, list[type[AVGECard]]] | None = None,
    start_turn: PlayerID = PlayerID.P1,
    starting_stadium: type[AVGEStadiumCard] | None = None,
    starting_stadium_player: PlayerID | None = None,
    open_phase_2: bool = True,
) -> AVGEEnvironment:
    # Build from explicit per-pile setup dictionaries.
    if(p1_setup is None):
        p1_setup = p1_setup_default
    if(p2_setup is None):
        p2_setup = p2_setup_default
    env = AVGEEnvironment(
        p1_setup,
        p2_setup,
        start_turn,
        starting_stadium=starting_stadium,
        starting_stadium_player=starting_stadium_player,
        start_round=start_round
    )

    env.player_turn = env.players[start_turn]
    if(open_phase_2):
        env.propose(
            AVGEPacket([
                Phase2(env.player_turn, ActionTypes.ENV, None)
            ], AVGEEngineID(None, ActionTypes.ENV, None))
        )
        env._engine._queue.flush_buffer()
    return env


# Function to update the scanner text panel
def update_label(label: Any, text: str):
    if(isinstance(label, tk.Text)):
        label.config(state="normal")
        label.delete("1.0", "end")
        label.insert("1.0", text)
        label.config(state="disabled")
    else:
        label.config(text=text)


def _safe_get_card(env: AVGEEnvironment, card_id: str) -> AVGECard | None:
    return env.cards.get(card_id)


def _coerce_input_value(raw_value: str, env: AVGEEnvironment) -> Any:
    val = raw_value.strip()
    lowered = val.lower()
    if(lowered in ["none", "null", "nil"]):
        return None
    if(lowered in ["true", "yes", "y"]):
        return True
    if(lowered in ["false", "no", "n"]):
        return False
    card = _safe_get_card(env, val)
    if(card is not None):
        return card
    try:
        return int(val)
    except ValueError:
        return val


def _split_values(raw: str) -> list[str]:
    cleaned = (raw or "").replace(",", " ")
    return [part for part in cleaned.split(" ") if part.strip() != ""]


def _parse_ordering(raw: str, unordered_groups: list[Any]) -> list[Any] | None:
    """
    Accepts either:
      - "order 2,0,1"
      - "2,0,1"
      - "2 0 1"
    Returns reordered listeners list or None if invalid.
    """
    if(raw is None):
        return None
    cleaned = raw.strip().lower()
    if(cleaned.startswith("order")):
        cleaned = raw.strip()[5:].strip()
    if(cleaned == ""):
        return None

    for sep in [",", " "]:
        if(sep in cleaned):
            parts = [p for p in cleaned.replace(",", " ").split(" ") if p != ""]
            break
    else:
        parts = [cleaned]

    try:
        indices = [int(p) for p in parts]
    except ValueError:
        return None

    if(len(indices) != len(unordered_groups)):
        return None
    if(sorted(indices) != list(range(len(unordered_groups)))):
        return None

    return [unordered_groups[i] for i in indices]


def _format_selection_item(item: Any) -> str:
    if(isinstance(item, AVGECard)):
        return item.unique_id
    if(isinstance(item, type)):
        return item.__name__
    return str(item)


def _find_display_index_for_target(target: Any, display: list[Any], used_indices: set[int]) -> int | None:
    for idx, item in enumerate(display):
        if(idx in used_indices):
            continue
        if(item is target):
            return idx
    for idx, item in enumerate(display):
        if(idx in used_indices):
            continue
        if(item == target):
            return idx
    return None


def _parse_display_selection(
    values: list[str],
    expected: int,
    display: list[Any],
    allow_none: bool,
    allow_repeats: bool,
) -> list[Any] | None:
    display= list(display)
    if(len(values) != expected):
        return None
    chosen: list[Any] = []
    non_none_chosen: list[Any] = []
    for token in values:
        try:
            idx = int(token)
        except ValueError:
            return None

        if(idx == -1):
            if(not allow_none):
                return None
            chosen.append(None)
            continue

        if(idx < 0 or idx >= len(display)):
            return None

        selected = display[idx]
        if(not allow_repeats):
            if any((x is selected) or (x == selected) for x in non_none_chosen):
                return None
        chosen.append(selected)
        non_none_chosen.append(selected)
    return chosen


def _parse_atk_action_token(token: str) -> ActionTypes | None:
    lowered = token.strip().lower().replace("_", "")
    if(lowered in ["atk1", "1"]):
        return ActionTypes.ATK_1
    if(lowered in ["atk2", "2"]):
        return ActionTypes.ATK_2
    if(lowered in ["skip", "pass"]):
        return ActionTypes.SKIP
    return None


def _build_input_prompt(resp: Response, last_error: str | None = None) -> str:
    qd = resp.data or {}
    query_type = qd.get("query_type", "generic")
    lines: list[str] = [f"query_type: {query_type}"]

    if(last_error is not None):
        lines.append(f"last error: {last_error}")

    # Special: For query_label 'david_man_top_bottom', display the card id from the 'card' attribute if present
    if query_type == "card_query":
        query_label = str(qd.get(LABEL_FLAG, ""))
        if query_label == "david_man_top_bottom":
            card = qd.get("card", None)
            if card is not None:
                # Try to get unique_id if it's a card object, else just str
                card_id = getattr(card, "unique_id", str(card))
                lines.append(f"card: {card_id}")

    if(query_type == "phase2"):
        p = qd.get("player_involved", None)
        if(isinstance(p, AVGEPlayer)):
            lines.append("player: " + str(p.unique_id))
        lines.append("format: atk | tool <tool_id> <attach_to_id> | supporter <id> | item <id> | stadium <id> | swap <bench_id> | energy <attach_to_id> | hand2bench <id>")
    elif(query_type == "atk"):
        p = qd.get("player_involved", None)
        if(isinstance(p, AVGEPlayer)):
            lines.append("player: " + str(p.unique_id))
        lines.append("format: atk1 | atk2 | skip")
    elif(query_type == "ordering"):
        unordered = qd.get("unordered_groups", [])
        lines.append("format: order by index (like 2, 0, 1)")
        lines.append(f"to order: {[type(o).__name__ for o in unordered]}")
    elif(query_type == "card_query"):
        query_for = qd.get("player_for")
        query_label = str(qd.get(LABEL_FLAG, ""))
        expected = int(qd.get("num_inputs", 0))
        input_type = qd.get("input_type")
        if(isinstance(query_for, AVGEPlayer)):
            lines.append(f"query_for: {query_for.unique_id}")
        lines.append(f"query_label: {query_label}")
        lines.append(f"num_inputs: {expected}")
        lines.append(f"input_type: {input_type}")
        normalized_input_types: list[Any]
        if(isinstance(input_type, list)):
            normalized_input_types = input_type
        else:
            normalized_input_types = [input_type] * expected

        is_selection = (
            input_type == InputType.SELECTION
            or (isinstance(input_type, list) and len(input_type) > 0 and all(i == InputType.SELECTION for i in input_type))
        )
        if(is_selection):
            allow_none = bool(qd.get(ALLOW_NONE, False))
            allow_repeats = bool(qd.get(ALLOW_REPEAT, False))
            targets = list(qd.get(TARGETS_FLAG, []))
            display = list(qd.get(DISPLAY_FLAG, []))
            lines.append(f"allow_none: {allow_none}")
            lines.append(f"allow_repeats: {allow_repeats}")
            lines.append("format: provide display indices (space/comma separated), use -1 for None")
            if(isinstance(display, list)):
                if(isinstance(targets, list)):
                    lines.append("targets:")
                    used_display_indices: set[int] = set()
                    for target in targets:
                        display_idx = _find_display_index_for_target(target, display, used_display_indices)
                        if(display_idx is None):
                            lines.append(f"  [?] {_format_selection_item(target)}")
                            continue
                        used_display_indices.add(display_idx)
                        lines.append(f"  [{display_idx}] {_format_selection_item(target)}")
                lines.append("display:")
                for idx, item in enumerate(display):
                    lines.append(f"  [{idx}] {_format_selection_item(item)}")
            elif(isinstance(targets, list)):
                lines.append("targets:")
                for idx, item in enumerate(targets):
                    lines.append(f"  [{idx}] {_format_selection_item(item)}")
        elif(query_label == "daniel_redirect"):
            max_dmg = qd.get("maxdmg")
            lines.append("format: one integer")
            if(max_dmg is not None):
                lines.append(f"maxdmg: {max_dmg}")
        elif(query_label == "kei_watanabe_drumkidworkshop"):
            display = qd.get(DISPLAY_FLAG, [])
            actions = qd.get("actions", [])
            lines.append("format: <display_index> <atk1|atk2>")
            if(isinstance(display, list)):
                lines.append("display:")
                for idx, item in enumerate(display):
                    lines.append(f"  [{idx}] {_format_selection_item(item)}")
            if(isinstance(actions, list)):
                lines.append("actions:")
                for action in actions:
                    lines.append(f"  - {action}")
        elif(query_label == "ryan_lee_atk1"):
            display = qd.get(DISPLAY_FLAG, [])
            max_amt = qd.get("maxamt")
            lines.append("format: <display_index> <integer>")
            if(max_amt is not None):
                lines.append(f"maxamt: {max_amt}")
            if(isinstance(display, list)):
                lines.append("display:")
                for idx, item in enumerate(display):
                    lines.append(f"  [{idx}] {_format_selection_item(item)}")
        else:
            lines.append(f"num_inputs: {expected}")
            if(len(normalized_input_types) > 0 and all(t == InputType.COIN for t in normalized_input_types)):
                lines.append("format: provide 0/1 for each input")
            elif(len(normalized_input_types) > 0 and all(t == InputType.BINARY for t in normalized_input_types)):
                lines.append("format: provide 0/1 for each input")
            elif(len(normalized_input_types) > 0 and all(t == InputType.D6 for t in normalized_input_types)):
                lines.append("format: provide values 1..6 for each input")
            else:
                lines.append("format: provide one value per input")
    else:
        filtered = _filtered_response_data(qd)
        if(len(filtered) > 0):
            lines.append(f"data: {filtered}")
        lines.append("format: key=value pairs")

    lines.append("global command: active <card_id>")
    lines.append("type quit/exit to close")
    return "\n".join(lines)


def parse_scanner_input(raw: str, response: Response, env: AVGEEnvironment) -> Data | None:
    """
    Parses scanner input into args for REQUIRES_QUERY responses.

    Query formats expected by current codebase:
      - phase2:
          atk
          tool <tool_card_id> <attach_to_char_card_id>
          supporter <supporter_card_id>
          item <item_card_id>
          stadium <stadium_card_id>
          swap <bench_card_id>
          energy <attach_to_char_card_id>
          hand2bench <char_card_id>
      - atk:
          atk1 | atk2
      - ext_modifier_order / ext_reactor_order:
          order 2,0,1
          (or just: 2,0,1)
      - card_query:
          card_1 card_2
          yes no
          1 6
      - fallback (no query_type):
          key=value key2=value2
    """
    raw = (raw or "").strip()
    if(raw == ""):
        return None

    query_data = response.data or {}
    query_type = query_data.get("query_type", None)
    tokens = raw.split()

    if(query_type == "phase2"):
        player_obj = query_data.get("player_involved")
        if(not isinstance(player_obj, AVGEPlayer)):
            return None
        player: AVGEPlayer = player_obj
        if(player is None or len(tokens) == 0):
            return None

        cmd = tokens[0].lower()
        if(cmd == "atk"):
            return {"next": "atk"}

        if(cmd == "tool" and len(tokens) >= 3):
            tool = _safe_get_card(env, tokens[1])
            attach_to = _safe_get_card(env, tokens[2])
            return {"next": "tool", "tool": tool, "attach_to": attach_to}

        if(cmd == "supporter" and len(tokens) >= 2):
            supporter_card = _safe_get_card(env, tokens[1])
            return {"next": "supporter", "supporter_card": supporter_card}

        if(cmd == "item" and len(tokens) >= 2):
            item_card = _safe_get_card(env, tokens[1])
            return {"next": "item", "item_card": item_card}

        if(cmd == "stadium" and len(tokens) >= 2):
            stadium_card = _safe_get_card(env, tokens[1])
            return {"next": "stadium", "stadium_card": stadium_card}

        if(cmd == "swap" and len(tokens) >= 2):
            bench_card = _safe_get_card(env, tokens[1])
            return {"next": "swap", "bench_card": bench_card}

        if(cmd == "energy" and len(tokens) >= 2):
            attach_to = _safe_get_card(env, tokens[1])
            return {"next": "energy", "attach_to": attach_to}

        if(cmd == "hand2bench" and len(tokens) >= 2):
            hand2bench = _safe_get_card(env, tokens[1])
            return {"next": "hand2bench", "hand2bench": hand2bench}

        return None

    if(query_type == "atk"):
        cmd = tokens[0].lower()
        if(cmd in ["atk1", "atk_1", "1"]):
            return {"type": ActionTypes.ATK_1}
        if(cmd in ["atk2", "atk_2", "2"]):
            return {"type": ActionTypes.ATK_2}
        if(cmd in ["skip", "pass"]):
            return {"type": ActionTypes.SKIP}
        return None

    if(query_type == "ko_replace"):
        if(len(tokens) >= 2 and tokens[0].lower() in ["replace", "swap", "ko_replace"]):
            swap_with = _safe_get_card(env, tokens[1])
            return {"swap_with": swap_with}
        return None

    if(query_type == "card_query"):
        expected = int(query_data.get("num_inputs", 0))
        if(expected <= 0):
            return None
        query_label = str(query_data.get(LABEL_FLAG, ""))

        if(query_label in ["cast_reserve_player_item_pick", "dress_rehearsal_roster_energy_remove"]):
            display = query_data.get(DISPLAY_FLAG, [])
            if(not isinstance(display, list)):
                return None
            values = _split_values(raw)
            allow_none = bool(query_data.get(ALLOW_NONE, False))
            allow_repeats = bool(query_data.get(ALLOW_REPEAT, False))
            chosen_selection = _parse_display_selection(values, expected, display, allow_none, allow_repeats)
            if(chosen_selection is None):
                return None
            return {"input_result": chosen_selection}

        if(query_label == "daniel_redirect"):
            values = _split_values(raw)
            if(len(values) != 1):
                return None
            try:
                amount = int(values[0])
            except ValueError:
                return None
            max_dmg_raw = query_data.get("maxdmg", None)
            if(isinstance(max_dmg_raw, int)):
                if(amount < 0 or amount > max_dmg_raw):
                    return None
            return {"input_result": [amount]}

        if(query_label == "kei_watanabe_drumkidworkshop"):
            values = _split_values(raw)
            if(len(values) != 2):
                return None
            display = query_data.get(DISPLAY_FLAG, [])
            if(not isinstance(display, list)):
                return None
            selected_list = _parse_display_selection([values[0]], 1, display, False, True)
            if(selected_list is None):
                return None
            action = _parse_atk_action_token(values[1])
            if(action is None):
                return None
            return {"input_result": [selected_list[0], action]}

        if(query_label == "ryan_lee_atk1"):
            values = _split_values(raw)
            if(len(values) != 2):
                return None
            display = query_data.get(DISPLAY_FLAG, [])
            if(not isinstance(display, list)):
                return None
            selected_list = _parse_display_selection([values[0]], 1, display, False, True)
            if(selected_list is None):
                return None
            try:
                amount = int(values[1])
            except ValueError:
                return None
            max_amt_raw = query_data.get("maxamt", None)
            if(isinstance(max_amt_raw, int)):
                if(amount < 0 or amount > max_amt_raw):
                    return None
            return {"input_result": [selected_list[0], amount]}

        input_type = query_data.get("input_type")
        normalized_input_types: list[Any]
        if(isinstance(input_type, list)):
            normalized_input_types = input_type
        else:
            normalized_input_types = [input_type] * expected

        if(len(normalized_input_types) != expected):
            return None

        is_selection_query = (
            input_type == InputType.SELECTION
            or (isinstance(input_type, list) and len(input_type) > 0 and all(i == InputType.SELECTION for i in input_type))
        )

        if(is_selection_query):
            display = query_data.get(DISPLAY_FLAG, [])
            allow_none = bool(query_data.get(ALLOW_NONE, False))
            allow_repeats = bool(query_data.get(ALLOW_REPEAT, False))

            values = _split_values(raw)
            if(len(values) != expected):
                return None

            chosen: list[Any] = []
            non_none_chosen: list[Any] = []
            for token in values:
                try:
                    idx = int(token)
                except ValueError:
                    return None

                if(idx == -1):
                    if(not allow_none):
                        return None
                    chosen.append(None)
                    continue

                if(not isinstance(display, list) or idx < 0 or idx >= len(display)):
                    return None

                selected = display[idx]
                if(not allow_repeats):
                    if any((x is selected) or (x == selected) for x in non_none_chosen):
                        return None
                chosen.append(selected)
                non_none_chosen.append(selected)

            return {"input_result": chosen}

        values = _split_values(raw)
        if(len(values) != expected):
            return None

        typed_results: list[Any] = []
        for idx, token in enumerate(values):
            current_type = normalized_input_types[idx]

            if(current_type == InputType.COIN):
                try:
                    num_val = int(token)
                except ValueError:
                    return None
                if(num_val not in [0, 1]):
                    return None
                typed_results.append(num_val)
                continue

            if(current_type == InputType.BINARY):
                try:
                    num_val = int(token)
                except ValueError:
                    return None
                if(num_val not in [0, 1]):
                    return None
                typed_results.append(num_val == 1)
                continue

            if(current_type == InputType.D6):
                try:
                    num_val = int(token)
                except ValueError:
                    return None
                if(num_val < 1 or num_val > 6):
                    return None
                typed_results.append(num_val)
                continue

            typed_results.append(_coerce_input_value(token, env))

        return {"input_result": typed_results}

    if(query_type in ["ext_modifier_order", "ext_reactor_order", "ordering"]):
        unordered_groups = query_data.get("unordered_groups", [])
        ordered = _parse_ordering(raw, unordered_groups)
        if(ordered is None):
            return None
        return {"group_ordering": ordered}

    # Fallback for REQUIRES_QUERY responses without query_type
    parsed: Data = {}
    for token in tokens:
        if("=" not in token):
            continue
        key, value = token.split("=", 1)
        parsed[key] = value
    return parsed if len(parsed) > 0 else None


def _print_scanner_help() -> None:
    print("Scanner input examples:")
    print("  phase2: atk | tool <tool_id> <attach_to_id> | supporter <id> | item <id> | stadium <id> | swap <bench_id> | energy <attach_to_id> | hand2bench <id>")
    print("  atk: atk1 | atk2")
    print("  card_query ko_replace: SELECTION-style input (provide display index)")
    print("  card_query: one value per requested input (cards by id, bools, ints)")
    print("  card_query SELECTION: provide display indices (space/comma separated)")
    print("    - use -1 for None when allow_none is True")
    print("    - display/targets are printed with [index] labels")
    print("  card_query COIN: provide 0/1 per input (returned as ints)")
    print("  card_query BINARY: provide 0/1 per input (returned as booleans)")
    print("  card_query D6: provide 1..6 per input")
    print("  card_query DETERMINISTIC:")
    print("    - daniel_redirect: <integer>")
    print("    - cast_reserve_player_item_pick: same as SELECTION indices")
    print("    - kei_watanabe_drumkidworkshop: <display_index> <atk1|atk2>")
    print("    - ryan_lee_atk1: <display_index> <integer>")
    print("    - dress_rehearsal_roster_energy_remove: same as SELECTION indices")
    print("  ext_*_order: order 2,0,1")
    print("  global: active <card_id> (queue ACTIVATE_ABILITY with priority 0)")
    print("  safe exit: type 'quit' or 'exit' in any scanner prompt, or close the window")


def _handle_global_scanner_command(raw: str, env: AVGEEnvironment) -> bool:
    tokens = _split_values(raw)
    if(len(tokens) != 2 or tokens[0].lower() != "active"):
        return False

    card = _safe_get_card(env, tokens[1])
    if(not isinstance(card, AVGECharacterCard)):
        print(f"active command requires a character card id. Got: {tokens[1]}")
        return True

    p: PacketType = [
        PlayCharacterCard(
            card,
            ActionTypes.ACTIVATE_ABILITY,
            ActionTypes.ENV,
            card,
        )
    ]
    packet = AVGEPacket(p, AVGEEngineID(None, ActionTypes.ENV, None))

    event_running = env._engine.event_running
    if(isinstance(event_running, (Phase2, AtkPhase))):
        env._engine.external_interrupt(packet)
        print(
            f"Queued active ability request for {card.unique_id} via external_interrupt "
            "(event_running is Phase2/AtkPhase)."
        )
    else:
        env.propose(packet, priority=0)
        print(
            f"Queued active ability request for {card.unique_id} with priority 0 "
            "(normal propose path)."
        )
    return True


def _truncate_repr(value: Any, max_len: int = 180) -> str:
    text = repr(value)
    if(len(text) <= max_len):
        return text
    return text[: max_len - 3] + "..."


def _wait_for_scanner_enter(root: tk.Tk, stop_event: threading.Event) -> None:
    wait_flag = threading.Event()
    dialog_state: dict[str, tk.Toplevel | None] = {"dialog": None}

    def show_pause_dialog() -> None:
        if(stop_event.is_set()):
            wait_flag.set()
            return
        try:
            dialog = tk.Toplevel(root)
        except tk.TclError:
            wait_flag.set()
            return

        dialog_state["dialog"] = dialog
        dialog.title("Finished")
        dialog.geometry(IO_GEOMETRY)

        prompt = tk.Label(
            dialog,
            text="FINISHED reached. Press Enter to continue.",
            justify="left",
            anchor="w",
        )
        prompt.pack(fill="x", padx=10, pady=(12, 8))

        entry = tk.Entry(dialog)
        entry.pack(fill="x", padx=10, pady=(0, 10))
        entry.focus_set()

        def continue_run(_event=None) -> None:
            wait_flag.set()
            try:
                dialog.destroy()
            except Exception:
                pass

        continue_btn = tk.Button(dialog, text="Continue", command=continue_run)
        continue_btn.pack(padx=10, pady=(0, 10), anchor="e")

        entry.bind("<Return>", continue_run)
        dialog.protocol("WM_DELETE_WINDOW", continue_run)

    root.after(0, show_pause_dialog)
    while(not wait_flag.wait(timeout=0.1)):
        if(stop_event.is_set()):
            maybe_dialog = dialog_state["dialog"]
            if(maybe_dialog is not None):
                try:
                    maybe_dialog.destroy()
                except Exception:
                    pass
            return


def _actuate_inspector_events(env: AVGEEnvironment, event_count : int) -> str:
    """Advance the engine immediately after inspector mutations are queued."""
    steps = 0
    while(steps < STEP_LIMIT):
        resp = env.forward()
        steps += 1
        if(resp.response_type == ResponseType.NO_MORE_EVENTS):
            return f"Actuated immediately in {steps} step(s)."
        if(resp.response_type == ResponseType.GAME_END):
            return f"Actuation reached GAME_END in {steps} step(s)."
        if(resp.response_type in [ResponseType.REQUIRES_QUERY]):
            return f"Actuation paused at {resp.response_type} after {steps} step(s)."
        if(resp.response_type == ResponseType.NEXT_EVENT):
            print("NEXT EVENT: ", env._engine.event_running)
    return f"Actuation stopped after 300 steps (safety limit)."


def _resolve_mv_cardholder(env: AVGEEnvironment, holder_ref: str, default_player: AVGEPlayer | None):
    """Resolve cardholder refs like deck, p1:deck, player2.hand, or stadium."""
    ref = holder_ref.strip().lower()
    if(ref == "stadium"):
        if(hasattr(env, "stadium_cardholder")):
            return env.stadium_cardholder, None
        return None, "Stadium cardholder is unavailable in this environment."

    scoped_player: AVGEPlayer | None = None
    pile_token = ref

    for delimiter in [":", "."]:
        if(delimiter in ref):
            scope, pile_part = ref.split(delimiter, 1)
            scope = scope.strip()
            pile_token = pile_part.strip()
            if(scope in ["p1", "player1", "1"]):
                scoped_player = env.players.get(PlayerID.P1)
            elif(scope in ["p2", "player2", "2"]):
                scoped_player = env.players.get(PlayerID.P2)
            else:
                return None, f"Unknown player scope '{scope}' in holder '{holder_ref}'."
            break

    try:
        pile = Pile(pile_token)
    except Exception:
        return None, f"Unknown holder '{holder_ref}'. Expected a pile like deck/hand/active/bench/discard/tool/stadium."

    candidate_players: list[AVGEPlayer] = []
    if(scoped_player is not None):
        candidate_players = [scoped_player]
    elif(default_player is not None):
        candidate_players = [default_player]
    else:
        candidate_players = list(env.players.values())

    matches = [
        p.cardholders[pile]
        for p in candidate_players
        if hasattr(p, "cardholders") and pile in p.cardholders
    ]

    if(len(matches) == 1):
        return matches[0], None
    if(len(matches) > 1 and scoped_player is None and default_player is None):
        return None, (
            f"Holder '{holder_ref}' is ambiguous across players. "
            "Use p1:<pile> or p2:<pile> (for example p1:hand)."
        )
    return None, f"Holder '{holder_ref}' is not available for the selected player."


def _inspect_card_with_dir(env: AVGEEnvironment, raw_command: str) -> str:

    command = (raw_command or "").strip()
    if(command == ""):
        return "No command provided. Use 'help' for available commands."

    tokens = command.split()
    first = tokens[0].lower()

    if(first == "mv"):
        # Usage: mv <card_id> <to_holder>
        if(len(tokens) != 3):
            return "Usage: mv <card_id> <to_holder>"

        card = env.cards.get(tokens[1])
        if(card is None):
            return f"Card not found: {tokens[1]}"

        to_key = tokens[2]

        default_player = getattr(getattr(card, "cardholder", None), "player", None)
        if(default_player is None and hasattr(card, "player")):
            default_player = card.player

        from_holder = getattr(card, "cardholder", None)
        if(from_holder is None):
            return f"Card {card.unique_id} is not currently in a cardholder."

        to_holder, to_err = _resolve_mv_cardholder(env, to_key, default_player)
        if(to_holder is None):
            assert to_err is not None
            return f"To cardholder not found: {to_err}"

        if(card not in from_holder):
            return f"Card {card.unique_id} could not be found in its current source holder."

        from_pile = getattr(from_holder, "pile_type", None)
        from_player = getattr(from_holder, "player", None)
        from_player_id = getattr(from_player, "unique_id", None)
        if(from_player_id is not None and from_pile is not None):
            from_label = f"{from_player_id}:{from_pile}"
        elif(from_pile is not None):
            from_label = str(from_pile)
        else:
            from_label = "unknown"

        # Build and queue the transfer event
        events: PacketType = []
        events.append(
            TransferCard(
                card,
                from_holder,
                to_holder,
                ActionTypes.ENV,
                None
            )
        )
        env._engine.external_interrupt(AVGEPacket(events, AVGEEngineID(None, ActionTypes.ENV, None)))
        actuation = _actuate_inspector_events(env, 1)
        return (
            f"Queued transfer of {card.unique_id} from {from_label} to {to_key}.\n"
            + actuation
        )

    if(first in ["help", "?"]):
        return (
            "Card Inspector commands:\n"
            "  <card_id>\n"
            "    - inspect this card by id (non-dunder dir attributes)\n"
            "  dir <card_id>\n"
            "    - same as <card_id>\n"
            "  inspect <card_id>\n"
            "    - same as <card_id>\n"
            "  all <card_id>\n"
            "    - include __dunder__ names in the dir() output\n"
            "  clear / cls\n"
            "    - clear the inspector output window\n"
            "  refresh / redraw\n"
            "    - force immediate scanner screen update\n"
            "  set_energy <card_id> <amount>\n"
            "    - queue ENV energy transfers to set card energy toward amount\n"
            "  sethp <card_id> <level>\n"
            "    - queue ENV HP set-state event to set card HP to level\n"
            "  mv <card_id> <to_holder>\n"
            "    - move card from its current holder to to_holder; supports p1:<pile>/p2:<pile> scoping\n"
            "  help"
        )

    if(first == "set_energy"):
        if(len(tokens) != 3):
            return "Usage: set_energy <card_id> <amount>"

        card = env.cards.get(tokens[1])
        if(not isinstance(card, AVGECharacterCard)):
            return f"set_energy requires a character card id. Got: {tokens[1]}"

        try:
            target_amount = int(tokens[2])
        except ValueError:
            return "Amount must be an integer."

        if(target_amount < 0):
            return "Amount must be >= 0."

        current_amount = len(card.energy)
        delta = target_amount - current_amount
        if(delta == 0):
            return f"No change needed: {card.unique_id} already has {current_amount} energy."

        events: PacketType = []
        if(delta > 0):
            movable = min(delta, len(card.player.energy))
            tokens_to_move = list(card.player.energy)[:movable]
            for token in tokens_to_move:
                events.append(AVGEEnergyTransfer(token, card.player, card, ActionTypes.ENV, None))
            if(len(events) == 0):
                return (
                    f"Queued nothing: player has no energy to move. "
                    f"{card.unique_id} remains at {current_amount}."
                )
            env._engine.external_interrupt(AVGEPacket(events, AVGEEngineID(None, ActionTypes.ENV, None)))
            actuation = _actuate_inspector_events(env, len(tokens_to_move))
            return (
                f"Queued {tokens_to_move} transfer(s) from player to {card.unique_id}. "
                f"Target={target_amount}, current={current_amount}.\n"
                + actuation
            )

        movable = min(-delta, len(card.energy))
        tokens_to_move = list(card.energy)[:movable]
        for token in tokens_to_move:
            events.append(AVGEEnergyTransfer(token, card, card.player, ActionTypes.ENV, None))
        if(len(events) == 0):
            return f"Queued nothing: {card.unique_id} has no energy to move."
        env._engine.external_interrupt(AVGEPacket(events, AVGEEngineID(None, ActionTypes.ENV, None)))
        actuation = _actuate_inspector_events(env, len(tokens_to_move))
        return (
            f"Queued {tokens_to_move} transfer(s) from {card.unique_id} to player. "
            f"Target={target_amount}, current={current_amount}.\n"
            + actuation
        )

    if(first == "sethp"):
        if(len(tokens) != 3):
            return "Usage: sethp <card_id> <level>"

        card = env.cards.get(tokens[1])
        if(not isinstance(card, AVGECharacterCard)):
            return f"sethp requires a character card id. Got: {tokens[1]}"

        try:
            hp_level = int(tokens[2])
        except ValueError:
            return "Level must be an integer."

        if(hp_level < 0):
            return "Level must be >= 0."
        p : PacketType = [
            AVGECardHPChange(
                card,
                hp_level,
                AVGEAttributeModifier.SET_STATE,
                CardType.ALL,
                ActionTypes.ENV,
                None,
            )
        ]
        packet = AVGEPacket(p, AVGEEngineID(None, ActionTypes.ENV, None))
        env._engine.external_interrupt(packet)
        actuation = _actuate_inspector_events(env, 1)
        return f"Queued HP set for {card.unique_id} to {hp_level}.\n{actuation}"

    include_dunder = False
    card_id: str | None = None

    if(first == "all"):
        include_dunder = True
        if(len(tokens) >= 2):
            card_id = tokens[1]
    elif(first in ["dir", "inspect", "card", "show"]):
        if(len(tokens) >= 2):
            card_id = tokens[1]
    elif(len(tokens) == 1):
        card_id = tokens[0]

    if(card_id is None):
        return "Could not parse command. Use 'help' for usage."

    card = env.cards.get(card_id)
    if(card is None):
        return f"Card not found: {card_id}"

    names = sorted(dir(card))
    if(not include_dunder):
        names = [name for name in names if not (name.startswith("__") and name.endswith("__"))]

    lines: list[str] = []
    lines.append(f"card_id: {card.unique_id}")
    lines.append(f"class: {type(card).__name__}")
    lines.append(f"attributes found via dir(): {len(names)}")
    lines.append("-" * 72)

    for name in names:
        try:
            value = getattr(card, name)
        except Exception as exc:
            lines.append(f"{name} = <error reading attribute: {type(exc).__name__}: {exc}>")
            continue

        if(callable(value)):
            lines.append(f"{name} = <callable>")
        else:
            lines.append(f"{name} = {_truncate_repr(str(value))}")

    return "\n".join(lines)

def run_scanner_ui(env_builder: Callable[[], AVGEEnvironment]) -> None:
    root = tk.Tk()
    root.title("AVGE Scanner")
    root.geometry(MAIN_SCREEN_GEOMETRY)
    stop_event = threading.Event()

    # Force visibility on macOS/desktop managers that may start the window behind other apps.
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    root.after(300, lambda: root.attributes("-topmost", False))
    root.focus_force()

    def request_shutdown():
        if(stop_event.is_set()):
            return
        print("[scanner] shutdown requested.")
        stop_event.set()
        try:
            root.quit()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", request_shutdown)
    root.bind("<Escape>", lambda _event: request_shutdown())
    root.bind("<Command-q>", lambda _event: request_shutdown())

    display_frame = tk.Frame(root)
    display_frame.pack(fill="both", expand=True, padx=12, pady=12)

    yscroll = tk.Scrollbar(display_frame, orient="vertical")
    yscroll.pack(side="right", fill="y")

    xscroll = tk.Scrollbar(display_frame, orient="horizontal")
    xscroll.pack(side="bottom", fill="x")

    label = tk.Text(
        display_frame,
        wrap="none",
        font=("Menlo", 13),
        yscrollcommand=yscroll.set,
        xscrollcommand=xscroll.set,
    )
    label.pack(side="left", fill="both", expand=True)
    yscroll.config(command=label.yview)
    xscroll.config(command=label.xview)
    label.insert("1.0", "Loading scanner environment...")
    label.config(state="disabled")
    root.update_idletasks()

    print("Scanner UI launched. If window is not visible, check Mission Control/Spaces for 'AVGE Scanner'.")
    env_state: dict[str, AVGEEnvironment | None] = {"env": None}
    scanner_settings: dict[str, bool] = {"pause_on_finished": False}

    inspector = tk.Toplevel(root)
    inspector.title("AVGE Card Inspector")
    inspector.geometry(INSPECTOR_GEOMETRY)

    inspector_header = tk.Label(
        inspector,
        text="Enter a command (help, <card_id>, dir <card_id>, inspect <card_id>, all <card_id>, clear, refresh, set_energy, sethp, finished_pause):",
        justify="left",
        anchor="w",
    )
    inspector_header.pack(fill="x", padx=10, pady=(10, 6))

    inspector_output = tk.Text(inspector, wrap="word", height=10)
    inspector_output.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    inspector_entry_frame = tk.Frame(inspector)
    inspector_entry_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

    inspector_entry = tk.Entry(inspector_entry_frame)
    inspector_entry.pack(side="left", fill="x", expand=True)

    def run_inspector_command(_event=None):
        env = env_state.get("env")
        raw_command = inspector_entry.get().strip()
        if(raw_command == ""):
            return

        if(raw_command.lower() in ["clear", "cls"]):
            inspector_output.delete("1.0", "end")
            inspector_entry.delete(0, "end")
            return

        if(raw_command.lower() in ["refresh", "redraw"]):
            if(isinstance(env, AVGEEnvironment)):
                update_label(label, _build_ui_text(env))
                inspector_output.insert("end", ">>> refresh\nForced scanner screen refresh.\n\n")
            else:
                inspector_output.insert("end", ">>> refresh\nEnvironment not ready yet.\n\n")
            inspector_output.see("end")
            inspector_entry.delete(0, "end")
            return

        lowered = raw_command.lower()
        if(lowered.startswith("finished_pause")):
            parts = lowered.split()
            if(len(parts) == 1):
                current = "on" if scanner_settings["pause_on_finished"] else "off"
                inspector_output.insert("end", f"FINISHED pause is currently: {current}\n\n")
                inspector_output.see("end")
                inspector_entry.delete(0, "end")
                return
            if(len(parts) == 2 and parts[1] in ["on", "off"]):
                scanner_settings["pause_on_finished"] = (parts[1] == "on")
                inspector_output.insert("end", f"FINISHED pause set to: {parts[1]}\n\n")
                inspector_output.see("end")
                inspector_entry.delete(0, "end")
                return
            inspector_output.insert("end", "Usage: finished_pause <on|off>\n\n")
            inspector_output.see("end")
            inspector_entry.delete(0, "end")
            return

        inspector_output.insert("end", f">>> {raw_command}\n")
        if(not isinstance(env, AVGEEnvironment)):
            inspector_output.insert("end", "Environment not ready yet.\n\n")
            inspector_output.see("end")
            return

        report = _inspect_card_with_dir(env, raw_command)
        inspector_output.insert("end", report + "\n\n")
        inspector_output.see("end")
        inspector_entry.delete(0, "end")
        update_label(label, _build_ui_text(env))

    inspector_run_button = tk.Button(inspector_entry_frame, text="Run", command=run_inspector_command)
    inspector_run_button.pack(side="left", padx=(8, 0))
    inspector_entry.bind("<Return>", run_inspector_command)
    inspector_output.insert(
        "end",
        "Card Inspector commands:\n"
        "  <card_id>                  inspect this card by id\n"
        "  dir <card_id>              same as <card_id>\n"
        "  inspect <card_id>          same as <card_id>\n"
        "  all <card_id>              include __dunder__ names\n"
        "  clear / cls                clear this output\n"
        "  refresh / redraw           force scanner screen refresh\n"
        "  set_energy <id> <amount>   queue ENV energy transfers (priority 10)\n"
        "  sethp <id> <level>         queue ENV HP set-state event (priority 10)\n"
        "  finished_pause <on|off>    toggle Enter pause after FINISHED (default off)\n"
        "  finished_pause             show current toggle setting\n"
        "  help\n\n",
    )

    def close_all_windows():
        request_shutdown()

    inspector.protocol("WM_DELETE_WINDOW", close_all_windows)

    def run_env():
        import tkinter.messagebox as mb

        def show_message_popup_if_present(resp: Response) -> None:
            if(not isinstance(resp.data, dict)):
                return
            message = resp.data.get(MESSAGE_KEY)
            if(message is None):
                message = cast(list[AVGECard], resp.data.get(REVEAL_KEY))
                if(message is None):
                    return
                new_line = ""
                for card in message:
                    new_line += "|" + str(card.unique_id) + "|"
                message = new_line

            wait_flag = threading.Event()

            def show_popup():
                mb.showinfo("Message", str(message))
                wait_flag.set()

            root.after(0, show_popup)
            while(not wait_flag.wait(timeout=0.1)):
                if(stop_event.is_set()):
                    return

        print("[scanner] building environment...")
        env = env_builder()
        if(stop_event.is_set()):
            return
        print("[scanner] environment ready.")
        env_state["env"] = env
        root.after(0, update_label, label, _build_ui_text(env))
        _print_scanner_help()

        while(not stop_event.is_set()):
            resp = env.forward()
            show_message_popup_if_present(resp)
            _log_scanner_response(resp)
            while(resp.response_type == ResponseType.REQUIRES_QUERY and not stop_event.is_set()):
                parse_error: str | None = None

                raw_container: dict[str, str | None] = {"value": None}
                wait_flag = threading.Event()
                query_dialog_state: dict[str, tk.Toplevel | None] = {"dialog": None}

                def ask_input():
                    prompt = _build_input_prompt(resp, parse_error)

                    if(query_dialog_state["dialog"] is not None):
                        try:
                            query_dialog_state["dialog"].destroy()
                        except Exception:
                            pass

                    dialog = tk.Toplevel(root)
                    query_dialog_state["dialog"] = dialog
                    dialog.title("Scan Query Input")
                    dialog.geometry("480x220+0+360")
                    dialog.minsize(480, 220)

                    prompt_box = tk.Text(dialog, height=7, wrap="word")
                    prompt_box.pack(fill="both", expand=True, padx=10, pady=(10, 6))
                    prompt_box.insert("1.0", prompt)
                    prompt_box.config(state="disabled")

                    entry_frame = tk.Frame(dialog)
                    entry_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

                    entry = tk.Entry(entry_frame)
                    entry.pack(side="left", fill="x", expand=True)
                    entry.focus_set()

                    def submit_input(_event=None):
                        value = entry.get().strip()
                        raw_container["value"] = value
                        wait_flag.set()
                        try:
                            dialog.destroy()
                        except Exception:
                            pass

                    def cancel_input():
                        raw_container["value"] = None
                        wait_flag.set()
                        try:
                            dialog.destroy()
                        except Exception:
                            pass

                    submit_btn = tk.Button(entry_frame, text="Submit", command=submit_input)
                    submit_btn.pack(side="left", padx=(8, 0))

                    cancel_btn = tk.Button(entry_frame, text="Cancel", command=cancel_input)
                    cancel_btn.pack(side="left", padx=(8, 0))

                    entry.bind("<Return>", submit_input)
                    dialog.protocol("WM_DELETE_WINDOW", cancel_input)

                root.after(0, ask_input)
                while(not wait_flag.wait(timeout=0.1)):
                    if(stop_event.is_set()):
                        return

                raw_value = raw_container["value"]
                if(raw_value is None):
                    print("Input canceled.")
                    continue

                if(raw_value.lower() in ["quit", "exit"]):
                    root.after(0, request_shutdown)
                    return

                if(_handle_global_scanner_command(raw_value, env)):
                    resp = env.forward()
                    show_message_popup_if_present(resp)
                    _log_scanner_response(resp)
                    continue

                parsed = parse_scanner_input(raw_value, resp, env)
                if(parsed is None):
                    parse_error = "Could not parse input for this query"
                    wait_flag.clear()
                    root.after(0, ask_input)
                    while(not wait_flag.wait(timeout=0.1)):
                        if(stop_event.is_set()):
                            return
                    raw_value = raw_container["value"]
                    if(raw_value is None):
                        continue
                    if(raw_value.lower() in ["quit", "exit"]):
                        root.after(0, request_shutdown)
                        return
                    if(_handle_global_scanner_command(raw_value, env)):
                        resp = env.forward()
                        show_message_popup_if_present(resp)
                        _log_scanner_response(resp)
                        continue
                    parsed = parse_scanner_input(raw_value, resp, env)
                    if(parsed is None):
                        continue

                print("Received:", raw_value)
                resp = env.forward(parsed)
                show_message_popup_if_present(resp)
                _log_scanner_response(resp)
            if(resp.response_type == ResponseType.NEXT_EVENT):
                print("--------------------------------------------------")
                print(f"NEW EVENT: {str(resp.source)}")
                if(scanner_settings["pause_on_finished"]):
                    root.after(0, update_label, label, _build_ui_text(env))
                    _wait_for_scanner_enter(root, stop_event)
            elif(resp.response_type == ResponseType.NEXT_PACKET):
                packet = env._engine.peek_n(1)[0]
                assert isinstance(packet, AVGEPacket)
                print("--------------------------------------------------")
                print(f"NEW PACKET OF LEN {len(packet)} FROM {packet.identifier.header_class.__name__ if packet.identifier.header_class is not None else "ENVIRONMENT"}")
                print("--------------------------------------------------")
            elif(resp.response_type == ResponseType.GAME_END):
                print("--------------------------------------------------")
                print("GAME END, WINNER: ", env.winner.unique_id if env.winner is not None else "????")
                break
            elif(resp.response_type == ResponseType.SKIP):
                print(f"SKIP: {_filtered_response_data(resp.data)}")
                print("--------------------------------------------------")
            elif(resp.response_type == ResponseType.FINISHED):
                print("EVENT FINISHED")
                print("--------------------------------------------------")
            elif(resp.response_type == ResponseType.FINISHED_PACKET):
                print("EVENT & PACKET FINISHED.")
                print("--------------------------------------------------")
            elif(resp.response_type == ResponseType.NO_MORE_EVENTS):
                print("\n\n\n")
                if(env.game_phase == GamePhase.ATK_PHASE):
                    if(env.player_turn.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] > 0):
                        env.propose(
                            AVGEPacket([
                                AtkPhase(env.player_turn, ActionTypes.ENV, None)
                            ], AVGEEngineID(None, ActionTypes.ENV, None))
                        )
                    else:
                        env.propose(
                            AVGEPacket([
                                TurnEnd(env, ActionTypes.ENV, None)
                            ], AVGEEngineID(None, ActionTypes.ENV, None))
                        )
                    env.force_flush()
                elif(env.game_phase == GamePhase.PHASE_2):
                    env.propose(
                        AVGEPacket([
                            Phase2(env.player_turn, ActionTypes.ENV, None)
                        ], AVGEEngineID(None, ActionTypes.ENV, None))
                    )
                    env.force_flush()
                else:
                    break

            root.after(0, update_label, label, _build_ui_text(env))

    threading.Thread(target=run_env, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    run_scanner_ui(build_demo_environment)

    
    
    