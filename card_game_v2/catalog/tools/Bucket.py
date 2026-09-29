from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGEToolCard, AVGECharacterCard, CardType, Ability
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Bucket",
                description=Bucket.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Bucket):
                raise TypeError("Bucket action requires its defining card")
            assert isinstance(action_card.parent_card, AVGECharacterCard)
            action_card._original_type = action_card.parent_card.card_type
            _id = AVGEEngineID(acting_card, self.action_type, Bucket)
            acting_card.env.push_packet(Packet(_id, [AVGECardTypeChange(
                _id, action_card.parent_card, CardType.PERCUSSION, acting_card.env,
            )]))
