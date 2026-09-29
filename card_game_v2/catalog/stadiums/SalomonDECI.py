from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEStadiumCard, CardType, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ...core.AVGEIOManager import D6Input, BroadcastIO
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class SalomonDECI(AVGEStadiumCard):
    '''"Electric Acoustics": whenever a GUITAR/PIANO/CHOIR/PERCUSSION character
    attacks, roll a D6 - 3 or higher reduces that hit by 30. v1 caches the roll
    per-stadium-lifetime with no explicit clear, which would (if that cache is never
    reset elsewhere) reuse a single roll forever rather than re-rolling per attack;
    v2 rolls fresh every qualifying hit instead, matching every other d6/coinflip
    per-attack roll in this migration (Open Question, resolved this way since a
    forever-cached single roll reads as almost certainly unintended).'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="SalomonDECI",
                description=SalomonDECI.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, SalomonDECI):
                raise TypeError("SalomonDECI action requires its defining card")
            acting_card.add_listener(_ElectricAcousticsModifier(action_card, acting_card.env))



class _ElectricAcousticsModifier(AVGEEventModifier):
    _SUPPORTED_TYPES = (CardType.GUITAR, CardType.PIANO, CardType.CHOIR, CardType.PERCUSSION)

    def __init__(self, owner_card: SalomonDECI, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, SalomonDECI), env, EngineGroup.EXTERNAL_MODIFIERS_2)
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
        _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, SalomonDECI)

        roll = await self.env.report(D6Input(attacker.owner, "Salomon DECI: Roll a d6."), _id)
        if roll >= 3:
            event.modify_magnitude(-30)
            await self.env.broadcast(BroadcastIO("Salomon DECI: Electric Acoustics took effect", default_timeout))
