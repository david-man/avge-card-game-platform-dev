import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from ...constants import CARDS_PER_DECK, NO_STARTING_ACTIVE_CARDS
from .. import deck_rules
from ..app import create_app


def _legal_deck(character: str = "AshleyToby") -> list[str]:
    items = [
        "AVGEBirb", "AnnotatedScore", "BAIEmail", "BUOStand", "Camera", "CastReserve",
        "ConcertProgram", "ConcertRoster", "ConcertTicket", "CorruptedMusescoreFile",
        "DressRehearsalRoster", "FoldingStand", "IceSkates", "MatchaLatte", "MikuOtamatone",
        "Otamatone", "PrintedScore", "RaffleTicket", "StandardMusescoreFile",
    ]
    deck = [character] + items
    assert len(deck) == CARDS_PER_DECK
    return deck


class DeckRoutesTestBase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.app = create_app(data_dir=Path(self._tmpdir.name))
        self.client = TestClient(self.app)

    def _login(self, username: str) -> dict[str, str]:
        with self.client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "login", "username": username})
            message = ws.receive_json()
        return {"Authorization": f"Bearer {message['auth_token']}"}


class CatalogRouteTests(DeckRoutesTestBase):
    def test_catalog_is_public_and_lists_every_card(self):
        response = self.client.get("/api/catalog")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["cards"]), 123)
        for card in body["cards"]:
            self.assertIn(card["kind"], {"character", "item", "tool", "stadium", "supporter"})

    def test_rules_block_matches_constants_and_deck_rules(self):
        body = self.client.get("/api/catalog").json()
        rules = body["rules"]
        self.assertEqual(rules["cards_per_deck"], CARDS_PER_DECK)
        self.assertEqual(rules["max_decks"], deck_rules.MAX_DECKS_PER_ACCOUNT)
        self.assertEqual(rules["max_copies_item_or_tool"], deck_rules.MAX_COPIES_ITEM_OR_TOOL)
        self.assertEqual(rules["max_copies_default"], deck_rules.MAX_COPIES_DEFAULT)
        self.assertEqual(rules["no_starting_active"], sorted(NO_STARTING_ACTIVE_CARDS))


class AuthTests(DeckRoutesTestBase):
    def test_missing_header_is_401_on_every_authed_route(self):
        self.assertEqual(self.client.get("/api/decks").status_code, 401)
        self.assertEqual(
            self.client.post("/api/decks", json={"name": "x", "cards": []}).status_code, 401,
        )
        self.assertEqual(
            self.client.put("/api/decks/some-id", json={"name": "x", "cards": []}).status_code,
            401,
        )
        self.assertEqual(self.client.delete("/api/decks/some-id").status_code, 401)
        self.assertEqual(
            self.client.put("/api/decks/selected", json={"deck_id": None}).status_code, 401,
        )

    def test_garbage_token_is_401(self):
        headers = {"Authorization": "Bearer not-a-real-token"}
        self.assertEqual(self.client.get("/api/decks", headers=headers).status_code, 401)

    def test_malformed_header_is_401(self):
        headers = {"Authorization": "not-even-bearer-shaped"}
        self.assertEqual(self.client.get("/api/decks", headers=headers).status_code, 401)


class DeckCrudTests(DeckRoutesTestBase):
    def test_full_crud_happy_path(self):
        headers = self._login("alice")

        listed = self.client.get("/api/decks", headers=headers).json()
        self.assertEqual(listed["decks"], [])
        self.assertIsNone(listed["selected_deck_id"])
        self.assertEqual(listed["max_decks"], deck_rules.MAX_DECKS_PER_ACCOUNT)

        created = self.client.post(
            "/api/decks", json={"name": "My Deck", "cards": _legal_deck()}, headers=headers,
        )
        self.assertEqual(created.status_code, 201)
        deck_id = created.json()["deck"]["deck_id"]
        self.assertEqual(created.json()["deck"]["name"], "My Deck")

        listed_again = self.client.get("/api/decks", headers=headers).json()
        self.assertEqual(len(listed_again["decks"]), 1)

        updated = self.client.put(
            f"/api/decks/{deck_id}",
            json={"name": "Renamed", "cards": _legal_deck("EmilyWang")},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["deck"]["name"], "Renamed")

        selected = self.client.put(
            "/api/decks/selected", json={"deck_id": deck_id}, headers=headers,
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.json()["selected_deck_id"], deck_id)
        self.assertEqual(
            self.client.get("/api/decks", headers=headers).json()["selected_deck_id"], deck_id,
        )

        deleted = self.client.delete(f"/api/decks/{deck_id}", headers=headers)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/decks", headers=headers).json()["decks"], [])

    def test_validation_failure_codes(self):
        headers = self._login("alice")

        wrong_count = self.client.post(
            "/api/decks", json={"name": "x", "cards": ["AshleyToby"]}, headers=headers,
        )
        self.assertEqual(wrong_count.status_code, 400)
        self.assertEqual(wrong_count.json()["detail"]["code"], "wrong_card_count")

        unknown = self.client.post(
            "/api/decks",
            json={"name": "x", "cards": ["NotARealCard"] + _legal_deck()[1:]},
            headers=headers,
        )
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.json()["detail"]["code"], "unknown_card")

        too_many_copies = self.client.post(
            "/api/decks",
            json={"name": "x", "cards": ["AshleyToby", "AshleyToby"] + _legal_deck()[2:]},
            headers=headers,
        )
        self.assertEqual(too_many_copies.status_code, 400)
        self.assertEqual(too_many_copies.json()["detail"]["code"], "too_many_copies")

        no_character = self.client.post(
            "/api/decks",
            json={"name": "x", "cards": _legal_deck()[1:] + ["Angel"]},
            headers=headers,
        )
        self.assertEqual(no_character.status_code, 400)
        self.assertEqual(no_character.json()["detail"]["code"], "no_character_card")

        bad_name = self.client.post(
            "/api/decks", json={"name": "   ", "cards": _legal_deck()}, headers=headers,
        )
        self.assertEqual(bad_name.status_code, 400)
        self.assertEqual(bad_name.json()["detail"]["code"], "invalid_name")

    def test_the_eleventh_deck_is_409(self):
        headers = self._login("alice")
        for i in range(deck_rules.MAX_DECKS_PER_ACCOUNT):
            resp = self.client.post(
                "/api/decks", json={"name": f"Deck {i}", "cards": _legal_deck()}, headers=headers,
            )
            self.assertEqual(resp.status_code, 201)
        eleventh = self.client.post(
            "/api/decks", json={"name": "One Too Many", "cards": _legal_deck()}, headers=headers,
        )
        self.assertEqual(eleventh.status_code, 409)
        self.assertEqual(eleventh.json()["detail"]["code"], "deck_limit_reached")

    def test_crud_against_another_accounts_deck_is_404(self):
        alice_headers = self._login("alice")
        bob_headers = self._login("bob")
        created = self.client.post(
            "/api/decks", json={"name": "Alice's", "cards": _legal_deck()}, headers=alice_headers,
        )
        deck_id = created.json()["deck"]["deck_id"]

        update = self.client.put(
            f"/api/decks/{deck_id}", json={"name": "Stolen", "cards": _legal_deck()},
            headers=bob_headers,
        )
        self.assertEqual(update.status_code, 404)

        delete = self.client.delete(f"/api/decks/{deck_id}", headers=bob_headers)
        self.assertEqual(delete.status_code, 404)

        select = self.client.put(
            "/api/decks/selected", json={"deck_id": deck_id}, headers=bob_headers,
        )
        self.assertEqual(select.status_code, 404)

    def test_selecting_a_nonexistent_deck_is_404(self):
        headers = self._login("alice")
        resp = self.client.put(
            "/api/decks/selected", json={"deck_id": "no-such-id"}, headers=headers,
        )
        self.assertEqual(resp.status_code, 404)

    def test_selecting_none_clears_the_selection(self):
        headers = self._login("alice")
        created = self.client.post(
            "/api/decks", json={"name": "Mine", "cards": _legal_deck()}, headers=headers,
        )
        deck_id = created.json()["deck"]["deck_id"]
        self.client.put("/api/decks/selected", json={"deck_id": deck_id}, headers=headers)

        cleared = self.client.put("/api/decks/selected", json={"deck_id": None}, headers=headers)
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(
            self.client.get("/api/decks", headers=headers).json()["selected_deck_id"],
        )


if __name__ == "__main__":
    unittest.main()
