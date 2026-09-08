from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, CardType
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, AVGEAttributeModifier
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ...engine.event import Event, Generator, Packet
from ...catalog.stadiums.PetterutiLounge import PetterutiLounge

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class MatchaLatte(AVGEItemCard):
    '''Heal your whole team +10 (+10 more, so +20 total, if PetterutiLounge is
    active). **Fixed a real v1 bug on sight**: v1 checks
    `isinstance(card.env.stadium_cardholder, PetterutiLounge)` - `stadium_cardholder`
    is the pile/cardholder container itself, never an instance of a specific stadium
    card class, so this check was always `False` and the bonus could never actually
    apply. Fixed by checking the card actually occupying the stadium slot instead.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, MatchaLatte)

        stadium = env.stadium_cardholder.cards_holding[0] if len(env.stadium_cardholder) > 0 else None
        heal = 20 if isinstance(stadium, PetterutiLounge) else 10

        own_chars: list[AVGECharacterCard] = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        if not own_chars:
            return

        events: list[Event | Generator] = [
            AVGECardHPChangeEvent(_id, character, heal, AVGEAttributeModifier.ADDITIVE, CardType.ALL, env)
            for character in own_chars
        ]
        env.push_packet(Packet(_id, events))
