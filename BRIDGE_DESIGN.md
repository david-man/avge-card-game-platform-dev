# Frontend Game Bridge Design

## Purpose

`FrontendGameBridge` is the translation and flow-control layer between:

- Frontend events (`/events` payloads from Phaser UI)
- Engine responses (`env.forward(...)` responses)
- Scanner commands (`input ...`, `mv ...`, `phase ...`, `notify ...`) consumed by the frontend replay loop

The bridge lives in [card-game-platform/card_game/server/game_runner.py](card-game-platform/card_game/server/game_runner.py).

This document explains exactly how command emission, ACK gating, query prompting, and phase synchronization work.

---

## Scope and Responsibilities

The bridge is responsible for:

1. Translating frontend interaction events into engine args (for example `input_result`, `energy_moved`, phase buttons).
2. Draining the engine incrementally and converting responses to frontend scanner commands.
3. Enforcing strict command-level ACK sequencing.
4. Preventing duplicate input prompt emissions for unresolved `InputEvent` queries.
5. Keeping frontend phase state synchronized (`phase no-input|phase2|atk`).

The bridge is not responsible for:

- Rendering UI overlays
- Applying Phaser scene mutations
- Core game logic decisions in card/event implementations

---

## High-Level Data Flow

1. Frontend sends event to `/events`.
2. Server passes event to `FrontendGameBridge.handle_frontend_event(...)`.
3. Bridge either:
   - accepts ACK and emits next queued command, or
   - queues event while waiting for ACK, or
   - applies event to engine and drains engine for next command batch.
4. Bridge returns `commands` list.
5. Server pushes each command into scanner queue.
6. Frontend scanner loop consumes one command, applies it, sends terminal ACK.

---

## Core State in FrontendGameBridge

Key fields in [card-game-platform/card_game/server/game_runner.py](card-game-platform/card_game/server/game_runner.py):

- `_outbound_command_queue`: buffered scanner commands awaiting emission.
- `_awaiting_frontend_ack`: strict gate that blocks new emission until ACK for last command.
- `_awaiting_frontend_ack_command`: exact command string expected in ACK payload.
- `_pending_frontend_events`: frontend events queued while ACK gate is closed.
- `_pending_engine_input_args`: input args to apply on next engine forward pass.
- `_pending_packet_commands`: packet-scoped command buffer while engine packet is in flight.
- `_last_emitted_phase_token`: dedupe token for phase commands.
- `_last_emitted_input_query_signature`: one-shot dedupe key for unresolved `InputEvent` query emission.

---

## Strict ACK Protocol

A backend command is emitted one-at-a-time.

- `_emit_next_command_if_ready()` emits exactly one command and sets `_awaiting_frontend_ack=True`.
- Frontend must send a `terminal_log` ACK payload:
  - `line = ACK backend_update_processed`
  - `command = exact emitted command`
- `_accept_frontend_ack(...)` validates strict match and opens the gate.

While awaiting ACK:

- non-ACK events are not dropped; they are queued in `_pending_frontend_events`.
- bridge logs `[ACK_WAIT] queued_event=... awaiting_command=...`

---

## Engine Draining Model

`_drain_engine(input_args, stop_after_command_batch=True)` performs bounded forward steps.

Per step:

1. `response = env.forward(next_args)`
2. Response mapped to commands via `_commands_from_response(...)`
3. Commands are packet-buffered unless response is `SKIP` or `REQUIRES_QUERY`
4. Flush conditions:
   - `FINISHED_PACKET`
   - `INTERRUPT`
   - `NO_MORE_EVENTS`
   - (and for query boundaries, pending packet commands are flushed before breaking)

Special handling:

- `SKIP`: packet commands are discarded, rollback/sync commands are emitted.
- `REQUIRES_QUERY`: query commands are emitted immediately, then drain breaks.
- Remaining `next_args` are persisted in `_pending_engine_input_args` for subsequent incremental passes.

---

## Query Emission and One-Shot Dedupe

### Problem

The engine may revisit the same unresolved `InputEvent` across multiple drain passes. If bridge emits prompt every time it observes `REQUIRES_QUERY`, frontend can receive duplicate prompt commands and appear stuck in overlay loops.

### Current behavior

On `REQUIRES_QUERY` with `InputEvent` source:

1. Build query signature:
   - `player_id`
   - `query_label`
   - `input_keys`
2. If signature matches `_last_emitted_input_query_signature`, suppress duplicate emission.
3. Else emit one input command and cache signature.
4. Signature resets when valid `input_result` parse starts (`_parse_frontend_input_result`).

Result: one prompt command per unresolved query cycle.

---

## Why One InputEvent Can Produce Many Engine Steps

`[ENGINE_RESPONSE]` logs are per `env.forward(...)` step, not per emitted scanner command or unique prompt.

The same unresolved `InputEvent` may produce multiple `ACCEPT` transitions in listener/group progression before or around query boundaries. This is normal event pipeline progression and does not imply multiple user prompts.

Prompt count is controlled by bridge query emission dedupe, not by raw number of `[ENGINE_RESPONSE]` lines.

In ACK mode, command emission remains single-flight and `_pump_outbound_until_next_command()` now advances exactly one boundary per ACK cycle (one queued frontend event application or one drain pass).

---

## InputEvent Waiting Guard After ACK

`_pump_outbound_until_next_command()` now advances one boundary per ACK cycle using this order:

1. If outbound queue already has commands, return immediately.
2. Else if frontend events are queued, apply exactly one queued event and return.
3. Else if engine is currently on `InputEvent` and there are no fresh input args, log waiting state and return.
4. Else run exactly one drain pass and enqueue any produced commands.

This preserves single-flight ACK behavior while preventing immediate re-observation of the same unresolved query boundary.

---

## Phase Synchronization

Phase commands are deduped with `_append_phase_command_if_changed(...)`.

Phase sync occurs when:

- core phase events (`PhasePickCard`, `Phase2`, `AtkPhase`) map commands
- phase events surface as `REQUIRES_QUERY` (phase sync is still appended)
- full environment sync on `TurnEnd` path

This prevents frontend from remaining on stale phase labels when backend has advanced.

---

## Auto-Advance and Transitional Recovery

When `NO_MORE_EVENTS` occurs, `_auto_advance_when_idle()` can propose next phase events depending on current phase.

Recovery for transitional phases (`INIT`, `TURN_END`, `PICK_CARD`) explicitly proposes `Phase2` to avoid no-input deadlocks after turn transition/draw flows.

---

## Logging and Diagnostics

Current logs include:

- `[ENGINE_RESPONSE]`: every `env.forward(...)` step (stage, step, type, source, data keys)
- `[ACK_TRACE][Bridge] emit_command_waiting_ack`
- `[ACK_TRACE][Bridge] ack_accepted`
- `[ACK_TRACE][Bridge] ack_rejected_command_mismatch`
- `[ACK_TRACE][Bridge] duplicate_input_query_suppressed`
- `[ACK_TRACE][Bridge] waiting_for_input_result`
- `[ACK_WAIT] queued_event=...`

These are intended to distinguish:

- true duplicate prompt emission
- engine step churn without prompt emission
- ACK gating stalls
- phase-transition starvation

---

## Known Tradeoffs

1. Strict ACK sequencing improves determinism but increases latency sensitivity.
2. Query dedupe signature assumes `(player, label, keys)` uniqueness per unresolved query cycle.
3. Recovery auto-proposals reduce deadlocks but can mask deeper event scheduling issues if overused.

---

## Suggested Operational Rules

1. Treat command emission as single-flight: one command, one ACK.
2. Never infer prompt count from raw engine step count.
3. Validate prompt loops via `EVENT->COMMANDS` plus query-dedupe logs.
4. Prefer admin view for integration debugging to avoid target-view suppression effects.
5. Keep card-specific prompt labels stable; they are part of bridge query signatures.

---

## Future Improvements

1. Replace tuple-based query signature with explicit query UUID generated by engine.
2. Add structured JSON logging for easier log ingestion.
3. Add metrics counters for duplicate suppressions and ACK wait depth.
4. Add trace IDs spanning frontend event -> engine step -> scanner command -> ACK.

---

## File Index

- Bridge implementation: [card-game-platform/card_game/server/game_runner.py](card-game-platform/card_game/server/game_runner.py)
- Engine loop: [card-game-platform/card_game/engine/engine.py](card-game-platform/card_game/engine/engine.py)
- Event pipeline: [card-game-platform/card_game/engine/event.py](card-game-platform/card_game/engine/event.py)
- InputEvent implementation: [card-game-platform/card_game/internal_events.py](card-game-platform/card_game/internal_events.py)
- Matthew passive example: [card-game-platform/card_game/catalog/characters/pianos/MatthewWang.py](card-game-platform/card_game/catalog/characters/pianos/MatthewWang.py)
- Existing architecture overview: [card-game-platform/SYSTEM_ARCHITECTURE.md](card-game-platform/SYSTEM_ARCHITECTURE.md)
