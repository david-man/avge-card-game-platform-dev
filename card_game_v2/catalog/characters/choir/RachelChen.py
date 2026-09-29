from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck
from ....core.AVGEIOManager import CardSelectionQuery, BroadcastIO, Notification
from ....catalog.items.ConcertProgram import ConcertProgram
from ....catalog.items.ConcertRoster import ConcertRoster
from ....catalog.items.ConcertTicket import ConcertTicket

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class RachelChen(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._active_last_used_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.CHOIR

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._SATB()}), **({ActionTypes.ACTIVATE_ABILITY: self._ProgramProduction()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    # ------------------------------------------------------------------
    # Abilities
    # ------------------------------------------------------------------

    class _ProgramProduction(Ability):
        '''Once per turn, retrieve a Concert Program, Concert Roster, or Concert Ticket
        from your discard pile and place it on top of your deck.'''

        def __init__(self):
            super().__init__(
                name="Program Production",
                description="Once per turn, retrieve a Concert Program, Concert Roster, or Concert Ticket from your discard pile and place it on top of your deck.",
                action_type=ActionTypes.ACTIVATE_ABILITY,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            card = action_card
            assert isinstance(card, RachelChen)
            # Ownership is verified centrally, server-side, before Phase2ActivateAbility is ever
            # constructed (server/io_adapter.py's _deserialize_phase2).
            if card._active_last_used_round == card.env.round:
                return False
            discard = card.env.players[card.owner].card_piles[DeckType.DISCARD]
            return any(isinstance(c, (ConcertProgram, ConcertRoster, ConcertTicket)) for c in discard.cards_holding)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, RachelChen)
            env = card.env
            player = env.players[card.owner]
            discard = player.card_piles[DeckType.DISCARD]
            deck = player.card_piles[DeckType.DECK]

            candidates = [c for c in discard.cards_holding if isinstance(c, (ConcertProgram, ConcertRoster, ConcertTicket))]
            _id = AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, RachelChen)
            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Program Production: Retrieve a Concert Program, Concert Roster, or Concert Ticket from your discard pile and place it on top of your deck.",
                1,
                cast(list[AVGECard], candidates),
                list(discard.cards_holding),
                True,
                False,
            ), _id)
            card._active_last_used_round = env.round

            if picked:
                chosen = picked[0]

                def _reordering_to_top(deck: AVGEDeck = deck, chosen: AVGECard = chosen):
                    def gen() -> list[AVGECard]:
                        return [chosen] + [c for c in deck.cards_holding if c is not chosen]
                    return gen

                events: list[Event | Generator] = [
                    TransferCard(_id, chosen, discard, deck, env),
                    ReorderDeck(_id, deck, _reordering_to_top(), env),
                ]
                env.push_packet(Packet(_id, events))

            await env.broadcast(BroadcastIO(f"{card} used Program Production!", default_timeout))

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _SATB(Attack):
        def __init__(self):
            super().__init__(
                name="SATB",
                description="Deal 20 damage to each of a number of chosen opposing characters equal to your own number of CHOIR characters in play (targets may repeat).",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.action_type, RachelChen)

            own_chars: list[AVGECharacterCard] = [
                c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            choir_count = sum(1 for c in own_chars if c.card_type == CardType.CHOIR)

            if choir_count <= 0:
                await env.report(Notification(
                    card.owner, "SATB, but it did nothing...", default_timeout,
                ), _id)
                return

            opposing_chars: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]

            targets = await env.report(CardSelectionQuery(
                card.owner,
                "SATB: Deal 20 damage to each selected character.",
                choir_count,
                cast(list[AVGECard], opposing_chars),
                cast(list[AVGECard], opposing_chars),
                False,
                True,
            ), _id)

            events: list[Event | Generator] = []
            for target in targets:
                assert isinstance(target, AVGECharacterCard)
                events.append(AVGECardHPChangeEvent(
                    _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.CHOIR, env,
                ))

            env.push_packet(Packet(_id, events))
