from __future__ import annotations

from ..avge_abstracts.AVGEEventListener import AVGEEventListener
from ..core.CoreListeners import (
    AVGETokenTransferCheck, AVGEHPChangeCheck, AVGEHPChangeReactor, AVGEWeaknessModifier,
    AVGEPlayerAttributeChangeReactor, AVGETransferValidityCheck, AVGERetreatCostReactor,
    AVGEPlayCharacterCardValidityCheck, AVGEPlayNonCharacterCardValidityCheck,
)
from ..catalog.status_effects.Goon import (
    AVGEGoonRetreatCostRegulator, AVGEGoonRetreatCostReactor, AVGEGoonStatusChangeReactor,
)
from ..catalog.status_effects.Maid import AVGEMaidDamageShieldModifier
from ..catalog.status_effects.Arranger import AVGEArrangerStatusReactor


def default_core_listeners() -> list[type[AVGEEventListener]]:
    '''The standard rules-enforcement listener set every real game needs - mirrors
    testing/helpers.py::core_listeners() exactly. Deliberately duplicated here rather than
    imported from testing/ (production server code should not depend on test scaffolding) or
    relocated into core/CoreListeners.py (which is deliberately independent of
    catalog/status_effects/ - moving the combined list there would introduce a core -> catalog
    dependency that doesn't exist today). Small, explicit duplication over a new cross-cutting
    shared module, consistent with this codebase's established policy elsewhere.'''
    return [
        AVGETokenTransferCheck, AVGEHPChangeCheck, AVGEHPChangeReactor, AVGEWeaknessModifier,
        AVGEMaidDamageShieldModifier, AVGEPlayerAttributeChangeReactor, AVGETransferValidityCheck,
        AVGERetreatCostReactor, AVGEPlayCharacterCardValidityCheck, AVGEPlayNonCharacterCardValidityCheck,
        AVGEGoonRetreatCostRegulator, AVGEGoonRetreatCostReactor, AVGEGoonStatusChangeReactor,
        AVGEArrangerStatusReactor,
    ]
