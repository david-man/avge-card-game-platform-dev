from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, CardType, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Generator, Packet
from .AVGEBirb import AVGEBirb


class RaffleTicket(AVGEItemCard):
    '''Draw the card from the *bottom* of your deck (not the top). If it's `AVGEBirb`,
    also fully heal a chosen own in-play character.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="RaffleTicket",
                description=RaffleTicket.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, RaffleTicket):
                raise TypeError("RaffleTicket action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]

            _id = AVGEEngineID(acting_card, self.action_type, RaffleTicket)
            if len(deck) == 0:
                await env.report(Notification(
                    acting_card.owner, "RaffleTicket: No cards in deck to draw.", default_timeout,
                ), _id)
                return

            bottom_card = deck.cards_holding[-1]

            heal_target: AVGECharacterCard | None = None
            if isinstance(bottom_card, AVGEBirb):
                own_chars: list[AVGECharacterCard] = [
                    c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
                ] + [
                    c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
                ]
                picked = (await env.report(CardSelectionQuery(
                    acting_card.owner,
                    "Raffle Ticket: Choose one character to heal.",
                    1,
                    cast(list[AVGECard], own_chars),
                    cast(list[AVGECard], own_chars),
                    False,
                    False,
                ), _id))[0]
                assert isinstance(picked, AVGECharacterCard)
                heal_target = picked

            events: list[Event | Generator] = [TransferCard(_id, bottom_card, deck, hand, env)]
            if heal_target is not None:
                events.append(AVGECardHPChangeEvent(
                    _id, heal_target, heal_target.max_hp, AVGEAttributeModifier.SET_STATE, CardType.ALL, env,
                ))
            env.push_packet(Packet(_id, events))
