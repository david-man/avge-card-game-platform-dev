from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery, Notification
from ....catalog.items.ConcertProgram import ConcertProgram
from ....catalog.items.ConcertRoster import ConcertRoster
from ....catalog.items.ConcertTicket import ConcertTicket

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class SarahChen(AVGECharacterCard):
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
        return {ActionTypes.ATK_1: self._DoubleTongue(), ActionTypes.ATK_2: self._ArtistAlley()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _DoubleTongue(Attack):
        '''v1 proposes the same 10dmg packet via two separate `card.propose(...)`
        calls - a structurally odd way to deal 20 total. v2 collapses this into one
        packet with 2 damage events, matching the total effect (and the individual
        event granularity, in case anything ever cares about per-hit magnitude).'''

        def __init__(self):
            super().__init__(
                name="Double Tongue",
                description="Deal 10 damage to the opposing active, twice.",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), SarahChen)

            env.push_packet(Packet(_id, [
                AVGECardHPChangeEvent(_id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
                AVGECardHPChangeEvent(_id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
            ]))

    class _ArtistAlley(Attack):
        def __init__(self):
            super().__init__(
                name="Artist Alley",
                description="Discard any number of Concert Program/Roster/Ticket cards from hand; deal 40 damage to a chosen opposing character per card discarded this way.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            hand = player.card_piles[DeckType.HAND]
            discard = player.card_piles[DeckType.DISCARD]
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), SarahChen)

            eligible_cards = [
                c for c in hand.cards_holding if isinstance(c, (ConcertProgram, ConcertRoster, ConcertTicket))
            ]
            if not eligible_cards:
                return

            discarded = await env.report(CardSelectionQuery(
                card.owner,
                "Artist Alley: Choose any number of Concert Programs, Concert Rosters, or Concert Tickets to discard.",
                len(eligible_cards),
                cast(list[AVGECard], eligible_cards),
                hand.cards_holding,
                True,
                False,
            ), _id)

            if not discarded:
                await env.report(Notification(
                    card.owner,
                    f"{card} used Artist Alley, but it didn't do anything...", default_timeout,
                ), _id)
                return

            possible_targets: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            targets = await env.report(CardSelectionQuery(
                card.owner,
                "Artist Alley: For each discarded card, choose one opposing character to take 40 damage.",
                len(discarded),
                cast(list[AVGECard], possible_targets),
                cast(list[AVGECard], possible_targets),
                False,
                True,
            ), _id)

            events: list[Event | Generator] = []
            for target in targets:
                assert isinstance(target, AVGECharacterCard)
                events.append(AVGECardHPChangeEvent(
                    _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
                ))
            for to_discard in discarded:
                events.append(TransferCard(_id, to_discard, hand, discard, env))

            env.push_packet(Packet(_id, events))
