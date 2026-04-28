from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.catalog.items import ConcertProgram, ConcertRoster, ConcertTicket

class RachelChen(AVGECharacterCard):
    _CARD_PICK_KEY = "rachel_chen_card_pick"
    _TARGET_BASE_KEY = "rachel_chen_satb_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.CHOIR, 1, 3)
        self.atk_1_name = 'SATB'
        self.has_active = True

    def can_play_active(self) -> bool:
        # once per turn check
        if self.env.player_turn != self.player:
            return False
        _, already_used_idx = self.env.check_history(
            self.env.round_id,
            PlayCharacterCard,
            {
                "card": self,
                "card_action": ActionTypes.ACTIVATE_ABILITY,
                "caller": self
            },
        )
        if already_used_idx != -1:
            return False
        # check discard for ConcertProgram, ConcertRoster, or ConcertTicket
        discard = self.player.cardholders[Pile.DISCARD]
        for c in discard:
            if isinstance(c, (ConcertProgram, ConcertRoster, ConcertTicket)):
                return True
        return False

    def active(self) -> Response:
        from card_game.internal_events import InputEvent, TransferCard
        discard = self.player.cardholders[Pile.DISCARD]
        deck = self.player.cardholders[Pile.DECK]

        # collect candidate items in discard
        candidates = [c for c in list(discard) if isinstance(c, (ConcertProgram, ConcertRoster, ConcertTicket))]
        chosen = self.env.cache.get(self, RachelChen._CARD_PICK_KEY, None, True)
        if chosen is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[InputEvent]([
                        InputEvent(
                            self.player,
                            [RachelChen._CARD_PICK_KEY],
                            lambda r : True,
                            ActionTypes.ACTIVATE_ABILITY,
                            self,
                            CardSelectionQuery("Program Production: Retrieve a Concert Program, Concert Roster, or Concert Ticket from your discard pile and place it on top of your deck.", candidates, list(discard), True, False)
                        )
                    ]),
            )
        if isinstance(chosen, (ConcertProgram, ConcertRoster, ConcertTicket)) and chosen in discard:
            self.propose(
                AVGEPacket(
                    [TransferCard(chosen, discard, deck, ActionTypes.ACTIVATE_ABILITY, self, None, 0)],
                    AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, RachelChen),
                )
            )
        return Response(ResponseType.CORE, Notify(f"{str(self)} used Program Production!", all_players, default_timeout))

    def atk_1(self, card : AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        player = card.player
        opponent = player.opponent

        # collect player's choir characters in play
        choir_count = 0
        for c in player.get_cards_in_play():
            if c.card_type == CardType.CHOIR:
                choir_count += 1

        if choir_count <= 0:
            return Response(ResponseType.CORE, Notify(f"{str(card)} used SATB, but it did nothing...", all_players, default_timeout))

        # build list of opponent character targets (can be chosen multiple times)
        packet = []
 
        # multiple opponent choices: ask player to pick `choir_count` targets (allow repeats)
        keys = [RachelChen._TARGET_BASE_KEY + str(i) for i in range(choir_count)]
        chars = [card.env.cache.get(card, key, None, True) for key in keys]
        if(chars[0] is None):
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[InputEvent](
                    [
                        InputEvent(
                            card.player,
                            keys,
                            lambda r :  True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                "SATB: Deal +20 damage to each selected character",
                                opponent.get_cards_in_play(),
                                opponent.get_cards_in_play(),
                                False,
                                True
                            )
                        )
                    ]
                )
            )
        else:
            for char in chars:
                assert(isinstance(char, AVGECharacterCard))
                packet.append(
                    AVGECardHPChange(
                        char,
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, RachelChen)))
        return self.generic_response(card, ActionTypes.ATK_1)