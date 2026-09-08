from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class HarperAitken(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Overblow(), ActionTypes.ATK_2: self._Wipeout()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Overblow(Attack):
        def __init__(self):
            super().__init__(
                name="Overblow",
                description="Deal 50 damage to the opposing active. Deal 10 recoil damage to yourself.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), HarperAitken)

            env.push_packet(Packet(_id, [
                AVGECardHPChangeEvent(_id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
                AVGECardHPChangeEvent(_id, card, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
            ]))

    class _Wipeout(Attack):
        def __init__(self):
            super().__init__(
                name="Wipeout",
                description="Choose up to 2 opposing characters to deal 80 damage each. Deal 80 recoil damage to yourself regardless.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), HarperAitken)

            chars_in_play: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]

            targets: list[AVGECard] = []
            if chars_in_play:
                targets = await env.report(CardSelectionQuery(
                    card.owner,
                    "Wipeout: Choose up to two different targets in opponent's play area.",
                    2,
                    cast(list[AVGECard], chars_in_play),
                    cast(list[AVGECard], chars_in_play),
                    True,
                    False,
                ), _id)

            events: list[Event | Generator] = []
            for target in targets:
                assert isinstance(target, AVGECharacterCard)
                events.append(AVGECardHPChangeEvent(
                    _id, target, 80, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
                ))
            events.append(AVGECardHPChangeEvent(
                _id, card, 80, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            ))

            env.push_packet(Packet(_id, events))
