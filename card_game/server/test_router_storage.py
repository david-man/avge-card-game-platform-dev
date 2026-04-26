from __future__ import annotations

from pathlib import Path

from card_game.server.router_storage import RouterStorage


def test_user_and_session_roundtrip(tmp_path: Path) -> None:
    storage = RouterStorage(str(tmp_path / "router.sqlite3"))

    user_id = storage.get_or_create_user("alice")
    storage.create_or_update_session("session-a", user_id, ttl_seconds=60)

    loaded = storage.get_session("session-a")
    assert loaded is not None
    assert loaded.session_id == "session-a"
    assert loaded.user_id == user_id
    assert loaded.username == "alice"


def test_deck_crud_and_selected_deck(tmp_path: Path) -> None:
    storage = RouterStorage(str(tmp_path / "router.sqlite3"))

    user_id = storage.get_or_create_user("bob")
    deck = storage.create_deck(user_id, "Deck One", '{"cards":["A","B"]}')

    listed = storage.list_decks_for_user(user_id)
    assert len(listed) == 1
    assert listed[0].deck_id == deck.deck_id

    updated = storage.update_deck(deck.deck_id, user_id, "Deck Updated", '{"cards":["X"]}')
    assert updated is True

    selected_ok = storage.set_selected_deck(user_id, deck.deck_id)
    assert selected_ok is True

    selected = storage.get_selected_deck(user_id)
    assert selected is not None
    assert selected["deck_id"] == deck.deck_id

    deleted = storage.delete_deck(deck.deck_id, user_id)
    assert deleted is True
    assert storage.get_selected_deck(user_id) is None


def test_set_selected_deck_rejects_foreign_deck(tmp_path: Path) -> None:
    storage = RouterStorage(str(tmp_path / "router.sqlite3"))

    user_a = storage.get_or_create_user("u1")
    user_b = storage.get_or_create_user("u2")

    deck = storage.create_deck(user_a, "A Deck", '{"cards":["A"]}')
    selected_ok = storage.set_selected_deck(user_b, deck.deck_id)
    assert selected_ok is False


def test_list_active_sessions_for_user_excludes_revoked(tmp_path: Path) -> None:
    storage = RouterStorage(str(tmp_path / "router.sqlite3"))

    user_id = storage.get_or_create_user("active-user")
    storage.create_or_update_session("session-a", user_id, ttl_seconds=60)
    storage.create_or_update_session("session-b", user_id, ttl_seconds=60)

    active_before = set(storage.list_active_session_ids_for_user(user_id))
    assert active_before == {"session-a", "session-b"}

    storage.revoke_session("session-a")

    active_after = set(storage.list_active_session_ids_for_user(user_id))
    assert active_after == {"session-b"}
