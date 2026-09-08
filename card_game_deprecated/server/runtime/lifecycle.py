from __future__ import annotations

from typing import Callable
from threading import Timer
import json
import urllib.error
import urllib.request


def notify_router_room_finished(
    *,
    router_base_url: str,
    room_id_from_env: str,
    reason: str,
) -> None:
    if not room_id_from_env:
        return

    endpoint = f"{router_base_url.rstrip('/')}/rooms/finish"
    payload = {
        'room_id': room_id_from_env,
        'reason': reason,
    }
    body = json.dumps(payload).encode('utf-8')
    request_obj = urllib.request.Request(
        endpoint,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=0.8) as response:
            _ = response.read()
    except urllib.error.URLError as exc:
        print(f'[ROOM_FINISH_NOTIFY] failed endpoint={endpoint} reason={reason} error={exc}')
    except Exception as exc:
        print(f'[ROOM_FINISH_NOTIFY] failed endpoint={endpoint} reason={reason} error={exc}')


def mark_room_finished_once(
    *,
    room_finished_notified: bool,
    reason: str,
    notify_callback: Callable[[str], None],
) -> bool:
    if room_finished_notified:
        return room_finished_notified
    notify_callback(reason)
    return True


def schedule_process_termination(
    *,
    termination_requested: bool,
    on_scheduled: Callable[[], None],
    terminate_process: Callable[[], None],
    delay_seconds: float = 0.25,
) -> bool:
    if termination_requested:
        return termination_requested

    on_scheduled()
    timer = Timer(delay_seconds, terminate_process)
    timer.daemon = True
    timer.start()
    return True


def schedule_both_disconnected_termination_if_needed(
    *,
    first_player_join_seen: bool,
    termination_requested: bool,
    sid_by_slot: dict[str, str | None],
    mark_room_finished_once: Callable[[str], None],
    schedule_process_termination: Callable[[str], None],
) -> None:
    if not first_player_join_seen or termination_requested:
        return

    # Simplified policy: if both slots are disconnected at the same time,
    # immediately finish the room and terminate the room server.
    if any(sid_by_slot.get(slot_name) is not None for slot_name in ('p1', 'p2')):
        return

    mark_room_finished_once('both_players_disconnected')
    schedule_process_termination('both players disconnected simultaneously')
