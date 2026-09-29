import unittest

from ...catalog.registry import CardKind
from ...constants import CARDS_PER_DECK
from .. import deck_rules


def _deck_of(*, characters: int = 0, items: int = 0, tools: int = 0,
             supporters: int = 0, stadiums: int = 0) -> list[str]:
    '''Builds a deck's card-name list from repeatable, known-good catalog entries of each kind -
    AshleyToby (character), Camera (item), Bucket (tool), Angel (supporter), MainHall (stadium) -
    each repeated as many times as requested (tests that want to exceed a copy limit pass a count
    higher than that kind's own max_copies_for()).'''
    return (
        ["AshleyToby"] * characters + ["Camera"] * items + ["Bucket"] * tools
        + ["Angel"] * supporters + ["MainHall"] * stadiums
    )


class MaxCopiesForTests(unittest.TestCase):
    def test_item_and_tool_allow_two_copies(self):
        self.assertEqual(deck_rules.max_copies_for(CardKind.ITEM), 2)
        self.assertEqual(deck_rules.max_copies_for(CardKind.TOOL), 2)

    def test_everything_else_allows_one_copy(self):
        self.assertEqual(deck_rules.max_copies_for(CardKind.CHARACTER), 1)
        self.assertEqual(deck_rules.max_copies_for(CardKind.SUPPORTER), 1)
        self.assertEqual(deck_rules.max_copies_for(CardKind.STADIUM), 1)


class ValidateDeckNameTests(unittest.TestCase):
    def test_strips_whitespace(self):
        self.assertEqual(deck_rules.validate_deck_name("  My Deck  "), "My Deck")

    def test_rejects_empty(self):
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_name("")
        self.assertEqual(ctx.exception.code, "invalid_name")

    def test_rejects_whitespace_only(self):
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_name("   ")
        self.assertEqual(ctx.exception.code, "invalid_name")

    def test_rejects_overlong_names_rather_than_truncating(self):
        overlong = "x" * (deck_rules.MAX_DECK_NAME_LENGTH + 1)
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_name(overlong)
        self.assertEqual(ctx.exception.code, "invalid_name")

    def test_exactly_max_length_is_accepted(self):
        exact = "x" * deck_rules.MAX_DECK_NAME_LENGTH
        self.assertEqual(deck_rules.validate_deck_name(exact), exact)


class ValidateDeckCardsTests(unittest.TestCase):
    def test_wrong_count_is_rejected(self):
        too_few = _deck_of(characters=1, items=(CARDS_PER_DECK - 2))
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(too_few)
        self.assertEqual(ctx.exception.code, "wrong_card_count")

        too_many = _deck_of(characters=1, items=CARDS_PER_DECK)
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(too_many)
        self.assertEqual(ctx.exception.code, "wrong_card_count")

    def test_unknown_card_name_is_rejected_and_named(self):
        deck = ["AshleyToby", "NotARealCard"] + _unique_items(CARDS_PER_DECK - 2, exclude=set())
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(deck)
        self.assertEqual(ctx.exception.code, "unknown_card")
        self.assertIn("NotARealCard", ctx.exception.message)

    def test_two_copies_of_an_item_is_allowed(self):
        deck = ["AshleyToby", "Camera", "Camera"] + _unique_items(
            CARDS_PER_DECK - 3, exclude={"Camera"},
        )
        validated = deck_rules.validate_deck_cards(deck)
        self.assertEqual(sorted(validated), sorted(deck))

    def test_three_copies_of_an_item_is_rejected(self):
        deck = ["AshleyToby"] + ["Camera"] * 3
        deck += _unique_items(CARDS_PER_DECK - len(deck), exclude={"Camera"})
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(deck)
        self.assertEqual(ctx.exception.code, "too_many_copies")

    def test_three_copies_of_a_tool_is_rejected(self):
        deck = ["AshleyToby"] + ["Bucket"] * 3
        deck += _unique_items(CARDS_PER_DECK - len(deck), exclude=set())
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(deck)
        self.assertEqual(ctx.exception.code, "too_many_copies")

    def test_two_copies_of_a_character_is_rejected(self):
        deck = ["AshleyToby"] * 2
        deck += _unique_items(CARDS_PER_DECK - len(deck), exclude=set())
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(deck)
        self.assertEqual(ctx.exception.code, "too_many_copies")

    def test_two_copies_of_a_supporter_is_rejected(self):
        deck = ["AshleyToby"] + ["Angel"] * 2
        deck += _unique_items(CARDS_PER_DECK - len(deck), exclude=set())
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(deck)
        self.assertEqual(ctx.exception.code, "too_many_copies")

    def test_two_copies_of_a_stadium_is_rejected(self):
        deck = ["AshleyToby"] + ["MainHall"] * 2
        deck += _unique_items(CARDS_PER_DECK - len(deck), exclude=set())
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(deck)
        self.assertEqual(ctx.exception.code, "too_many_copies")

    def test_no_character_card_is_rejected(self):
        deck = _unique_items(CARDS_PER_DECK, exclude=set())
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(deck)
        self.assertEqual(ctx.exception.code, "no_character_card")

    def test_deck_whose_only_characters_cannot_start_is_rejected(self):
        deck = ["BenCherekIII"] + _unique_items(CARDS_PER_DECK - 1, exclude=set())
        with self.assertRaises(deck_rules.DeckValidationError) as ctx:
            deck_rules.validate_deck_cards(deck)
        self.assertEqual(ctx.exception.code, "no_starter_character")

    def test_a_restricted_character_is_fine_alongside_one_that_can_start(self):
        deck = ["BenCherekIII", "AshleyToby"] + _unique_items(CARDS_PER_DECK - 2, exclude=set())
        self.assertEqual(sorted(deck_rules.validate_deck_cards(deck)), sorted(deck))

    def test_exactly_one_character_is_the_legal_minimum(self):
        deck = ["AshleyToby"] + _unique_items(CARDS_PER_DECK - 1, exclude=set())
        validated = deck_rules.validate_deck_cards(deck)
        self.assertEqual(sorted(validated), sorted(deck))

    def test_does_not_mutate_or_reorder_the_input(self):
        deck = ["AshleyToby"] + _unique_items(CARDS_PER_DECK - 1, exclude=set())
        original = list(deck)
        result = deck_rules.validate_deck_cards(deck)
        self.assertEqual(result, original)


_ALL_ITEM_NAMES = [
    "AVGEBirb", "AnnotatedScore", "BAIEmail", "BUOStand", "Camera", "CastReserve",
    "ConcertProgram", "ConcertRoster", "ConcertTicket", "CorruptedMusescoreFile",
    "DressRehearsalRoster", "FoldingStand", "IceSkates", "MatchaLatte", "MikuOtamatone",
    "Otamatone", "PrintedScore", "RaffleTicket", "StandardMusescoreFile",
    "StrawberryMatchaLatte", "VideoCamera",
]


def _unique_items(count: int, exclude: set[str]) -> list[str]:
    '''`count` distinct item-card names (max 1 copy each requested here, though items themselves
    allow up to 2) not already present in `exclude` - lets deck-composition tests pad out to
    exactly CARDS_PER_DECK without accidentally tripping the copy-limit rule under test.'''
    available = [name for name in _ALL_ITEM_NAMES if name not in exclude]
    if count > len(available):
        raise ValueError("not enough distinct item names for this test fixture")
    return available[:count]


if __name__ == "__main__":
    unittest.main()
