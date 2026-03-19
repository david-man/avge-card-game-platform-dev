from ..abstract.environment import Environment
from .AVGECardholder import AVGEStadiumCardholder, AVGECardholder
from .AVGEPlayer import AVGEPlayer
from ..abstract.card import Card
from ..constants import *
from enum import StrEnum
from typing import Type

class GamePhase(StrEnum):
    INIT = 'init'
    TURN_BEGIN = 'begin'
    PICK_CARD = 'pick'
    PHASE_2 = 'phase_2'
    ATK_PHASE = 'phase_atk'
    TURN_END = 'end'
class AVGEEnvironment(Environment):
    def __init__(self, p1_deck : list[Type[Card]], p2_deck : list[Type[Card]]):
        super().__init__()
        self.stadium_cardholder : AVGEStadiumCardholder = AVGEStadiumCardholder()
        self.stadium_cardholder.env = self
        self.cards : dict[str, Card] = {}
        #adds players
        p1 = AVGEPlayer(PlayerID.P1)
        p2 = AVGEPlayer(PlayerID.P2)
        p1.opponent = p2
        p2.opponent = p1
        self.add_player(p1)
        self.add_player(p2)
        #gives cards
        id_on = 0
        for card_type in p1_deck:
            self.cards[f"card_{id_on}"] = card_type(str(f"card_{id_on}"))
            p1.cardholders[Pile.DECK].add_card(self.cards[f"card_{id_on}"])
            id_on+=1
        for card_type in p2_deck:
            self.cards[f"card_{id_on}"] = card_type(str(f"card_{id_on}"))
            p2.cardholders[Pile.DECK].add_card(self.cards[f"card_{id_on}"])
            id_on+=1
        #pointer to whose turn it is
        self.player_turn : AVGEPlayer = None
        self.winner : AVGEPlayer = None

        self.game_phase : GamePhase = GamePhase.INIT 
        self.round = 1#round gets increments once every time both players finish

    def _format_card(self, c : Card | None) -> str:
        if(c is None):
            return "None"
        return f"{c.unique_id}<{c.__class__.__name__}>"

    def _format_pile(self, player : AVGEPlayer, pile : Pile, preview_count : int = 3) -> str:
        holder = player.cardholders[pile]
        count = len(holder)
        cards = list(holder.cards_by_id.values())
        preview = ", ".join(self._format_card(c) for c in cards[:preview_count])
        if(count > preview_count):
            preview += f", ... (+{count - preview_count} more)"
        if(preview == ""):
            preview = "(empty)"
        return f"{pile}: {count} | {preview}"

    def _format_card_attributes(self, c : Card) -> list[str]:
        if(c is None):
            return ["None"]
        if(not hasattr(c, "attributes") or getattr(c, "attributes") is None):
            return ["(no attributes)"]

        attr_lines : list[str] = []
        for key, value in c.attributes.items():
            attr_lines.append(f"{key}: {value}")
        if(len(attr_lines) == 0):
            return ["(empty attributes)"]
        return attr_lines

    def __str__(self) -> str:
        lines : list[str] = []
        lines.append("=" * 72)
        lines.append("AVGEEnvironment")
        lines.append("-" * 72)
        lines.append(f"PHASE: {self.game_phase}")
        lines.append(f"TURN: {self.player_turn.unique_id if self.player_turn is not None else 'None'}")
        lines.append(f"WINNER: {self.winner.unique_id if self.winner is not None else 'None'}")
        lines.append("-" * 72)

        stadium_count = len(self.stadium_cardholder)
        stadium_active = self.stadium_cardholder.peek() if stadium_count > 0 else None
        lines.append(f"STADIUM: {self._format_card(stadium_active)}")
        lines.append("-" * 72)

        for player_id, player in self.players.items():
            lines.append(f"PLAYER {player_id}")
            a = ""
            for attr, value in player.attributes.items():
                a += (f"| {attr}: {value} |")
            lines.append(a)
            lines.append("")
            active_card = player.get_active_card() if len(player.cardholders[Pile.ACTIVE]) > 0 else None
            lines.append(f"ACTIVE CARD: {self._format_card(active_card)}")
            a = "attributes: "
            for attr_line in self._format_card_attributes(active_card):
                a += f"| {attr_line} |"
            lines.append(a)

            bench_cards = list(player.cardholders[Pile.BENCH].cards_by_id.values())
            lines.append("\nBENCH CARDS:")
            if(len(bench_cards) == 0):
                lines.append("(empty)")
            else:
                for idx, bench_card in enumerate(bench_cards, start=1):
                    a = f"- [{idx}] {self._format_card(bench_card)}: "
                    for attr_line in self._format_card_attributes(active_card):
                        a += f"| {attr_line} |"
                    lines.append(a)

            
            lines.append("\nPILES:")
            lines.append(f"- {self._format_pile(player, Pile.DECK)}")
            lines.append(f"- {self._format_pile(player, Pile.HAND)}")
            lines.append(f"- {self._format_pile(player, Pile.DISCARD)}")
            lines.append("-" * 72)

        lines.append("=" * 72)
        return "\n".join(lines)

    def get_active_card(self, player_id : PlayerID):
        return self.players[player_id].cardholders[Pile.ACTIVE].peek()
    