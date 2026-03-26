from __future__ import annotations

import unittest

from card_game.constants import ResponseType, INTERRUPT_KEY
from card_game.engine.constrainer import Constraint
from card_game.engine.engine import Engine
from card_game.engine.engine_constants import EngineGroup, QueueStatus
from card_game.engine.event import Event, EventAssembler
from card_game.engine.event_listener import AssessorEventListener, ModifierEventListener


class MutableState:
    def __init__(self):
        self.value = 0


class BaseEvent(Event):
    def get_kwargs(self):
        return {}

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "base-event"

    def core(self, args={}):
        return self.generate_core_response()

    def invert_core(self, args={}) -> None:
        return

    def generate_internal_listeners(self):
        return


class CountingExternalListener(AssessorEventListener[str]):
    def __init__(self, identifier: str, should_effect: bool = True, ttl_events: int | None = None):
        super().__init__(identifier=identifier, group=EngineGroup.EXTERNAL_MODIFIERS_1, internal=False)
        self.call_count = 0
        self.should_effect = should_effect
        self.ttl_events = ttl_events

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return self.should_effect

    def assess(self, args={}):
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

    def assess(self, args={}):
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

    def assess(self, args={}):
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

    def assess(self, args={}):
        self.call_count += 1
        if not args.get("approved", False):
            return self.generate_response(ResponseType.REQUIRES_QUERY, {"query_type": "approval"})
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "query-listener"


class CountingModifierListener(ModifierEventListener[str]):
    def __init__(self, identifier: str, should_effect: bool = True):
        super().__init__(identifier=identifier, group=EngineGroup.EXTERNAL_MODIFIERS_1, internal=False)
        self.call_count = 0
        self.should_effect = should_effect

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return self.should_effect

    def modify(self, args={}):
        self.call_count += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "counting-modifier-listener"


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
    def get_kwargs(self):
        return {}

    def generate_internal_listeners(self):
        self.event_listener_groups[EngineGroup.INTERNAL_1].append(SkipListener(EngineGroup.INTERNAL_1))


class PostCoreSkipEvent(BaseEvent):
    def __init__(self, state: MutableState, delta: int):
        self.state = state
        self.delta = delta
        super().__init__(state=state, delta=delta)

    def core(self, args={}):
        self.state.value += self.delta
        return self.generate_core_response()

    def get_kwargs(self):
        return {
            "state": self.state,
            "delta": self.delta,
        }

    def invert_core(self, args={}) -> None:
        self.state.value -= self.delta

    def generate_internal_listeners(self):
        self.event_listener_groups[EngineGroup.INTERNAL_3].append(SkipListener(EngineGroup.INTERNAL_3))


class DeltaEvent(BaseEvent):
    def __init__(self, state: MutableState, delta: int, propose_extra: bool = False):
        self.state = state
        self.delta = delta
        self.propose_extra = propose_extra
        super().__init__(state=state, delta=delta, propose_extra=propose_extra)

    def core(self, args={}):
        self.state.value += self.delta
        if self.propose_extra:
            self.propose(BaseEvent())
        return self.generate_core_response()

    def get_kwargs(self):
        return {
            "state": self.state,
            "delta": self.delta,
            "propose_extra": self.propose_extra,
        }

    def invert_core(self, args={}) -> None:
        self.state.value -= self.delta


class AddListenerEvent(BaseEvent):
    def __init__(self, listener: CountingExternalListener):
        self.listener = listener
        super().__init__(listener=listener)

    def core(self, args={}):
        self.engine.add_listener(self.listener)
        return self.generate_core_response()

    def get_kwargs(self):
        return {"listener": self.listener}


class AddConstraintEvent(BaseEvent):
    def __init__(self, constraint: Constraint):
        self.constraint = constraint
        super().__init__(constraint=constraint)

    def core(self, args={}):
        self.engine.add_constraint(self.constraint)
        return self.generate_core_response()

    def get_kwargs(self):
        return {"constraint": self.constraint}


class InternalInvalidatedEvent(BaseEvent):
    def __init__(self):
        self.listener = CountingInternalListener("invalidated", group=EngineGroup.INTERNAL_1)
        self.listener.invalidate()
        super().__init__()

    def generate_internal_listeners(self):
        self.event_listener_groups[EngineGroup.INTERNAL_1].append(self.listener)

    def get_kwargs(self):
        return {}


class InternalNoEffectEvent(BaseEvent):
    def __init__(self):
        self.listener = CountingInternalListener("no-effect", group=EngineGroup.INTERNAL_1)
        super().__init__()

    def generate_internal_listeners(self):
        self.listener.event_effect = lambda: False
        self.event_listener_groups[EngineGroup.INTERNAL_1].append(self.listener)

    def get_kwargs(self):
        return {}


class ProposeDeferredAssemblerEvent(BaseEvent):
    def __init__(self, state: MutableState, deferred_delta_source: dict[str, int]):
        self.state = state
        self.deferred_delta_source = deferred_delta_source
        super().__init__(state=state, deferred_delta_source=deferred_delta_source)

    def get_kwargs(self):
        return {
            "state": self.state,
            "deferred_delta_source": self.deferred_delta_source,
        }

    def core(self, args={}):
        self.propose(
            EventAssembler(
                DeltaEvent,
                {
                    "state": self.state,
                    "delta": lambda: self.deferred_delta_source["delta"],
                    "propose_extra": False,
                },
            )
        )
        return self.generate_core_response()


class DeferredKwargsDeltaEvent(BaseEvent):
    def __init__(
        self,
        state: MutableState,
        delta: int,
        propose_extra: bool = False,
        deferred_delta_source: dict[str, int] | None = None,
    ):
        self.state = state
        self.delta = delta
        self.propose_extra = propose_extra
        self.deferred_delta_source = deferred_delta_source
        super().__init__(
            state=state,
            delta=(lambda: deferred_delta_source["delta"]) if deferred_delta_source is not None else delta,
            propose_extra=propose_extra,
        )

    def get_kwargs(self):
        return {
            "state": self.state,
            "delta": (lambda: self.deferred_delta_source["delta"]) if self.deferred_delta_source is not None else self.delta,
            "propose_extra": self.propose_extra,
        }

    def core(self, args={}):
        self.state.value += self.delta
        if self.propose_extra:
            self.propose(BaseEvent())
        return self.generate_core_response()

    def invert_core(self, args={}) -> None:
        self.state.value -= self.delta


class RollbackCache:
    def __init__(self):
        self._store: dict[str, object] = {}
        self._capturing = False
        self._changelog: list[tuple[str, str, object]] = []

    def set(self, key: str, value: object):
        if self._capturing:
            if key in self._store:
                self._changelog.append(("alter", key, self._store[key]))
            else:
                self._changelog.append(("insert", key, None))
        self._store[key] = value

    def get(self, key: str, default=None):
        return self._store.get(key, default)

    def delete(self, key: str):
        if key not in self._store:
            return
        if self._capturing:
            self._changelog.append(("delete", key, self._store[key]))
        del self._store[key]

    def capture(self):
        self._capturing = True
        self._changelog = []

    def release(self):
        self._capturing = False
        self._changelog = []

    def rewind(self):
        self._capturing = False
        while len(self._changelog) > 0:
            kind, key, old_val = self._changelog.pop()
            if kind == "insert":
                self._store.pop(key, None)
            elif kind in ["alter", "delete"]:
                self._store[key] = old_val
        self._changelog = []


class UpdatePacketInputEvent(BaseEvent):
    def __init__(self, cache: RollbackCache, input_key: str):
        self.cache = cache
        self.input_key = input_key
        self.core_calls = 0
        super().__init__(cache=cache, input_key=input_key)

    def core(self, args={}):
        self.core_calls += 1
        input_result = args.get("input_result")
        if not isinstance(input_result, list) or len(input_result) != 1:
            return self.generate_core_response(ResponseType.REQUIRES_QUERY, {"query_type": "card_query"})
        self.cache.set(self.input_key, input_result[0])
        return self.generate_core_response()

    def invert_core(self, args={}):
        self.cache.delete(self.input_key)


class UpdatePacketReplayEvent(BaseEvent):
    def __init__(self, cache: RollbackCache, touch_key: str, input_key: str):
        self.cache = cache
        self.touch_key = touch_key
        self.input_key = input_key
        super().__init__(cache=cache, touch_key=touch_key, input_key=input_key)


class CacheTouchModifier(ModifierEventListener[str]):
    def __init__(self, cache: RollbackCache, touch_key: str, metrics: dict[str, int]):
        super().__init__(identifier="touch-mod", group=EngineGroup.EXTERNAL_MODIFIERS_1, internal=False)
        self.cache = cache
        self.touch_key = touch_key
        self.metrics = metrics

    def event_match(self, event: Event) -> bool:
        return isinstance(event, UpdatePacketReplayEvent)

    def event_effect(self) -> bool:
        return True

    def modify(self, args={}):
        self.metrics["modifier1_runs"] += 1
        self.cache.set(self.touch_key, True)
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "cache-touch-modifier"


class RequestInputModifier(ModifierEventListener[str]):
    def __init__(self, cache: RollbackCache, input_key: str, metrics: dict[str, int]):
        super().__init__(identifier="input-mod", group=EngineGroup.EXTERNAL_MODIFIERS_2, internal=False)
        self.cache = cache
        self.input_key = input_key
        self.metrics = metrics

    def event_match(self, event: Event) -> bool:
        return isinstance(event, UpdatePacketReplayEvent)

    def event_effect(self) -> bool:
        return True

    def modify(self, args={}):
        if self.cache.get(self.input_key) is None:
            self.metrics["modifier2_update_requests"] += 1
            return self.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [UpdatePacketInputEvent(self.cache, self.input_key)]
                },
            )
        self.metrics["modifier2_passes"] += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "request-input-modifier"


class DownstreamBlockAssessor(AssessorEventListener[str]):
    def __init__(self, cache: RollbackCache, input_key: str, metrics: dict[str, int]):
        super().__init__(identifier="downstream-block", group=EngineGroup.EXTERNAL_PRECHECK_4, internal=False)
        self.cache = cache
        self.input_key = input_key
        self.metrics = metrics

    def event_match(self, event: Event) -> bool:
        return isinstance(event, UpdatePacketReplayEvent)

    def event_effect(self) -> bool:
        return True

    def assess(self, args={}):
        self.metrics["downstream_assessments"] += 1
        if self.cache.get(self.input_key) is not None:
            return self.generate_response(ResponseType.SKIP, {"reason": "downstream-block"})
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "downstream-block-assessor"


class InterruptChainReplayEvent(BaseEvent):
    def __init__(self, cache: RollbackCache, metrics: dict[str, int]):
        self.cache = cache
        self.metrics = metrics
        super().__init__(cache=cache, metrics=metrics)

    def get_kwargs(self):
        return {
            "cache": self.cache,
            "metrics": self.metrics,
        }

    def core(self, args={}):
        self.metrics["core_runs"] += 1
        return self.generate_core_response()


class SequencedInterruptModifier(ModifierEventListener[str]):
    def __init__(self, identifier: str, cache: RollbackCache, input_key: str):
        super().__init__(identifier=identifier, group=EngineGroup.EXTERNAL_MODIFIERS_1, internal=False)
        self.cache = cache
        self.input_key = input_key
        self.interrupt_count = 0
        self.pass_count = 0

    def event_match(self, event: Event) -> bool:
        return isinstance(event, InterruptChainReplayEvent)

    def event_effect(self) -> bool:
        return True

    def modify(self, args={}):
        if self.cache.get(self.input_key) is None:
            self.interrupt_count += 1
            return self.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [UpdatePacketInputEvent(self.cache, self.input_key)],
                },
            )
        self.pass_count += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "sequenced-interrupt-modifier"


class OverrideCandidateEvent(BaseEvent):
    def __init__(self, metrics: dict[str, int]):
        self.metrics = metrics
        super().__init__(metrics=metrics)

    def get_kwargs(self):
        return {"metrics": self.metrics}

    def core(self, args={}):
        self.metrics["event_core_runs"] += 1
        return self.generate_core_response()


class InterruptPayloadEvent(BaseEvent):
    def __init__(self, metrics: dict[str, int]):
        self.metrics = metrics
        super().__init__(metrics=metrics)

    def get_kwargs(self):
        return {"metrics": self.metrics}

    def core(self, args={}):
        self.metrics["payload_core_runs"] += 1
        return self.generate_core_response()


class InterruptThenFastForwardAssessor(AssessorEventListener[str]):
    def __init__(self, metrics: dict[str, int]):
        super().__init__(identifier="interrupt-then-ff", group=EngineGroup.EXTERNAL_PRECHECK_1, internal=False)
        self.metrics = metrics

    def event_match(self, event: Event) -> bool:
        return isinstance(event, OverrideCandidateEvent)

    def event_effect(self) -> bool:
        return True

    def assess(self, args={}):
        if self.metrics["interrupts"] == 0:
            self.metrics["interrupts"] += 1
            return self.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [InterruptPayloadEvent(self.metrics)],
                },
            )
        self.metrics["fast_forwards"] += 1
        return self.generate_response(ResponseType.FAST_FORWARD)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "interrupt-then-fast-forward-assessor"


class DownstreamOverrideModifier(ModifierEventListener[str]):
    def __init__(self, metrics: dict[str, int]):
        super().__init__(identifier="downstream-override-mod", group=EngineGroup.EXTERNAL_MODIFIERS_1, internal=False)
        self.metrics = metrics

    def event_match(self, event: Event) -> bool:
        return isinstance(event, OverrideCandidateEvent)

    def event_effect(self) -> bool:
        return True

    def modify(self, args={}):
        self.metrics["downstream_modifier_runs"] += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "downstream-override-modifier"


class InterruptThenAcceptAssessor(AssessorEventListener[str]):
    def __init__(self, metrics: dict[str, int]):
        super().__init__(identifier="interrupt-then-accept", group=EngineGroup.EXTERNAL_PRECHECK_1, internal=False)
        self.metrics = metrics

    def event_match(self, event: Event) -> bool:
        return isinstance(event, OverrideCandidateEvent)

    def event_effect(self) -> bool:
        return True

    def assess(self, args={}):
        if self.metrics["interrupts"] == 0:
            self.metrics["interrupts"] += 1
            return self.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [InterruptPayloadEvent(self.metrics)],
                },
            )
        self.metrics["accepts"] += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def package(self):
        return "interrupt-then-accept-assessor"


class EngineEdgeCaseTests(unittest.TestCase):
    def make_engine(self) -> Engine:
        eng = Engine()
        if not hasattr(eng, "_reset_constraints"):
            eng._reset_constraints = lambda: None
        return eng

    def drain_engine(self, eng: Engine, max_steps: int = 200):
        last = None
        for _ in range(max_steps):
            last = eng.forward({})
            if last.response_type == ResponseType.NO_MORE_EVENTS:
                return last
        self.fail("Engine did not reach NO_MORE_EVENTS in max_steps")

    def forward_with_cache(self, eng: Engine, cache: RollbackCache, args=None):
        if args is None:
            args = {}
        response = eng.forward(args)
        if response.response_type == ResponseType.NEXT_PACKET:
            cache.capture()
        elif response.response_type == ResponseType.FINISHED_PACKET:
            cache.release()
        elif response.response_type == ResponseType.SKIP:
            cache.rewind()
        return response

    def forward_until(self, eng: Engine, predicate, max_steps: int = 200):
        last = None
        for _ in range(max_steps):
            last = eng.forward({})
            if predicate(last):
                return last
        return last

    def test_skip_before_core_reopens_queue_for_next_packets(self):
        eng = self.make_engine()
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
        eng = self.make_engine()
        state = MutableState()
        eng._propose([
            DeltaEvent(state, 5),
            PostCoreSkipEvent(state, 7),
        ])

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 0)

    def test_skip_clears_buffered_proposals_from_failed_packet(self):
        eng = self.make_engine()
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
        eng = self.make_engine()
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
        eng = self.make_engine()
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
        eng = self.make_engine()
        listener = CountingExternalListener(identifier="ttl-listener", ttl_events=1)
        eng.add_listener(listener)

        eng._propose([BaseEvent(), BaseEvent()])
        self.drain_engine(eng)

        self.assertEqual(listener.call_count, 1)
        self.assertTrue(listener._invalidated)

    def test_requires_query_replays_same_listener_until_answered(self):
        eng = self.make_engine()
        query_listener = QueryListener()

        class QueryEvent(BaseEvent):
            def generate_internal_listeners(self_nonlocal):
                self_nonlocal.event_listener_groups[EngineGroup.INTERNAL_1].append(query_listener)

        eng._propose([QueryEvent()])

        self.assertEqual(eng.forward({}).response_type, ResponseType.NEXT_PACKET)
        self.assertEqual(eng.forward({}).response_type, ResponseType.NEXT_EVENT)

        first_query = None
        for _ in range(10):
            maybe_query = eng.forward({})
            if maybe_query.response_type == ResponseType.REQUIRES_QUERY:
                first_query = maybe_query
                break

        self.assertIsNotNone(first_query)
        self.assertEqual(first_query.response_type, ResponseType.REQUIRES_QUERY)
        self.assertEqual(query_listener.call_count, 1)

        answered = eng.forward({"approved": True})
        self.assertEqual(answered.response_type, ResponseType.ACCEPT)
        self.assertEqual(query_listener.call_count, 2)

        final = self.drain_engine(eng)
        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)

    def test_invalidated_internal_listener_is_skipped(self):
        eng = self.make_engine()
        event = InternalInvalidatedEvent()
        eng._propose([event])

        self.drain_engine(eng)
        self.assertEqual(event.listener.call_count, 0)

    def test_internal_listener_with_false_event_effect_is_skipped(self):
        eng = self.make_engine()
        event = InternalNoEffectEvent()
        eng._propose([event])

        self.drain_engine(eng)
        self.assertEqual(event.listener.call_count, 0)

    def test_proposed_event_assembler_resolves_callable_kwargs_at_assembly_time(self):
        eng = self.make_engine()
        state = MutableState()
        deferred_delta_source = {"delta": 1}

        eng._propose([ProposeDeferredAssemblerEvent(state, deferred_delta_source)])

        response = None
        for _ in range(50):
            response = eng.forward({})
            if response.response_type == ResponseType.FINISHED_PACKET:
                break
        self.assertIsNotNone(response)
        self.assertEqual(response.response_type, ResponseType.FINISHED_PACKET)

        deferred_delta_source["delta"] = 6

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 6)

    def test_proposed_event_instance_uses_deferred_get_kwargs_callables(self):
        eng = self.make_engine()
        state = MutableState()
        deferred_delta_source = {"delta": 2}

        eng._propose(DeferredKwargsDeltaEvent(state, delta=0, deferred_delta_source=deferred_delta_source))
        deferred_delta_source["delta"] = 9

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 9)

    def test_update_packet_input_then_downstream_skip_rewinds_cache(self):
        eng = self.make_engine()
        cache = RollbackCache()
        cache.set("baseline", "persist")

        metrics = {
            "modifier1_runs": 0,
            "modifier2_update_requests": 0,
            "modifier2_passes": 0,
            "downstream_assessments": 0,
        }

        touch_key = "modifier_1_touch"
        input_key = "modifier_2_input"

        eng.add_listener(CacheTouchModifier(cache, touch_key, metrics))
        eng.add_listener(RequestInputModifier(cache, input_key, metrics))
        eng.add_listener(DownstreamBlockAssessor(cache, input_key, metrics))

        eng._propose([UpdatePacketReplayEvent(cache, touch_key, input_key)])

        saw_interrupt = False
        saw_requires_query = False
        final_response = None

        for _ in range(150):
            response = self.forward_with_cache(eng, cache, {})
            if response.response_type == ResponseType.INTERRUPT:
                saw_interrupt = True
            if response.response_type == ResponseType.REQUIRES_QUERY:
                saw_requires_query = True
                response = self.forward_with_cache(eng, cache, {"input_result": [99]})

            if response.response_type == ResponseType.SKIP:
                final_response = response
                break

        self.assertTrue(saw_interrupt)
        self.assertTrue(saw_requires_query)
        self.assertIsNotNone(final_response)
        self.assertEqual(final_response.response_type, ResponseType.SKIP)

        self.assertEqual(metrics["modifier2_update_requests"], 1)
        self.assertGreaterEqual(metrics["modifier2_passes"], 1)
        self.assertGreaterEqual(metrics["modifier1_runs"], 1)
        self.assertGreaterEqual(metrics["downstream_assessments"], 1)

        self.assertEqual(cache.get("baseline"), "persist")
        self.assertIsNone(cache.get(touch_key))
        self.assertIsNone(cache.get(input_key))

    def test_constraint_constrains_listener_when_expected(self):
        eng = self.make_engine()
        constrained_listener = CountingModifierListener("constrained")
        eng.add_listener(constrained_listener)
        eng.add_constraint(TagConstraint("constrained"))

        eng._propose([BaseEvent()])
        final = self.drain_engine(eng)

        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(constrained_listener.call_count, 0)

    def test_ordering_required_with_two_non_constrained_listeners(self):
        eng = self.make_engine()
        listener_a = CountingModifierListener("a")
        listener_b = CountingModifierListener("b")
        eng.add_listener(listener_a)
        eng.add_listener(listener_b)

        eng._propose([BaseEvent()])
        ordering_query = self.forward_until(
            eng,
            lambda r: r.response_type in [ResponseType.REQUIRES_QUERY, ResponseType.NO_MORE_EVENTS],
        )

        self.assertEqual(ordering_query.response_type, ResponseType.REQUIRES_QUERY)
        self.assertEqual(ordering_query.data.get("query_type"), "ordering")
        self.assertEqual(listener_a.call_count, 0)
        self.assertEqual(listener_b.call_count, 0)

    def test_runtime_constraint_then_ordering_when_two_non_constrained_remain(self):
        eng = self.make_engine()
        constrained = CountingModifierListener("constrained")
        remaining_1 = CountingModifierListener("remaining_1")
        remaining_2 = CountingModifierListener("remaining_2")
        eng.add_listener(constrained)
        eng.add_listener(remaining_1)
        eng.add_listener(remaining_2)
        eng.add_constraint(TagConstraint("constrained"))

        eng._propose([BaseEvent()])

        saw_constraint_announcement = False
        ordering_query = None
        for _ in range(50):
            response = eng.forward({})
            if response.data.get("constrainer_announced") == "tag-constraint":
                saw_constraint_announcement = True
            if response.response_type == ResponseType.REQUIRES_QUERY:
                ordering_query = response
                break

        self.assertTrue(saw_constraint_announcement)
        self.assertIsNotNone(ordering_query)
        self.assertEqual(ordering_query.data.get("query_type"), "ordering")
        self.assertEqual(constrained.call_count, 0)

    def test_runtime_constraints_reduce_to_one_listener_so_no_ordering_required(self):
        eng = self.make_engine()
        constrained_1 = CountingModifierListener("constrained_1")
        constrained_2 = CountingModifierListener("constrained_2")
        survivor = CountingModifierListener("survivor")
        eng.add_listener(constrained_1)
        eng.add_listener(constrained_2)
        eng.add_listener(survivor)
        eng.add_constraint(TagConstraint("constrained_1"))
        eng.add_constraint(TagConstraint("constrained_2"))

        eng._propose([BaseEvent()])

        saw_ordering_query = False
        final = None
        for _ in range(100):
            response = eng.forward({})
            if response.response_type == ResponseType.REQUIRES_QUERY and response.data.get("query_type") == "ordering":
                saw_ordering_query = True
                break
            if response.response_type == ResponseType.NO_MORE_EVENTS:
                final = response
                break

        self.assertFalse(saw_ordering_query)
        self.assertIsNotNone(final)
        self.assertEqual(constrained_1.call_count, 0)
        self.assertEqual(constrained_2.call_count, 0)
        self.assertEqual(survivor.call_count, 1)

    def test_assessor_interrupt_then_fast_forward_overrides_event(self):
        eng = self.make_engine()
        metrics = {
            "interrupts": 0,
            "fast_forwards": 0,
            "payload_core_runs": 0,
            "event_core_runs": 0,
            "downstream_modifier_runs": 0,
        }

        eng.add_listener(InterruptThenFastForwardAssessor(metrics))
        eng.add_listener(DownstreamOverrideModifier(metrics))
        eng._propose([OverrideCandidateEvent(metrics)])

        saw_interrupt = False

        for _ in range(200):
            response = eng.forward({})
            if response.response_type == ResponseType.INTERRUPT:
                saw_interrupt = True
            elif response.response_type == ResponseType.NO_MORE_EVENTS:
                break

        self.assertTrue(saw_interrupt)
        self.assertEqual(metrics["interrupts"], 1)
        self.assertGreaterEqual(metrics["fast_forwards"], 1)
        self.assertEqual(metrics["payload_core_runs"], 1)
        self.assertEqual(metrics["event_core_runs"], 0)
        self.assertEqual(metrics["downstream_modifier_runs"], 0)

    def test_assessor_interrupt_then_accept_does_not_override_event(self):
        eng = self.make_engine()
        metrics = {
            "interrupts": 0,
            "accepts": 0,
            "payload_core_runs": 0,
            "event_core_runs": 0,
            "downstream_modifier_runs": 0,
        }

        eng.add_listener(InterruptThenAcceptAssessor(metrics))
        eng.add_listener(DownstreamOverrideModifier(metrics))
        eng._propose([OverrideCandidateEvent(metrics)])

        saw_interrupt = False
        for _ in range(200):
            response = eng.forward({})
            if response.response_type == ResponseType.INTERRUPT:
                saw_interrupt = True
            elif response.response_type == ResponseType.NO_MORE_EVENTS:
                break

        self.assertTrue(saw_interrupt)
        self.assertEqual(metrics["interrupts"], 1)
        self.assertGreaterEqual(metrics["accepts"], 1)
        self.assertEqual(metrics["payload_core_runs"], 1)
        self.assertEqual(metrics["event_core_runs"], 1)
        self.assertEqual(metrics["downstream_modifier_runs"], 1)

    def test_multiple_interrupting_modifiers_in_row_all_pass_through(self):
        eng = self.make_engine()
        cache = RollbackCache()
        metrics = {
            "core_runs": 0,
        }

        mod_a = SequencedInterruptModifier("mod-a", cache, "input_a")
        mod_b = SequencedInterruptModifier("mod-b", cache, "input_b")
        eng.add_listener(mod_a)
        eng.add_listener(mod_b)

        eng._propose([InterruptChainReplayEvent(cache, metrics)])

        saw_interrupts = 0
        saw_ordering = False
        finished = False
        next_args = {}

        for _ in range(300):
            response = eng.forward(next_args)
            next_args = {}

            if response.response_type == ResponseType.INTERRUPT:
                saw_interrupts += 1
            elif response.response_type == ResponseType.REQUIRES_QUERY:
                if response.data.get("query_type") == "ordering":
                    saw_ordering = True
                    next_args = {"group_ordering": response.data.get("unordered_groups", [])}
                elif response.data.get("query_type") == "card_query":
                    next_args = {"input_result": [1]}
                else:
                    self.fail(f"Unexpected query type: {response.data.get('query_type')}")
            elif response.response_type == ResponseType.NO_MORE_EVENTS:
                finished = True
                break

        self.assertTrue(finished)
        self.assertTrue(saw_ordering)
        self.assertGreaterEqual(saw_interrupts, 2)
        self.assertEqual(mod_a.interrupt_count, 1)
        self.assertEqual(mod_b.interrupt_count, 1)
        self.assertGreaterEqual(mod_a.pass_count, 1)
        self.assertGreaterEqual(mod_b.pass_count, 1)
        self.assertEqual(metrics["core_runs"], 1)


if __name__ == "__main__":
    unittest.main()
