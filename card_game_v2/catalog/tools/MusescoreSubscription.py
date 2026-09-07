from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEToolCard, AVGECharacterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, AVGEToolHolder
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, StatusEffect, AVGEStatusModifier
from ...core.EventCatalog import AVGECardStatusChange, TransferCard
from ...engine.event import Packet


class MusescoreSubscription(AVGEToolCard):
    '''Grants ARRANGER to the equipped character; revokes it on unequip.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if isinstance(deck_from, AVGEToolHolder) and self.parent_card is not None:
            character = self.parent_card
            _id = AVGEEngineID(self, ActionTypes.NONCHAR, MusescoreSubscription)
            self.env.push_packet(Packet(_id, [AVGECardStatusChange(
                _id, character, self, StatusEffect.ARRANGER, AVGEStatusModifier.REMOVE, self.env,
            )]))

    async def play_card(self) -> None:
        assert isinstance(self.parent_card, AVGECharacterCard)
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, MusescoreSubscription)
        self.env.push_packet(Packet(_id, [AVGECardStatusChange(
            _id, self.parent_card, self, StatusEffect.ARRANGER, AVGEStatusModifier.ADD, self.env,
        )]))
