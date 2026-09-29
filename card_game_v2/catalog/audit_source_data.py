"""Deterministic, privacy-scoped audit of the approved 2026-09-25 card exports.

Only the rule-bearing columns named in the migration plan are indexed below. The
remaining form columns are never loaded into a row model, emitted, logged, or served.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..avge_abstracts.AVGECard import AVGECharacterCard
from ..avge_abstracts.AVGEDeck import DeckType
from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ..constants import User
from ..core.AVGEIOManager import AVGEIO
from . import registry


SOURCE_DIR = Path(__file__).resolve().parent / "source_data" / "2026-09-25"
EXPECTED_HASHES = {
    "Characters.csv": "9539b01bb8aee4bad005c4c0fa72e70cbb76cf5b78349be6a3591c9a0f4e145e",
    "Others.csv": "934923e585236e2b646adfb14be8cc800332d8edde243634a985e02ae13d9c00",
}

# CSV positions are deliberately explicit so ignored columns are not converted to
# dictionaries or otherwise propagated. These are the only character rule fields.
_CHAR_NAME = 1
_CHAR_FINALIZED = 2
_CHAR_TYPE = 4
_CHAR_HP = 5
_CHAR_RETREAT = 6
_CHAR_MOVE_1 = 7
_CHAR_MOVE_2 = 8

_OTHER_NAME = 0
_OTHER_TYPE = 1
_OTHER_DESCRIPTION = 2

ALIASES = {
    "Ben Jose Cherek III": "BenCherekIII",
    "Steinert Basement Studio": "SteinertBasement",
    "Victoria Chen": "Victoria",
}
APPROVED_UNFINISHED_CHARACTERS = {"Jaden Ouyang", "Philip Yao"}
EXPECTED_STATUS_ROWS = {"Maid", "Goon", "Arranger"}

_CHARACTER_TYPE_NAMES = {
    "brass": "BRASS",
    "choir": "CHOIR",
    "guitar": "GUITAR",
    "percussion": "PERCUSSION",
    "piano": "PIANO",
    "string": "STRING",
    "strings": "STRING",
    "perc": "PERCUSSION",
    "woodwind": "WOODWIND",
    "woodwinds": "WOODWIND",
    "ww": "WOODWIND",
}
_OTHER_KIND_NAMES = {
    "item": registry.CardKind.ITEM,
    "stadium": registry.CardKind.STADIUM,
    "supporter": registry.CardKind.SUPPORTER,
    "tool": registry.CardKind.TOOL,
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _class_name(source_name: str) -> str:
    return ALIASES.get(source_name, re.sub(r"[^A-Za-z0-9]", "", source_name))


def _action_name(move: str) -> str:
    first_line = move.strip().splitlines()[0] if move.strip() else ""
    first_line = re.sub(r"^\([^)]*\)\s*", "", first_line)
    first_line = first_line.split(":", 1)[0]
    first_line = re.sub(r"\s+\d+(?:\+)?\s*$", "", first_line)
    return first_line.strip().rstrip("!")


def _read_characters() -> list[dict[str, str]]:
    with (SOURCE_DIR / "Characters.csv").open(
        newline="", encoding="utf-8-sig",
    ) as source:
        rows = csv.reader(source)
        next(rows)
        return [{
            "name": row[_CHAR_NAME].strip(),
            "finalized": row[_CHAR_FINALIZED].strip(),
            "type": row[_CHAR_TYPE].strip(),
            "hp": row[_CHAR_HP].strip(),
            "retreat": row[_CHAR_RETREAT].strip(),
            "move_1": row[_CHAR_MOVE_1].strip(),
            "move_2": row[_CHAR_MOVE_2].strip(),
        } for row in rows if row[_CHAR_NAME].strip()]


def _read_others() -> list[dict[str, str]]:
    with (SOURCE_DIR / "Others.csv").open(
        newline="", encoding="utf-8-sig",
    ) as source:
        rows = csv.reader(source)
        next(rows)
        return [{
            "name": row[_OTHER_NAME].strip(),
            "type": row[_OTHER_TYPE].strip(),
            "description": row[_OTHER_DESCRIPTION].strip(),
        } for row in rows if row[_OTHER_NAME].strip()]


def build_report() -> dict[str, Any]:
    entries = registry.all_entries()
    entries_by_name = {entry.class_name: entry for entry in entries}
    characters = [
        row for row in _read_characters()
        if row["finalized"] == "TRUE" or row["name"] in APPROVED_UNFINISHED_CHARACTERS
    ]
    others = _read_others()
    deck_others = [row for row in others if row["type"].casefold() != "status"]
    status_rows = {row["name"] for row in others if row["type"].casefold() == "status"}

    source_character_names = {_class_name(row["name"]) for row in characters}
    source_other_names = {_class_name(row["name"]) for row in deck_others}
    registry_character_names = {
        entry.class_name for entry in entries if entry.kind is registry.CardKind.CHARACTER
    }
    registry_other_names = {
        entry.class_name for entry in entries if entry.kind is not registry.CardKind.CHARACTER
    }

    env = AVGEEnvironment(
        AVGEIO(),
        {
            User.PLAYER_1: [entry.card_class for entry in entries],
            User.PLAYER_2: [entry.card_class for entry in entries],
        },
        [],
    )
    instances = {
        type(card).__name__: card
        for card in env.players[User.PLAYER_1].card_piles[DeckType.DECK]
    }

    stat_mismatches: list[dict[str, Any]] = []
    action_name_mismatches: list[dict[str, Any]] = []
    for row in sorted(characters, key=lambda item: item["name"]):
        class_name = _class_name(row["name"])
        card = instances.get(class_name)
        if not isinstance(card, AVGECharacterCard):
            continue
        comparisons = {
            "type": (
                _CHARACTER_TYPE_NAMES.get(row["type"].casefold(), row["type"].upper()),
                card.card_type.name,
            ),
            "hp": (int(row["hp"]), card.max_hp),
            "retreat": (int(row["retreat"]), card.retreat_cost),
        }
        for field, (source_value, implementation_value) in comparisons.items():
            if source_value != implementation_value:
                stat_mismatches.append({
                    "card": class_name,
                    "field": field,
                    "source": source_value,
                    "implementation": implementation_value,
                })
        implemented_actions = {
            re.sub(r"[^a-z0-9]", "", action.name.casefold()) for action in card.actions.values()
        }
        for field in ("move_1", "move_2"):
            expected_action = _action_name(row[field])
            normalized = re.sub(r"[^a-z0-9]", "", expected_action.casefold())
            if normalized and not any(
                implemented.startswith(normalized) for implemented in implemented_actions
            ):
                action_name_mismatches.append({
                    "card": class_name,
                    "field": field,
                    "source_action_name": expected_action,
                    "implementation_action_names": sorted(
                        action.name for action in card.actions.values()
                    ),
                })

    kind_mismatches: list[dict[str, str]] = []
    for row in sorted(deck_others, key=lambda item: item["name"]):
        class_name = _class_name(row["name"])
        entry = entries_by_name.get(class_name)
        expected_kind = _OTHER_KIND_NAMES.get(row["type"].casefold())
        if entry is not None and expected_kind is not None and entry.kind is not expected_kind:
            kind_mismatches.append({
                "card": class_name,
                "source": expected_kind.value,
                "implementation": entry.kind.value,
            })

    counts = Counter(entry.kind.value for entry in entries)
    return {
        "source_hashes": {
            name: {"expected": expected, "actual": _hash(SOURCE_DIR / name)}
            for name, expected in sorted(EXPECTED_HASHES.items())
        },
        "counts": {
            "source_characters": len(characters),
            "source_noncharacters": len(deck_others),
            "source_statuses": len(status_rows),
            "registry_total": len(entries),
            "registry_by_kind": dict(sorted(counts.items())),
        },
        "identity_mismatches": {
            "missing_characters": sorted(source_character_names - registry_character_names),
            "unexpected_characters": sorted(registry_character_names - source_character_names),
            "missing_noncharacters": sorted(source_other_names - registry_other_names),
            "unexpected_noncharacters": sorted(registry_other_names - source_other_names),
        },
        "stat_mismatches": stat_mismatches,
        "action_name_mismatches": action_name_mismatches,
        "kind_mismatches": kind_mismatches,
        "status_rows": {
            "found": sorted(status_rows),
            "missing": sorted(EXPECTED_STATUS_ROWS - status_rows),
            "unexpected": sorted(status_rows - EXPECTED_STATUS_ROWS),
        },
    }


def main() -> None:
    print(json.dumps(build_report(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
