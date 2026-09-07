from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, MAX_BENCH_SIZE, User, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class AshleyToby(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._instagram_viral: AshleyToby._InstagramViral | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._SealAttack()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._InstagramViralPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _InstagramViralPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Instagram Viral",
                description="Doubles this character's own attack damage while both benches are completely full.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, AshleyToby)
            if card._instagram_viral is None:
                card._instagram_viral = AshleyToby._InstagramViral(card, card.env)
                card.add_listener(card._instagram_viral)

    class _InstagramViral(AVGEEventModifier):
        def __init__(self, owner_card: AshleyToby, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, AshleyToby), env, EngineGroup.EXTERNAL_MODIFIERS_2)
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
            if event.id.calling_card is not self.owner_card:
                return False
            player = self.env.players[self.owner_card.owner]
            opponent = self.env.get_opponent(self.owner_card.owner)
            return len(player.card_piles[DeckType.BENCH]) == MAX_BENCH_SIZE and len(opponent.card_piles[DeckType.BENCH]) == MAX_BENCH_SIZE

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            assert not callable(event.magnitude)
            event.modify_magnitude(event.magnitude)
            await self.env.broadcast(BroadcastIO("Instagram Viral: Ashley Toby doubled her damage!", default_timeout))

    class _SealAttack(Attack):
        def __init__(self):
            super().__init__(name="Code Gyu: Seal Attack", description="Deal 40 damage to the opposing active.", atk_type=ActionTypes.ATK_1, cost=2)

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), AshleyToby)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))
