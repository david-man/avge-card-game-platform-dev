from __future__ import annotations

from .AVGECardholder import AVGEStadiumCardholder
from typing import TYPE_CHECKING, Type, cast, Tuple
from ..constants import *
from enum import StrEnum
from .envcache import EnvironmentCache
from .AVGEPlayer import AVGEPlayer
from .AVGECards import *
from .AVGEEvent import AVGEPacket
from ..engine.engine import Engine
import random
if TYPE_CHECKING:
    from .AVGECardholder import AVGECardholder
    from . import PacketType
    from card_game.internal_events import Phase2, AtkPhase, PlayCharacterCard, TransferCard
    

class GamePhase(StrEnum):
    INIT = 'init'
    TURN_BEGIN = 'begin'
    PICK_CARD = 'pick'
    PHASE_2 = 'phase_2'
    ATK_PHASE = 'phase_atk'
    TURN_END = 'end'
class AVGEEnvironment():
    def __init__(self, p1_deck_dict : dict[Pile, list[Type[AVGECard]]], p2_deck_dict : dict[Pile, list[Type[AVGECard]]], start_turn : PlayerID, starting_stadium : type[AVGEStadiumCard] | None = None, starting_stadium_player : PlayerID | None = None):
        #in standard initialization, all cards should go to the deck
        self._engine : Engine[AVGEEvent] = Engine()
        from card_game.internal_events import TransferCard
        from card_game.catalog.status_effects.Goon import GoonStatusChangeReactor, GoonStatusTransferModifier
        from card_game.catalog.status_effects.Arranger import ArrangerStatusReactor
        super().__init__()
        self.stadium_cardholder : AVGEStadiumCardholder = AVGEStadiumCardholder()
        self.stadium_cardholder.env = self
        self.cards : dict[str, AVGECard] = {}
        self.players : dict[str, AVGEPlayer] = {}
        #adds players
        p1 = AVGEPlayer(PlayerID.P1)
        p2 = AVGEPlayer(PlayerID.P2)
        p1.opponent = p2
        p2.opponent = p1
        self.add_player(p1)
        self.add_player(p2)
        #assigns card_ids
        id_on = 0
        found_char = False
        p1_deck : list[Tuple[type[AVGECard], Pile]] = []
        p2_deck : list[Tuple[type[AVGECard], Pile]]  = []
        for pile in p1_deck_dict.keys():
            for card in p1_deck_dict[pile]:
                p1_deck.append((card, pile))
        for pile in p2_deck_dict.keys():
            for card in p2_deck_dict[pile]:
                p2_deck.append((card, pile))
        assert len(p1_deck) > 5 and len(p2_deck) > 5
        if(starting_stadium is not None and starting_stadium_player is not None):
            deck = p1_deck if starting_stadium_player == PlayerID.P1 else p2_deck
            deck.append((starting_stadium, Pile.STADIUM))
        #assert len(p1_deck) == cards_per_deck and len(p2_deck) == cards_per_deck
        packet : PacketType = []
        for card_type, pile in p1_deck:
            self.cards[f"card_{id_on}"] = card_type(str(f"card_{id_on}"))
            card = self.cards[f"card_{id_on}"]
            if(isinstance(card, AVGECharacterCard)):
                found_char = True
            p1.cardholders[Pile.DECK].add_card(card)
            if(pile != Pile.DECK):
                if(pile == Pile.STADIUM):
                    assert isinstance(card, AVGEStadiumCard)
                    card.original_owner = self.players[PlayerID.P1]
                    packet.append(TransferCard(card,
                                        p1.cardholders[Pile.DECK],
                                        self.stadium_cardholder,
                                        ActionTypes.ENV,
                                        None))
                else:
                    packet.append(TransferCard(card,
                                            p1.cardholders[Pile.DECK],
                                            p1.cardholders[pile],
                                            ActionTypes.ENV,
                                            None))
            id_on+=1
        if(not found_char):
            raise Exception("Player 1's deck is invalid; need at least 1 char")
        found_char = False
        for card_type, pile in p2_deck:
            self.cards[f"card_{id_on}"] = card_type(str(f"card_{id_on}"))
            card = self.cards[f"card_{id_on}"]
            if(isinstance(card, AVGECharacterCard)):
                found_char = True
            p2.cardholders[Pile.DECK].add_card(card)
            if(pile != Pile.DECK):
                if(pile == Pile.STADIUM):
                    assert isinstance(card, AVGEStadiumCard)
                    card.original_owner = self.players[PlayerID.P2]
                    packet.append(TransferCard(card,
                                        p2.cardholders[Pile.DECK],
                                        self.stadium_cardholder,
                                        ActionTypes.ENV,
                                        None))
                else:
                    packet.append(TransferCard(card,
                                            p2.cardholders[Pile.DECK],
                                            p2.cardholders[pile],
                                            ActionTypes.ENV,
                                            None))
            id_on+=1
        if(not found_char):
            raise Exception("Player 2's deck is invalid; need at least 1 char")
        #pointer to whose turn it is
        self.player_turn : AVGEPlayer = p1 if start_turn == PlayerID.P1 else p2
        self.winner : AVGEPlayer | None = None

        self.game_phase : GamePhase = GamePhase.INIT 
        self.round_id = 0

        self.cache = EnvironmentCache(list(self.cards.keys()))
        self.energy : list[EnergyToken] = []#where energy goes to die

        #status-based listeners
        self.add_listener(GoonStatusTransferModifier())
        self.add_listener(GoonStatusChangeReactor())
        self.add_listener(ArrangerStatusReactor())

        if(len(packet) > 0):
            self.propose(AVGEPacket(packet, AVGEEngineID(None, ActionTypes.ENV, None)))
        #force engine to run through all packets until everything is set
        while(True):
            setup_response = self.forward()
            if(setup_response.response_type == ResponseType.NO_MORE_EVENTS):
                break
            if(setup_response.response_type in [ResponseType.REQUIRES_QUERY, ResponseType.INTERRUPT]):
                raise Exception(f"Unexpected interactive setup response: {setup_response.response_type}")
            if(setup_response.response_type in [ResponseType.SKIP, ResponseType.GAME_END]):
                raise Exception(f"Environment initialization failed: {setup_response.response_type} {setup_response.data}")

    def force_flush(self):
        #forces the buffer to flush and actualize all buffered events
        self._engine._queue.flush_buffer()
    def transfer_card(self, card : AVGECard, 
                      cardholder_from : AVGECardholder, 
                      cardholder_to : AVGECardholder,
                      new_idx = None):
        #transfers a card from one cardholder to another. 
        cardholder_from.remove_card_by_id(card.unique_id)
        if(new_idx is None):
            cardholder_to.add_card(card)
        else:
            cardholder_to.insert_card(new_idx, card)
    def propose(self, p : AVGEPacket, priority : int = 0):
        #opens engine in limited manner to cards and players
        self._engine._propose(p, priority=priority)
    def add_listener(self, el : AbstractEventListener):
        """
        If you're thinking of using this, you should have a VERY clear update_status invalidation constraint that you can guarantee will fire eventually. 
        """
        el.internal = False
        #opens engine in limited manner to cards and players
        self._engine.add_listener(el)
    def add_constrainer(self, constrainer : AVGEConstraint):
        #opens engine in limited manner to cards and players
        self._engine.add_constraint(constrainer)
    def add_player(self, player : AVGEPlayer):
        player.attach_to_env(self)
        self.players[player.unique_id] = player


    def _format_card(self, c : AVGECard | None) -> str:
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

    def _format_card_attributes(self, c : AVGECard) -> list[str]:
        if(c is None):
            return ["None"]
        if(isinstance(c, AVGECharacterCard)):
            details = [
                f"hp: {c.hp}",
                f"max_hp: {c.max_hp}",
                f"card_type: {c.card_type}",
                f"retreat_cost: {c.retreat_cost}",
                f"energy: {len(c.energy)}",
                f"tools: {len(c.tools_attached)}",
            ]
            if(c.has_atk_1):
                details.append(f"atk_1_cost: {c.atk_1_cost}")
            if(c.has_atk_2):
                details.append(f"atk_2_cost: {c.atk_2_cost}")
            statuses = []
            for status_effect, attached_cards in c.statuses_attached.items():
                if(len(attached_cards) > 0):
                    statuses.append(f"{status_effect}({len(attached_cards)})")
            details.append(f"statuses: {', '.join(statuses) if len(statuses) > 0 else 'none'}")
            return details
        return []

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
            player_attr_line = ""
            for attr, value in player.attributes.items():
                player_attr_line += f"| {attr}: {value} |"
            lines.append(player_attr_line if player_attr_line != "" else "(no player attributes)")
            lines.append(f"TOKENS: {len(player.energy)}")

            active_card = player.get_active_card() if len(player.cardholders[Pile.ACTIVE]) > 0 else None
            if(active_card is not None):
                lines.append(f"ACTIVE CARD: {self._format_card(active_card)}")
                a = "details: "
                for attr_line in self._format_card_attributes(active_card):
                    a += f"| {attr_line} |"
                lines.append(a)

            bench_cards = list(player.cardholders[Pile.BENCH].cards_by_id.values())
            lines.append("BENCH CARDS:")
            if(len(bench_cards) == 0):
                lines.append("(empty)")
            else:
                for idx, bench_card in enumerate(bench_cards, start=1):
                    a = f"- [{idx}] {self._format_card(bench_card)} details: "
                    for attr_line in self._format_card_attributes(bench_card):
                        a += f"| {attr_line} |"
                    lines.append(a)

            lines.append("PILES:")
            lines.append(f"- {self._format_pile(player, Pile.DECK)}")
            lines.append(f"- {self._format_pile(player, Pile.HAND)}")
            lines.append(f"- {self._format_pile(player, Pile.DISCARD)}")
            lines.append("-" * 72)

        lines.append(f"ENV TOKENS: {len(self.energy)}")

        lines.append("=" * 72)
        return "\n".join(lines)

    def get_active_card(self, player_id : PlayerID):
        return self.players[player_id].cardholders[Pile.ACTIVE].peek()

    def forward(self, args : Data | None = None) -> Response:
        if(args is None):
            args = {}
        if(args.get(ACTIVE_FLAG, None) is not None):
            from . import PacketType
            card = args[ACTIVE_FLAG]
            if(isinstance(card, AVGECharacterCard) and card.has_active and
               card.can_play_active(card)):
                event_running = self._engine.event_running
                if(isinstance(event_running, (Phase2, AtkPhase))):
                    event_running._ff()
                p : PacketType = [
                    PlayCharacterCard(
                        card,
                        ActionTypes.ACTIVATE_ABILITY,
                        ActionTypes.ENV,
                        card
                    )
                ]
                self.propose(AVGEPacket(p, AVGEEngineID(None, ActionTypes.ENV, None)), 10)#act as soon as this packet is done.
                
        resp = self._engine.forward(args)
        if(resp.response_type == ResponseType.GAME_END):
            #cut immediately on GAME_END
            return resp
        if(resp.response_type == ResponseType.FINISHED_PACKET):
            #commits to the environment's data cache once a packet is complete
            self.cache.release()
            #safely releases all expired listeners & constraints from a card once a packet successfully finalizes
            for card in self.cards.values():
                modified_listeners = []
                modified_constraints = []
                for listener in card.owned_listeners:
                    if(not listener._invalidated):
                        modified_listeners.append(listener)
                for constraint in card.owned_constraints:
                    if(not constraint._invalidated):
                        modified_constraints.append(constraint)
                card.owned_listeners = modified_listeners
                card.owned_constraints = modified_constraints
        elif(resp.response_type == ResponseType.NEXT_PACKET):
            #begins capturing changes
            self.cache.release()
            self.cache.capture()
        elif(resp.response_type == ResponseType.SKIP):
            #when response is failed, drop changes manually 
            self.cache.rewind()

            #next, note that the engine has reverted all listeners & constraints
            #thus, all cards' owned listeners & constraints need to revert to how they were before
            for card in self.cards.values():
                modified_listeners = []
                modified_constraints = []
                for listener in card.owned_listeners:
                    if(not listener._invalidated):
                        modified_listeners.append(listener)
                for constraint in card.owned_constraints:
                    if(not constraint._invalidated):
                        modified_constraints.append(constraint)
                card.owned_listeners = modified_listeners
                card.owned_constraints = modified_constraints

        return resp
        
    