from __future__ import annotations
from .event_listener import AbstractEventListener
from typing import Tuple, TYPE_CHECKING, TypeVar, Generic
if TYPE_CHECKING:
    from .engine import Engine
    from .event import Event
T = TypeVar('T')
class Constraint(Generic[T]):
    def __init__(self, identifier : T):
        self.identifier = identifier
        self._invalidated : bool = False
    
    def match(self, obj : AbstractEventListener | Constraint) -> bool:
        """
        Function that checks whether its constraining functionality matches the object
        """
        raise NotImplementedError()
    def constrain_listener(self, listener : AbstractEventListener):
        """
        Function that checks at runtime whether a listener who has this constraint attached to it should be constrained 

        Called right before the listener itself is run
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
    def _should_attach(self, obj : AbstractEventListener | Constraint):
        return (not self._invalidated) and (self.match(obj))
    def make_announcement(self) -> bool:
        raise NotImplementedError()
    def package(self):
        raise NotImplementedError()
    def attempt_attach(self, listener : AbstractEventListener):
        if(self._should_attach(listener)):
            listener.constraints.append(self)
