from __future__ import annotations
from typing import TYPE_CHECKING
from ..engine.listener import *
from ..constants import EngineGroup
if TYPE_CHECKING:
    from .AVGEID import AVGEEngineID
    from .AVGEEnvironment import AVGEEnvironment


class AVGEEventListener(EventListener):
    def __init__(self, id: AVGEEngineID, env : AVGEEnvironment, engine_group: EngineGroup):
        super().__init__(id, engine_group)
        self.id = id
        self.env = env


class AVGEEventRegulator(AVGEEventListener, EventRegulator):
    pass


class AVGEEventModifier(AVGEEventListener, EventModifier):
    pass


class AVGEEventReactor(AVGEEventListener, EventReactor):
    pass


class AVGEPacketReactor(PacketReactor):
    def __init__(self, id: AVGEEngineID, env : AVGEEnvironment):
        super().__init__(id)
        self.id = id
        self.env=env
