from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType, AVGEToolCard, AVGEStadiumCard
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, PlayNonCharacterCard
from ....core.AVGEIOManager import D6Input, StringSelectionQuery, RevealCards

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class BokaiBi(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._algorithm: BokaiBi._Algorithm | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Rimshot()}), **({ActionTypes.PASSIVE: self._AlgorithmPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _AlgorithmPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Algorithm",
                description="Whenever the opponent plays a card matching a card in your hand, you may reveal your copy to deal 20 damage.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, BokaiBi)
            if card._algorithm is None:
                card._algorithm = BokaiBi._Algorithm(card, card.env)
                card.add_listener(card._algorithm)

    class _Algorithm(AVGEEventReactor):
        def __init__(self, owner_card: BokaiBi, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, BokaiBi), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def _matching_hand_card(self, played: AVGECard) -> AVGECard | None:
            hand = self.env.players[self.owner_card.owner].card_piles[DeckType.HAND]
            for c in hand.cards_holding:
                if type(c) is type(played):
                    return c
            return None

        def _played_card(self, event: Event) -> AVGECard | None:
            opponent = self.env.get_opponent(self.owner_card.owner)
            if isinstance(event, TransferCard):
                if callable(event.card) or callable(event.deck_from) or callable(event.deck_to):
                    return None
                if event.deck_from.deck_type != DeckType.HAND:
                    return None
                if event.deck_to.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH, DeckType.OFFHAND, DeckType.STADIUM):
                    return None
                if event.card.owner != opponent.id:
                    return None
                return event.card
            if isinstance(event, PlayNonCharacterCard):
                if callable(event.target_card):
                    return None
                if isinstance(event.target_card, (AVGEToolCard, AVGEStadiumCard)):
                    # tools/stadiums are already covered by the TransferCard branch above
                    # (TransferCard.act()'s own "Special Case 3" fires this event as a
                    # *consequence* of that same hand->OFFHAND/STADIUM transfer) - without
                    # this exclusion, a single tool/stadium play matches both branches and
                    # Algorithm fires twice for one play.
                    return None
                if event.target_card.owner != opponent.id:
                    return None
                return event.target_card
            return None

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            played = self._played_card(event)
            if played is None:
                return False
            return self._matching_hand_card(played) is not None

        async def react(self, event: Event) -> None:
            played = self._played_card(event)
            assert played is not None
            overlap = self._matching_hand_card(played)
            assert overlap is not None

            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, BokaiBi)
            choice = await self.env.report(StringSelectionQuery(
                self.owner_card.owner,
                "Algorithm: Reveal matching hand card to deal 20 damage?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                return

            await self.env.broadcast(RevealCards(self.owner_card.owner, [overlap]))
            opponent = self.env.get_opponent(self.owner_card.owner)
            target = self.env.get_player_active(opponent)
            event.push_event([AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, self.env,
            )])

    class _Rimshot(Attack):
        def __init__(self):
            super().__init__(name="Rimshot", description="Roll a die. On 4 or less, deal 60 damage.", action_type=ActionTypes.ATK_1, cost=2)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            _id = AVGEEngineID(card, self.action_type, BokaiBi)
            roll = await env.report(D6Input(card.owner, "Rimshot: Roll a d6"), _id)
            if roll > 4:
                return
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 60, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]))
