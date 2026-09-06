from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from ..constants import ActionTypes, ID
if TYPE_CHECKING:
    from .AVGECard import AVGECard


type CardID = str

@dataclass
class AVGEEngineID(ID):
    calling_card: AVGECard | None
    calling_action: ActionTypes
    caller_class: type[AVGECard] | None
    
