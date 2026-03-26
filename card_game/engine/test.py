from __future__ import annotations

import unittest

from card_game.constants import ResponseType
from card_game.engine.constrainer import Constraint
from card_game.engine.engine import Engine
from card_game.engine.engine_constants import EngineGroup, QueueStatus
from card_game.engine.event import Event
from card_game.engine.event_listener import AssessorEventListener


class MutableState:
    def __init__(self):
        self.value = 0


class BaseEvent(Event):
    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "base-event"

    def core(self, args=None):
        return self.generate_core_response()

    def invert_core(self, args=None) -> None:
        return

    def generate_internal_listeners(self):
        return


class CountingExternalListener(AssessorEventListener[str]):
    def __init__(self, identifier: str, should_effect: bool = True, ttl_events: int | None = None):
        super().__init__(identifier=identifier, group=EngineGroup.EXTERNAL_MODIFIERS, internal=False)
        self.call_count = 0
        self.should_effect = should_effect
        self.ttl_events = ttl_events

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return self.should_effect

    def assess(self, args=None):
        self.call_count += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        if self.ttl_events is not None:
            self.ttl_events -= 1
            if self.ttl_events <= 0:
                self.invalidate()
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "counting-external-listener"


class SkipListener(AssessorEventListener[str]):
    def __init__(self, group: EngineGroup):
        super().__init__(identifier="skip-listener", group=group, internal=True)

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return True

    def assess(self, args=None):
        return self.generate_response(ResponseType.SKIP, {"reason": "forced"})

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "skip-listener"


class CountingInternalListener(AssessorEventListener[str]):
    def __init__(self, identifier: str, group: EngineGroup = EngineGroup.INTERNAL_1):
        super().__init__(identifier=identifier, group=group, internal=True)
        self.call_count = 0
        self.invalidated_after_first = False

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return True

    def assess(self, args=None):
        self.call_count += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        if self.invalidated_after_first and self.call_count >= 1:
            self.invalidate()

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "counting-internal-listener"


class QueryListener(AssessorEventListener[str]):
    def __init__(self):
        super().__init__(identifier="query-listener", group=EngineGroup.INTERNAL_1, internal=True)
        self.call_count = 0

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return True

    def assess(self, args=None):
        self.call_count += 1
        args = {} if args is None else args
        if not args.get("approved", False):
            return self.generate_response(ResponseType.REQUIRES_QUERY, {"query_type": "approval"})
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "query-listener"


class TagConstraint(Constraint[str]):
    def __init__(self, identifier: str):
        super().__init__(identifier)

    def match(self, obj) -> bool:
        if isinstance(obj, Constraint):
            return False
        return getattr(obj, "identifier", None) == self.identifier

    def constrain_listener(self, listener: AssessorEventListener[str]):
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "tag-constraint"


class PreCoreSkipEvent(BaseEvent):
    def generate_internal_listeners(self):
        self.event_listener_groups[EngineGroup.INTERNAL_1].append(SkipListener(EngineGroup.INTERNAL_1))


class PostCoreSkipEvent(BaseEvent):
    def __init__(self, state: MutableState, delta: int):
        self.state = state
        self.delta = delta
        super().__init__()

    def core(self, args=None):
        self.state.value += self.delta
        return self.generate_core_response()

    def invert_core(self, args=None) -> None:
        self.state.value -= self.delta

    def generate_internal_listeners(self):
        self.event_listener_groups[EngineGroup.INTERNAL_3].append(SkipListener(EngineGroup.INTERNAL_3))


class DeltaEvent(BaseEvent):
    def __init__(self, state: MutableState, delta: int, propose_extra: bool = False):
        self.state = state
        self.delta = delta
        self.propose_extra = propose_extra
        super().__init__()

    def core(self, args=None):
        self.state.value += self.delta
        if self.propose_extra:
            self.propose(BaseEvent())
        return self.generate_core_response()

    def invert_core(self, args=None) -> None:
        self.state.value -= self.delta


class AddListenerEvent(BaseEvent):
    def __init__(self, listener: CountingExternalListener):
        self.listener = listener
        super().__init__()

    def core(self, args=None):
        self.engine.add_listener(self.listener)
        return self.generate_core_response()


class AddConstraintEvent(BaseEvent):
    def __init__(self, constraint: Constraint):
        self.constraint = constraint
        super().__init__()

    def core(self, args=None):
        self.engine.add_constraint(self.constraint)
        return self.generate_core_response()


class InternalInvalidatedEvent(BaseEvent):
    def __init__(self):
        self.listener = CountingInternalListener("invalidated", group=EngineGroup.INTERNAL_1)
        self.listener.invalidate()
        super().__init__()

    def generate_internal_listeners(self):
        self.event_listener_groups[EngineGroup.INTERNAL_1].append(self.listener)


class InternalNoEffectEvent(BaseEvent):
    def __init__(self):
        self.listener = CountingInternalListener("no-effect", group=EngineGroup.INTERNAL_1)
        super().__init__()

    def generate_internal_listeners(self):
        self.listener.event_effect = lambda: False
        self.event_listener_groups[EngineGroup.INTERNAL_1].append(self.listener)


class EngineEdgeCaseTests(unittest.TestCase):
    def drain_engine(self, eng: Engine, max_steps: int = 200):
        last = None
        for _ in range(max_steps):
            last = eng.forward({})
            if last.response_type == ResponseType.NO_MORE_EVENTS:
                return last
        self.fail("Engine did not reach NO_MORE_EVENTS in max_steps")

    def test_skip_before_core_reopens_queue_for_next_packets(self):
        eng = Engine()
        eng._propose([PreCoreSkipEvent()])

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(eng._queue.queue_status, QueueStatus.OPEN)

        state = MutableState()
        eng._propose([DeltaEvent(state, 3)])
        last_after = self.drain_engine(eng)
        self.assertEqual(last_after.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 3)

    def test_skip_after_core_reverts_current_and_prior_events_in_packet(self):
        eng = Engine()
        state = MutableState()
        eng._propose([
            DeltaEvent(state, 5),
            PostCoreSkipEvent(state, 7),
        ])

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 0)

    def test_skip_clears_buffered_proposals_from_failed_packet(self):
        eng = Engine()
        state = MutableState()
        eng._propose([
            DeltaEvent(state, 2, propose_extra=True),
            PreCoreSkipEvent(),
        ])

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(eng._queue.queue_len(), 0)
        self.assertEqual(state.value, 0)

    def test_listener_added_mid_packet_is_not_persisted_after_skip(self):
        eng = Engine()
        listener = CountingExternalListener(identifier="tmp-listener")
        eng._propose([
            AddListenerEvent(listener),
            PreCoreSkipEvent(),
        ])
        self.drain_engine(eng)

        eng._propose([BaseEvent()])
        self.drain_engine(eng)
        self.assertEqual(listener.call_count, 0)
        self.assertTrue(listener._invalidated)

    def test_constraint_added_mid_packet_is_not_persisted_after_skip(self):
        eng = Engine()
        listener = CountingExternalListener(identifier="tagged")
        eng.add_listener(listener)

        transient_constraint = TagConstraint("tagged")
        eng._propose([
            AddConstraintEvent(transient_constraint),
            PreCoreSkipEvent(),
        ])
        self.drain_engine(eng)
        baseline_calls = listener.call_count

        eng._propose([BaseEvent()])
        self.drain_engine(eng)
        self.assertEqual(listener.call_count, baseline_calls + 1)
        self.assertNotIn(transient_constraint, eng._constraints)

    def test_listener_invalidated_after_event_does_not_attach_to_next_event_in_packet(self):
        eng = Engine()
        listener = CountingExternalListener(identifier="ttl-listener", ttl_events=1)
        eng.add_listener(listener)

        eng._propose([BaseEvent(), BaseEvent()])
        self.drain_engine(eng)

        self.assertEqual(listener.call_count, 1)
        self.assertTrue(listener._invalidated)

    def test_requires_query_replays_same_listener_until_answered(self):
        eng = Engine()
        query_listener = QueryListener()

        class QueryEvent(BaseEvent):
            def generate_internal_listeners(self_nonlocal):
                self_nonlocal.event_listener_groups[EngineGroup.INTERNAL_1].append(query_listener)

        eng._propose([QueryEvent()])

        self.assertEqual(eng.forward({}).response_type, ResponseType.NEXT_PACKET)
        self.assertEqual(eng.forward({}).response_type, ResponseType.NEXT_EVENT)
        self.assertEqual(eng.forward({}).response_type, ResponseType.ACCEPT)
        first_query = eng.forward({})
        self.assertEqual(first_query.response_type, ResponseType.REQUIRES_QUERY)
        self.assertEqual(query_listener.call_count, 1)

        answered = eng.forward({"approved": True})
        self.assertEqual(answered.response_type, ResponseType.ACCEPT)
        self.assertEqual(query_listener.call_count, 2)

        final = self.drain_engine(eng)
        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)

    def test_invalidated_internal_listener_is_skipped(self):
        eng = Engine()
        event = InternalInvalidatedEvent()
        eng._propose([event])

        self.drain_engine(eng)
        self.assertEqual(event.listener.call_count, 0)

    def test_internal_listener_with_false_event_effect_is_skipped(self):
        eng = Engine()
        event = InternalNoEffectEvent()
        eng._propose([event])

        self.drain_engine(eng)
        self.assertEqual(event.listener.call_count, 0)


if __name__ == "__main__":
    unittest.main()
