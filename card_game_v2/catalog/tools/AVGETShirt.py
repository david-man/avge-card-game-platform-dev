from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGEToolCard, AVGECharacterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, AVGEToolHolder
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, StatusEffect, AVGEStatusModifier
from ...core.EventCatalog import AVGECardStatusChange, TransferCard
from ...engine.event import Packet


class AVGETShirt(AVGEToolCard):
    '''Grants GOON to the equipped character; revokes it on unequip.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if isinstance(deck_from, AVGEToolHolder) and self.parent_card is not None:
            character = self.parent_card
            _id = AVGEEngineID(self, ActionTypes.NONCHAR, AVGETShirt)
            self.env.push_packet(Packet(_id, [AVGECardStatusChange(
                _id, character, self, StatusEffect.GOON, AVGEStatusModifier.REMOVE, self.env,
            )]))

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="AVGETShirt",
                description=AVGETShirt.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, AVGETShirt):
                raise TypeError("AVGETShirt action requires its defining card")
            assert isinstance(action_card.parent_card, AVGECharacterCard)
            _id = AVGEEngineID(acting_card, self.action_type, AVGETShirt)
            acting_card.env.push_packet(Packet(_id, [AVGECardStatusChange(
                _id, action_card.parent_card, action_card, StatusEffect.GOON, AVGEStatusModifier.ADD, acting_card.env,
            )]))
