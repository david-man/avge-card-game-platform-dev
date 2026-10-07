from __future__ import annotations

import re

# Lives here (not catalog/registry.py, which originally defined this) so AVGECard.__str__ can use
# it without a circular import - registry.py imports from AVGECard.py, so AVGECard.py can't import
# label_for back from registry.py. Pure string logic, no dependency on any card class.
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_DISPLAY_NAMES = {
    "KikisHeadband": "Kiki's Headband",
    "SteinertBasement": "Steinert Basement Studio",
    "Victoria": "Victoria Chen",
}


def label_for(class_name: str) -> str:
    '''A human-readable display label for a class name - "HappyRuthJara" -> "Happy Ruth Jara",
    "AVGEBirb" -> "AVGE Birb". Purely cosmetic (used by server/deck_routes.py's catalog payload
    and AVGECard.__str__, not for any lookup) - imperfect on some acronym-adjacent edge cases
    (e.g. "AVGETShirt" -> "AVGET Shirt") is an acceptable tradeoff for a simple,
    dependency-free splitter.'''
    return _DISPLAY_NAMES.get(class_name, _CAMEL_SPLIT_RE.sub(" ", class_name))
