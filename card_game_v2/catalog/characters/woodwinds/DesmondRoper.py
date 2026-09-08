from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, PlayCharacterCard

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class DesmondRoper(AVGECharacterCard):
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
        return {ActionTypes.ATK_1: self._CircularBreathing(), ActionTypes.ATK_2: self._SpeedrunCentral()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _CircularBreathing(Attack):
        '''Byte-identical streak formula to EvelynWu's/RachaelYuan's atk_1, implemented
        independently. Consecutive-own-turns are 2 chapters apart in history (the
        opponent's intervening turn is 1 chapter back), matching v1's `turn -= 2`.'''

        def __init__(self):
            super().__init__(
                name="Circular Breathing",
                description="Deal 10 damage, plus 10 more per consecutive prior turn this attack was used (capped at +40).",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        def _streak(self, card: AVGECharacterCard) -> int:
            '''v2's normal attack dispatch tags the outer `PlayCharacterCard`'s
            `id.calling_card` as None (not the attacker) for a genuine player-driven
            attack - unlike v1, where `caller` is always the attacking character
            itself. So unlike v1's kwargs match (which also checks `caller: card`),
            this only needs `target_card`/`action` - the character that actually
            executed the move.'''
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

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), DesmondRoper)

            streak = self._streak(card)
            damage = 10 + min(40, 10 * streak)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))

    class _SpeedrunCentral(Attack):
        def __init__(self):
            super().__init__(
                name="Speedrun Central",
                description="Deal 100 damage if Desmond moved into active this turn, else 40.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), DesmondRoper)

            active_pile = player.card_piles[DeckType.ACTIVE_CARD]
            event, _ = env.search_history(
                TransferCard,
                {"card": card, "deck_to": active_pile},
                increment=0,
                attribute_search=True,
            )
            damage = 100 if event is not None else 40

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))
