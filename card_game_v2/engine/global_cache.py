from dataclasses import dataclass
from typing import Any
class Cache[T]:
    @dataclass
    class Change:
        owner: T
        key: str

    @dataclass
    class Removal(Change):
        removed_value: Any

    @dataclass
    class Insertion(Change):
        new_value: Any

    @dataclass
    class Replacement(Change):
        old_value: Any
        new_value: Any

    def __init__(self, owners : list[T]):
        self.cache : dict[T, dict[str, Any]] = {
            owner : {} for owner in owners
        }
        self._wound_changes: list[Cache.Change] = []

    def unwind(self):
        for change in reversed(self._wound_changes):
            if (isinstance(change, Cache.Removal)):
                self.cache[change.owner][change.key] = change.removed_value
            elif (isinstance(change, Cache.Insertion)):
                del self.cache[change.owner][change.key]
            elif (isinstance(change, Cache.Replacement)):
                self.cache[change.owner][change.key] = change.old_value
            else:
                raise Exception("cache unwind failed")
        self._wound_changes = []

    def solidy_changes(self):
        self._wound_changes = []

    def remove(self, owner: T, key: str):
        '''Removes a key from an owner's associated cache. '''
        val = self.cache[owner].pop(key, None)
        assert val is not None
        self._wound_changes.append(Cache.Removal(owner, key, val))

    def set(self, owner: T, key: str, new_value: Any):
        '''Sets a key in an owner's associated cache'''
        if (key in self.cache[owner]):
            self._wound_changes.append(Cache.Replacement(
                owner, key, self.cache[owner][key], new_value))
        else:
            self._wound_changes.append(Cache.Insertion(
                owner, key, new_value))
        self.cache[owner][key] = new_value