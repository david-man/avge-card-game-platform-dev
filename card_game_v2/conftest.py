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
from .engine.event import IOEvent
from .engine.record import HistoricalStatus

_MAX_EVENTS_PER_FLUSH = 2000


@pytest.fixture(autouse=True)
def _cap_engine_flush_for_tests(monkeypatch):
    original_flush = Engine.flush

    async def capped_flush(self, new_chapter_condition):
        previous_add_record = self.history.add_record
        committed = 0

        def count_and_stop(status, event):
            nonlocal committed
            previous_add_record(status, event)
            if status == HistoricalStatus.PENDING and not isinstance(event, IOEvent):
                committed += 1
                if committed > _MAX_EVENTS_PER_FLUSH:
                    self.terminate_flag = True

        self.history.add_record = count_and_stop
        try:
            result = await original_flush(self, new_chapter_condition)
        finally:
            self.history.add_record = previous_add_record

        if committed > _MAX_EVENTS_PER_FLUSH:
            raise AssertionError(
                f"Engine.flush() did not terminate within {_MAX_EVENTS_PER_FLUSH} "
                "committed events - likely both players' decks are permanently empty "
                "(test-only safety net from conftest.py, not a production behavior)"
            )
        return result

    monkeypatch.setattr(Engine, "flush", capped_flush)
