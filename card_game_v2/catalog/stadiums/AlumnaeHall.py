from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEItemCard, AVGEStadiumCard, CardType, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventReactor
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ...core.AVGEIOManager import BroadcastIO
from ...engine.event import Event, Generator, Packet

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class AlumnaeHall(AVGEStadiumCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="AlumnaeHall",
                description=AlumnaeHall.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, AlumnaeHall):
                raise TypeError("AlumnaeHall action requires its defining card")
            env = acting_card.env
            _id = AVGEEngineID(acting_card, self.action_type, AlumnaeHall)

            if env.round > 0:
                events: list[Event | Generator] = []
                for player in env.players.values():
                    hand = player.card_piles[DeckType.HAND]
                    discard = player.card_piles[DeckType.DISCARD]
                    items = [c for c in hand.cards_holding if isinstance(c, AVGEItemCard)]
                    for item in items:
                        events.append(TransferCard(_id, item, hand, discard, env))
                if events:
                    await env.broadcast(BroadcastIO("Alumnae Hall: Return by 4PM", default_timeout))
                    env.push_packet(Packet(_id, events))

            acting_card.add_listener(_IntenseReverbReactor(action_card, env))



class _IntenseReverbReactor(AVGEEventReactor):
    '''Whenever anyone draws a card, deals 10 damage (capped so nobody drops below 1
    HP, matching v1's `min(current_hp - 1, 10)`) to the drawer's whole board.'''

    def __init__(self, owner_card: AlumnaeHall, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, AlumnaeHall), env, EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if not isinstance(event, TransferCard):
            return False
        if callable(event.card) or callable(event.deck_from) or callable(event.deck_to):
            return False
        if event.deck_from.deck_type != DeckType.DECK or event.deck_to.deck_type != DeckType.HAND:
            return False
        return True

    async def react(self, event: Event) -> None:
        assert isinstance(event, TransferCard)
        assert not callable(event.card)
        env = self.env
        target_player = env.players[event.card.owner]
        _id = AVGEEngineID(self.owner_card, ActionTypes.NONCHAR, AlumnaeHall)

        own_chars: list[AVGECharacterCard] = [
            c for c in target_player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in target_player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        if not own_chars:
            return

        await env.broadcast(BroadcastIO("Alumnae Hall: Intense Reverb", default_timeout))
        events: list[Event | Generator] = [
            AVGECardHPChangeEvent(
                _id, character, max(0, min(character.hp - 1, 10)),
                AVGEAttributeModifier.SUBSTRACTIVE, CardType.ALL, env,
            )
            for character in own_chars
        ]
        event.push_event(events)
