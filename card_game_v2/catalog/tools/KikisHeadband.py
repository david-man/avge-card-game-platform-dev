from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGEToolCard, AVGECharacterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType, AVGEToolHolder
from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEID import AVGEEngineID, CardID
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...constants import ActionTypes, EngineGroup, User
from ...core.EventCatalog import TransferCard
from ...engine.event import Event


class KikisHeadband(AVGEToolCard):
    '''-1 retreat energy cost (floor 0) for the equipped character, while equipped.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._cost_modifier: KikisHeadband._RetreatCostModifier | None = None

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if isinstance(deck_from, AVGEToolHolder) and self._cost_modifier is not None:
            self._cost_modifier.cleanup()
            self._cost_modifier = None

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="KikisHeadband",
                description=KikisHeadband.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, KikisHeadband):
                raise TypeError("KikisHeadband action requires its defining card")
            assert isinstance(action_card.parent_card, AVGECharacterCard)
            if action_card._cost_modifier is None:
                action_card._cost_modifier = KikisHeadband._RetreatCostModifier(action_card)
                acting_card.add_listener(action_card._cost_modifier)


    class _RetreatCostModifier(AVGEEventModifier):
        '''-1 to the equipped character's own ACTIVE_CARD -> BENCH retreat leg's cost
        field (see TransferCard's own cost field and A2's retreat-cost fix) - a plain
        EXTERNAL_MODIFIERS_1 modifier, same as any other cost modifier
        (DemiLu's/the Steinert stadiums' attack-cost modifiers follow the identical
        pattern), replacing the old regulator-plus-top-up-event trick this needed when
        the only thing available to adjust was the reactor's own always-full-price
        discard. No internal clamp: AVGETransferValidityCheck (the affordability
        gate) and TransferCard.act() (the actual charge) both floor at 0 once, at the
        single point each of them reads event.cost - see AVGETransferValidityCheck's
        own docstring for why clamping here instead could make the net result
        order-dependent if this ever stacks with something else.'''

        def __init__(self, owner_card: KikisHeadband):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, KikisHeadband),
                owner_card.env,
                EngineGroup.EXTERNAL_MODIFIERS_1,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            return (
                isinstance(event, TransferCard)
                and not callable(event.card)
                and not callable(event.deck_from)
                and not callable(event.deck_to)
                and not callable(event.cost)
                and event.id.calling_action == ActionTypes.PLAYER_CHOICE
                and self.owner_card.parent_card is not None
                and event.card is self.owner_card.parent_card
                and event.deck_from.deck_type == DeckType.ACTIVE_CARD
                and event.deck_to.deck_type == DeckType.BENCH
            )

        async def modify(self, event: Event) -> None:
            assert isinstance(event, TransferCard)
            assert not callable(event.cost)
            event.cost -= 1
