from __future__ import annotations
from typing import Tuple, TYPE_CHECKING, TypeVar, Generic

if TYPE_CHECKING:
    from .event_listener import AbstractEventListener
    from .event import Event
EV = TypeVar('EV', bound='Event')
class Constraint(Generic[EV]):
    def __init__(self):
        self._invalidated : bool = False
    
    def match(self, obj : AbstractEventListener[EV] | Constraint[EV]) -> bool:
        """
        Function that checks whether its constraining functionality matches the object.
        It matches to other constraints the moment it is added, but it matches to listeners at runtime. 
        
        Because it matches to listeners right before the listener group is run, it can be used to replace that listener with a different one by using attach_listener
        """
        raise NotImplementedError()
    def update_status(self):
        """
        Makes the constraint evaluate whether it should still be valid. If it shouldn't be, it should call invalidate by itself
        """
        raise NotImplementedError()
    def invalidate(self):
        """
        Invalidates this constraint. Constraints are dropped out the moment they are invalidated
        """
        self._invalidated = True
    def _should_attach(self, obj : AbstractEventListener[EV] | Constraint[EV]):
        return (not self._invalidated) and (self.match(obj))
    def package(self):
        raise NotImplementedError()
