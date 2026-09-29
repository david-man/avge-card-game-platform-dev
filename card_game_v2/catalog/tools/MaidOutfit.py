from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGEToolCard, AVGECharacterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, AVGEToolHolder
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, StatusEffect, AVGEStatusModifier
from ...core.EventCatalog import AVGECardStatusChange, TransferCard
from ...engine.event import Packet


class MaidOutfit(AVGEToolCard):
    '''Grants MAID to the equipped character; revokes it on unequip.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if isinstance(deck_from, AVGEToolHolder) and self.parent_card is not None:
            character = self.parent_card
            _id = AVGEEngineID(self, ActionTypes.NONCHAR, MaidOutfit)
            self.env.push_packet(Packet(_id, [AVGECardStatusChange(
                _id, character, self, StatusEffect.MAID, AVGEStatusModifier.REMOVE, self.env,
            )]))

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="MaidOutfit",
                description=MaidOutfit.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, MaidOutfit):
                raise TypeError("MaidOutfit action requires its defining card")
            assert isinstance(action_card.parent_card, AVGECharacterCard)
            _id = AVGEEngineID(acting_card, self.action_type, MaidOutfit)
            acting_card.env.push_packet(Packet(_id, [AVGECardStatusChange(
                _id, action_card.parent_card, action_card, StatusEffect.MAID, AVGEStatusModifier.ADD, acting_card.env,
            )]))
