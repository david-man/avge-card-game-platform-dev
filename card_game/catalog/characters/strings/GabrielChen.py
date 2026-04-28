from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, AVGECardHPChange


class _GabrielThresholdReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(
            identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, GabrielChen),
            group=EngineGroup.EXTERNAL_REACTORS,
        )
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.target_card != self.owner_card:
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        return self.owner_card.hp < 60

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        if args is None:
            args = {}

        owner = self.owner_card
        player = owner.player
        env = owner.env

        choice = env.cache.get(owner, GabrielChen._PASSIVE_DECISION_KEY, None, True)
        if choice is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            player,
                            [GabrielChen._PASSIVE_DECISION_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            StrSelectionQuery(
                                'You know what it is: Deal 70 damage to one random opposing character?',
                                ['Yes', 'No'],
                                ['Yes', 'No'],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if choice != 'Yes':
            self.invalidate()
            return Response(ResponseType.ACCEPT, Data())

        targets = [c for c in player.opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]
        if len(targets) == 0:
            return Response(ResponseType.ACCEPT, Data())

        target = random.choice(targets)
        owner.propose(
            AVGEPacket([
                AVGECardHPChange(
                    target,
                    70,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.PASSIVE,
                    None,
                    owner,
                )
            ], AVGEEngineID(owner, ActionTypes.PASSIVE, GabrielChen))
        )
        self.invalidate()
        return Response(ResponseType.ACCEPT, Notify('You know what it is: Dealt 70 damage to a random opposing character.', all_players, default_timeout))

class GabrielChen(AVGECharacterCard):
    _COIN_KEY_0 = "gabrielchen_coin_0"
    _COIN_KEY_1 = "gabrielchen_coin_1"
    _PASSIVE_DECISION_KEY = "gabrielchen_passive_decision"
    _ATK2_SELECTION_BASE_KEY = "gabrielchen_atk2_targets"
    _ATK2_MODE_KEY = "gabrielchen_atk2_mode"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.STRING, 2, 1, 2)
        self.has_passive = True
        self.atk_2_name = 'Harmonics'

    def passive(self) -> Response:
        self.add_listener(_GabrielThresholdReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        r0 = card.env.cache.get(card, GabrielChen._COIN_KEY_0, None)
        r1 = card.env.cache.get(card, GabrielChen._COIN_KEY_1, None)
        if r0 is None or r1 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [GabrielChen._COIN_KEY_0, GabrielChen._COIN_KEY_1],
                            lambda res: True,
                            ActionTypes.ATK_2,
                            card,
                            CoinflipData('Harmonics: Flip two coins.')
                        )
                    ]),
            )

        heads = int(r0) + int(r1)
        if heads != 2:
            card.env.cache.delete(card, GabrielChen._COIN_KEY_0)
            card.env.cache.delete(card, GabrielChen._COIN_KEY_1)
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Harmonics, but they didn't roll both heads...", all_players, default_timeout))

        mode = card.env.cache.get(card, GabrielChen._ATK2_MODE_KEY, None)
        if mode is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [GabrielChen._ATK2_MODE_KEY],
                            lambda r : True,
                            ActionTypes.ATK_2,
                            card,
                            StrSelectionQuery(
                                'Harmonics: Choose one effect',
                                ['Deal 60 to three opposing characters', 'Deal 70 to two opposing characters'],
                                ['Deal 60 to three opposing characters', 'Deal 70 to two opposing characters'],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        targets = [c for c in card.player.opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]
        req_count = 3 if mode == 'Deal 60 to three opposing characters' else 2
        count = min(req_count, len(targets))
        if count == 0:
            card.env.cache.delete(card, GabrielChen._ATK2_MODE_KEY)
            card.env.cache.delete(card, GabrielChen._COIN_KEY_0)
            card.env.cache.delete(card, GabrielChen._COIN_KEY_1)
            return self.generic_response(card, ActionTypes.ATK_2)

        keys = [GabrielChen._ATK2_SELECTION_BASE_KEY + str(i) for i in range(count)]
        chosen = [card.env.cache.get(card, key, None, True) for key in keys]
        if chosen[0] is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            keys,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CardSelectionQuery(
                                'Harmonics: Choose opposing targets',
                                targets,
                                targets,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        dmg_amt = 60 if mode == 'Deal 60 to three opposing characters' else 70

        def generate_packet() -> PacketType:
            packet: PacketType = []
            for tgt in chosen:
                if isinstance(tgt, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            tgt,
                            dmg_amt,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.STRING,
                            ActionTypes.ATK_2,
                            None,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, GabrielChen)))
        card.env.cache.delete(card, GabrielChen._ATK2_MODE_KEY)
        card.env.cache.delete(card, GabrielChen._COIN_KEY_0)
        card.env.cache.delete(card, GabrielChen._COIN_KEY_1)
        return self.generic_response(card, ActionTypes.ATK_2)
