from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGEToolCard, AVGECharacterCard, Ability
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="AVGEShowcaseSticker",
                description=AVGEShowcaseSticker.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, AVGEShowcaseSticker):
                raise TypeError("AVGEShowcaseSticker action requires its defining card")
            assert isinstance(action_card.parent_card, AVGECharacterCard)
            if action_card._turn_start_reactor is None:
                action_card._turn_start_reactor = AVGEShowcaseSticker._TurnStartReactor(action_card)
                acting_card.add_listener(action_card._turn_start_reactor)


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

            # push_packet (front-of-queue), matching every other card in the catalog, so this
            # draw actually lands at the start of the turn - usable during that turn's own
            # play/attack phases - instead of append_packet's back-of-the-whole-queue behavior,
            # which used to leave it resolving only after that turn's play/attack phases (and,
            # via TurnEnd's own push_packet'd cascade, sometimes not until well into the
            # opponent's turn) were already over, making the card effectively useless on the
            # turn its own text describes.
            #
            # Deferring both the emptiness check and the top-of-deck lookup into a generator -
            # evaluated only once this packet is actually popped and run, not when it's queued -
            # still means this always looks at whatever is *currently* on top at that moment, so
            # there's no double-draw hazard either way: PhasePickCard's own normal draw (also
            # queued via its own act(), independently) resolves against whatever's on top at
            # *its* own run time, whichever of the two packets happens to run first.
            def gen() -> list[Event | Generator]:
                deck = player.card_piles[DeckType.DECK]
                if len(deck) == 0:
                    return []
                hand = player.card_piles[DeckType.HAND]
                return [TransferCard(_id, deck.get_top(), deck, hand, env)]

            self.env.push_packet(Packet(_id, [gen]))
