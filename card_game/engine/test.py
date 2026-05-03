from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any, cast

from card_game.constants import Data, Interrupt, OrderingQuery, Response, ResponseType
from card_game.engine.constrainer import Constraint
from card_game.engine.engine import Engine, EngineHistory, HistoryState
from card_game.engine.engine_constants import EngineGroup, QueueStatus
from card_game.engine.event import Event, Packet
from card_game.engine.event_listener import AbstractEventListener, AbstractPacketListener, AssessorEventListener, ModifierEventListener, ReactorEventListener


@dataclass
class QueryData(Data):
    query_type: str


@dataclass
class ConstraintAnnouncement(Data):
    constrainer_announced: str


def _coerce_response_data(response_type: ResponseType, payload: dict[str, Any] | Data | None):
    if isinstance(payload, Data):
        return payload

    payload_dict = payload if isinstance(payload, dict) else {}

    if response_type == ResponseType.INTERRUPT:
        insertion = payload_dict.get("INTERRUPT_KEY", [])
        return Interrupt[Event](insertion=insertion)

    if response_type == ResponseType.REQUIRES_QUERY:
        query_type = payload_dict.get("query_type")
        if query_type == "ordering":
            unordered = payload_dict.get("unordered_groups", payload_dict.get("unordered_listeners", []))
            return OrderingQuery(unordered_listeners=unordered)
        return QueryData(query_type=query_type or "legacy_query")

    return Data()


class TestAssessor(AssessorEventListener[Event]):
    def generate_response(self, response_type: ResponseType = ResponseType.ACCEPT, payload: dict[str, Any] | Data | None = None):
        return Response(response_type, _coerce_response_data(response_type, payload))


class TestModifier(ModifierEventListener[Event]):
    def generate_response(self, response_type: ResponseType = ResponseType.ACCEPT, payload: dict[str, Any] | Data | None = None):
        return Response(response_type, _coerce_response_data(response_type, payload))


class TestReactor(ReactorEventListener[Event]):
    def generate_response(self, response_type: ResponseType = ResponseType.ACCEPT, payload: dict[str, Any] | Data | None = None):
        return Response(response_type, _coerce_response_data(response_type, payload))


def response_query_type(response) -> str | None:
    if isinstance(response.data, OrderingQuery):
        return "ordering"
    return getattr(response.data, "query_type", None)


def response_unordered_groups(response):
    if isinstance(response.data, OrderingQuery):
        return response.data.unordered_listeners
    return getattr(response.data, "unordered_groups", [])


def response_data_value(response, key: str, default=None):
    if hasattr(response.data, key):
        return getattr(response.data, key)
    getter = getattr(response.data, "get", None)
    if callable(getter):
        return getter(key, default)
    return default


class MutableState:
    def __init__(self):
        self.value = 0


class BaseEvent(Event):
    def generate_core_response(self, response_type: ResponseType = ResponseType.CORE, payload: dict[str, Any] | Data | None = None):
        return Response(response_type, _coerce_response_data(response_type, payload))

    def get_kwargs(self):
        return {}

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "base-event"

    def core(self, args={}):
        return self.generate_core_response()

    def invert_core(self, args={}) -> None:
        return

    def generate_internal_listeners(self):
        return


class CountingExternalListener(TestAssessor):
    def __init__(self, identifier: str, should_effect: bool = True, ttl_events: int | None = None):
        self.identifier = identifier
        super().__init__(group=EngineGroup.EXTERNAL_MODIFIERS_2, )
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

    def __str__(self):
        return "counting-external-listener"


class SkipListener(TestAssessor):
    def __init__(self, group: EngineGroup):
        self.identifier = "skip-listener"
        super().__init__(group=group, )

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

    def __str__(self):
        return "skip-listener"


class CountingInternalListener(TestAssessor):
    def __init__(self, identifier: str, group: EngineGroup = EngineGroup.INTERNAL_1):
        self.identifier = identifier
        super().__init__(group=group, )
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

    def __str__(self):
        return "counting-internal-listener"


class QueryListener(TestAssessor):
    def __init__(self):
        self.identifier = "query-listener"
        super().__init__(group=EngineGroup.INTERNAL_1, )
        self.call_count = 0
        self.approved = False

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return True

    def assess(self, args={}):
        self.call_count += 1
        if not self.approved:
            return self.generate_response(ResponseType.REQUIRES_QUERY, QueryData("approval"))
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "query-listener"


class CountingModifierListener(TestModifier):
    def __init__(self, identifier: str, should_effect: bool = True):
        self.identifier = identifier
        super().__init__(group=EngineGroup.EXTERNAL_MODIFIERS_2, )
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

    def __str__(self):
        return "counting-modifier-listener"


class TagConstraint(Constraint[Event]):
    def __init__(self, identifier: str):
        super().__init__()
        self.identifier = identifier

    def __str__(self):
        return "tag-constraint"

    def match(self, obj) -> bool:
        if isinstance(obj, Constraint):
            return False
        return getattr(obj, "identifier", None) == self.identifier

    def constrain_listener(self, listener: AssessorEventListener[Event]):
        return True

    def response_data_on_attach(self, attached_to: AbstractEventListener[Event]) -> Data:
        return ConstraintAnnouncement(constrainer_announced=str(self))

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
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
            self.propose(Packet([BaseEvent()]))
        return self.generate_core_response()

    def get_kwargs(self):
        return {
            "state": self.state,
            "delta": self.delta,
            "propose_extra": self.propose_extra,
        }

    def invert_core(self, args={}) -> None:
        self.state.value -= self.delta


class PacketStatusProbeListener(AbstractPacketListener[Event]):
    def __init__(
        self,
        attach_on: set[ResponseType],
        response_type: ResponseType = ResponseType.ACCEPT,
        state: MutableState | None = None,
        propose_delta: int | None = None,
        propose_priority: int = 0,
        invalidate_after_react: bool = False,
    ):
        super().__init__()
        self.attach_on = attach_on
        self.response_type = response_type
        self.state = state
        self.propose_delta = propose_delta
        self.propose_priority = propose_priority
        self.invalidate_after_react = invalidate_after_react
        self.react_count = 0
        self.seen_statuses: list[ResponseType] = []

    def packet_match(self, packet: Packet[Event], packet_finish_status: ResponseType) -> bool:
        self.seen_statuses.append(packet_finish_status)
        return packet_finish_status in self.attach_on

    def update_status(self):
        return

    def react(self, p: Packet[Event]) -> Response:
        self.react_count += 1
        if self.state is not None and self.propose_delta is not None:
            self.propose(Packet([DeltaEvent(self.state, self.propose_delta)]), self.propose_priority)
        if self.invalidate_after_react:
            self.invalidate()
        return Response(self.response_type, Data())


class ExplicitSkipEvent(BaseEvent):
    def core(self, args={}):
        return self.generate_core_response(ResponseType.SKIP)

    def get_kwargs(self):
        return {}


class AddListenerEvent(BaseEvent):
    def __init__(self, listener: CountingExternalListener):
        self.listener = listener
        super().__init__(listener=listener)

    def core(self, args={}):
        assert self.engine is not None
        self.engine.add_listener(self.listener)
        return self.generate_core_response()

    def get_kwargs(self):
        return {"listener": self.listener}


class AddConstraintEvent(BaseEvent):
    def __init__(self, constraint: Constraint):
        self.constraint = constraint
        super().__init__(constraint=constraint)

    def core(self, args={}):
        assert self.engine is not None
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
            Packet([
                lambda: [
                    DeltaEvent(
                        state=self.state,
                        delta=self.deferred_delta_source["delta"],
                        propose_extra=False,
                    )
                ]
            ])
        )
        return self.generate_core_response()


class AssemblyTimingDeltaEvent(BaseEvent):
    def __init__(
        self,
        state: MutableState,
        metrics: dict[str, int] | None = None,
        delta_source: dict[str, int] | None = None,
        delta: int | None = None,
    ):
        self.state = state
        self.metrics = metrics
        self.delta_source = delta_source
        self.delta = delta

        if delta is not None:
            self.delta = delta
            super().__init__(state=state, delta=delta)
        elif metrics is not None and delta_source is not None:
            self.delta = self.resolve_delta()
            super().__init__(state=state, delta=self.delta)
        else:
            raise ValueError("AssemblyTimingDeltaEvent requires either delta or (metrics and delta_source)")

    def resolve_delta(self) -> int:
        if self.metrics is None or self.delta_source is None:
            raise ValueError("Cannot resolve delta without metrics and delta_source")
        self.metrics["event_kwarg_resolves"] += 1
        return self.delta_source["delta"]

    def get_kwargs(self):
        return {
            "state": self.state,
            "metrics": self.metrics,
            "delta_source": self.delta_source,
            "delta": self.delta,
        }

    def core(self, args={}):
        assert self.delta is not None
        self.state.value += self.delta
        return self.generate_core_response()

    def invert_core(self, args={}) -> None:
        assert self.delta is not None
        self.state.value -= self.delta


class MutateDeltaSourceEvent(BaseEvent):
    def __init__(self, delta_source: dict[str, int], new_delta: int, metrics: dict[str, int]):
        self.delta_source = delta_source
        self.new_delta = new_delta
        self.metrics = metrics
        super().__init__(delta_source=delta_source, new_delta=new_delta, metrics=metrics)

    def get_kwargs(self):
        return {
            "delta_source": self.delta_source,
            "new_delta": self.new_delta,
            "metrics": self.metrics,
        }

    def core(self, args={}):
        self.metrics["mutations"] += 1
        self.delta_source["delta"] = self.new_delta
        return self.generate_core_response()


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
            return self.generate_core_response(ResponseType.REQUIRES_QUERY, QueryData("card_query"))
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


class CacheTouchModifier(TestModifier):
    def __init__(self, cache: RollbackCache, touch_key: str, metrics: dict[str, int]):
        self.identifier = "touch-mod"
        super().__init__(group=EngineGroup.EXTERNAL_MODIFIERS_2, )
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

    def __str__(self):
        return "cache-touch-modifier"


class RequestInputModifier(TestModifier):
    def __init__(self, cache: RollbackCache, input_key: str, metrics: dict[str, int]):
        self.identifier = "input-mod"
        super().__init__(group=EngineGroup.EXTERNAL_MODIFIERS_2, )
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
                Interrupt[Event]([UpdatePacketInputEvent(self.cache, self.input_key)]),
            )
        self.metrics["modifier2_passes"] += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "request-input-modifier"


class DownstreamBlockAssessor(TestAssessor):
    def __init__(self, cache: RollbackCache, input_key: str, metrics: dict[str, int]):
        self.identifier = "downstream-block"
        super().__init__(group=EngineGroup.EXTERNAL_PRECHECK_2, )
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

    def __str__(self):
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


class listdInterruptModifier(TestModifier):
    def __init__(self, identifier: str, cache: RollbackCache, input_key: str):
        self.identifier = identifier
        super().__init__(group=EngineGroup.EXTERNAL_MODIFIERS_2, )
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
                Interrupt[Event]([UpdatePacketInputEvent(self.cache, self.input_key)]),
            )
        self.pass_count += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "listd-interrupt-modifier"


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


class ForceFastForwardEvent(BaseEvent):
    def __init__(self, metrics: dict[str, int]):
        self.metrics = metrics
        super().__init__(metrics=metrics)

    def get_kwargs(self):
        return {"metrics": self.metrics}

    def core(self, args={}):
        self.metrics["core_runs"] += 1
        return self.generate_core_response()


class ForceFastForwardAssessor(TestAssessor):
    def __init__(self, metrics: dict[str, int]):
        self.identifier = "force-ff-assessor"
        super().__init__(group=EngineGroup.EXTERNAL_PRECHECK_1, )
        self.metrics = metrics

    def event_match(self, event: Event) -> bool:
        return isinstance(event, ForceFastForwardEvent)

    def event_effect(self) -> bool:
        return True

    def assess(self, args={}):
        self.metrics["assess_runs"] += 1
        assert self.attached_event is not None
        self.attached_event._ff()
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "force-fast-forward-assessor"


class ForceFastForwardDownstreamModifier(TestModifier):
    def __init__(self, metrics: dict[str, int]):
        self.identifier = "force-ff-downstream"
        super().__init__(group=EngineGroup.EXTERNAL_MODIFIERS_2, )
        self.metrics = metrics

    def event_match(self, event: Event) -> bool:
        return isinstance(event, ForceFastForwardEvent)

    def event_effect(self) -> bool:
        return True

    def modify(self, args={}):
        self.metrics["downstream_runs"] += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "force-fast-forward-downstream-modifier"


class InterruptThenFastForwardAssessor(TestAssessor):
    def __init__(self, metrics: dict[str, int]):
        self.identifier = "interrupt-then-ff"
        super().__init__(group=EngineGroup.EXTERNAL_PRECHECK_1, )
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
                Interrupt[Event]([InterruptPayloadEvent(self.metrics)]),
            )
        self.metrics["fast_forwards"] += 1
        assert self.attached_event is not None
        self.attached_event._ff()
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "interrupt-then-fast-forward-assessor"


class DownstreamOverrideModifier(TestModifier):
    def __init__(self, metrics: dict[str, int]):
        self.identifier = "downstream-override-mod"
        super().__init__(group=EngineGroup.EXTERNAL_MODIFIERS_2, )
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

    def __str__(self):
        return "downstream-override-modifier"


class InterruptThenAcceptAssessor(TestAssessor):
    def __init__(self, metrics: dict[str, int]):
        self.identifier = "interrupt-then-accept"
        super().__init__(group=EngineGroup.EXTERNAL_PRECHECK_1, )
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
                Interrupt[Event]([InterruptPayloadEvent(self.metrics)]),
            )
        self.metrics["accepts"] += 1
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "interrupt-then-accept-assessor"


class OrderedInterruptPayloadEvent(BaseEvent):
    def __init__(self, order: list[str]):
        self.order = order
        super().__init__(order=order)

    def get_kwargs(self):
        return {"order": self.order}

    def core(self, args={}):
        self.order.append("payload_core")
        return self.generate_core_response()


class OrderedInterruptCandidateEvent(BaseEvent):
    def __init__(self, order: list[str]):
        self.order = order
        super().__init__(order=order)

    def get_kwargs(self):
        return {"order": self.order}

    def core(self, args={}):
        self.order.append("candidate_core")
        return self.generate_core_response()


class OrderedInterruptAssessor(TestAssessor):
    def __init__(self, order: list[str]):
        self.identifier = "ordered-interrupt"
        super().__init__(group=EngineGroup.EXTERNAL_PRECHECK_1, )
        self.order = order
        self.did_interrupt = False

    def event_match(self, event: Event) -> bool:
        return isinstance(event, OrderedInterruptCandidateEvent)

    def event_effect(self) -> bool:
        return True

    def assess(self, args={}):
        if not self.did_interrupt:
            self.did_interrupt = True
            self.order.append("interrupt")
            return self.generate_response(
                ResponseType.INTERRUPT,
                Interrupt[Event]([OrderedInterruptPayloadEvent(self.order)]),
            )
        self.order.append("resume")
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "ordered-interrupt-assessor"


class OrderedCoreInterruptEvent(BaseEvent):
    def __init__(self, order: list[str]):
        self.order = order
        self.did_interrupt = False
        super().__init__(order=order)

    def get_kwargs(self):
        return {"order": self.order}

    def core(self, args={}):
        if not self.did_interrupt:
            self.did_interrupt = True
            self.order.append("core_interrupt")
            return self.generate_core_response(
                ResponseType.INTERRUPT,
                Interrupt[Event]([OrderedInterruptPayloadEvent(self.order)]),
            )
        self.order.append("core_resume")
        return self.generate_core_response()


class OrderedModifierInterruptCandidateEvent(BaseEvent):
    def __init__(self, order: list[str]):
        self.order = order
        super().__init__(order=order)

    def get_kwargs(self):
        return {"order": self.order}

    def core(self, args={}):
        self.order.append("candidate_core")
        return self.generate_core_response()


class OrderedInterruptModifier(TestModifier):
    def __init__(self, order: list[str]):
        self.identifier = "ordered-interrupt-modifier"
        super().__init__(group=EngineGroup.EXTERNAL_MODIFIERS_2, )
        self.order = order
        self.did_interrupt = False

    def event_match(self, event: Event) -> bool:
        return isinstance(event, OrderedModifierInterruptCandidateEvent)

    def event_effect(self) -> bool:
        return True

    def modify(self, args={}):
        if not self.did_interrupt:
            self.did_interrupt = True
            self.order.append("modifier_interrupt")
            return self.generate_response(
                ResponseType.INTERRUPT,
                Interrupt[Event]([OrderedInterruptPayloadEvent(self.order)]),
            )
        self.order.append("modifier_resume")
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "ordered-interrupt-modifier"


class OrderedReactorInterruptCandidateEvent(BaseEvent):
    def __init__(self, order: list[str]):
        self.order = order
        super().__init__(order=order)

    def get_kwargs(self):
        return {"order": self.order}

    def core(self, args={}):
        self.order.append("candidate_core")
        return self.generate_core_response()


class OrderedInterruptReactor(TestReactor):
    def __init__(self, order: list[str]):
        self.identifier = "ordered-interrupt-reactor"
        super().__init__(group=EngineGroup.EXTERNAL_REACTORS, )
        self.order = order
        self.did_interrupt = False

    def event_match(self, event: Event) -> bool:
        return isinstance(event, OrderedReactorInterruptCandidateEvent)

    def event_effect(self) -> bool:
        return True

    def react(self, args={}):
        if not self.did_interrupt:
            self.did_interrupt = True
            self.order.append("reactor_interrupt")
            return self.generate_response(
                ResponseType.INTERRUPT,
                Interrupt[Event]([OrderedInterruptPayloadEvent(self.order)]),
            )
        self.order.append("reactor_resume")
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "ordered-interrupt-reactor"


class PriorityTaggedEvent(BaseEvent):
    def __init__(self, order: list[str], tag: str):
        self.order = order
        self.tag = tag
        super().__init__(order=order, tag=tag)

    def get_kwargs(self):
        return {
            "order": self.order,
            "tag": self.tag,
        }

    def core(self, args={}):
        self.order.append(self.tag)
        return self.generate_core_response()


class PriorityBaselineProposalEvent(BaseEvent):
    def __init__(self, order: list[str]):
        self.order = order
        super().__init__(order=order)

    def get_kwargs(self):
        return {
            "order": self.order,
        }

    def core(self, args={}):
        self.order.append("base_event_core")
        self.propose(Packet([PriorityTaggedEvent(self.order, "priority_0")]), priority=0)
        return self.generate_core_response()


class PriorityEscalatingReactor(TestReactor):
    def __init__(self, order: list[str]):
        self.identifier = "priority-escalating-reactor"
        super().__init__(group=EngineGroup.EXTERNAL_REACTORS, )
        self.order = order

    def event_match(self, event: Event) -> bool:
        return isinstance(event, PriorityBaselineProposalEvent)

    def event_effect(self) -> bool:
        return True

    def react(self, args={}):
        self.order.append("reactor")
        self.propose(Packet([PriorityTaggedEvent(self.order, "priority_1")]), priority=1)
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "priority-escalating-reactor"


class InterruptInsertedPayloadEvent(BaseEvent):
    def __init__(self, state: MutableState, metrics: dict[str, int]):
        self.state = state
        self.metrics = metrics
        super().__init__(state=state, metrics=metrics)

    def get_kwargs(self):
        return {
            "state": self.state,
            "metrics": self.metrics,
        }

    def core(self, args={}):
        self.metrics["payload_core_runs"] += 1
        self.state.value += 10
        return self.generate_core_response()

    def invert_core(self, args={}) -> None:
        self.metrics["payload_invert_runs"] += 1
        self.state.value -= 10


class InterruptThenSkipAssessor(TestAssessor):
    def __init__(self, owner_event: Event, state: MutableState, metrics: dict[str, int]):
        self.identifier = "interrupt-then-skip-assessor"
        super().__init__(group=EngineGroup.INTERNAL_1, )
        self.owner_event = owner_event
        self.state = state
        self.metrics = metrics
        self.did_interrupt = False

    def event_match(self, event: Event) -> bool:
        return event is self.owner_event

    def event_effect(self) -> bool:
        return True

    def assess(self, args={}):
        self.metrics["assessor_runs"] += 1
        if not self.did_interrupt:
            self.did_interrupt = True
            self.metrics["interrupts"] += 1
            return self.generate_response(
                ResponseType.INTERRUPT,
                Interrupt[Event]([InterruptInsertedPayloadEvent(self.state, self.metrics)]),
            )
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "interrupt-then-skip-assessor"


class InterruptThenSkipEvent(BaseEvent):
    def __init__(self, state: MutableState, metrics: dict[str, int]):
        self.state = state
        self.metrics = metrics
        super().__init__(state=state, metrics=metrics)

    def get_kwargs(self):
        return {
            "state": self.state,
            "metrics": self.metrics,
        }

    def generate_internal_listeners(self):
        self.event_listener_groups[EngineGroup.INTERNAL_1].append(
            InterruptThenSkipAssessor(self, self.state, self.metrics)
        )
        self.event_listener_groups[EngineGroup.INTERNAL_3].append(
            SkipListener(EngineGroup.INTERNAL_3)
        )

    def core(self, args={}):
        self.metrics["original_core_runs"] += 1
        self.state.value += 1
        return self.generate_core_response()

    def invert_core(self, args={}) -> None:
        self.metrics["original_invert_runs"] += 1
        self.state.value -= 1


class AttachTracingModifier(TestModifier):
    def __init__(self, identifier: str, group: EngineGroup, trace: list[tuple]):
        self.identifier = identifier
        super().__init__(group=group, )
        self.trace = trace
        self.attach_count = 0
        self.detach_count = 0
        self.modify_count = 0

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return True

    def attach_to_event(self, e: Event):
        super().attach_to_event(e)
        self.attach_count += 1
        self.trace.append(("attach", self.identifier, type(e).__name__))

    def detach_from_event(self):
        self.trace.append(("detach", self.identifier, self.attached_event is not None))
        self.detach_count += 1
        super().detach_from_event()

    def modify(self, args={}):
        self.modify_count += 1
        self.trace.append(("modify", self.identifier))
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "attach-tracing-modifier"


class AttachStateConstraint(TagConstraint):
    def __init__(self, identifier: str, trace: list[tuple]):
        super().__init__(identifier)
        self.trace = trace

    def match(self, obj) -> bool:
        if isinstance(obj, Constraint):
            return False
        attached = getattr(obj, "attached_event", None) is not None
        self.trace.append(("constrain_match", getattr(obj, "identifier", None), attached))
        return getattr(obj, "identifier", None) == self.identifier


class AttachTracingAssessor(TestAssessor):
    def __init__(self, identifier: str, group: EngineGroup, trace: list[tuple]):
        self.identifier = identifier
        super().__init__(group=group, )
        self.trace = trace
        self.attach_count = 0
        self.detach_count = 0
        self.assess_count = 0

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return True

    def attach_to_event(self, e: Event):
        super().attach_to_event(e)
        self.attach_count += 1
        self.trace.append(("attach", self.identifier, type(e).__name__))

    def detach_from_event(self):
        self.trace.append(("detach", self.identifier, self.attached_event is not None))
        self.detach_count += 1
        super().detach_from_event()

    def assess(self, args={}):
        self.assess_count += 1
        self.trace.append(("assess", self.identifier))
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "attach-tracing-assessor"


class AttachTracingReactor(TestReactor):
    def __init__(self, identifier: str, group: EngineGroup, trace: list[tuple]):
        self.identifier = identifier
        super().__init__(group=group, )
        self.trace = trace
        self.attach_count = 0
        self.detach_count = 0
        self.react_count = 0

    def event_match(self, event: Event) -> bool:
        return True

    def event_effect(self) -> bool:
        return True

    def attach_to_event(self, e: Event):
        super().attach_to_event(e)
        self.attach_count += 1
        self.trace.append(("attach", self.identifier, type(e).__name__))

    def detach_from_event(self):
        self.trace.append(("detach", self.identifier, self.attached_event is not None))
        self.detach_count += 1
        super().detach_from_event()

    def react(self, args={}):
        self.react_count += 1
        self.trace.append(("react", self.identifier))
        return self.generate_response(ResponseType.ACCEPT)

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return False

    def __str__(self):
        return "attach-tracing-reactor"


class ToggleCacheSetEvent(BaseEvent):
    def __init__(self, cache: RollbackCache, key: str, metrics: dict[str, int]):
        self.cache = cache
        self.key = key
        self.metrics = metrics
        super().__init__(cache=cache, key=key, metrics=metrics)

    def get_kwargs(self):
        return {
            "cache": self.cache,
            "key": self.key,
            "metrics": self.metrics,
        }

    def core(self, args={}):
        self.metrics["set_runs"] += 1
        self.cache.set(self.key, True)
        return self.generate_core_response()


class ToggleCacheEraseEvent(BaseEvent):
    def __init__(self, cache: RollbackCache, key: str, metrics: dict[str, int]):
        self.cache = cache
        self.key = key
        self.metrics = metrics
        super().__init__(cache=cache, key=key, metrics=metrics)

    def get_kwargs(self):
        return {
            "cache": self.cache,
            "key": self.key,
            "metrics": self.metrics,
        }

    def core(self, args={}):
        self.metrics["erase_runs"] += 1
        self.cache.delete(self.key)
        return self.generate_core_response()


class IndefiniteCacheToggleInterruptEvent(BaseEvent):
    def __init__(self, cache: RollbackCache, key: str, metrics: dict[str, int]):
        self.cache = cache
        self.key = key
        self.metrics = metrics
        super().__init__(cache=cache, key=key, metrics=metrics)

    def get_kwargs(self):
        return {
            "cache": self.cache,
            "key": self.key,
            "metrics": self.metrics,
        }

    def core(self, args={}):
        self.metrics["playcard_calls"] += 1
        if self.cache.get(self.key) is None:
            return self.generate_core_response(
                ResponseType.INTERRUPT,
                Interrupt[Event]([ToggleCacheSetEvent(self.cache, self.key, self.metrics)]),
            )
        return self.generate_core_response(
            ResponseType.INTERRUPT,
            Interrupt[Event]([ToggleCacheEraseEvent(self.cache, self.key, self.metrics)]),
        )


class EngineEdgeCaseTests(unittest.TestCase):
    def make_engine(self) -> Engine[Event]:
        eng = Engine[Event]()
        eng._packet_reactors = []

        # History API now raises on empty chapter updates. For event packets that
        # produce no history entries (e.g., constrained/no-op flows), treat these
        # transitions as no-op history updates in tests.
        history_update = eng.event_history.set_unformalized_changes

        def safe_set_unformalized_changes(new_state: HistoryState):
            try:
                return history_update(new_state)
            except IndexError:
                return []

        eng.event_history.set_unformalized_changes = safe_set_unformalized_changes
        return eng

    def add_packet_listener(self, eng: Engine[Event], listener: AbstractPacketListener[Event]):
        listener.engine = eng
        eng._packet_reactors.append(listener)

    def drain_engine(self, eng: Engine[Event], max_steps: int = 200):
        last = None
        for _ in range(max_steps):
            last = eng.forward({})
            if last.response_type == ResponseType.NO_MORE_EVENTS:
                return last
        self.fail("Engine did not reach NO_MORE_EVENTS in max_steps")

    def forward_with_cache(self, eng: Engine[Event], cache: RollbackCache, args=None):
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

    def forward_until(self, eng: Engine[Event], predicate, max_steps: int = 200):
        last = None
        for _ in range(max_steps):
            last = eng.forward({})
            if predicate(last):
                return last
        return last

    def test_skip_before_core_reopens_queue_for_next_packets(self):
        eng = self.make_engine()
        eng._propose(Packet([PreCoreSkipEvent()]))

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(eng._queue.queue_status, QueueStatus.OPEN)

        state = MutableState()
        eng._propose(Packet([DeltaEvent(state, 3)]))
        last_after = self.drain_engine(eng)
        self.assertEqual(last_after.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 3)

    def test_packet_listener_attaches_by_finished_packet_or_skip_status(self):
        eng = self.make_engine()
        state = MutableState()
        finished_listener = PacketStatusProbeListener({ResponseType.FINISHED_PACKET})
        skip_listener = PacketStatusProbeListener({ResponseType.SKIP})
        self.add_packet_listener(eng, finished_listener)
        self.add_packet_listener(eng, skip_listener)

        eng._propose(Packet([DeltaEvent(state, 1)]))
        self.drain_engine(eng)

        self.assertEqual(finished_listener.react_count, 1)
        self.assertEqual(skip_listener.react_count, 0)

        eng._propose(Packet([ExplicitSkipEvent()]))
        self.drain_engine(eng)

        self.assertEqual(finished_listener.react_count, 1)
        self.assertEqual(skip_listener.react_count, 1)
        self.assertIn(ResponseType.FINISHED_PACKET, finished_listener.seen_statuses)
        self.assertIn(ResponseType.SKIP, skip_listener.seen_statuses)

    def test_packet_listener_can_propose_events_even_on_skip(self):
        eng = self.make_engine()
        state = MutableState()
        skip_listener = PacketStatusProbeListener(
            {ResponseType.SKIP},
            response_type=ResponseType.ACCEPT,
            state=state,
            propose_delta=5,
            invalidate_after_react=True,
        )
        self.add_packet_listener(eng, skip_listener)

        eng._propose(Packet([ExplicitSkipEvent()]))
        self.drain_engine(eng)

        self.assertEqual(skip_listener.react_count, 1)
        self.assertEqual(state.value, 5)

    def test_multiple_packet_listeners_can_attach_and_propose_together(self):
        eng = self.make_engine()
        state = MutableState()
        listener_a = PacketStatusProbeListener(
            {ResponseType.FINISHED_PACKET},
            response_type=ResponseType.ACCEPT,
            state=state,
            propose_delta=2,
            propose_priority=1,
            invalidate_after_react=True,
        )
        listener_b = PacketStatusProbeListener(
            {ResponseType.FINISHED_PACKET},
            response_type=ResponseType.ACCEPT,
            state=state,
            propose_delta=3,
            propose_priority=0,
            invalidate_after_react=True,
        )
        self.add_packet_listener(eng, listener_a)
        self.add_packet_listener(eng, listener_b)

        eng._propose(Packet([BaseEvent()]))
        self.drain_engine(eng)

        self.assertEqual(listener_a.react_count, 1)
        self.assertEqual(listener_b.react_count, 1)
        self.assertEqual(state.value, 5)

    def test_packet_listener_skip_after_finished_packet_keeps_engine_progressing(self):
        eng = self.make_engine()
        state = MutableState()
        skip_on_finish_listener = PacketStatusProbeListener(
            {ResponseType.FINISHED_PACKET},
            response_type=ResponseType.SKIP,
            invalidate_after_react=True,
        )
        self.add_packet_listener(eng, skip_on_finish_listener)

        eng._propose(Packet([DeltaEvent(state, 1)]))

        saw_skip = False
        final_response = None
        for _ in range(50):
            response = eng.forward({})
            if response.response_type == ResponseType.SKIP:
                saw_skip = True
            if response.response_type == ResponseType.NO_MORE_EVENTS:
                final_response = response
                break

        self.assertTrue(saw_skip)
        self.assertIsNotNone(final_response)
        self.assertEqual(state.value, 1)
        self.assertEqual(skip_on_finish_listener.react_count, 1)

        eng._propose(Packet([DeltaEvent(state, 2)]))
        post_response = self.drain_engine(eng)
        self.assertEqual(post_response.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 3)

    def test_skip_after_core_reverts_current_and_prior_events_in_packet(self):
        eng = self.make_engine()
        state = MutableState()
        eng._propose(Packet([
            DeltaEvent(state, 5),
            PostCoreSkipEvent(state, 7),
        ]))

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 0)

    def test_skip_clears_buffered_proposals_from_failed_packet(self):
        eng = self.make_engine()
        state = MutableState()
        eng._propose(Packet([
            DeltaEvent(state, 2, propose_extra=True),
            PreCoreSkipEvent(),
        ]))

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(eng._queue.queue_len(), 0)
        self.assertEqual(state.value, 0)

    def test_listener_added_mid_packet_is_not_persisted_after_skip(self):
        eng = self.make_engine()
        listener = CountingExternalListener(identifier="tmp-listener")
        eng._propose(Packet([
            AddListenerEvent(listener),
            PreCoreSkipEvent(),
        ]))
        self.drain_engine(eng)

        eng._propose(Packet([BaseEvent()]))
        self.drain_engine(eng)
        self.assertEqual(listener.call_count, 0)
        self.assertTrue(listener._invalidated)

    def test_constraint_added_mid_packet_is_not_persisted_after_skip(self):
        eng = self.make_engine()
        listener = CountingExternalListener(identifier="tagged")
        eng.add_listener(listener)

        transient_constraint = TagConstraint("tagged")
        eng._propose(Packet([
            AddConstraintEvent(transient_constraint),
            PreCoreSkipEvent(),
        ]))
        self.drain_engine(eng)
        baseline_calls = listener.call_count

        eng._propose(Packet([BaseEvent()]))
        self.drain_engine(eng)
        self.assertEqual(listener.call_count, baseline_calls + 1)
        self.assertNotIn(transient_constraint, eng._constraints)

    def test_listener_invalidated_after_event_does_not_attach_to_next_event_in_packet(self):
        eng = self.make_engine()
        listener = CountingExternalListener(identifier="ttl-listener", ttl_events=1)
        eng.add_listener(listener)

        eng._propose(Packet([BaseEvent(), BaseEvent()]))
        self.drain_engine(eng)

        self.assertEqual(listener.call_count, 1)
        self.assertTrue(listener._invalidated)

    def test_requires_query_replays_same_listener_until_answered(self):
        eng = self.make_engine()
        query_listener = QueryListener()

        class QueryEvent(BaseEvent):
            def generate_internal_listeners(self):
                self.event_listener_groups[EngineGroup.INTERNAL_1].append(query_listener)

        eng._propose(Packet([QueryEvent()]))

        self.assertEqual(eng.forward({}).response_type, ResponseType.NEXT_PACKET)
        self.assertEqual(eng.forward({}).response_type, ResponseType.NEXT_EVENT)

        first_query = None
        for _ in range(10):
            maybe_query = eng.forward({})
            if maybe_query.response_type == ResponseType.REQUIRES_QUERY:
                first_query = maybe_query
                break

        self.assertIsNotNone(first_query)
        first_query = cast(Response, first_query)
        self.assertEqual(first_query.response_type, ResponseType.REQUIRES_QUERY)
        self.assertEqual(query_listener.call_count, 1)

        query_listener.approved = True
        answered = eng.forward({})
        self.assertEqual(answered.response_type, ResponseType.ACCEPT)
        self.assertEqual(query_listener.call_count, 2)

        final = self.drain_engine(eng)
        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)

    def test_invalidated_internal_listener_is_skipped(self):
        eng = self.make_engine()
        event = InternalInvalidatedEvent()
        eng._propose(Packet([event]))

        self.drain_engine(eng)
        self.assertEqual(event.listener.call_count, 0)

    def test_internal_listener_with_false_event_effect_is_skipped(self):
        eng = self.make_engine()
        event = InternalNoEffectEvent()
        eng._propose(Packet([event]))

        self.drain_engine(eng)
        self.assertEqual(event.listener.call_count, 0)

    def test_proposed_event_assembler_resolves_callable_kwargs_at_assembly_time(self):
        eng = self.make_engine()
        state = MutableState()
        deferred_delta_source = {"delta": 1}

        eng._propose(Packet([ProposeDeferredAssemblerEvent(state, deferred_delta_source)]))

        response = None
        for _ in range(50):
            response = eng.forward({})
            if response.response_type == ResponseType.FINISHED_PACKET:
                break
        self.assertIsNotNone(response)
        response = cast(Response, response)
        self.assertEqual(response.response_type, ResponseType.FINISHED_PACKET)

        deferred_delta_source["delta"] = 6

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 6)

    def test_packet_factory_item_runs_when_next_event_is_requested(self):
        eng = self.make_engine()
        state = MutableState()
        metrics = {"packet_assembles": 0}

        def packet_factory():
            metrics["packet_assembles"] += 1
            return [DeltaEvent(state, 4)]

        eng._propose(Packet([packet_factory]))  # type: ignore[arg-type]

        self.assertEqual(metrics["packet_assembles"], 0)

        next_packet = eng.forward({})
        self.assertEqual(next_packet.response_type, ResponseType.NEXT_PACKET)
        self.assertEqual(metrics["packet_assembles"], 0)

        next_event = eng.forward({})
        self.assertEqual(next_event.response_type, ResponseType.NEXT_EVENT)
        self.assertEqual(metrics["packet_assembles"], 1)

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 4)
        self.assertEqual(metrics["packet_assembles"], 1)

    def test_packet_mixes_event_and_lazy_factory_items(self):
        eng = self.make_engine()
        state = MutableState()
        deferred_delta_source = {"delta": 5}

        eng._propose(Packet(
            [
                DeltaEvent(state, 2),
                lambda: [DeltaEvent(state, deferred_delta_source["delta"], propose_extra=False)],
                DeltaEvent(state, 3),
            ]
        ))

        self.assertEqual(eng.forward({}).response_type, ResponseType.NEXT_PACKET)
        self.assertEqual(eng.forward({}).response_type, ResponseType.NEXT_EVENT)

        deferred_delta_source["delta"] = 7

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 12)

    def test_empty_packet_is_a_safe_noop(self):
        eng = self.make_engine()
        listener = CountingExternalListener(identifier="baseline-listener")
        constraint = TagConstraint("never-matches")
        eng.add_listener(listener)
        eng.add_constraint(constraint)

        eng._propose(Packet([]))

        first = eng.forward({})
        second = eng.forward({})

        self.assertEqual(first.response_type, ResponseType.NEXT_PACKET)
        self.assertEqual(second.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertIsNone(eng.event_running)
        self.assertEqual(len(eng.packet_running), 0)
        self.assertEqual(eng._queue.queue_len(), 0)
        self.assertEqual(eng._queue.queue_status, QueueStatus.OPEN)
        self.assertEqual(listener.call_count, 0)
        self.assertIn(constraint, eng._constraints)

    def test_event_assembly_occurs_immediately_before_event_running(self):
        eng = self.make_engine()
        state = MutableState()
        metrics = {"event_kwarg_resolves": 0}
        delta_source = {"delta": 7}

        eng._propose(Packet(
            [
                lambda: [
                    AssemblyTimingDeltaEvent(
                        state=state,
                        metrics=metrics,
                        delta_source=delta_source,
                    )
                ]
            ]
        ))

        self.assertEqual(metrics["event_kwarg_resolves"], 0)

        next_packet = eng.forward({})
        self.assertEqual(next_packet.response_type, ResponseType.NEXT_PACKET)
        self.assertEqual(metrics["event_kwarg_resolves"], 0)

        next_event = eng.forward({})
        self.assertEqual(next_event.response_type, ResponseType.NEXT_EVENT)
        self.assertEqual(metrics["event_kwarg_resolves"], 1)

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 7)
        self.assertEqual(metrics["event_kwarg_resolves"], 1)

    def test_lazy_factory_event_uses_latest_values_when_assembled(self):
        eng = self.make_engine()
        state = MutableState()
        deferred_delta_source = {"delta": 2}

        eng._propose(Packet([
            lambda: [
                DeltaEvent(
                    state,
                    deferred_delta_source["delta"],
                    propose_extra=False,
                )
            ]
        ]))
        deferred_delta_source["delta"] = 9

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 9)

    def test_normal_event_instance_stays_static_while_lazy_factory_is_just_in_time(self):
        eng = self.make_engine()
        state = MutableState()
        delta_source = {"delta": 3}

        eng._propose(Packet(
            [
                DeltaEvent(state, delta_source["delta"]),
                lambda: [
                    DeltaEvent(
                        state=state,
                        delta=delta_source["delta"],
                        propose_extra=False,
                    )
                ],
            ]
        ))

        # Mutate after packet composition; normal event should keep 3 while lazy factory reads 7.
        delta_source["delta"] = 7

        last = self.drain_engine(eng)
        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(state.value, 10)

    def test_later_event_lambda_uses_object_modified_by_prior_event(self):
        eng = self.make_engine()
        state = MutableState()
        delta_source = {"delta": 1}
        metrics = {
            "mutations": 0,
            "event_kwarg_resolves": 0,
        }

        eng._propose(Packet(
            [
                MutateDeltaSourceEvent(delta_source, new_delta=11, metrics=metrics),
                lambda: [
                    AssemblyTimingDeltaEvent(
                        state=state,
                        metrics=metrics,
                        delta_source=delta_source,
                    )
                ],
            ]
        ))

        last = self.drain_engine(eng)

        self.assertEqual(last.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(metrics["mutations"], 1)
        self.assertEqual(metrics["event_kwarg_resolves"], 1)
        self.assertEqual(delta_source["delta"], 11)
        self.assertEqual(state.value, 11)

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

        eng._propose(Packet([UpdatePacketReplayEvent(cache, touch_key, input_key)]))

        saw_interrupt = False
        saw_requires_query = False
        final_response = None

        for _ in range(150):
            response = self.forward_with_cache(eng, cache, {})
            if response.response_type == ResponseType.INTERRUPT:
                saw_interrupt = True
            if response.response_type == ResponseType.REQUIRES_QUERY:
                if response_query_type(response) == "ordering":
                    response = self.forward_with_cache(
                        eng,
                        cache,
                        {"group_ordering": response_unordered_groups(response)},
                    )
                elif response_query_type(response) == "card_query":
                    saw_requires_query = True
                    response = self.forward_with_cache(eng, cache, {"input_result": [99]})

            if response.response_type == ResponseType.SKIP:
                final_response = response
                break

        self.assertTrue(saw_interrupt)
        self.assertTrue(saw_requires_query)
        self.assertIsNotNone(final_response)
        final_response = cast(Response, final_response)
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

        eng._propose(Packet([BaseEvent()]))
        final = self.drain_engine(eng)

        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(constrained_listener.call_count, 0)

    def test_ordering_required_with_two_non_constrained_listeners(self):
        eng = self.make_engine()
        listener_a = CountingModifierListener("a")
        listener_b = CountingModifierListener("b")
        eng.add_listener(listener_a)
        eng.add_listener(listener_b)

        eng._propose(Packet([BaseEvent()]))
        ordering_query = self.forward_until(
            eng,
            lambda r: r.response_type in [ResponseType.REQUIRES_QUERY, ResponseType.NO_MORE_EVENTS],
        )

        ordering_query = cast(Response, ordering_query)
        self.assertEqual(ordering_query.response_type, ResponseType.REQUIRES_QUERY)
        self.assertEqual(response_query_type(ordering_query), "ordering")
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

        eng._propose(Packet([BaseEvent()]))

        saw_constraint_announcement = False
        ordering_query = None
        for _ in range(50):
            response = eng.forward({})
            if response_data_value(response, "constrainer_announced") == "tag-constraint":
                saw_constraint_announcement = True
            if response.response_type == ResponseType.REQUIRES_QUERY:
                ordering_query = response
                break

        self.assertTrue(saw_constraint_announcement)
        self.assertIsNotNone(ordering_query)
        self.assertEqual(response_query_type(ordering_query), "ordering")
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

        eng._propose(Packet([BaseEvent()]))

        saw_ordering_query = False
        final = None
        for _ in range(100):
            response = eng.forward({})
            if response.response_type == ResponseType.REQUIRES_QUERY and response_query_type(response) == "ordering":
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
        eng._propose(Packet([OverrideCandidateEvent(metrics)]))

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

    def test_event_ff_forces_fast_forward_to_end(self):
        eng = self.make_engine()
        metrics = {
            "assess_runs": 0,
            "core_runs": 0,
            "downstream_runs": 0,
        }

        eng.add_listener(ForceFastForwardAssessor(metrics))
        eng.add_listener(ForceFastForwardDownstreamModifier(metrics))
        eng._propose(Packet([ForceFastForwardEvent(metrics)]))

        saw_finished_packet = False

        for _ in range(200):
            response = eng.forward({})
            if response.response_type == ResponseType.FINISHED_PACKET:
                saw_finished_packet = True
            elif response.response_type == ResponseType.NO_MORE_EVENTS:
                break

        self.assertTrue(saw_finished_packet)
        self.assertEqual(metrics["assess_runs"], 1)
        self.assertEqual(metrics["core_runs"], 0)
        self.assertEqual(metrics["downstream_runs"], 0)

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
        eng._propose(Packet([OverrideCandidateEvent(metrics)]))

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

        mod_a = listdInterruptModifier("mod-a", cache, "input_a")
        mod_b = listdInterruptModifier("mod-b", cache, "input_b")
        eng.add_listener(mod_a)
        eng.add_listener(mod_b)

        eng._propose(Packet([InterruptChainReplayEvent(cache, metrics)]))

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
                if response_query_type(response) == "ordering":
                    saw_ordering = True
                    next_args = {"group_ordering": response_unordered_groups(response)}
                elif response_query_type(response) == "card_query":
                    next_args = {"input_result": [1]}
                else:
                    self.fail(f"Unexpected query type: {response_query_type(response)}")
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

    def test_interrupt_runs_payload_before_resuming_interrupted_event(self):
        eng = self.make_engine()
        order: list[str] = []

        eng.add_listener(OrderedInterruptAssessor(order))
        eng._propose(Packet([OrderedInterruptCandidateEvent(order)]))

        final = self.drain_engine(eng)
        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(order, ["interrupt", "payload_core", "resume", "candidate_core"])

    def test_core_interrupt_runs_payload_before_resuming_core(self):
        eng = self.make_engine()
        order: list[str] = []

        eng._propose(Packet([OrderedCoreInterruptEvent(order)]))

        final = self.drain_engine(eng)
        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(order, ["core_interrupt", "payload_core", "core_resume"])

    def test_modifier_interrupt_runs_payload_before_resuming_modifier_then_core(self):
        eng = self.make_engine()
        order: list[str] = []

        eng.add_listener(OrderedInterruptModifier(order))
        eng._propose(Packet([OrderedModifierInterruptCandidateEvent(order)]))

        final = self.drain_engine(eng)
        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(order, ["modifier_interrupt", "payload_core", "modifier_resume", "candidate_core"])

    def test_reactor_interrupt_runs_payload_before_resuming_reactor(self):
        eng = self.make_engine()
        order: list[str] = []

        eng.add_listener(OrderedInterruptReactor(order))
        eng._propose(Packet([OrderedReactorInterruptCandidateEvent(order)]))

        final = self.drain_engine(eng)
        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(order, ["candidate_core", "reactor_interrupt", "payload_core", "reactor_resume"])

    def test_reactor_priority_proposal_runs_before_baseline_priority_zero_proposal(self):
        eng = self.make_engine()
        order: list[str] = []

        eng.add_listener(PriorityEscalatingReactor(order))
        eng._propose(Packet([PriorityBaselineProposalEvent(order)]))

        final = self.drain_engine(eng)

        self.assertEqual(final.response_type, ResponseType.NO_MORE_EVENTS)
        self.assertEqual(order, ["base_event_core", "reactor", "priority_1", "priority_0"])

    def test_interrupt_inserted_event_then_original_skip_undoes_both_cores(self):
        eng = self.make_engine()
        state = MutableState()
        metrics = {
            "interrupts": 0,
            "assessor_runs": 0,
            "payload_core_runs": 0,
            "payload_invert_runs": 0,
            "original_core_runs": 0,
            "original_invert_runs": 0,
        }

        eng._propose(Packet([InterruptThenSkipEvent(state, metrics)]))

        saw_interrupt = False
        saw_skip = False

        for _ in range(300):
            response = eng.forward({})
            if response.response_type == ResponseType.INTERRUPT:
                saw_interrupt = True
            elif response.response_type == ResponseType.SKIP:
                saw_skip = True
            elif response.response_type == ResponseType.NO_MORE_EVENTS:
                break

        self.assertTrue(saw_interrupt)
        self.assertTrue(saw_skip)
        self.assertEqual(metrics["interrupts"], 1)
        self.assertEqual(metrics["payload_core_runs"], 1)
        self.assertEqual(metrics["payload_invert_runs"], 1)
        self.assertEqual(metrics["original_core_runs"], 1)
        self.assertEqual(metrics["original_invert_runs"], 1)
        self.assertEqual(state.value, 0)

    def test_external_listener_attaches_before_constraint_match(self):
        eng = self.make_engine()
        trace: list[tuple] = []

        listener = AttachTracingModifier("trace-target", EngineGroup.EXTERNAL_MODIFIERS_2, trace)
        eng.add_listener(listener)
        eng.add_constraint(AttachStateConstraint("trace-target", trace))
        eng._propose(Packet([BaseEvent()]))

        self.drain_engine(eng)

        attach_idx = next(i for i, t in enumerate(trace) if t[0] == "attach" and t[1] == "trace-target")
        match_idx = next(i for i, t in enumerate(trace) if t[0] == "constrain_match" and t[1] == "trace-target")

        self.assertLess(attach_idx, match_idx)
        self.assertTrue(trace[match_idx][2])
        self.assertEqual(listener.modify_count, 0)

    def test_constrained_listener_detaches_after_attach(self):
        eng = self.make_engine()
        trace: list[tuple] = []

        listener = AttachTracingModifier("detach-target", EngineGroup.EXTERNAL_MODIFIERS_2, trace)
        eng.add_listener(listener)
        eng.add_constraint(AttachStateConstraint("detach-target", trace))
        eng._propose(Packet([BaseEvent()]))

        self.drain_engine(eng)

        self.assertEqual(listener.attach_count, 1)
        self.assertEqual(listener.detach_count, 1)
        self.assertIsNone(listener.attached_event)
        self.assertEqual(listener.modify_count, 0)

    def test_only_matching_listener_is_constrained_after_attachment(self):
        eng = self.make_engine()
        trace: list[tuple] = []

        constrained = AttachTracingModifier("constrained-target", EngineGroup.EXTERNAL_MODIFIERS_2, trace)
        survivor = AttachTracingModifier("survivor-target", EngineGroup.EXTERNAL_MODIFIERS_2, trace)

        eng.add_listener(constrained)
        eng.add_listener(survivor)
        eng.add_constraint(AttachStateConstraint("constrained-target", trace))
        eng._propose(Packet([BaseEvent()]))

        self.drain_engine(eng)

        constrained_match_idx = next(
            i for i, t in enumerate(trace) if t[0] == "constrain_match" and t[1] == "constrained-target"
        )
        self.assertTrue(trace[constrained_match_idx][2])
        self.assertEqual(constrained.modify_count, 0)
        self.assertEqual(survivor.modify_count, 1)

    def test_assessor_listener_attaches_before_constraint_match(self):
        eng = self.make_engine()
        trace: list[tuple] = []

        listener = AttachTracingAssessor("assessor-target", EngineGroup.EXTERNAL_PRECHECK_1, trace)
        eng.add_listener(listener)
        eng.add_constraint(AttachStateConstraint("assessor-target", trace))
        eng._propose(Packet([BaseEvent()]))

        self.drain_engine(eng)

        attach_idx = next(i for i, t in enumerate(trace) if t[0] == "attach" and t[1] == "assessor-target")
        match_idx = next(i for i, t in enumerate(trace) if t[0] == "constrain_match" and t[1] == "assessor-target")

        self.assertLess(attach_idx, match_idx)
        self.assertTrue(trace[match_idx][2])
        self.assertEqual(listener.assess_count, 0)
        self.assertEqual(listener.detach_count, 1)

    def test_reactor_listener_attaches_before_constraint_match(self):
        eng = self.make_engine()
        trace: list[tuple] = []

        listener = AttachTracingReactor("reactor-target", EngineGroup.EXTERNAL_REACTORS, trace)
        eng.add_listener(listener)
        eng.add_constraint(AttachStateConstraint("reactor-target", trace))
        eng._propose(Packet([BaseEvent()]))

        self.drain_engine(eng)

        attach_idx = next(i for i, t in enumerate(trace) if t[0] == "attach" and t[1] == "reactor-target")
        match_idx = next(i for i, t in enumerate(trace) if t[0] == "constrain_match" and t[1] == "reactor-target")

        self.assertLess(attach_idx, match_idx)
        self.assertTrue(trace[match_idx][2])
        self.assertEqual(listener.react_count, 0)
        self.assertEqual(listener.detach_count, 1)

    def test_core_interrupt_toggle_cache_event_does_not_terminate(self):
        eng = self.make_engine()
        cache = RollbackCache()
        key = "X"
        metrics = {
            "playcard_calls": 0,
            "set_runs": 0,
            "erase_runs": 0,
        }

        eng._propose(Packet([IndefiniteCacheToggleInterruptEvent(cache, key, metrics)]))

        terminal_responses = {
            ResponseType.NO_MORE_EVENTS,
            ResponseType.FINISHED_PACKET,
            ResponseType.GAME_END,
            ResponseType.SKIP,
        }

        saw_interrupt = 0
        steps = 240
        for _ in range(steps):
            response = eng.forward({})
            if response.response_type == ResponseType.INTERRUPT:
                saw_interrupt += 1
            self.assertNotIn(
                response.response_type,
                terminal_responses,
                "Toggle cache interrupt loop unexpectedly terminated",
            )

        self.assertGreaterEqual(saw_interrupt, 8)
        self.assertEqual(metrics["playcard_calls"], saw_interrupt)
        self.assertGreater(metrics["set_runs"], 0)
        self.assertGreater(metrics["erase_runs"], 0)
        self.assertLessEqual(abs(metrics["set_runs"] - metrics["erase_runs"]), 1)

        queue_drained = (
            eng.event_running is None
            and len(eng.packet_running) == 0
            and eng._queue.queue_len() == 0
        )
        self.assertFalse(queue_drained)


class EngineHistoryTests(unittest.TestCase):
    def test_set_unformalized_changes_returns_matching_nonformalized_events(self):
        history = EngineHistory[Event]()
        state = MutableState()
        first = DeltaEvent(state, 1)
        second = DeltaEvent(state, 2)

        history.propose_event(first)
        history.propose_event(second)

        changed = history.set_unformalized_changes(HistoryState.UNDONE)
        self.assertEqual(changed, [first, second])

    def test_new_chapter_requires_formalized_changes(self):
        history = EngineHistory[Event]()
        history.propose_event(BaseEvent())

        with self.assertRaises(Exception):
            history.new_chapter()

        last_event, _ = history.history[0][-1]
        history.history[0][-1] = (last_event, HistoryState.FORMALIZED)
        history.new_chapter()

        self.assertIn(1, history.history)
        self.assertEqual(history.history[1], [])

    def test_search_handles_missing_chapter_and_matches_kwargs(self):
        history = EngineHistory[Event]()
        state = MutableState()
        event = DeltaEvent(state, 5)
        history.propose_event(event)

        missing_event, missing_idx = history.search(99, DeltaEvent, {"delta": 5})
        self.assertIsNone(missing_event)
        self.assertEqual(missing_idx, -1)

        found_event, found_idx = history.search(
            0,
            DeltaEvent,
            {"delta": 5},
            index_to_start=0,
            specific_state=HistoryState.NONFORMALIZED,
        )
        self.assertIs(found_event, event)
        self.assertEqual(found_idx, 0)

    def test_search_returns_absolute_index_and_skips_nonmatching_kwargs(self):
        history = EngineHistory[Event]()
        state = MutableState()
        first = DeltaEvent(state, 3)
        second = DeltaEvent(state, 9)
        third = DeltaEvent(state, 3)

        history.propose_event(first)
        history.propose_event(second)
        history.propose_event(third)

        found_event, found_idx = history.search(
            0,
            DeltaEvent,
            {"delta": 3},
            index_to_start=1,
            specific_state=HistoryState.NONFORMALIZED,
        )

        self.assertIs(found_event, third)
        self.assertEqual(found_idx, 2)


if __name__ == "__main__":
    unittest.main()
