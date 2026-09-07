"""Engine-layer consequence listeners for status effects (GOON/MAID/ARRANGER).

These are core_listeners() entries, not catalog cards - see V2_MIGRATION_PLAN.md
Section 0/2 for why status effects live here instead of card_game_v2/catalog/.
"""
from .Goon import *
from .Maid import *
from .Arranger import *
