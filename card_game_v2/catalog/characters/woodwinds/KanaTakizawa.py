from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import D6Input, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class KanaTakizawa(AVGECharacterCard):
    '''Flutter Tongue's "roll until pair sums to 7" is byte-identical to KathySun's
    atk_2, implemented independently as a plain async loop (much simpler than v1's
    cache-based reentry) - unlike v1's separate `randint` shuffle position, this needs
    no closure-capture tricks since v2 just awaits each roll in sequence.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._immense_aura: KanaTakizawa._ImmenseAuraModifier | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._FlutterTongue()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._ImmenseAuraPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _ImmenseAuraPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Immense Aura",
                description="Reduce incoming attack damage by 10.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, KanaTakizawa)
            if card._immense_aura is None:
                card._immense_aura = KanaTakizawa._ImmenseAuraModifier(card, card.env)
                card.add_listener(card._immense_aura)

    class _ImmenseAuraModifier(AVGEEventModifier):
        '''v1 registers this at `EngineGroup.EXTERNAL_MODIFIERS_3`, not
        `_MODIFIERS_2` like most other flat-damage-reduction passives in this
        migration - replicated faithfully as specified, since nothing here depends on
        ordering relative to another _MODIFIERS_2 listener on the same event.'''

        def __init__(self, owner_card: KanaTakizawa, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, KanaTakizawa), env, EngineGroup.EXTERNAL_MODIFIERS_3)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.target_card) or callable(event.modifier_type) or callable(event.change_type):
                return False
            if event.target_card is not self.owner_card:
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.change_type == CardType.ALL:
                return False
            return event.id.calling_action in (ActionTypes.ATK_1, ActionTypes.ATK_2)

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(-10)
            await self.env.broadcast(BroadcastIO("Immense Aura: -10 damage from attack.", default_timeout))

    class _FlutterTongue(Attack):
        def __init__(self):
            super().__init__(
                name="Flutter Tongue",
                description="Roll a D6 repeatedly until two consecutive rolls sum to 7. Deal 10 damage to the opposing active per roll taken.",
                atk_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), KanaTakizawa)

            prev_roll: int | None = None
            roll_count = 0
            while True:
                roll = await env.report(D6Input(card.owner, "Flutter Tongue: Roll a D6."), _id)
                roll_count += 1
                if prev_roll is not None and prev_roll + roll == 7:
                    break
                prev_roll = roll

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env)
                for _ in range(roll_count)
            ]
            env.push_packet(Packet(_id, events))
