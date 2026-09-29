from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import D6Input

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class KevinYang(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Rimshot(), ActionTypes.ATK_2: self._Stickshot()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Rimshot(Attack):
        def __init__(self):
            super().__init__(name="Rimshot", description="Roll a die. On 4 or less, deal 60 damage.", action_type=ActionTypes.ATK_1, cost=2)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            _id = AVGEEngineID(card, self.action_type, KevinYang)
            roll = await env.report(D6Input(card.owner, "Rimshot: Roll a dice!"), _id)
            if roll > 4:
                return
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 60, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]))

    class _Stickshot(Attack):
        def __init__(self):
            super().__init__(name="Stickshot", description="Roll a die 4 times. Deal 40 damage per pip of the lowest roll.", action_type=ActionTypes.ATK_2, cost=3)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            _id = AVGEEngineID(card, self.action_type, KevinYang)
            rolls = [await env.report(D6Input(card.owner, "Stickshot: Roll a dice four times!"), _id) for _ in range(4)]
            damage = 40 * min(rolls)

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]))
