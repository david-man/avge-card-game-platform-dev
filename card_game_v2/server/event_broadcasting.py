from __future__ import annotations

from typing import TYPE_CHECKING

from ..avge_abstracts.AVGECard import AVGECharacterCard
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..core.EventCatalog import (
    AVGECardHPChangeEvent, AVGECardMaxHPChangeEvent, AVGECardTypeChange, AVGECardStatusChange,
    AVGEEnergyTransfer, AVGEPlayerAttributeChange, TransferCard, ReorderDeck, PlayCharacterCard,
    PlayNonCharacterCard, PhasePickCard, Phase2, AtkPhase, TurnEnd,
)
from ..core.AVGEIOManager import (
    HPChangeUpdate, MaxHPChangeUpdate, CardTypeChangeUpdate, StatusChangeUpdate,
    EnergyTransferUpdate, PlayerAttributeUpdate, CardMovedUpdate, DeckReorderedUpdate,
    CharacterActionUpdate, NonCharacterPlayUpdate, TurnEndUpdate, PhaseChangedUpdate,
    ActionRejectedUpdate,
)

if TYPE_CHECKING:
    from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ..engine.event import Event
    from ..engine.engine_io import IOType


def event_to_update_io(event: Event) -> IOType[None] | None:
    '''Pure Event -> IOType translation - one branch per player-visible Event subclass in
    core/EventCatalog.py, mirroring core/AVGEIOManager.py's per-event update table. Deliberately
    has no side effects (no broadcasting here) so it can be unit-tested directly, without any
    async/engine machinery involved - see server/game_setup.py for where this actually gets wired
    into env.engine.on_event_committed.

    By the time on_event_committed fires (after the event's own act() has already run, per
    engine/event.py's _run_queue), every field on the event is guaranteed already-resolved (not a
    callable) - the assert-not-callable checks below just satisfy pyright strict mode, matching
    the exact same pattern already used throughout EventCatalog.py's own act() methods.'''

    if isinstance(event, AVGECardHPChangeEvent):
        assert not callable(event.target_card) and not callable(event.magnitude)
        assert not callable(event.modifier_type) and not callable(event.change_type)
        assert event.original_hp is not None and event.final_change is not None
        return HPChangeUpdate(
            event.target_card, event.magnitude, event.modifier_type, event.change_type,
            event.original_hp, event.final_change, event.is_crit,
        )

    if isinstance(event, AVGECardMaxHPChangeEvent):
        assert not callable(event.target_card) and not callable(event.magnitude)
        assert not callable(event.modifier_type) and not callable(event.change_type)
        assert event.original_hp is not None and event.original_max_hp is not None
        assert event.final_hp is not None and event.final_max_hp is not None
        return MaxHPChangeUpdate(
            event.target_card, event.magnitude, event.modifier_type, event.change_type,
            event.original_hp, event.original_max_hp, event.final_hp, event.final_max_hp,
        )

    if isinstance(event, AVGECardTypeChange):
        assert not callable(event.target) and not callable(event.new_type)
        assert event.original_type is not None
        return CardTypeChangeUpdate(event.target, event.original_type, event.new_type)

    if isinstance(event, AVGECardStatusChange):
        assert not callable(event.target) and not callable(event.giver)
        assert not callable(event.status) and not callable(event.change)
        return StatusChangeUpdate(event.target, event.giver, event.status, event.change, event.made_modification)

    if isinstance(event, AVGEEnergyTransfer):
        assert not callable(event.token_from) and not callable(event.token_to)
        return EnergyTransferUpdate(event.token_from, event.token_to)

    if isinstance(event, AVGEPlayerAttributeChange):
        assert not callable(event.player) and not callable(event.attribute)
        assert not callable(event.modifier_type) and not callable(event.magnitude)
        return PlayerAttributeUpdate(
            event.player, event.attribute, event.modifier_type, event.magnitude,
            event.player.attributes[event.attribute],
        )

    if isinstance(event, TransferCard):
        assert not callable(event.card) and not callable(event.deck_from) and not callable(event.deck_to)
        return CardMovedUpdate(event.card, event.deck_from, event.deck_to)

    if isinstance(event, ReorderDeck):
        assert not callable(event.deck) and not callable(event.reordering)
        return DeckReorderedUpdate(event.deck, event.reordering)

    if isinstance(event, PlayCharacterCard):
        assert not callable(event.target_card) and not callable(event.action) and not callable(event.cost)
        assert isinstance(event.id, AVGEEngineID)
        calling_card = event.id.calling_card if isinstance(event.id.calling_card, AVGECharacterCard) else None
        return CharacterActionUpdate(event.target_card, event.action, event.cost, calling_card)

    if isinstance(event, PlayNonCharacterCard):
        assert not callable(event.target_card) and not callable(event.action)
        return NonCharacterPlayUpdate(event.target_card, event.action)

    if isinstance(event, PhasePickCard):
        return PhaseChangedUpdate(phase="draw")

    if isinstance(event, Phase2):
        return PhaseChangedUpdate(phase="main")

    if isinstance(event, AtkPhase):
        return PhaseChangedUpdate(phase="attack")

    if isinstance(event, TurnEnd):
        return TurnEndUpdate(event.env.turn, event.env.round)

    return None


def action_rejected_update(env: AVGEEnvironment, reason: str | None = None) -> ActionRejectedUpdate:
    '''Built from env.engine.on_packet_failed - sent to whoever's turn it currently is. `reason`
    is whatever the failing regulator left on Packet.rejection_reason (None if it didn't set
    one).'''
    return ActionRejectedUpdate(rejected_for=env.turn, reason=reason)
