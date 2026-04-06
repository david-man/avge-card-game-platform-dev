from __future__ import annotations

from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEEnvironment import *
from .avge_abstracts.AVGEPlayer import *
from .internal_events import *
import tkinter as tk
import threading
from typing import Any, Callable
from .catalog.characters.brass.BarronLee import BarronLee
from .catalog.characters.pianos.HenryWang import HenryWang
from .catalog.items.ConcertTicket import ConcertTicket
from .catalog.stadiums.MainHall import MainHall
from .catalog.tools.KikisHeadband import KikisHeadband


class ScannerDummyCharacter(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.BRASS, 1, 0, 1)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card) -> Response:
        from .internal_events import AVGECardHPChange

        target = card.player.opponent.get_active_card()
        if(not isinstance(target, AVGECharacterCard)):
            return card.generate_response()

        card.propose(
            AVGEPacket([
                AVGECardHPChange(
                    target,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    ActionTypes.ATK_1,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, ScannerDummyCharacter))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card) -> Response:
        from .internal_events import AVGECardStatusChange

        target = card.player.opponent.get_active_card()
        if(not isinstance(target, AVGECharacterCard)):
            return card.generate_response()

        card.propose(
            AVGEPacket([
                AVGECardStatusChange(
                    StatusEffect.GOON,
                    StatusChangeType.ADD,
                    target,
                    ActionTypes.ATK_2,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_2, ScannerDummyCharacter))
        )
        return card.generate_response()
p1_deck = [
    BarronLee,
    HenryWang,
    ScannerDummyCharacter,
    ScannerDummyCharacter,
    ConcertTicket,
    KikisHeadband,
    MainHall,
    ScannerDummyCharacter,
]
p2_deck = [
    HenryWang,
    BarronLee,
    ScannerDummyCharacter,
    ScannerDummyCharacter,
    ConcertTicket,
    KikisHeadband,
    MainHall,
    ScannerDummyCharacter,
]

def build_demo_environment() -> AVGEEnvironment:
    # Keep a deterministic deck order: first cards become active/bench, then non-chars can be drawn/played.
    
    env = AVGEEnvironment(p1_deck, p2_deck, PlayerID.P1)
    for player in env.players.values():
        deck = player.cardholders[Pile.DECK]
        active = player.cardholders[Pile.ACTIVE]
        bench = player.cardholders[Pile.BENCH]
        hand = player.cardholders[Pile.HAND]

        env.transfer_card(deck.peek(), deck, active)
        for _ in range(3):
            env.transfer_card(deck.peek(), deck, bench)

        # Draw remaining cards into hand so scanner commands can exercise non-character play paths.
        while(len(deck) > 0):
            env.transfer_card(deck.peek(), deck, hand)
    # Bootstrap passives with the real event path used by the engine.
    for player in env.players.values():
        for card in player.cardholders[Pile.ACTIVE] + player.cardholders[Pile.BENCH]:
            if(isinstance(card, AVGECharacterCard) and card.has_passive):
                env.propose(
                    AVGEPacket([
                        PlayCharacterCard(card, ActionTypes.PASSIVE, ActionTypes.ENV, card)
                    ], AVGEEngineID(card, ActionTypes.PASSIVE, card.__class__))
                )

    env.player_turn = env.players[PlayerID.P1]
    env.propose(
        AVGEPacket([
            Phase2(env.player_turn, ActionTypes.ENV, None)
        ], AVGEEngineID(None, ActionTypes.ENV, None))
    )
    
    return env


# Function to update the label text
def update_label(label: tk.Label, text: str):
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
      - ko_replace:
          replace <bench_card_id>
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
        values = _split_values(raw)
        if(len(values) != expected):
            return None
        return {"input_result": [_coerce_input_value(v, env) for v in values]}

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
    print("  ko_replace: replace <bench_id>")
    print("  card_query: one value per requested input (cards by id, bools, ints)")
    print("  ext_*_order: order 2,0,1")
    print("  safe exit: type 'quit' or 'exit' in any scanner prompt, or close the window")


def _print_board_state(env: AVGEEnvironment, context: str) -> None:
    print(f"\n===== BOARD STATE ({context}) =====")
    print(str(env))
    print("===== END BOARD STATE =====\n")


def run_scanner_ui(env_builder: Callable[[], AVGEEnvironment]) -> None:
    root = tk.Tk()
    root.title("AVGE Scanner")
    root.geometry("1280x760+80+80")
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

    label = tk.Label(root, text="Loading scanner environment...", font=("Arial", 11), justify="left", anchor="w")
    label.pack(padx=12, pady=12)
    root.update_idletasks()

    print("Scanner UI launched. If window is not visible, check Mission Control/Spaces for 'AVGE Scanner'.")
    env_state: dict[str, AVGEEnvironment | None] = {"env": None}

    def run_env():
        import tkinter.simpledialog as sd

        print("[scanner] building environment...")
        env = env_builder()
        if(stop_event.is_set()):
            return
        print("[scanner] environment ready.")
        env_state["env"] = env
        root.after(0, update_label, label, str(env))
        _print_scanner_help()
        _print_board_state(env, "startup")

        while(not stop_event.is_set()):
            resp = env.forward()
            _print_board_state(env, f"response={resp.response_type}")
            while(resp.response_type == ResponseType.REQUIRES_QUERY and not stop_event.is_set()):
                query_type = (resp.data or {}).get("query_type", "generic")
                print(f"\nREQUIRES_QUERY ({query_type})")
                print(f"Data: {resp.data}")

                raw_container: dict[str, str | None] = {"value": None}
                wait_flag = threading.Event()

                def ask_input():
                    value = sd.askstring("Scan", "->")
                    raw_container["value"] = None if value is None else value.strip()
                    wait_flag.set()

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

                parsed = parse_scanner_input(raw_value, resp, env)
                if(parsed is None):
                    print("Could not parse scanner input for this query. Try again.")
                    continue

                print("Received:", raw_value)
                resp = env.forward(parsed)
                _print_board_state(env, f"post-input response={resp.response_type}")

            if(resp.response_type == ResponseType.SKIP):
                print(f"SKIP: {resp.data}")
            elif(resp.response_type == ResponseType.FINISHED):
                print("Event finished.")
            elif(resp.response_type == ResponseType.FINISHED_PACKET):
                print("Packet finished.")
            elif(resp.response_type == ResponseType.NO_MORE_EVENTS):
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
                elif(env.game_phase == GamePhase.PHASE_2):
                    env.propose(
                        AVGEPacket([
                            Phase2(env.player_turn, ActionTypes.ENV, None)
                        ], AVGEEngineID(None, ActionTypes.ENV, None))
                    )
                else:
                    break

            root.after(0, update_label, label, str(env))

    threading.Thread(target=run_env, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    run_scanner_ui(build_demo_environment)

    
    
    