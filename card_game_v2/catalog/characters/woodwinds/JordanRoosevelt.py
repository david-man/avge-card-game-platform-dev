from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class JordanRoosevelt(AVGECharacterCard):
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

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Trickster(), ActionTypes.ATK_2: self._SparklingRun()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _OpponentAttackBoost(AVGEEventModifier):
        '''Deliberately buffs the OPPONENT's next attack - confirmed against v1
        source (a matched pair with `_SelfAttackBoost`, each with its own distinct
        notify text), not a bug: Jordan's own next attack gets a much bigger buff
        (+60 vs +20), so this is a net-favorable trickster gamble, not a mistake.'''

        def __init__(self, owner_card: JordanRoosevelt, env: AVGEEnvironment, round_active: int):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.ATK_1, JordanRoosevelt), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner_card = owner_card
            self.round_active = round_active

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_active:
                self.cleanup()
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            attacker = event.id.calling_card
            if not isinstance(attacker, AVGECharacterCard):
                return False
            if attacker.owner != self.env.get_opponent(self.owner_card.owner).id:
                return False
            return self.env.round == self.round_active

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(20)
            await self.env.broadcast(BroadcastIO("Trickster: Opponent attack +20 this turn.", default_timeout))

    class _SelfAttackBoost(AVGEEventModifier):
        def __init__(self, owner_card: JordanRoosevelt, env: AVGEEnvironment, round_active: int):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.ATK_1, JordanRoosevelt), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner_card = owner_card
            self.round_active = round_active

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_active:
                self.cleanup()
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            if event.id.calling_card is not self.owner_card:
                return False
            return self.env.round == self.round_active

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(60)
            await self.env.broadcast(BroadcastIO("Trickster: Jordan attack +60 this turn.", default_timeout))

    class _Trickster(Attack):
        '''Deals no damage of its own. Attaches its two round-scoped buffs directly
        from the attack rather than a passive - the first card in this migration to
        do so.'''

        def __init__(self):
            super().__init__(
                name="Trickster",
                description="Deals no damage. Your next attack this cycle gets +60 damage; the opponent's next attack gets +20.",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            assert isinstance(card, JordanRoosevelt)
            env = card.env
            next_opp_round = env.round + (1 if env.turn == card.owner else 2)
            next_own_round = env.round + (2 if env.turn == card.owner else 1)
            card.add_listener(JordanRoosevelt._OpponentAttackBoost(card, env, next_opp_round))
            card.add_listener(JordanRoosevelt._SelfAttackBoost(card, env, next_own_round))

    class _SparklingRun(Attack):
        def __init__(self):
            super().__init__(
                name="Sparkling Run",
                description="Deal 30 damage to the opposing active. Heal yourself 20.",
                atk_type=ActionTypes.ATK_2,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), JordanRoosevelt)

            env.push_packet(Packet(_id, [
                AVGECardHPChangeEvent(_id, target, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
                AVGECardHPChangeEvent(_id, card, 20, AVGEAttributeModifier.ADDITIVE, CardType.WOODWIND, env),
            ]))
