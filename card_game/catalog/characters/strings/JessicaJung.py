from __future__ import annotations

from random import randint

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard, AVGECardHPChange, PlayCharacterCard

class JessicaJung(AVGECharacterCard):
    _COIN_KEY = "jessicajung_coin"
    _SUPPORTER_SELECTION_KEY = "jessicajung_supporter_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 2)
        self.atk_1_name = 'Vibrato'
        self.active_name = 'Cleric Spell'

    def can_play_active(self) -> bool:
        if self.env is None or self.player is None:
            return False
        if self.env.player_turn != self.player:
            return False
        _, used_idx = self.env.check_history(
            self.env.round_id,
            PlayCharacterCard,
            {
                'card': self,
                'card_action': ActionTypes.ACTIVATE_ABILITY,
                'caller': self,
            },
        )
        return used_idx == -1

    def active(self) -> Response:
        discard = self.player.cardholders[Pile.DISCARD]
        supporter_cards = [c for c in list(discard) if isinstance(c, AVGESupporterCard)]
        flip = self.env.cache.get(self, JessicaJung._COIN_KEY, None, True)
        if flip is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.player,
                            [JessicaJung._COIN_KEY],
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            self,
                            CoinflipData('Cleric Spell: Flip a coin.')
                        )
                    ]),
            )

        if int(flip) != 1:
            return Response(ResponseType.CORE, Notify("Jessica Jung used Cleric Spell, but she didn't roll a heads...", [self.player.unique_id], default_timeout))

        if len(supporter_cards) == 0:
            return Response(ResponseType.CORE, Notify("Jessica Jung used Cleric Spell, but there are no supporter cards in the discard pile...", [self.player.unique_id], default_timeout))

        missing = object()
        chosen = self.env.cache.get(self, JessicaJung._SUPPORTER_SELECTION_KEY, missing, True)
        if chosen is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.player,
                            [JessicaJung._SUPPORTER_SELECTION_KEY],
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            self,
                            CardSelectionQuery(
                                'Cleric Spell: Choose a supporter in your discard to shuffle into your deck.',
                                supporter_cards,
                                supporter_cards,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        deck = self.player.cardholders[Pile.DECK]
        if not isinstance(chosen, AVGESupporterCard):
            raise Exception("Choice invalid - Jessica Jung")

        def generate_packet() -> PacketType:
            packet: PacketType = []
            packet.append(
                TransferCard(
                    chosen,
                    discard,
                    deck,
                    ActionTypes.ACTIVATE_ABILITY,
                    self,
                    None,
                    randint(0, len(deck)),
                )
            )
            return packet

        self.propose(AVGEPacket([generate_packet], AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, JessicaJung)))
        return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            packet: PacketType = []
            if not isinstance(active, AVGECharacterCard):
                return packet
            packet.append(
                AVGECardHPChange(
                    active,
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, JessicaJung)))

        return self.generic_response(card, ActionTypes.ATK_1)
