from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEToolCard, AVGECharacterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType, AVGEToolHolder
from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEID import AVGEEngineID, CardID
from ...avge_abstracts.AVGEEventListener import AVGEEventReactor
from ...constants import ActionTypes, EngineGroup, User
from ...core.EventCatalog import TransferCard, PhasePickCard
from ...core.AVGEIOManager import CoinflipData
from ...engine.event import Event, Generator, Packet


class AVGEShowcaseSticker(AVGEToolCard):
    '''Flips a coin at the start of the equipped character's controller's turn, while
    that character is active; heads draws the top card of the deck.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._turn_start_reactor: AVGEShowcaseSticker._TurnStartReactor | None = None

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if isinstance(deck_from, AVGEToolHolder) and self._turn_start_reactor is not None:
            self._turn_start_reactor.cleanup()
            self._turn_start_reactor = None

    async def play_card(self) -> None:
        assert isinstance(self.parent_card, AVGECharacterCard)
        if self._turn_start_reactor is None:
            self._turn_start_reactor = AVGEShowcaseSticker._TurnStartReactor(self)
            self.add_listener(self._turn_start_reactor)

    class _TurnStartReactor(AVGEEventReactor):
        def __init__(self, owner_card: AVGEShowcaseSticker):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, AVGEShowcaseSticker),
                owner_card.env,
                EngineGroup.EXTERNAL_REACTORS,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, PhasePickCard):
                return False
            character = self.owner_card.parent_card
            if character is None:
                return False
            return character.deck_type == DeckType.ACTIVE_CARD and self.env.turn == character.owner

        async def react(self, event: Event):
            character = self.owner_card.parent_card
            assert isinstance(character, AVGECharacterCard)
            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, AVGEShowcaseSticker)
            result = await self.env.report(CoinflipData(character.owner, "AVGE Ambassador: Flip a coin."), _id)
            if result != 1:
                return
            player = self.env.players[character.owner]
            env = self.env

            # PhasePickCard's own normal turn-start draw is queued as a *separate*,
            # later packet (env.append_packet from within its own act()) that still
            # holds a reference to whatever was on top of the deck *before* this
            # reactor runs. Resolving our own draw target eagerly here (deck.get_top())
            # would race that already-queued draw and grab the same card out from
            # under it. Deferring both the emptiness check and the top-of-deck lookup
            # into a generator - itself queued as another separate, still-later packet
            # - makes this draw only actually look at the deck once the normal draw has
            # already happened.
            def gen() -> list[Event | Generator]:
                deck = player.card_piles[DeckType.DECK]
                if len(deck) == 0:
                    return []
                hand = player.card_piles[DeckType.HAND]
                return [TransferCard(_id, deck.get_top(), deck, hand, env)]

            self.env.append_packet(Packet(_id, [gen]))
