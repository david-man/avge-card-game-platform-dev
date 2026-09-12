from __future__ import annotations

import queue
import threading
import time
from typing import Any


class QueuedWebSocket:
    '''Wraps a Starlette WebSocketTestSession with a background reader thread + Queue, so a test
    can poll multiple sockets with a bounded timeout instead of blocking forever on one socket's
    receive_json() (which has no timeout parameter of its own). Needed because which player's
    socket receives the next message (e.g. the opening Phase2IO request) depends on the random
    per-game deck shuffle/turn order - a test that exhaustively drains one socket before ever
    checking the other can hang forever if the message it wants actually landed on the other one.'''

    def __init__(self, ws: Any):
        self._ws = ws
        self._queue: "queue.Queue[dict[str, Any] | None]" = queue.Queue()
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        try:
            while True:
                self._queue.put(self._ws.receive_json())
        except Exception:
            self._queue.put(None)

    def send_json(self, data: dict[str, Any]) -> None:
        self._ws.send_json(data)

    def try_receive(self, timeout: float = 0.2) -> dict[str, Any] | None:
        '''Returns the next message, or None if none arrived within timeout OR the socket closed.'''
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def receive_json(self, timeout: float = 5.0) -> dict[str, Any]:
        message = self.try_receive(timeout)
        if message is None:
            raise AssertionError(f"no message received within {timeout}s")
        return message


def login(ws: Any, username: str) -> dict[str, Any]:
    '''Sends the required login-first-message and returns the logged_in response. Works with
    either a raw Starlette websocket test session or a QueuedWebSocket - both expose compatible
    send_json/receive_json.'''
    ws.send_json({"type": "login", "username": username})
    message = ws.receive_json()
    if message["type"] != "logged_in":
        raise AssertionError(f"expected logged_in, got {message!r}")
    return message


def drain_for_type(qws: QueuedWebSocket, expected_type: str, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"never received a {expected_type!r} message within {timeout}s")
        message = qws.try_receive(timeout=remaining)
        if message is not None and message["type"] == expected_type:
            return message


def first_io_request(*sockets: QueuedWebSocket, timeout: float = 5.0) -> tuple[QueuedWebSocket, dict[str, Any]]:
    '''Polls all given sockets until one produces an io_request - whichever player env.turn
    actually is receives it, which varies with the random per-game deck shuffle.'''
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for qws in sockets:
            message = qws.try_receive(timeout=0.05)
            if message is not None and message["type"] == "io_request":
                return qws, message
    raise AssertionError(f"no io_request arrived on any socket within {timeout}s")
