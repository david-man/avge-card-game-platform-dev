from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket

from . import config
from ..catalog import registry
from .accounts import AccountStore
from .deck_routes import build_deck_router
from .deck_store import DeckStore
from .logging_setup import configure_logging
from .matchmaker import Matchmaker
from .ws_routes import websocket_endpoint


def create_app(*, data_dir: Path | None = None) -> FastAPI:
    '''`data_dir` overrides where the account/deck stores persist to - defaults to
    config.DATA_DIR (the real on-disk location). Tests should always pass a temp directory here
    instead of writing into the real server/data/ (see server/tests/_ws_test_utils.py).'''
    configure_logging()
    # Warm the catalog registry at boot rather than on the first /api/catalog request or the
    # first game that resolves a custom deck - an import error in a catalog file should fail
    # startup, not surface as a random 500/game-start failure later.
    registry.all_entries()
    app = FastAPI()
    matchmaker = Matchmaker()
    resolved_data_dir = data_dir if data_dir is not None else config.DATA_DIR
    accounts = AccountStore(resolved_data_dir / config.ACCOUNTS_FILE_PATH.name)
    decks = DeckStore(resolved_data_dir / config.DECKS_DB_PATH.name)
    # Not read anywhere in this module - the `ws` closure below captures `matchmaker` directly,
    # which pyright can track as a Matchmaker rather than the Any that reading it back off
    # app.state would produce. This exists solely for tests (e.g. test_both_disconnected.py) that
    # need to reach the live Matchmaker from an app built via create_app().
    app.state.matchmaker = matchmaker

    app.include_router(build_deck_router(accounts, decks))

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        # Registered via the decorator's side effect - pyright can't see FastAPI's routing
        # table, so it looks unused even though it's the actual "/ws" handler.
        await websocket_endpoint(websocket, matchmaker, accounts, decks)

    return app


app = create_app()
