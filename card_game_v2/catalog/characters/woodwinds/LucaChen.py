from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class LucaChen(AVGECharacterCard):
    '''Sparkling Run (atk_1) is byte-identical to JordanRoosevelt's atk_2, implemented
    independently.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._SparklingRun(), ActionTypes.ATK_2: self._PiccoloSolo()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _SparklingRun(Attack):
        def __init__(self):
            super().__init__(
                name="Sparkling Run",
                description="Deal 30 damage to the opposing active. Heal yourself 20.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, LucaChen)

            env.push_packet(Packet(_id, [
                AVGECardHPChangeEvent(_id, target, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
                AVGECardHPChangeEvent(_id, card, 20, AVGEAttributeModifier.ADDITIVE, CardType.WOODWIND, env),
            ]))

    class _PiccoloSolo(Attack):
        def __init__(self):
            super().__init__(
                name="Piccolo Solo",
                description="Deal 40 damage to the opposing active (90 if Luca is the only WOODWIND character anywhere in play).",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, LucaChen)

            all_chars = [
                c for p in (player, opponent)
                for pile in (DeckType.ACTIVE_CARD, DeckType.BENCH)
                for c in p.card_piles[pile]
                if isinstance(c, AVGECharacterCard)
            ]
            other_ww_count = sum(
                1 for c in all_chars if c is not card and c.card_type == CardType.WOODWIND
            )
            damage = 40 + (50 if other_ww_count == 0 else 0)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))
