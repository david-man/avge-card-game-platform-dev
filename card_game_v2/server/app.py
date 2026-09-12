from __future__ import annotations

from fastapi import FastAPI, WebSocket

from . import config
from .accounts import AccountStore
from .logging_setup import configure_logging
from .matchmaker import Matchmaker
from .ws_routes import websocket_endpoint


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI()
    matchmaker = Matchmaker()
    accounts = AccountStore(config.ACCOUNTS_FILE_PATH)
    # Not read anywhere in this module - the `ws` closure below captures `matchmaker` directly,
    # which pyright can track as a Matchmaker rather than the Any that reading it back off
    # app.state would produce. This exists solely for tests (e.g. test_both_disconnected.py) that
    # need to reach the live Matchmaker from an app built via create_app().
    app.state.matchmaker = matchmaker

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        # Registered via the decorator's side effect - pyright can't see FastAPI's routing
        # table, so it looks unused even though it's the actual "/ws" handler.
        await websocket_endpoint(websocket, matchmaker, accounts)

    return app


app = create_app()
