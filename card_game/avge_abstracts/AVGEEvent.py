from __future__ import annotations

from ..engine.event import Event, Packet
from ..engine.event_listener import *
from typing import TYPE_CHECKING, Callable, TypeVar, cast
from ..constants import *
if TYPE_CHECKING:
    from .AVGEEnvironment import AVGEEnvironment


AEV = TypeVar("AEV", bound="AVGEEvent")
type DeferredAVGEPacket = Callable[[], list[AVGEEvent | DeferredAVGEPacket]]
class AVGEEvent(Event):
    def __init__(self,
                 catalyst_action : ActionTypes,
                 caller : AVGECard | AVGEPlayer | AVGEEnvironment,
                 core_notif : Notify | None,
                 **kwargs):
        super().__init__(catalyst_action = catalyst_action, caller = caller, core_notif=core_notif,**kwargs)
        self.caller = caller
        self.catalyst_action = catalyst_action
        self.core_notif = core_notif
        self.identifier = AVGEEngineID(caller, catalyst_action, None)
        self.temp_cache = {}
    def __str__(self):
        package_fn = getattr(self, "package", None)
        if(callable(package_fn)):
            try:
                description = package_fn()
                if(isinstance(description, str) and description.strip() != ""):
                    return description
            except Exception:
                pass
        return type(self).__name__
    
class AVGEPacket(Packet[AEV]):
    type AVGEGenerator = Callable[[], list[AEV | AVGEGenerator]]
    def __init__(self, element : list[AEV | AVGEGenerator], identifier : AVGEEngineID):
        super().__init__(element)
        self.identifier = identifier
    

type PacketType = list[AVGEEvent | DeferredAVGEPacket]