from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, RLock, Thread
from time import monotonic
from typing import Callable, TextIO
import json
import os
import subprocess
import sys


@dataclass(frozen=True)
class RoomWorkerSnapshot:
    room_id: str
    host: str
    port: int
    process_pid: int | None
    log_path: str
    started_at: float
    finished: bool
    finish_reason: str | None


class RoomWorker:
    """Supervisor for a single room backend process lifecycle."""

    def __init__(
        self,
        room_id: str,
        player_session_ids: tuple[str, str],
        host: str,
        port: int,
        p1_username: str,
        p2_username: str,
        p1_selected_cards: list[str] | None,
        p2_selected_cards: list[str] | None,
        on_finished: Callable[[str, str], None],
    ) -> None:
        self.room_id = room_id
        self.player_session_ids = player_session_ids
        self.host = host
        self.port = port
        self.p1_username = p1_username
        self.p2_username = p2_username
        self.p1_selected_cards = p1_selected_cards
        self.p2_selected_cards = p2_selected_cards
        self._on_finished = on_finished
        self._stop_event = Event()
        self._lock = RLock()
        self._monitor_thread = Thread(target=self._run, name=f"room-worker-{room_id}", daemon=True)
        self._started_at = monotonic()
        self._process: subprocess.Popen[str] | None = None
        self._log_path = str(Path('/tmp') / f"avge-room-{room_id}.log")
        self._log_file: TextIO | None = None
        self._finished = False
        self._finish_reason: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._monitor_thread.is_alive() or self._finished:
                return

            env = os.environ.copy()
            env['SERVER_HOST'] = self.host
            env['SERVER_PORT'] = str(self.port)
            env['ROOM_ID'] = self.room_id
            env['P1_USERNAME'] = self.p1_username
            env['P2_USERNAME'] = self.p2_username
            env['P1_SESSION_ID'] = self.player_session_ids[0]
            env['P2_SESSION_ID'] = self.player_session_ids[1]
            if isinstance(self.p1_selected_cards, list):
                env['P1_DECK_CARDS_JSON'] = json.dumps(self.p1_selected_cards)
            if isinstance(self.p2_selected_cards, list):
                env['P2_DECK_CARDS_JSON'] = json.dumps(self.p2_selected_cards)
            env.setdefault('SERVER_DEBUG', 'false')
            env.setdefault('PYTHONUNBUFFERED', '1')

            # If router is launched with Flask debug reloader, these inherited
            # vars can make child room servers try to reuse invalid fds.
            env.pop('WERKZEUG_SERVER_FD', None)
            env.pop('WERKZEUG_RUN_MAIN', None)
            env.pop('FLASK_RUN_FROM_CLI', None)

            project_root = Path(__file__).resolve().parents[2]
            self._log_file = open(self._log_path, 'a', encoding='utf-8')
            self._process = subprocess.Popen(
                [sys.executable, '-m', 'card_game.server.server'],
                cwd=str(project_root),
                env=env,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )

            self._monitor_thread.start()

    def stop(self, reason: str = "stopped") -> None:
        with self._lock:
            if self._finished:
                return

            process = self._process
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

            if self._log_file is not None:
                self._log_file.flush()
                self._log_file.close()
                self._log_file = None

            self._mark_finished_locked(reason)

    def mark_finished(self, reason: str) -> None:
        with self._lock:
            if self._finished:
                return
            self._mark_finished_locked(reason)

    def _mark_finished_locked(self, reason: str) -> None:
        self._finished = True
        self._finish_reason = reason
        self._stop_event.set()
        self._on_finished(self.room_id, reason)

    def snapshot(self) -> RoomWorkerSnapshot:
        process_pid = self._process.pid if self._process is not None else None
        return RoomWorkerSnapshot(
            room_id=self.room_id,
            host=self.host,
            port=self.port,
            process_pid=process_pid,
            log_path=self._log_path,
            started_at=self._started_at,
            finished=self._finished,
            finish_reason=self._finish_reason,
        )

    def _run(self) -> None:
        process: subprocess.Popen[str] | None = None
        with self._lock:
            process = self._process

        if process is None:
            return

        return_code = process.wait()
        with self._lock:
            if self._log_file is not None:
                self._log_file.flush()
                self._log_file.close()
                self._log_file = None

            if self._finished:
                return
            reason = f'room_process_exit_{return_code}'
            if return_code != 0:
                print(
                    f"[ROOM_WORKER] process_failed room_id={self.room_id} "
                    f"code={return_code} log={self._log_path}"
                )
            self._mark_finished_locked(reason)
