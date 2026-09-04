from __future__ import annotations
from abc import abstractmethod, ABC
from typing import TYPE_CHECKING
from ..constants import ID
if TYPE_CHECKING:
    from .listener import EventListener


class Constrainer(ABC):
    def __init__(self, id: ID):
        self.id = id
        self.requires_cleanup = False
        
    def cleanup(self):
        self.requires_cleanup = True

    @abstractmethod
    def match(self, obj: 'Constrainer | EventListener') -> bool:
        '''Returns whether this constrainer constrains another'''
        pass
