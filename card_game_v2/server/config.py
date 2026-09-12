"""Tunable timing/config constants for the networking layer."""

from pathlib import Path

LOG_DIR: Path = Path(__file__).resolve().parent / "logs"
"""Base directory for all server-side logs - fixed relative to this file, not the process's
current working directory, so logs always land in the same place regardless of where uvicorn is
launched from."""

LOG_FILE_PATH: str = str(LOG_DIR / "server.log")
"""Operational/exception log - plain text, append-mode, one line per log record."""

MATCH_LOG_DIR: Path = LOG_DIR / "matches"
"""One JSON file per finished match, named `<game_id>.json` - see match_log.py."""

DATA_DIR: Path = Path(__file__).resolve().parent / "data"
"""Base directory for persistent (non-log, non-ephemeral) server state - currently just the
account roster, which - unlike everything else in this system - is meant to survive a restart."""

ACCOUNTS_FILE_PATH: Path = DATA_DIR / "accounts.json"
"""Username -> account roster, persisted across restarts - see accounts.py."""

RECONNECT_GRACE_SECONDS: float = 30.0
"""How long a disconnected seat has to reconnect before the opponent is awarded the win."""

BOTH_DISCONNECTED_GRACE_SECONDS: float = 30.0
"""How long a session with both seats disconnected waits before being abandoned with no winner."""

ACK_BACKSTOP_SECONDS: float = 5.0
"""Server-side backstop for acknowledgment-only IOTypes that carry no explicit `timeout` field
(EndOfTurn, RevealCards, ShowBoxedStrings, GameEndIO) - matches the engine's own `default_timeout`
convention. IOTypes that do carry a `timeout` (BroadcastIO, Notification) use that value instead."""
