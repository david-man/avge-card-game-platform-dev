from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CoinflipData, StringSelectionQuery
from ....catalog.items.AVGEBirb import AVGEBirb

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class YuelinHu(AVGECharacterCard):
    '''Triple Stop is byte-identical to EmilyWang's/InaMa's atk_1, implemented
    independently here. v1's passive also excludes the initial hand deal
    (`game_phase == INIT`) - v2 has no equivalent concept (nothing in this migration's
    simplified test harness deals an initial hand via a real TransferCard event), so
    that guard has nothing to port.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._birb_reactor: YuelinHu._BirbDrawReactor | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._TripleStop()}), **({ActionTypes.PASSIVE: self._MusicalCatSummonedPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _MusicalCatSummonedPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Musical Cat Summoned!",
                description="Whenever you draw AVGE Birb from your deck, you may discard it to deal 20 damage to the opposing active.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, YuelinHu)
            if card._birb_reactor is None:
                card._birb_reactor = YuelinHu._BirbDrawReactor(card, card.env)
                card.add_listener(card._birb_reactor)

    class _BirbDrawReactor(AVGEEventReactor):
        def __init__(self, owner_card: YuelinHu, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, YuelinHu), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, TransferCard):
                return False
            if callable(event.card) or callable(event.deck_from) or callable(event.deck_to):
                return False
            if not isinstance(event.card, AVGEBirb):
                return False
            if event.deck_from.deck_type != DeckType.DECK:
                return False
            if event.deck_to.deck_type != DeckType.HAND:
                return False
            if event.deck_to.deck_owner.id != self.owner_card.owner:
                return False
            return self.owner_card.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)

        async def react(self, event: Event) -> None:
            assert isinstance(event, TransferCard)
            assert not callable(event.card) and not callable(event.deck_to)
            owner = self.owner_card
            env = self.env
            _id = AVGEEngineID(owner, ActionTypes.PASSIVE, YuelinHu)

            choice = await env.report(StringSelectionQuery(
                owner.owner,
                "Musical Cat Summoned!: Discard the drawn AVGE Birb to deal 20 damage?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                return

            birb = event.card
            player = env.players[owner.owner]
            hand = player.card_piles[DeckType.HAND]
            discard = player.card_piles[DeckType.DISCARD]
            opponent = env.get_opponent(owner.owner)
            target = env.get_player_active(opponent)

            event.push_event([
                TransferCard(_id, birb, hand, discard, env),
                AVGECardHPChangeEvent(_id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env),
            ])

    class _TripleStop(Attack):
        def __init__(self):
            super().__init__(name="Triple Stop", description="Flip 3 coins. Deal 40 damage to the opposing active per head.", action_type=ActionTypes.ATK_1, cost=3)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            _id = AVGEEngineID(card, self.action_type, YuelinHu)
            heads = 0
            for _ in range(3):
                heads += await env.report(CoinflipData(card.owner, "Triple Stop: Flip 3 coins."), _id)
            if heads <= 0:
                return

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env)
                for _ in range(heads)
            ]
            env.push_packet(Packet(_id, events))
