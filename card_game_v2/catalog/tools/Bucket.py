from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEToolCard, AVGECharacterCard, CardType
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType, AVGEToolHolder
from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEID import AVGEEngineID, CardID
from ...constants import ActionTypes, User
from ...core.EventCatalog import AVGECardTypeChange, TransferCard
from ...engine.event import Packet


class Bucket(AVGEToolCard):
    '''Changes the equipped character's type to PERCUSSION; reverts to its original type on unequip.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._original_type: CardType | None = None

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if isinstance(deck_from, AVGEToolHolder) and self.parent_card is not None and self._original_type is not None:
            character = self.parent_card
            original_type = self._original_type
            _id = AVGEEngineID(self, ActionTypes.NONCHAR, Bucket)
            self.env.push_packet(Packet(_id, [AVGECardTypeChange(
                _id, character, original_type, self.env,
            )]))
            self._original_type = None

    async def play_card(self) -> None:
        assert isinstance(self.parent_card, AVGECharacterCard)
        self._original_type = self.parent_card.card_type
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Bucket)
        self.env.push_packet(Packet(_id, [AVGECardTypeChange(
            _id, self.parent_card, CardType.PERCUSSION, self.env,
        )]))
