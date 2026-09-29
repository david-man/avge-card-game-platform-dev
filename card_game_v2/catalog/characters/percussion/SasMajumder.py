from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck
from ....core.AVGEIOManager import StringSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class SasMajumder(AVGECharacterCard):
    '''"Cybersecurity"'s once-per-round guard uses a plain instance field
    (`_last_triggered_round`), same simplification already established for
    RachelChen/AntongChen/EugeniaAmpofo, rather than replicating v1's
    "any discard-to-my-discard-pile this round" history search.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._cybersecurity: SasMajumder._Cybersecurity | None = None
        self._last_triggered_round: int | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._FourMallets()}), **({ActionTypes.PASSIVE: self._CybersecurityPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _CybersecurityPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Cybersecurity",
                description="Once per round, if your own card gets discarded during the opponent's turn, you may put it back on top of your deck.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, SasMajumder)
            if card._cybersecurity is None:
                card._cybersecurity = SasMajumder._Cybersecurity(card, card.env)
                card.add_listener(card._cybersecurity)

    class _Cybersecurity(AVGEEventReactor):
        def __init__(self, owner_card: SasMajumder, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, SasMajumder), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            if not isinstance(event, TransferCard):
                return False
            if callable(event.card) or callable(event.deck_to):
                return False
            if event.deck_to.deck_type != DeckType.DISCARD:
                return False
            if event.card.owner != self.owner_card.owner:
                return False
            if self.env.turn != self.env.get_opponent(self.owner_card.owner).id:
                return False
            return self.owner_card._last_triggered_round != self.env.round

        async def react(self, event: Event) -> None:
            assert isinstance(event, TransferCard)
            assert not callable(event.card) and not callable(event.deck_to)
            discarded = event.card
            discard_pile = event.deck_to

            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, SasMajumder)
            choice = await self.env.report(StringSelectionQuery(
                self.owner_card.owner,
                f"Cybersecurity: Put {discarded} back on top of your deck?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            self.owner_card._last_triggered_round = self.env.round
            if choice[0] != "Yes":
                return

            player = self.env.players[self.owner_card.owner]
            deck = player.card_piles[DeckType.DECK]

            def _reordering_to_top(deck: AVGEDeck = deck, chosen: AVGECard = discarded):
                def gen() -> list[AVGECard]:
                    return [chosen] + [c for c in deck.cards_holding if c is not chosen]
                return gen

            event.push_event([
                TransferCard(_id, discarded, discard_pile, deck, self.env),
                ReorderDeck(_id, deck, _reordering_to_top(), self.env),
            ])

    class _FourMallets(Attack):
        '''Byte-identical to RyanLee's atk_2, implemented independently.'''

        def __init__(self):
            super().__init__(
                name="Four Mallets",
                description="Deal 10 damage 4 times to the opposing active. The 4th hit also draws a card.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]
            _id = AVGEEngineID(card, self.action_type, SasMajumder)

            events: list[Event | Generator] = []
            for i in range(4):
                events.append(AVGECardHPChangeEvent(
                    _id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
                ))
                if i == 3 and len(deck) > 0:
                    events.append(TransferCard(_id, lambda: deck.get_top(), deck, hand, env))
            env.push_packet(Packet(_id, events))
