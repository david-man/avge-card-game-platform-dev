from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, TurnEnd
from ....core.AVGEIOManager import CardSelectionQuery, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class AliceWang(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._equalizer: AliceWang._EuclideanAlgorithm | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Vibrato()}), **({ActionTypes.PASSIVE: self._EuclideanAlgorithmPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _EuclideanAlgorithmPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Euclidean Algorithm",
                description="Whenever the opponent's turn ends, if their hand is bigger than yours, they discard down to match.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, AliceWang)
            if card._equalizer is None:
                card._equalizer = AliceWang._EuclideanAlgorithm(card, card.env)
                card.add_listener(card._equalizer)

    class _EuclideanAlgorithm(AVGEEventReactor):
        def __init__(self, owner_card: AliceWang, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, AliceWang), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, TurnEnd):
                return False
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            # TurnEnd.act() already flipped env.turn - see Section 2's pipeline-
            # ordering note - so "the opponent's turn just ended" reads post-flip as
            # env.turn being mine again.
            if self.env.turn != self.owner_card.owner:
                return False
            player = self.env.players[self.owner_card.owner]
            opponent = self.env.get_opponent(self.owner_card.owner)
            return len(opponent.card_piles[DeckType.HAND]) > len(player.card_piles[DeckType.HAND])

        async def react(self, event: Event) -> None:
            player = self.env.players[self.owner_card.owner]
            opponent = self.env.get_opponent(self.owner_card.owner)
            opponent_hand = opponent.card_piles[DeckType.HAND]
            opponent_discard = opponent.card_piles[DeckType.DISCARD]
            extra_cards = len(opponent_hand) - len(player.card_piles[DeckType.HAND])
            if extra_cards <= 0:
                return

            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, AliceWang)
            choices = list(opponent_hand.cards_holding)
            picked = await self.env.report(CardSelectionQuery(
                opponent.id,
                "Euclidean Algorithm: Choose cards to discard until hand sizes match.",
                extra_cards,
                choices,
                choices,
                False,
                False,
            ), _id)

            events: list[Event | Generator] = [
                TransferCard(_id, c, opponent_hand, opponent_discard, self.env) for c in picked
            ]
            # Resolve these transfers now, before another Alice listener checks
            # the hand sizes and before either player's notice opens. The order
            # prompt still appears for the two eligible listeners.
            await event.interrupt(events)
            await self.env.report(Notification(
                player.id,
                "Euclidean Algorithm: Your opponent discarded until your hand sizes matched.",
                default_timeout,
            ), _id)
            await self.env.report(Notification(
                opponent.id,
                "Euclidean Algorithm: You discarded until your hand sizes matched.",
                default_timeout,
            ), _id)

    class _Vibrato(Attack):
        def __init__(self):
            super().__init__(name="Vibrato", description="Deal 40 damage to the opposing active.", action_type=ActionTypes.ATK_1, cost=2)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, AliceWang)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))
