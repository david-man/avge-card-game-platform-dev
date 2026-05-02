from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Event, RLock, Thread
from time import monotonic
from typing import Any, Callable, Literal, TextIO
import json
import os
import subprocess
import sys
import tempfile
from uuid import uuid4


type RoomTransportMode = Literal['pipe']


@dataclass(frozen=True)
class RoomWorkerSnapshot:
    room_id: str
    host: str
    port: int
    transport_mode: RoomTransportMode
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
        transport_mode: RoomTransportMode,
        on_finished: Callable[[str, str], None],
        on_event: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> None:
        if transport_mode != 'pipe':
            raise ValueError('RoomWorker only supports pipe transport_mode.')

        self.room_id = room_id
        self.player_session_ids = player_session_ids
        self.host = host
        self.port = port
        self.transport_mode = transport_mode
        self.p1_username = p1_username
        self.p2_username = p2_username
        self.p1_selected_cards = p1_selected_cards
        self.p2_selected_cards = p2_selected_cards
        self._on_finished = on_finished
        self._on_event = on_event
        self._stop_event = Event()
        self._lock = RLock()
        self._response_condition = Condition(self._lock)
        self._monitor_thread = Thread(target=self._run, name=f"room-worker-{room_id}", daemon=True)
        self._started_at = monotonic()
        self._process: subprocess.Popen[str] | None = None
        self._log_path = str(Path(tempfile.gettempdir()) / f"avge-room-{room_id}.log")
        self._log_file: TextIO | None = None
        self._pending_responses: dict[str, dict[str, Any] | None] = {}
        self._finished = False
        self._finish_reason: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._monitor_thread.is_alive() or self._finished:
                return

            env = os.environ.copy()
            env['ROOM_TRANSPORT_MODE'] = self.transport_mode
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

            project_root = Path(__file__).resolve().parents[3]
            self._log_file = open(self._log_path, 'a', encoding='utf-8')
            self._process = subprocess.Popen(
                [sys.executable, '-m', 'card_game.server.workers.room_pipe_runtime'],
                cwd=str(project_root),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._log_file,
                text=True,
                bufsize=1,
            )

            print(
                f"[ROOM_WORKER] process_started room_id={self.room_id} "
                f"pid={self._process.pid} log={self._log_path}"
            )

            self._monitor_thread.start()

    def request(self, method: str, params: dict[str, Any], timeout_seconds: float = 2.0) -> dict[str, Any]:
        with self._lock:
            process = self._process
            stdin = process.stdin if process is not None else None
            if process is None or process.poll() is not None or stdin is None:
                raise RuntimeError('Room worker process is not available for pipe request.')

            request_id = uuid4().hex
            self._pending_responses[request_id] = None
            payload = {
                'type': 'command',
                'id': request_id,
                'method': method,
                'params': params,
            }

            try:
                stdin.write(json.dumps(payload, separators=(',', ':')) + '\n')
                stdin.flush()
            except Exception as exc:
                self._pending_responses.pop(request_id, None)
                raise RuntimeError(f'Failed to send pipe request {method}: {exc}') from exc

            deadline = monotonic() + max(0.1, timeout_seconds)
            while self._pending_responses.get(request_id) is None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    self._pending_responses.pop(request_id, None)
                    raise TimeoutError(f'Pipe request timed out for method={method}')
                self._response_condition.wait(timeout=remaining)

            response = self._pending_responses.pop(request_id)

        if not isinstance(response, dict):
            raise RuntimeError(f'Invalid pipe response for method={method}')

        if response.get('ok') is not True:
            error = response.get('error')
            if isinstance(error, str) and error.strip():
                raise RuntimeError(error.strip())
            raise RuntimeError(f'Pipe request failed for method={method}')

        result = response.get('result')
        return result if isinstance(result, dict) else {}

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
            transport_mode=self.transport_mode,
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

        self._run_pipe(process)

    def _run_pipe(self, process: subprocess.Popen[str]) -> None:
        stdout = process.stdout
        if stdout is None:
            with self._lock:
                if self._finished:
                    return
                self._mark_finished_locked('room_pipe_stdout_unavailable')
            return

        for line in stdout:
            raw = line.strip()
            if not raw:
                continue

            try:
                message = json.loads(raw)
            except Exception:
                print(f'[ROOM_WORKER] pipe_decode_failed room_id={self.room_id} line={raw!r}')
                continue

            if not isinstance(message, dict):
                continue

            message_type = message.get('type')
            if message_type == 'response':
                response_id = message.get('id')
                if not isinstance(response_id, str) or not response_id:
                    continue
                with self._lock:
                    if response_id in self._pending_responses:
                        self._pending_responses[response_id] = message
                        self._response_condition.notify_all()
                continue

            if message_type == 'event':
                event_type = message.get('event_type')
                payload = message.get('payload')
                if not isinstance(event_type, str) or not event_type.strip() or not isinstance(payload, dict):
                    continue
                self._dispatch_event(event_type.strip(), payload)

        return_code = process.wait()
        with self._lock:
            for response_id, pending in list(self._pending_responses.items()):
                if pending is None:
                    self._pending_responses[response_id] = {
                        'type': 'response',
                        'id': response_id,
                        'ok': False,
                        'error': f'room process exited with code {return_code}',
                    }
            self._response_condition.notify_all()

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

    def _dispatch_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(self.room_id, event_type, payload)
        except Exception as exc:
            print(
                f'[ROOM_WORKER] event_callback_failed room_id={self.room_id} '
                f'event={event_type} error={exc}'
            )
