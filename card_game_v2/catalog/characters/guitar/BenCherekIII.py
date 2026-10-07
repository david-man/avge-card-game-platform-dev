from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import StringSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class BenCherekIII(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.GUITAR

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._FeedbackLoop()}), **({ActionTypes.PASSIVE: self._Loudmouth()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Loudmouth(Ability):
        '''Offers to swap into active only when this bench entry came from hand.'''

        def __init__(self):
            super().__init__(
                name="Loudmouth",
                description="When played from hand to bench, may immediately swap into active.",
                action_type=ActionTypes.PASSIVE,
            )

        def _entered_bench_from_hand(self, card: AVGECharacterCard) -> bool:
            index = 0
            last_source: DeckType | None = None
            while True:
                event, index = card.env.search_history(TransferCard, None, increment=0, index_to_start=index)
                if event is None:
                    return last_source == DeckType.HAND
                if (event.card == card
                    and isinstance(event.deck_from, AVGEDeck)
                    and isinstance(event.deck_to, AVGEDeck)
                        and event.deck_to.deck_type == DeckType.BENCH):
                    last_source = event.deck_from.deck_type
                index += 1

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            if not isinstance(card, BenCherekIII):
                raise TypeError("Loudmouth's definition card must be BenCherekIII")
            if card.deck_type != DeckType.BENCH:
                return
            env = card.env
            player = env.players[card.owner]
            active_holder = player.card_piles[DeckType.ACTIVE_CARD]
            if len(active_holder) == 0:
                return
            if not self._entered_bench_from_hand(card):
                return

            _id = AVGEEngineID(card, ActionTypes.PASSIVE, BenCherekIII)
            choice = await env.report(StringSelectionQuery(
                card.owner,
                "Loudmouth: Do you want to immediately set Ben Cherek as active?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                return

            old_active = env.get_player_active(card.owner)
            events: list[Event | Generator] = [
                TransferCard(_id, card, player.card_piles[DeckType.BENCH], active_holder, env),
                TransferCard(_id, old_active, active_holder, player.card_piles[DeckType.BENCH], env),
            ]
            env.push_packet(Packet(_id, events))

    class _FeedbackLoop(Attack):
        def __init__(self):
            super().__init__(
                name="Feedback Loop",
                description="Deal 50 damage to the opposing active. Also deal 10 damage to each of your own benched GUITAR characters.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, BenCherekIII)

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]
            for c in player.card_piles[DeckType.BENCH]:
                if isinstance(c, AVGECharacterCard) and c.card_type == CardType.GUITAR:
                    events.append(AVGECardHPChangeEvent(
                        _id, c, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
                    ))
            env.push_packet(Packet(_id, events))
