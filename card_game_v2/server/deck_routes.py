from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel

from ..catalog import registry
from ..constants import CARDS_PER_DECK, INITIAL_HAND_SIZE, MAX_BENCH_SIZE, NO_STARTING_ACTIVE_CARDS
from . import deck_rules
from .accounts import Account, AccountStore
from .deck_store import DeckStore, StoredDeck

# --- Request/response bodies ---
# Pydantic models live here, not protocol.py - protocol.py is explicitly the hand-mirrored WS
# protocol only (see its own top comment); this is a separate, REST-only surface.


class DeckWriteRequest(BaseModel):
    name: str
    cards: list[str]


class SelectDeckRequest(BaseModel):
    deck_id: str | None = None


def _error_detail(code: str, message: str) -> dict[str, str]:
    # Mirrors protocol.ErrorMessage's {code, message} shape, so the frontend's error handling
    # convention stays the same across the WS and REST surfaces.
    return {"code": code, "message": message}


def _deck_wire(deck: StoredDeck) -> dict[str, Any]:
    return {
        "deck_id": deck.deck_id,
        "name": deck.name,
        "cards": deck.cards,
        "created_at": deck.created_at,
        "updated_at": deck.updated_at,
    }


def _catalog_wire() -> dict[str, Any]:
    entries = registry.all_entries()
    return {
        "cards": [
            {
                "class_name": e.class_name,
                "kind": e.kind.value,
                "subtype": e.subtype,
                "label": registry.label_for(e.class_name),
            }
            for e in entries
        ],
        "rules": {
            "cards_per_deck": CARDS_PER_DECK,
            "max_decks": deck_rules.MAX_DECKS_PER_ACCOUNT,
            "max_copies_item_or_tool": deck_rules.MAX_COPIES_ITEM_OR_TOOL,
            "max_copies_default": deck_rules.MAX_COPIES_DEFAULT,
            "initial_hand_size": INITIAL_HAND_SIZE,
            "max_bench_size": MAX_BENCH_SIZE,
            "no_starting_active": sorted(NO_STARTING_ACTIVE_CARDS),
        },
    }


def build_deck_router(accounts: AccountStore, decks: DeckStore) -> APIRouter:
    '''Deck CRUD + the full catalog, as REST routes rather than new WS message types - see
    session's own migration plan for why (WS request/response correlation is server->client only;
    deck CRUD is client-initiated and orthogonal to any active game session). Auth is the same
    "remember me" auth_token accounts.py already hands out at login, read here from a bearer
    token instead of the WS's first-message login handshake.'''
    router = APIRouter()

    def _authenticate(authorization: str | None = Header(default=None)) -> Account:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(401, detail=_error_detail(
                "unauthorized", "Missing or malformed Authorization header.",
            ))
        token = authorization.removeprefix("Bearer ").strip()
        account = accounts.login_by_token(token)
        if account is None:
            raise HTTPException(401, detail=_error_detail(
                "unauthorized", "Invalid or expired auth token.",
            ))
        return account

    @router.get("/api/catalog")
    async def get_catalog() -> dict[str, Any]:
        return _catalog_wire()

    @router.get("/api/decks")
    async def list_decks(account: Account = Depends(_authenticate)) -> dict[str, Any]:
        stored = await decks.list_decks(account.account_id)
        selected_id = await decks.get_selected_deck_id(account.account_id)
        return {
            "decks": [_deck_wire(d) for d in stored],
            "selected_deck_id": selected_id,
            "max_decks": deck_rules.MAX_DECKS_PER_ACCOUNT,
        }

    @router.post("/api/decks", status_code=201)
    async def create_deck(
        body: DeckWriteRequest, account: Account = Depends(_authenticate),
    ) -> dict[str, Any]:
        try:
            created = await decks.create_deck(account.account_id, body.name, body.cards)
        except deck_rules.DeckLimitError as exc:
            raise HTTPException(409, detail=_error_detail(exc.code, exc.message)) from exc
        except deck_rules.DeckValidationError as exc:
            raise HTTPException(400, detail=_error_detail(exc.code, exc.message)) from exc
        return {"deck": _deck_wire(created)}

    # Registered BEFORE the /api/decks/{deck_id} routes below - FastAPI/Starlette matches routes
    # in registration order, and {deck_id} would otherwise greedily match the literal path
    # "/api/decks/selected" too (treating "selected" as a deck_id), shadowing this route entirely.
    @router.put("/api/decks/selected")
    async def select_deck(
        body: SelectDeckRequest, account: Account = Depends(_authenticate),
    ) -> dict[str, Any]:
        ok = await decks.set_selected_deck(account.account_id, body.deck_id)
        if not ok:
            raise HTTPException(404, detail=_error_detail("deck_not_found", "No such deck."))
        return {"selected_deck_id": body.deck_id}

    @router.put("/api/decks/{deck_id}")
    async def update_deck(
        deck_id: str, body: DeckWriteRequest, account: Account = Depends(_authenticate),
    ) -> dict[str, Any]:
        try:
            updated = await decks.update_deck(account.account_id, deck_id, body.name, body.cards)
        except deck_rules.DeckValidationError as exc:
            raise HTTPException(400, detail=_error_detail(exc.code, exc.message)) from exc
        if updated is None:
            raise HTTPException(404, detail=_error_detail("deck_not_found", "No such deck."))
        return {"deck": _deck_wire(updated)}

    @router.delete("/api/decks/{deck_id}", status_code=204)
    async def delete_deck(deck_id: str, account: Account = Depends(_authenticate)) -> Response:
        ok = await decks.delete_deck(account.account_id, deck_id)
        if not ok:
            raise HTTPException(404, detail=_error_detail("deck_not_found", "No such deck."))
        return Response(status_code=204)

    return router
