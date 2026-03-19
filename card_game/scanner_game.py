from .avge_abstracts.AVGECardholder import *
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEEnvironment import *
from .avge_abstracts.AVGEEvent import *
from .avge_abstracts.AVGEPlayer import *
from .internal_events import *
import tkinter as tk
import threading
from typing import Any


root = tk.Tk()
root.title("Display Window")


class BasicCharacterCard(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.attributes : dict[AVGECardAttribute, Type | float] = {
            AVGECardAttribute.TYPE: Type.BRASS,
            AVGECardAttribute.HP: 100,
            AVGECardAttribute.MV_1_COST: 0,
            AVGECardAttribute.MV_2_COST: 1,
            AVGECardAttribute.SWITCH_COST: 1,
            AVGECardAttribute.ENERGY_ATTACHED: 0
        }
        self.has_atk_1 : bool = True
        self.has_atk_2 : bool = True
        self.has_passive : bool = False#any ability that activates when the card gets put in play
        self.has_active : bool = False#any ability that can be activated whenever
    def atk_1(card, args : Data | None = None) -> bool:
        print("ATTACK ONE")
        return True
    def atk_2(card, args : Data | None = None) -> bool:
        env : AVGEEnvironment = card.env
        opponent_active_card : AVGECharacterCard = env.get_active_card(card.player.opponent.unique_id)
        env.propose(AVGECardAttributeChange(opponent_active_card,
                                            AVGECardAttribute.HP,
                                            -10,
                                            AVGEAttributeModifier.ADDITIVE,
                                            ActionTypes.ATK_1,
                                            card,
                                            Type.BRASS))
        return True
    def deactivate_card(self):
        return


# Function to update the label text
def update_label(text):
    label.config(text=text)


def _safe_get_card(env: AVGEEnvironment, card_id: str) -> Card | None:
    return env.cards.get(card_id)


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
        player: AVGEPlayer = query_data.get("player_involved")
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

    if(query_type in ["ext_modifier_order", "ext_reactor_order"]):
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


if __name__ == "__main__":
    env = AVGEEnvironment([BasicCharacterCard] * 20, [BasicCharacterCard] * 20)
    for i in range(3):
        env.transfer_card(env.players[PlayerID.P1].cardholders[Pile.DECK].peek(), 
                          env.players[PlayerID.P1].cardholders[Pile.DECK],
                          env.players[PlayerID.P1].cardholders[Pile.BENCH])
        env.transfer_card(env.players[PlayerID.P2].cardholders[Pile.DECK].peek(), 
                          env.players[PlayerID.P2].cardholders[Pile.DECK],
                          env.players[PlayerID.P2].cardholders[Pile.BENCH])
    env.transfer_card(env.players[PlayerID.P1].cardholders[Pile.DECK].peek(), 
                        env.players[PlayerID.P1].cardholders[Pile.DECK],
                        env.players[PlayerID.P1].cardholders[Pile.ACTIVE])
    env.transfer_card(env.players[PlayerID.P2].cardholders[Pile.DECK].peek(), 
                        env.players[PlayerID.P2].cardholders[Pile.DECK],
                        env.players[PlayerID.P2].cardholders[Pile.ACTIVE])
    env.player_turn = env.players[PlayerID.P1]
    env.propose(Phase2(env.player_turn, ActionTypes.ENV, None))
    label = tk.Label(root, text=str(env), font=("Arial", 12))
    label.pack(padx=20, pady=20)
    print("Scanner input examples:")
    print("  phase2: atk | tool <tool_id> <attach_to_id> | supporter <id> | item <id> | stadium <id> | swap <bench_id> | energy <attach_to_id> | hand2bench <id>")
    print("  atk: atk1 | atk2")
    print("  ko_replace: replace <bench_id>")
    print("  ext_*_order: order 2,0,1")
    def run_env():
        import tkinter.simpledialog as sd
        while(True):
            resp = env.forward()
            while(resp.response_type == ResponseType.REQUIRES_QUERY):
                query_type = (resp.data or {}).get('query_type', 'generic')
                print(f"\nREQUIRES_QUERY ({query_type})")
                print(f"Data: {resp.data}")
                
                global raw
                raw = None
                def f():
                    global raw
                    raw = sd.askstring("Scan", "->").strip()
                root.after(0, f)
                while raw is None:
                    continue
                parsed = parse_scanner_input(raw, resp, env)
                if(parsed is None):
                    print("Could not parse scanner input for this query. Try again.")
                    continue
                resp = env.forward(parsed)
            if(resp.announce):
                print("EVENT RESPONSE PKG:", resp.source.package())
                if(resp.source.package() == "Phase 2"):
                    env.game_phase = GamePhase.PHASE_2
                elif(resp.source.package() == "Atk phase"):
                    env.game_phase = GamePhase.ATK_PHASE

            if(resp.response_type == ResponseType.SKIP):
                print(f"SKIP: {resp.data}")
            elif(resp.response_type == ResponseType.FINISHED):
                print("Event finished.")
            elif(resp.response_type == ResponseType.NO_MORE_EVENTS):
                if(env.game_phase == GamePhase.ATK_PHASE):
                    env.propose(AtkPhase(env.player_turn, ActionTypes.ENV, None))
                elif(env.game_phase == GamePhase.PHASE_2):
                    env.propose(Phase2(env.player_turn, ActionTypes.ENV, None))
                else:
                    break

            root.after(0, update_label, str(env))
    threading.Thread(target = run_env, daemon = True).start()
    root.mainloop()

    
    
    