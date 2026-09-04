from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from ..constants import ActionTypes, ID
if TYPE_CHECKING:
    from .AVGECard import AVGECard
    from .AVGEPlayer import AVGEPlayer
    from .AVGEEnvironment import AVGEEnvironment


type CardID = str

@dataclass
class AVGEEngineID(ID):
    caller: AVGECard | AVGEPlayer | AVGEEnvironment
    action_type: ActionTypes
    header_class: type[AVGECard] | None
