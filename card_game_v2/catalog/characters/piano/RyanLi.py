from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, StatusEffect, User, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class RyanLi(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._maid_buff: RyanLi._MoeMoeKyun | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._FourHands()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._MoeMoeKyunPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _MoeMoeKyunPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Moe moe kyun~!",
                description="Any of your own characters carrying MAID deal +10 damage on their attacks.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, RyanLi)
            if card._maid_buff is None:
                card._maid_buff = RyanLi._MoeMoeKyun(card, card.env)
                card.add_listener(card._maid_buff)

    class _MoeMoeKyun(AVGEEventModifier):
        def __init__(self, owner_card: RyanLi, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.NONCHAR, RyanLi), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
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
            if attacker.owner != self.owner_card.owner:
                return False
            return len(attacker.statuses_attached[StatusEffect.MAID]) > 0

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(10)
            await self.env.broadcast(BroadcastIO("Moe moe kyun~!: +10 damage for your maid.", default_timeout))

    class _FourHands(Attack):
        '''Byte-identical to CathyRong's atk_2, implemented independently.'''

        def __init__(self):
            super().__init__(
                name="Four Hands",
                description="Deal 50 damage to the opposing active (80 if another PIANO character is on your bench).",
                atk_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), RyanLi)

            has_piano_benchmate = any(
                isinstance(c, AVGECharacterCard) and c is not card and c.card_type == CardType.PIANO
                for c in player.card_piles[DeckType.BENCH]
            )
            dmg = 80 if has_piano_benchmate else 50
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, dmg, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
