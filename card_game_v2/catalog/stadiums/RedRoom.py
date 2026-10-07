from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEStadiumCard, CardType, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ...core.AVGEIOManager import BroadcastIO
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class RedRoom(AVGEStadiumCard):
    '''+10 damage for GUITAR/PIANO/CHOIR/PERCUSSION attackers, -10 for WOODWIND/BRASS/STRING.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="RedRoom",
                description=RedRoom.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, RedRoom):
                raise TypeError("RedRoom action requires its defining card")
            acting_card.add_listener(_AmpDiffModifier(action_card, acting_card.env))



class _AmpDiffModifier(AVGEEventModifier):
    _SUPPORTED_TYPES = (
        CardType.GUITAR, CardType.PIANO, CardType.CHOIR,
        CardType.PERCUSSION, CardType.WOODWIND, CardType.BRASS, CardType.STRING,
    )

    def __init__(self, owner_card: RedRoom, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, RedRoom), env, EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if not isinstance(event, AVGECardHPChangeEvent):
            return False
        if callable(event.modifier_type) or callable(event.change_type):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.change_type == CardType.ALL:
            return False
        if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
            return False
        attacker = event.id.calling_card
        if not isinstance(attacker, AVGECharacterCard):
            return False
        return attacker.card_type in self._SUPPORTED_TYPES

    async def modify(self, event: Event) -> None:
        assert isinstance(event, AVGECardHPChangeEvent)
        attacker = event.id.calling_card
        assert isinstance(attacker, AVGECharacterCard)

        if attacker.card_type in (CardType.WOODWIND, CardType.BRASS, CardType.STRING):
            event.modify_magnitude(-10)
        else:
            event.modify_magnitude(10)
        await self.env.broadcast(BroadcastIO("Red Room: Amp Diff", default_timeout))
