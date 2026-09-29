from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, PlayCharacterCard

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class EvelynWu(AVGECharacterCard):
    '''Byte-identical Circular Breathing streak formula to DesmondRoper's/RachaelYuan's
    atk_1, implemented independently.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._CircularBreathing(), ActionTypes.ATK_2: self._SmallEnsembleLord()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _CircularBreathing(Attack):
        def __init__(self):
            super().__init__(
                name="Circular Breathing",
                description="Deal 10 damage, plus 10 more per consecutive prior turn this attack was used (capped at +40).",
                action_type=ActionTypes.ATK_1,
                cost=1,
            )

        def _streak(self, card: AVGECharacterCard) -> int:
            '''See DesmondRoper's identical helper for why this only checks
            `target_card`/`action`, not `id.calling_card` (v2's normal attack dispatch
            tags that None, unlike v1's `caller`).'''
            env = card.env
            streak = 0
            chapter_increment = 2
            while streak < 4:
                event, _ = env.search_history(
                    PlayCharacterCard,
                    {"target_card": card, "action": ActionTypes.ATK_1},
                    increment=chapter_increment,
                    attribute_search=True,
                )
                if event is None:
                    break
                streak += 1
                chapter_increment += 2
            return streak

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, EvelynWu)

            streak = self._streak(card)
            damage = 10 + min(40, 10 * streak)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))

    class _SmallEnsembleLord(Attack):
        def __init__(self):
            super().__init__(
                name="Small Ensemble Lord",
                description="Heal all damaged opposing bench characters to full, then deal the total healed as damage to the opposing active.",
                action_type=ActionTypes.ATK_2,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.action_type, EvelynWu)

            events: list[Event | Generator] = []
            transfer_total = 0
            for bench_card in opponent.card_piles[DeckType.BENCH]:
                if not isinstance(bench_card, AVGECharacterCard):
                    continue
                existing_damage = max(0, bench_card.max_hp - bench_card.hp)
                if existing_damage <= 0:
                    continue
                transfer_total += existing_damage
                events.append(AVGECardHPChangeEvent(
                    _id, bench_card, existing_damage, AVGEAttributeModifier.ADDITIVE, CardType.ALL, env,
                ))

            if transfer_total > 0:
                target = env.get_player_active(opponent)
                events.append(AVGECardHPChangeEvent(
                    _id, target, transfer_total, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
                ))

            if events:
                env.push_packet(Packet(_id, events))
