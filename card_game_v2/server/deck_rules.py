from __future__ import annotations

import collections
from typing import NoReturn, Sequence

from ..catalog import registry
from ..catalog.registry import CardKind
from ..constants import CARDS_PER_DECK

MAX_DECKS_PER_ACCOUNT = 10
MAX_COPIES_ITEM_OR_TOOL = 2
MAX_COPIES_DEFAULT = 1
MAX_DECK_NAME_LENGTH = 64


class DeckValidationError(ValueError):
    '''Raised by validate_deck_name/validate_deck_cards for any rule violation - `code` is a
    stable, machine-readable identifier (server/deck_routes.py maps these straight into a 400
    response body; the frontend's own deckRules.ts mirrors the same codes for live feedback while
    editing), `message` is the human-readable explanation shown to the user.'''

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class DeckLimitError(DeckValidationError):
    '''Raised specifically when an account already has MAX_DECKS_PER_ACCOUNT decks saved - kept
    as its own subclass (rather than just another DeckValidationError code) since callers that
    care about count-based backpressure (server/deck_routes.py, to return 409 instead of 400) can
    catch it distinctly from a malformed-deck rejection.'''

    def __init__(self) -> None:
        super().__init__(
            "deck_limit_reached",
            f"You already have {MAX_DECKS_PER_ACCOUNT} saved decks - delete one before saving another.",
        )


def max_copies_for(kind: CardKind) -> int:
    '''Adopts the original card_game's deck-builder rule: items and tools can appear twice,
    everything else (characters, supporters, stadiums) only once.'''
    if kind in (CardKind.ITEM, CardKind.TOOL):
        return MAX_COPIES_ITEM_OR_TOOL
    return MAX_COPIES_DEFAULT


def validate_deck_name(name: str) -> str:
    '''Strips surrounding whitespace and returns the cleaned name - never silently truncates an
    overlong name (the legacy deck builder did; a silently-renamed deck is worse than a rejected
    save).'''
    stripped = name.strip()
    if not stripped:
        _raise("invalid_name", "Deck name can't be empty.")
    if len(stripped) > MAX_DECK_NAME_LENGTH:
        _raise(
            "invalid_name",
            f"Deck name can't be longer than {MAX_DECK_NAME_LENGTH} characters.",
        )
    return stripped


def validate_deck_cards(cards: Sequence[str]) -> list[str]:
    '''The full deck-legality ruleset, checked in order: exact card count, every name resolves in
    the catalog, per-card copy limits by kind, at least one character card. Returns the validated
    list unchanged on success (never mutates/reorders it - callers that care about the user's own
    ordering, e.g. round-tripping a saved deck back to the builder, can rely on that).'''
    cards = list(cards)
    if len(cards) != CARDS_PER_DECK:
        _raise(
            "wrong_card_count",
            f"A deck must have exactly {CARDS_PER_DECK} cards (got {len(cards)}).",
        )

    counts = collections.Counter(cards)
    has_character = False
    for name, count in counts.items():
        found = registry.entry(name)
        if found is None:
            _raise("unknown_card", f"Unknown card: {name!r}.")
        if found.kind is CardKind.CHARACTER:
            has_character = True
        limit = max_copies_for(found.kind)
        if count > limit:
            copies = "copy" if limit == 1 else "copies"
            _raise(
                "too_many_copies",
                f"{name} can only appear {limit} {copies} per deck (found {count}).",
            )

    if not has_character:
        _raise("no_character_card", "A deck must contain at least one character card.")

    return cards


def _raise(code: str, message: str) -> NoReturn:
    raise DeckValidationError(code, message)
