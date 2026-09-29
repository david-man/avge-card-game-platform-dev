'''Test-only safety net, not imported by any production code.

PhasePickCard.act() used to gate its entire draw+Phase2 queuing behind
`if len(deck) > 0` - an empty deck queued nothing at all, so a turn simply stalled
there forever (the deck-out bug this fixed). A side effect of always reaching Phase2
now, regardless of deck size, is that a scenario where *both* players' decks are
already empty has no natural stopping point any more: turns just keep flipping back
and forth (draw is skipped both ways, Phase2/AtkPhase auto-resolve under the test
harness's TestIO) forever. Plenty of existing tests build boards with both decks sized
to exactly what setup consumes - previously safe, since one empty deck was always a
dead end - and now hang instead, however that flush() call was reached (an explicit
fire_phase_pick_card() call, a card effect that itself ends the turn like Johann's,
etc.). Finding and fixing every individual call site is impractical; this wraps
engine.Engine.flush itself for the duration of the test suite with a generous,
chainable event-count safety net, so any such cascade fails fast with a clear
AssertionError instead of hanging the whole run. It never fires for a normal, bounded
scenario - only once a flush() call has clearly stopped making one-time progress.'''
from __future__ import annotations

import pytest

from .engine.engine import Engine

_MAX_EVENTS_PER_FLUSH = 2000


@pytest.fixture(autouse=True)
def _cap_engine_flush_for_tests(monkeypatch):
    original_flush = Engine.flush

    async def capped_flush(self, new_chapter_condition):
        previous_hook = self.on_event_committed
        committed = 0

        async def count_and_stop(event):
            nonlocal committed
            committed += 1
            if committed > _MAX_EVENTS_PER_FLUSH:
                self.terminate_flag = True
            if previous_hook is not None:
                await previous_hook(event)

        self.on_event_committed = count_and_stop
        try:
            result = await original_flush(self, new_chapter_condition)
        finally:
            self.on_event_committed = previous_hook

        if committed > _MAX_EVENTS_PER_FLUSH:
            raise AssertionError(
                f"Engine.flush() did not terminate within {_MAX_EVENTS_PER_FLUSH} "
                "committed events - likely both players' decks are permanently empty "
                "(test-only safety net from conftest.py, not a production behavior)"
            )
        return result

    monkeypatch.setattr(Engine, "flush", capped_flush)
