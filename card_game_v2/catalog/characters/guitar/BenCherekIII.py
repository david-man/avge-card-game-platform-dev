from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
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

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._FeedbackLoop()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._Loudmouth()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Loudmouth(Ability):
        '''On entering bench, offers to immediately swap into active (if there is
        already an active character). Only offered once for a given hand-to-bench
        entry - the guard searches `IMMUTABLE` history for an earlier matching
        transfer, which doesn't see the very transfer that's currently triggering this
        same passive call (not yet solidified), so it only suppresses a *second*,
        separate hand-to-bench entry later in the same chapter - same resolved shape as
        `HappyRuthJara`'s own "did I just enter bench from hand" guard.'''

        def __init__(self):
            super().__init__(
                name="Loudmouth",
                description="On entering bench, may immediately swap into active.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        def _already_entered_bench_from_hand(self, card: AVGECharacterCard) -> bool:
            index = 0
            while True:
                event, index = card.env.search_history(TransferCard, None, increment=0, index_to_start=index)
                if event is None:
                    return False
                if (event.card == card
                    and isinstance(event.deck_from, AVGEDeck)
                    and isinstance(event.deck_to, AVGEDeck)
                    and event.deck_from.deck_type == DeckType.HAND
                        and event.deck_to.deck_type == DeckType.BENCH):
                    return True
                index += 1

        async def __call__(self, card: AVGECharacterCard) -> None:
            if card.deck_type != DeckType.BENCH:
                return
            env = card.env
            player = env.players[card.owner]
            active_holder = player.card_piles[DeckType.ACTIVE_CARD]
            if len(active_holder) == 0:
                return
            if self._already_entered_bench_from_hand(card):
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
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), BenCherekIII)

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]
            for c in player.card_piles[DeckType.BENCH]:
                if isinstance(c, AVGECharacterCard) and c.card_type == CardType.GUITAR:
                    events.append(AVGECardHPChangeEvent(
                        _id, c, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
                    ))
            env.push_packet(Packet(_id, events))
