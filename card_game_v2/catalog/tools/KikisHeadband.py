from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEToolCard, AVGECharacterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType, AVGEToolHolder
from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEID import AVGEEngineID, CardID
from ...avge_abstracts.AVGEEventListener import AVGEEventRegulator
from ...constants import ActionTypes, EngineGroup, ResponseStatus, User
from ...core.EventCatalog import TransferCard, AVGEEnergyTransfer
from ...engine.event import Event


class KikisHeadband(AVGEToolCard):
    '''-1 retreat energy cost (floor 0) for the equipped character, while equipped.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._cost_regulator: KikisHeadband._RetreatCostRegulator | None = None

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if isinstance(deck_from, AVGEToolHolder) and self._cost_regulator is not None:
            self._cost_regulator.cleanup()
            self._cost_regulator = None

    async def play_card(self) -> None:
        assert isinstance(self.parent_card, AVGECharacterCard)
        if self._cost_regulator is None:
            self._cost_regulator = KikisHeadband._RetreatCostRegulator(self)
            self.add_listener(self._cost_regulator)

    class _RetreatCostRegulator(AVGEEventRegulator):
        '''Independently re-checks the retreat's energy requirement against
        max(0, retreat_cost - 1) (see V2_MIGRATION_PLAN.md Section 2 on GOON for why
        this doesn't rely on however the base retreat validity check is wired). The
        base retreat-cost reactor (INTERNAL_3, after this regulator's own INTERNAL_1)
        always discards the card's *full*, undiscounted retreat_cost - it doesn't know
        about this tool - so on a pass, this also pre-emptively tops the card up by 1
        energy (a real, rollback-safe event, run before that discard) so the full-price
        discard still succeeds. Net effect: retreat_cost - 1 paid from the player's own
        pool.'''

        def __init__(self, owner_card: KikisHeadband):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, KikisHeadband),
                owner_card.env,
                EngineGroup.INTERNAL_1,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            return (
                isinstance(event, TransferCard)
                and not callable(event.card)
                and not callable(event.deck_from)
                and not callable(event.deck_to)
                and event.id.calling_action == ActionTypes.PLAYER_CHOICE
                and self.owner_card.parent_card is not None
                and event.card is self.owner_card.parent_card
                and event.deck_from.deck_type == DeckType.ACTIVE_CARD
                and event.deck_to.deck_type == DeckType.BENCH
            )

        async def respond(self, event: Event) -> ResponseStatus:
            assert isinstance(event, TransferCard)
            assert isinstance(event.card, AVGECharacterCard)
            effective_cost = max(0, event.card.retreat_cost - 1)
            if len(event.card.energy_tokens) < effective_cost:
                return ResponseStatus.REGULATE_FAIL
            if event.card.retreat_cost > 0:
                event.push_event([AVGEEnergyTransfer(
                    AVGEEngineID(None, ActionTypes.ENV, None),
                    self.env,
                    event.card,
                    self.env,
                )])
            return ResponseStatus.REGULATE_PASS
