from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from dataclasses import dataclass
from enum import StrEnum

from .. import catalog
from ..avge_abstracts.AVGECard import (
    AVGECard, AVGECharacterCard, AVGEItemCard, AVGEStadiumCard, AVGESupporterCard, AVGEToolCard,
)

# Instrument sub-package names under catalog/characters/ - the only thing `subtype` is ever
# derived from (never from `kind`, and never used to classify a card - isinstance against the
# five base classes below is the sole classification authority, matching every other call site in
# this codebase, e.g. serialization.py's card_to_wire, io_adapter.py's Phase2 kind checks).
_CHARACTER_SUBTYPES = frozenset({
    "brass", "choir", "guitar", "percussion", "piano", "strings", "woodwinds",
})


class CardKind(StrEnum):
    CHARACTER = "character"
    ITEM = "item"
    TOOL = "tool"
    STADIUM = "stadium"
    SUPPORTER = "supporter"


# Order matters: AVGECharacterCard is checked first since it's the most specific/common case, but
# none of these five actually overlap in this codebase's class hierarchy - each concrete card
# class subclasses exactly one of them.
_KIND_BY_BASE: tuple[tuple[type[AVGECard], CardKind], ...] = (
    (AVGECharacterCard, CardKind.CHARACTER),
    (AVGEToolCard, CardKind.TOOL),
    (AVGEItemCard, CardKind.ITEM),
    (AVGEStadiumCard, CardKind.STADIUM),
    (AVGESupporterCard, CardKind.SUPPORTER),
)


def kind_of(card_class: type[AVGECard]) -> CardKind:
    '''The single source of truth for "what kind of card is this" - isinstance against the five
    base classes in avge_abstracts/AVGECard.py, the same distinction already used ad hoc
    throughout the codebase (serialization.py's card_to_wire, io_adapter.py's Phase2 legality
    checks). Raises for anything that isn't a concrete subclass of exactly one of them - should be
    unreachable for anything all_entries() ever returns.'''
    for base, kind in _KIND_BY_BASE:
        if issubclass(card_class, base):
            return kind
    raise ValueError(f"{card_class!r} is not a classifiable AVGECard subclass")


@dataclass(frozen=True)
class CatalogEntry:
    class_name: str
    kind: CardKind
    card_class: type[AVGECard]
    # Instrument sub-package name (brass/choir/guitar/percussion/piano/strings/woodwinds) for
    # characters only - None for every other kind.
    subtype: str | None


_entries: tuple[CatalogEntry, ...] | None = None


def _build_entries() -> tuple[CatalogEntry, ...]:
    by_name: dict[str, CatalogEntry] = {}
    for module_info in pkgutil.walk_packages(catalog.__path__, catalog.__name__ + "."):
        name = module_info.name
        if name == __name__:
            # This module itself lives inside catalog/ but defines no cards - skip it explicitly
            # rather than relying on the isinstance/isabstract filters below to exclude it.
            continue
        module = importlib.import_module(name)
        parts = name.split(".")
        # catalog.characters.strings.AshleyToby -> parts[2] == "characters", parts[3] == "strings"
        # catalog.items.Camera -> parts[2] == "items", no instrument segment.
        subtype = parts[3] if len(parts) > 3 and parts[2] == "characters" else None
        if subtype is not None and subtype not in _CHARACTER_SUBTYPES:
            subtype = None
        for attr_name, obj in vars(module).items():
            if not inspect.isclass(obj):
                continue
            if not issubclass(obj, AVGECard):
                continue
            # Every card module imports its base class(es) by name (`from ...avge_abstracts.
            # AVGECard import AVGEItemCard, ...`) - without this check, every one of those
            # re-exported imports would look like a locally-defined card too.
            if obj.__module__ != name:
                continue
            if inspect.isabstract(obj):
                # Excludes AVGECard/AVGECharacterCard and the four thin AVGE*Card bases
                # themselves - each still has at least one unimplemented @abstractmethod
                # (on_transfer / play_card) until a concrete leaf class overrides it.
                continue
            card_class = obj
            class_name = attr_name
            if class_name in by_name:
                raise ValueError(
                    f"Duplicate catalog class name {class_name!r}: defined in both "
                    f"{by_name[class_name].card_class.__module__!r} and {name!r}"
                )
            kind = kind_of(card_class)
            by_name[class_name] = CatalogEntry(
                class_name=class_name, kind=kind, card_class=card_class,
                subtype=subtype if kind == CardKind.CHARACTER else None,
            )
    return tuple(sorted(by_name.values(), key=lambda e: e.class_name))


def all_entries() -> tuple[CatalogEntry, ...]:
    '''Every deck-buildable card in the catalog, sorted by class name. Built once by walking the
    whole catalog/ package tree (there is no hand-maintained registry anywhere in this codebase to
    read from instead) and cached for the life of the process - warm this at server startup
    (see server/app.py's create_app()) so an import error in a catalog file fails boot, not a
    random first request.'''
    global _entries
    if _entries is None:
        _entries = _build_entries()
    return _entries


def entry(class_name: str) -> CatalogEntry | None:
    for e in all_entries():
        if e.class_name == class_name:
            return e
    return None


def card_class(class_name: str) -> type[AVGECard] | None:
    found = entry(class_name)
    return found.card_class if found is not None else None


_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def label_for(class_name: str) -> str:
    '''A human-readable display label for a class name - "HappyRuthJara" -> "Happy Ruth Jara",
    "AVGEBirb" -> "AVGE Birb". Purely cosmetic (used by server/deck_routes.py's catalog payload,
    not for any lookup) - imperfect on some acronym-adjacent edge cases (e.g. "AVGETShirt" ->
    "AVGET Shirt") is an acceptable tradeoff for a simple, dependency-free splitter.'''
    return _CAMEL_SPLIT_RE.sub(" ", class_name)
