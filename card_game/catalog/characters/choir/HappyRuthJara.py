from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import TransferCard

class HappyRuthJara(AVGECharacterCard):
    _TARGET_BASE_KEY = "happy_satb_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.CHOIR, 1, 1)
        self.atk_1_name = 'SATB'
        self.has_active = True

    def can_play_active(self) -> bool:
        # once per turn, must be on bench and have no tools attached
        # on bench
        if self.env.player_turn != self.player:
            return False
        if self.cardholder.pile_type != Pile.BENCH:
            return False
        # no tools attached
        if len(self.tools_attached) > 0:
            return False
        # once per turn: this active must not already be recorded in this round.
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
        return True

    def active(self) -> Response:
        # activating: remove all statuses, reset HP, move to owner's hand(reactor does all of this)
        # move to hand
        hand = self.player.cardholders[Pile.HAND]
        self.propose(
            AVGEPacket(
                [TransferCard(self, self.cardholder, hand, ActionTypes.ACTIVATE_ABILITY, self, None)],
                AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, HappyRuthJara),
            )
        )
        return Response(ResponseType.ACCEPT, Notify(f"{str(self)} left rehearsal early...", all_players, default_timeout))

    def atk_1(self, card: AVGECharacterCard) -> Response:
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
        keys = [HappyRuthJara._TARGET_BASE_KEY + str(i) for i in range(choir_count)]
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
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, HappyRuthJara)))
        return self.generic_response(card, ActionTypes.ATK_1)
