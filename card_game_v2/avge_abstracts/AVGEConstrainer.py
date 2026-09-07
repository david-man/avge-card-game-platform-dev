from __future__ import annotations
from typing import TYPE_CHECKING
from ..engine.constrainer import Constrainer
if TYPE_CHECKING:
    from .AVGEID import AVGEEngineID


class AVGEConstrainer(Constrainer):
    def __init__(self, id: AVGEEngineID):
        super().__init__(id)
        self.id = id
