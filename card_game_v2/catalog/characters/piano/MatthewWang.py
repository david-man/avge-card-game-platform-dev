from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, PhasePickCard, TransferCard
from ....core.AVGEIOManager import CoinflipData, StringSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class MatthewWang(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._pot_of_greed: MatthewWang._PotOfGreed | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Arpeggios()}), **({ActionTypes.PASSIVE: self._PotOfGreedPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _PotOfGreedPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Pot of Greed",
                description="While Active: At the start of your turn, flip a coin. If heads, you may draw two cards instead of one.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, MatthewWang)
            if card._pot_of_greed is None:
                card._pot_of_greed = MatthewWang._PotOfGreed(card, card.env)
                card.add_listener(card._pot_of_greed)

    class _PotOfGreed(AVGEEventReactor):
        def __init__(self, owner_card: MatthewWang, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, MatthewWang), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, PhasePickCard):
                return False
            if self.owner_card.deck_type != DeckType.ACTIVE_CARD:
                return False
            player = self.env.players[self.owner_card.owner]
            return self.env.turn == self.owner_card.owner and len(player.card_piles[DeckType.DECK]) > 0

        async def react(self, event: Event) -> None:
            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, MatthewWang)
            heads = await self.env.report(CoinflipData(self.owner_card.owner, "Pot of Greed: Flip a coin!"), _id)
            if heads != 1:
                return

            choice = await self.env.report(StringSelectionQuery(
                self.owner_card.owner,
                "Pot of Greed: Draw one extra card (2 instead of 1)?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                return

            player = self.env.players[self.owner_card.owner]
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]

            def draw_top() -> list[Event | Generator]:
                if len(deck) == 0:
                    return []
                return [TransferCard(_id, deck.get_top(), deck, hand, self.env)]

            event.push_event([draw_top])

    class _Arpeggios(Attack):
        def __init__(self):
            super().__init__(name="Arpeggios", description="Deal 40 damage to the opposing active.", action_type=ActionTypes.ATK_1, cost=2)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, MatthewWang)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
