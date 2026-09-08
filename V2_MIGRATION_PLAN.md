# Card Game v2 Migration Plan

This is a living reference for migrating the rest of `card_game/catalog/` (characters,
items, stadiums, status effects, tools, supporters) into `card_game_v2/catalog/`. It is
meant to be read at the start of every migration session and updated as decisions get
made or new wrinkles are discovered. Treat "Open Questions" as blocking — resolve or
explicitly punt on each one before leaning on it.

**`SYSTEM_ARCHITECTURE.md` (repo root) is confirmed stale/illustrative** — it uses an
older, simplified API shape and has at least one factual error (FelixChen's atk_1
effect). Never use it as a migration source; the real `.py` files under `card_game/`
are the only ground truth.

## Process — re-read this file every 3 cards, log progress every time you touch it

This migration spans many sessions. Context goes stale, and sessions can end abruptly
(credit limits, connectivity, anything). To keep work resumable by a *different* agent
with zero shared memory of prior sessions:

- **Re-read this entire file at the start of every session, and again after every 3
  cards migrated within a session.** Conventions and open questions get added/changed
  as work progresses; don't rely on a stale in-context copy from earlier in a long
  session.
- **Every time you open/read this file, before doing anything else, append one short
  line to the Progress Log (Section 7) with the date and what you're about to work on
  or just finished** — even if it's just "resumed session, about to start
  OwenLandry (guitar)." This is the mechanism that makes the migration resumable: the
  next agent's first move is reading Section 7 to see exactly where the last one left
  off, without needing any other context.
- When a card is actually finished (migrated + tested + regression suite passing),
  move it from "not started" to done in Section 0 and add a Progress Log line noting
  it's complete.
- If a bug is fixed along the way (see Section 6, item 2), log it in Section 8 (Bugs
  Fixed) immediately, not just at the end of a session — the log entry is the durable
  record if the session ends before you get to summarize verbally.
- **Pylance (the IDE's type checker) must always check out clean.** After writing or
  editing any `card_game_v2` file, make sure no diagnostics are showing for it before
  moving on — a plain `Write` doesn't always surface them the way an `Edit` does, so if
  in doubt, make a trivial touch-edit to the file to force a check. Don't leave a file
  with an outstanding Pylance error/warning, even one that doesn't affect runtime
  behavior (e.g. a redundant `isinstance`, an unused import) — either fix it or, if it
  is a deliberate/necessary suppression (e.g. `# type: ignore` on `AVGEEnvironment`'s
  `core_listeners` construction), leave a comment saying why it's there.

## 0. Where things stand

Migrated and tested (both a real integration test and, for the trickiest ones, an
"extended" edge-case suite — see `card_game_v2/catalog/characters/brass/` and `.../choir/`
for the finished shape to copy):

- **Brass** (5/5): BarronLee, CarolynZheng, FilipKaminski, JuanBurgos, VincentChen
- **Choir (5/5): HappyRuthJara, RossWilliams, RyanDu, YanwanZhu, RachelChen.**
  RachelChen was the last one, unblocked once `ConcertProgram`/`ConcertRoster`/
  `ConcertTicket` existed (see items, below). Her "once per turn" ability gate uses a
  simple instance field (`_active_last_used_round`, compared against `env.round`)
  rather than replicating v1's `check_history` search - same idiom already used for
  round-scoped listeners (AVGEBirb, FoldingStand, etc.), just applied to a plain
  ability instead of a temporary listener. 7 new tests in
  `testing/test_rachelchen.py`.
- **Guitar (8/8, DONE): OwenLandry, ChristmasKim, AntongChen, RobertoGonzales,
  BenCherekIII, GraceZhao, EdwardWibowo, MeyaGao.**
  `card_game_v2/catalog/characters/guitar/`
  (singular directory name - matches the pre-existing empty scaffolding, not v1's
  `guitars/`). Only `MeyaGao` (flagged hardest in this element) remains. Roberto and
  Edward both port the "+40 GUITAR damage on your own next turn" Distortion buff
  independently (per policy) - same round-scoped-modifier idiom as AVGEBirb's curse,
  but without a fire-once self-invalidate (matches v1: neither has an
  `on_packet_completion` override). GraceZhao's `TurnEnd`-reactive passive needed a
  real adaptation, not just a port: v2's event pipeline runs an event's own `act()`
  (CORE) *before* `EXTERNAL_REACTORS`, so `TurnEnd.act()` has already flipped
  `env.turn` to the next player by the time any reactor's `match()` sees it - v1's
  literal condition (`player_turn == opponent → skip`) only makes sense if v1's
  reactors evaluate pre-flip, so it was translated to its *intended* effect ("fires
  when the owner's own turn just ended") rather than ported literally - see Section 2.
  BenCherekIII reuses HappyRuthJara's already-resolved "did I just enter bench from
  hand" history-search guard (Open Question 5), independently reimplemented. MeyaGao
  (the hardest, done last) has 3 cooperating listeners: a permanent reactor that
  watches for attack damage landing on her while active, and on each hit attaches two
  fresh round-scoped `EXTERNAL_PRECHECK_1` regulators (one on her, one on the
  attacker) that `REGULATE_FAIL` any `PlayCharacterCard` ATK from that specific card
  during that specific round - a mutual "hit me, we're both locked out next turn"
  retaliation. 31 new tests across the 8 (`testing/test_owenlandry.py`,
  `test_christmaskim.py`, `test_antongchen.py`, `test_robertogonzales.py`,
  `test_bencherekiii.py`, `test_gracezhao.py`, `test_edwardwibowo.py`,
  `test_meyagao.py`).

- **Percussion (11/11, DONE): KevinYang, LoangChiang, HanleiGao, RyanLee, CavinXue,
  DanielYang, PascalKim, EugeniaAmpofo, KeiWatanabe, BokaiBi, SasMajumder.**
  `card_game_v2/catalog/characters/percussion/`. First use of `D6Input` and `IntInput`
  IO types in this migration - `testing/helpers.py`'s `TestIO` gained `d6_results`
  (falls back to 6) and `int_input_results` (falls back to `io.max_num`) lists,
  mirroring `coinflip_results`. **Test gotcha worth knowing for every future
  PERCUSSION-attacks-Dummy test**: `Dummy`'s `CardType.WOODWIND` is weak to
  `CardType.PERCUSSION` per `type_weaknesses` (`core/CoreListeners.py`'s
  `AVGEWeaknessModifier`), and `TestIO`'s coinflip defaults to heads (1) - so any
  PERCUSSION attack against a bare `Dummy` auto-crits (doubles) unless the test sets
  `io.coinflip_results = [0]` first; all 4 percussion test files now do this in
  `asyncSetUp`. HanleiGao/LoangChiang share a byte-identical "Stick Trick" atk_1
  (20dmg + optional free bench swap), implemented independently per policy. 12 new
  tests. CavinXue and DanielYang add a permanent (no expiry) `EXTERNAL_MODIFIERS_2`
  board-scanning modifier (scans `env.players.values()` × `[ACTIVE_CARD, BENCH]`) -
  CavinXue's own-attack boost per other MAID carrier anywhere in play, DanielYang's
  own-attack +10 unless a BRASS character is in play anywhere. DanielYang is filed
  under `catalog/characters/percussion/` (matching v1's actual file location) despite
  being `CardType.PIANO` - a v1 folder/CardType mismatch kept as-is, since v2 file
  location is pure bookkeeping with no bearing on `base_card_type()`. PascalKim,
  EugeniaAmpofo, KeiWatanabe, BokaiBi, and SasMajumder finished the element - see
  Section 2 for two new engine/testing gotchas discovered along the way (a
  `pkt.flush()` vs `env.engine.flush()` history-solidification trap, and
  `AVGETokenTransferCheck`'s `ENERGY_ADD_REMAINING_IN_TURN` gate) and a real BokaiBi
  bug fix (Algorithm double-firing on tool/stadium plays). 27 new tests across the
  batch.

- **Piano (12/12): DONE.** CathyRong, CocoZeng, HenryWang, JoshuaKou, RyanLi, DavidMan,
  MatthewWang, LukeXu, SophiaSWang, KatieXiang, DemiLu, JennieWang.
  `card_game_v2/catalog/characters/piano/`. CocoZeng/HenryWang share a byte-identical
  Glissando cooldown attack (round-scoped instance field, same idiom as AntongChen);
  CathyRong/RyanLi share a byte-identical Four Hands attack. JoshuaKou's Separate
  Hands is genuinely the *inverse* of that cooldown (only deals damage when it *was*
  used last turn, not when it wasn't) - re-read v1 closely and found the original
  survey note had the polarity backwards; corrected it. JoshuaKou's Category Theory
  passive is the first `PhasePickCard`-reactive passive with its own draw effect since
  Yanwan/MatthewWang's precedent, and **surfaced a real, previously-undiscovered
  engine bug**: `PhasePickCard.act()` itself eagerly captured `deck[0]` into its
  once-per-turn draw event, so any reactor to the *same* `PhasePickCard` that also
  draws from that deck (via the correct lazy pattern) could invalidate that stale
  reference first, crashing the *engine's own* draw with the same
  `list.remove(x): x not in list` failure already known from the ConcertTicket/
  ShowcaseSticker races - just triggered from the opposite direction. Fixed in
  `core/EventCatalog.py` by deferring both the emptiness check and the card lookup
  into a lazy generator, matching the established pattern - see Section 2. DavidMan's
  Reverse Heist is the first *private* reveal (`env.report(RevealCards(...), id)` to
  just the owner) versus the public `env.broadcast(RevealCards(...))` used everywhere
  else so far - v1's own `[self.player.unique_id]` audience confirms this is
  intentional, not an oversight. 22 new tests.

  A second batch finished 4 more: MatthewWang, SophiaSWang, KatieXiang, and
  **LukeXu** - the element's hardest file, and the first card in this whole migration
  to use `AVGEConstrainer` (v2's "this listener/constrainer disables that one"
  primitive). Building it surfaced a second real, previously-undiscovered engine bug:
  `AVGEConstrainer.__init__` never called `super().__init__(id)`, so every
  `AVGEConstrainer` instance was silently missing `requires_cleanup` - harmless until
  the engine's own end-of-packet cleanup pass (`[c for c in self.constrainers if not
  c.requires_cleanup]`) tried to read it and crashed with `AttributeError`, the moment
  *any* constrainer was ever actually used. Fixed with a one-line `super().__init__()`
  call in `avge_abstracts/AVGEConstrainer.py` - see Section 2. LukeXu's Nullify
  disables opposing PASSIVE/ACTIVATE_ABILITY-tagged listeners for the rest of the
  owner's current turn only (self-expiring `Constrainer.match()`, same idiom as the
  round-scoped `EventListener`s elsewhere, just applied to the newer primitive).
  LukeXu/SophiaSWang share a byte-identical "halve the opponent's very next attack,
  whenever it lands" fire-once modifier (no round scoping at all, unlike AVGEBirb's
  curse) - independently implemented in both. KatieXiang reuses PascalKim's
  delayed-cross-turn-damage idiom, but targeting a turn-boundary *one hop later*
  (`env.round + 3`, not PascalKim's `+2`) since Katie schedules for the *owner's own*
  next turn ending, not the opponent's. 19 new tests across the 4.

- **String (16/16): DONE.** AshleyToby, EmilyWang, InaMa, AliceWang, MaggieLi,
  JessicaJung, AndreaCR, FionaLi, GabrielChen, IrisYang, JuliaCeccarelli, SophiaYWang,
  YuelinHu, MasonYu, MichaelTu, MichelleKim.
  `card_game_v2/catalog/characters/strings/` (v2's own directory naming - matches v1's
  `strings/`, unlike guitar/piano which are singular). EmilyWang/InaMa/YuelinHu share a
  byte-identical Triple Stop attack (3 coinflips, 40dmg/head); JuliaCeccarelli/
  SophiaYWang share a byte-identical Ricochet (50dmg + recursive KO-chain-splash
  reactor). MaggieLi/MatthewWang (piano)/Yanwan (choir) all share the
  `PhasePickCard`-reactive Yes/No-heal-or-draw shape. AliceWang's Euclidean Algorithm is
  the first passive whose effect targets the *opponent* (a cross-player
  `CardSelectionQuery` routed to `opponent.id`) with a dynamic `num_selections`.
  JuliaCeccarelli's Ricochet was the first card anywhere in this migration to actually
  drive a character to 0 HP through the real engine KO path, which surfaced a real,
  previously-undiscovered engine bug in `AVGEHPChangeReactor`'s discard/replace flow -
  two swapped `TransferCard` arguments, both fixed (see Section 2). GabrielChen's
  passive threshold is an absolute `hp < 60`, not 60% of max HP as the original survey
  gloss said - corrected against v1 source. MasonYu (flagged hardest string file)
  forces one character to execute another's named attack via `PlayCharacterCard`
  (reusing KeiWatanabe's `acting_card = id.calling_card` resolution) - porting the
  borrowed attack's real energy cost into `PlayCharacterCard` silently `REGULATE_FAIL`ed
  the whole packet, since v1 actually calls this with no `energy_requirement` (defaults
  to 0) to deliberately bypass that gate; fixed by passing `cost=0` explicitly,
  matching v1. 64 new tests across the three string batches (20 + 26 + 18). String
  element now effectively done (only stadium-blocked cards remain).

- **Woodwinds (8/18): AnaliseJia, AnnaBrown, BettySolomon, DanielZhu, DesmondRoper,
  EvelynWu, FelixChen, HarperAitken.** `card_game_v2/catalog/characters/woodwinds/`.
  Fixed two more real, obvious v1 typo-bugs on sight (DanielZhu's whole atk_1
  internally mistagged `ATK_2` despite no `atk_2` existing; FelixChen's passive
  checking `[ATK_1, ATK_1]` instead of `[ATK_1, ATK_2]`, silently never reducing ATK_2
  damage) - v2's architecture makes the first one structurally impossible to even
  accidentally reproduce. Found a real, non-obvious **v1→v2 semantic gap** while
  testing DesmondRoper's streak counter (see Section 2): v1's history-search kwargs
  match `caller: card` because v1's real dispatch always sets `caller` to the
  attacking character, but v2's normal attack dispatch tags the outer
  `PlayCharacterCard`'s `id.calling_card` as `None` instead - porting that check
  verbatim silently zeroed the streak on every use. This is a durable lesson for any
  *future* card that ports a v1 `caller`/`calling_card` history-match: check
  `target_card`, not `calling_card`, unless the card specifically needs to
  distinguish a borrowed/forced execution (MasonYu-style) from genuine self-use. 33
  new tests. Full suite now 371 tests, all green; strict pyright still 0 errors
  outside `testing/`.

- **Woodwinds continued (12/18): + IzzyChen, JordanRoosevelt, KanaTakizawa,
  KathySun.** Found a real test-harness hang trap while testing JordanRoosevelt's
  round-scoped buffs (see Section 2): chaining several bare-`flush()` `TurnEnd`s (the
  established exact-round-math idiom) leaves each one's follow-up packet buffered but
  never run; a later *real* `engine.flush()` call drains them all at once and can
  cascade into a hanging draw/attack-phase loop. Fixed by resetting the engine's
  push/append buffer after each bare `TurnEnd`. 16 new tests. Full suite now 387
  tests, all green; strict pyright still 0 errors outside `testing/`.

- **Woodwinds continued (17/18): + LucaChen, MeiyiSong, RachaelYuan, SarahChen,
  WestonPoe.** Only JaydenBrown remains, deferred for its new-engine-hook requirement
  (Open Question 4 - the "intercept any upcoming coinflip system-wide" mechanic).
  `Dummy` (the test double) being WOODWIND-typed means any "only WOODWIND in play"
  bonus check (LucaChen/MeiyiSong) needs a non-Dummy opponent to test the
  bonus-applies path. WestonPoe's reflection reactor deliberately has no "still in
  play" gate - a failing test caught that the engine's own KO-and-discard flow (which
  runs *before* this `EXTERNAL_REACTORS` listener) would otherwise make the exact hit
  that KO'd the owner look like it happened while already out of play, wrongly
  blocking the reflection a last-stand effect exists to provide. 18 new tests. Full
  suite now 406 tests, all green; strict pyright still 0 errors outside `testing/`.

- **Woodwinds (18/18): DONE.** + JaydenBrown, the last woodwind and the first card
  anywhere in this migration to actually use the `IOListener` engine hook (built
  ahead of time per Open Question 4, never previously exercised by a real card).
  `card.add_io_listener(...)` registers a listener whose `match()` filters to
  `CoinflipData` requests for its own controller (while active, once per round via a
  plain instance field) and whose `modify()` - itself `async` - awaits its own
  follow-up Yes/No query before deciding whether to override the already-resolved
  coinflip result. Confirmed working end-to-end via a direct `env.report(CoinflipData(...))`
  test. 5 new tests. Full suite now 411 tests, all green; strict pyright still 0
  errors outside `testing/`. All 18 woodwinds are now done - the whole element is
  complete.

- **Stadiums (6/10): RedRoom, RileyHall, LindemannPracticeRoom, AlumnaeHall,
  SalomonDECI, MainHall.** `card_game_v2/catalog/stadiums/` (new package).
  Established `self.deck_type == DeckType.STADIUM` as the v2 equivalent of v1's
  `_is_active_stadium()` - every stadium listener gates on this and self-cleans via
  it. MainHall is the first card outside `CoreListeners.py` to use
  `AVGEEventRegulator`. Corrected a survey imprecision for SalomonDECI (no separate
  flat damage table, just its d6-roll mechanic). Found a pyright narrowing gotcha:
  `TransferCard`/`PlayCharacterCard`/`PlayNonCharacterCard` need an explicit `assert
  isinstance(event.id, AVGEEngineID)` before `.calling_action`/`.calling_card` access,
  since (unlike `AVGECardHPChangeEvent`) they don't annotate `self.id`'s type
  explicitly. Added `play_stadium()` to `testing/helpers.py`. 24 new tests across the
  two stadium batches. Full suite now 435 tests, all green; strict pyright still 0
  errors outside `testing/`. Remaining: PetterutiLounge (packet-listener API),
  SteinertBasement + SteinertPracticeRoom (with DemiLu), FriedmanHall (hardest).

- **Stadiums (10/10): DONE.** + PetterutiLounge (first card in the migration to use
  the packet-level `AVGEPacketReactor` API - `packet.event_log`, the packet's own
  record of every event it ran, is how it finds the real attacker, since the packet's
  own `id.calling_card` is `None` for a normal player-driven attack); SteinertBasement
  + SteinertPracticeRoom together (export `_AttackExtraCostModifier` for DemiLu,
  still deferred, to reference - flagged that v2's `AVGEConstrainer` can't see
  per-event context like v1's could, so DemiLu will likely need its own compensating
  modifier instead); FriedmanHall (flagged hardest stadium, **redesigned rather than
  literally ported** - v1's re-entrant "cancel-and-replace `PhasePickCard`, guard
  against re-triggering itself" dance has no safe v2 equivalent since `REGULATE_FAIL`
  rolls back the whole enclosing packet, not one event; instead this reactor just
  reorders the deck so the opponent's chosen card is on top *before* the engine's own
  already-queued normal draw runs, achieving the same player-visible result with no
  double-draw risk and nothing to guard against). 11 new tests. Full suite now 451
  tests, all green; strict pyright still 0 errors outside `testing/`. **All 10
  stadiums done - the whole element is complete.**

- **Supporters (9/9): DONE.** Angel, Emma, Johann, Lio, Lucas, Michelle, Richard,
  Victoria, Will - `card_game_v2/catalog/supporters/` (new package). **Found and
  fixed two compounding, severe engine bugs while migrating Lio, the first supporter
  in this migration - supporters were 100% unplayable in real gameplay before this
  fix** (see Section 2): `Phase2.act()`'s supporter dispatch decremented the wrong
  player attribute, *and* sequenced that decrement before the validity check that
  gates on it, so the check always saw the just-zeroed value and failed every single
  supporter play. Both fixed in `core/EventCatalog.py`. Corrected two survey
  imprecisions (Lucas's first pick goes to the top of the deck, not to hand; Johann's
  "at most 1 per category" constraint has no v2 retry-validator equivalent, so it's
  enforced structurally via three separately-scoped queries instead, same fix shape
  as CastReserve). Emma (flagged hardest, the only "one-shot" supporter that isn't
  actually one-shot) leaves a persistent `AVGEEventRegulator` locking a forced-active
  opponent character from retreating during their very next turn only. Added
  `play_supporter()` to `testing/helpers.py`. 20 new tests across the two supporter
  batches. Full suite now 472 tests, all green; strict pyright still 0 errors outside
  `testing/`. **All 9 supporters done - the whole element is complete.**

- **Status effects (3/3): GOON, MAID, ARRANGER.** Implemented as engine-layer
  `core_listeners()` entries, not character files, but living under `catalog/` anyway
  (own `card_game_v2/catalog/status_effects/` package - `Goon.py`, `Maid.py`,
  `Arranger.py` - **not** folded into `CoreListeners.py`, per explicit user direction).
  `core_listeners()` (in `testing/helpers.py`) still has to list
  `AVGEMaidDamageShieldModifier` after `AVGEWeaknessModifier` - order matters, see
  Section 2 - even though they now live in different files/packages.
- **Tools (6/6): AVGETShirt, MaidOutfit, MusescoreSubscription, Bucket, KikisHeadband,
  AVGEShowcaseSticker.** `card_game_v2/catalog/tools/`.
- **All tests live in `card_game_v2/testing/`** (one flat folder, not colocated - see
  Section 1), 472 tests total, all green.
- **Pylance/pyright strict mode is on for all of `card_game_v2` except
  `card_game_v2/testing/`** (`pyrightconfig.json` at the repo root, plus
  `.vscode/settings.json`'s `python.analysis.typeCheckingMode`). Currently 0 errors.
  Test files are deliberately excluded from strict enforcement - see Section 2.
- **Items (21/21): DONE.** `card_game_v2/catalog/items/`. Concert* were done first (per
  Section 4's staging order) since they unblock RachelChen (choir) and SarahChen
  (woodwind). Migrating them surfaced a real gap in `Phase2.act()`'s item/supporter
  dispatch - see Section 2 - now fixed. `testing/helpers.py` gained a `play_item()`
  helper mirroring the real dispatch. `AVGEBirb` turned up a second real bug - v1's
  self-damage curse could never actually fire - see Section 2. `BAIEmail` is
  implemented by gating the `TransferCard` that moves a card into
  `env.stadium_cardholder`, not `PlayNonCharacterCard` like v1's assessor - confirmed
  `Phase2`'s `Phase2CardMovement` case (a plain player-initiated `TransferCard`) is
  the *only* way a stadium card ever enters that pile, so this is both the sole gate
  point and a cleaner one than v1's (stops the card leaving hand at all, rather than
  moving it and only cancelling the follow-on play effect) - see Section 2.
  `testing/helpers.py`'s `TestIO` gained a `card_answer_sequence` list so a test can
  answer sequential `CardSelectionQuery` calls differently per call (`None` / `int` /
  `list[int]`), plus an `Attacker` test double for energy-cost/damage-modifier cards.
  The last 3 items (MikuOtamatone, MatchaLatte, StrawberryMatchaLatte) needed
  `PetterutiLounge`/other stadiums and were done once stadiums finished - all three
  turned up real v1 bugs on sight: MikuOtamatone's gating tuple silently excluded the
  imported `FriedmanHall` (fixed by including all 5 imported "performance hall"
  stadiums), and both MatchaLatte and StrawberryMatchaLatte checked
  `isinstance(env.stadium_cardholder, PetterutiLounge)` - the cardholder container
  itself, never an instance of a stadium card class, so the check was always `False`
  and the bonus could never apply - fixed by checking the card actually occupying the
  slot instead. 77 tests total in `testing/test_items.py` (7 new this batch). Full
  suite now 479 tests, all green; strict pyright still 0 errors outside `testing/`.
  **All 21 items done - the whole element is complete.**

**Status as of 2026-09-07: THE ENTIRE MIGRATION IS COMPLETE.** Every element -
brass, choir, guitar, percussion, piano, strings, woodwinds, stadiums, status effects,
tools, supporters, and items - is now fully migrated to `card_game_v2`, including the
4 cards that were deliberately deferred for cross-file dependencies (DemiLu,
JennieWang, MichaelTu, MichelleKim). 500 tests, all green, in
`card_game_v2/testing/`. Strict pyright is 0 errors across all 160 analyzed files
outside `testing/`. No further "remaining work" sections apply - see Section 7's
final progress-log entry for the closing summary.

## 1. Test infrastructure — DECIDED, being built out

**Decision (user, this session): formalize the tests into the real repo.** Everything
written so far (9 characters' worth) lived only in the ephemeral session scratchpad and
would otherwise have been lost. Settled shape:

- Shared test utilities live in `card_game_v2/testing/helpers.py` (a real package, not
  a scratchpad file): `Dummy`, `DummyStadium`, `TestIO` (fake IO manager answering
  `CardSelectionQuery`, `StringSelectionQuery`, `CoinflipData`, `Phase2IO`, `AtkPhaseIO`,
  `ListenerReorderIO`, broadcasts), `core_listeners()`, and async helpers
  (`put_into_play`, `bench`, `discard`, `run_attack`, `activate_ability`, `give_status`,
  `remove_status`, `attach_tool`, `detach_tool`, `fire_phase_pick_card`).
- **SUPERSEDED (user, later session): all tests live in `card_game_v2/testing/`, one
  flat folder, not colocated with the production file they test.** Every `test_*.py`
  (one per character/tool/status-effect-group) sits directly in `testing/` alongside
  `helpers.py` - e.g. `testing/test_barronlee.py` imports
  `catalog.characters.brass.BarronLee`, it does not sit next to it. This is a deliberate
  reversal of the original "colocate with production file" decision below (kept here
  for context, no longer followed) - the user wants test code and "game elements"
  cleanly separated into different trees, not interleaved. When adding a new test file,
  put it in `testing/`, not next to the card/tool/listener it exercises.
- ~~Tests are colocated with the production file they test~~ (superseded above).
- **Framework: `unittest.IsolatedAsyncioTestCase`**, not pytest-asyncio. The repo's
  existing v2-adjacent tests (`card_game/avge_abstracts/test_envcache.py`,
  `card_game/engine/test.py`, `card_game/test_internal_events_input_event.py`) are all
  plain `unittest.TestCase`, and pytest (already installed, confirmed via
  `python3 -c "import pytest"`) auto-discovers and runs `unittest.TestCase` subclasses
  natively, including `IsolatedAsyncioTestCase` — no extra dependency needed
  (`pytest-asyncio` is **not** installed and won't be added). Run via
  `python3 -m unittest <module>` or `pytest <path>` — both work against the same files.
- One test class per character (or per listener/mechanic group for the more complex
  ones), one `async def test_...(self):` method per scenario. Merge what used to be a
  "base" + "extended" scratchpad pair into a single file/class.

## 2. v2 architecture — conventions established so far

These are the patterns settled on (some through trial and error, some through direct
user course-correction) while doing brass + choir. Follow them by default; if a new card
seems to need a genuinely different pattern, flag it rather than silently inventing a
third convention.

### File/class shape
- One file per character: `card_game_v2/catalog/characters/<element>/<Name>.py`.
- The character class implements `base_hp`, `base_max_hp`, `base_card_type`,
  `base_retreat_cost`, `base_attacks`, `base_abilities`, `on_transfer`.
- All `Attack`/`Ability`/listener classes are **nested inside the character class**,
  in this order: base-class overrides and `on_transfer` first, then a
  `# --- Listeners ---` section, then `# --- Abilities ---`, then `# --- Attacks ---`
  (each with the exact `# ----...---- \n # SectionName \n # ----...----` banner comment —
  copy the existing banner style verbatim). Instantiate them via `self._ClassName()`
  inside `base_attacks`/`base_abilities`, not at module scope.
- `<element>/__init__.py` does `from .<Name> import *` for every migrated file in that
  folder, in the order the files were migrated.

### Passives, abilities, and `can_play`
- **`can_play` must always return `True` for `PASSIVE` abilities.** The engine's
  `AVGEPlayCharacterCardValidityCheck` never actually calls `can_play` for `PASSIVE` (it
  only checks the ability exists), but the user has explicitly said passives should
  return `True` there as a matter of convention, not just because it's unchecked.
- **`can_play` is a real, enforced gate for `ACTIVATE_ABILITY`.** The validity check
  *does* call `event.target_card.abilities[ACTIVATE_ABILITY].can_play(event.target_card)`
  and `REGULATE_FAIL`s the whole event if it returns `False`. Any v1 card with
  `has_active`/`can_play_active` needs its gating logic ported faithfully into
  `can_play`, including "once per turn" checks (see below) — this isn't a formality.
- **Passives auto-trigger on entering play.** `TransferCard.act()` has a built-in
  special case: whenever a character moves into `ACTIVE_CARD` or `BENCH` from
  somewhere else, and `ActionTypes.PASSIVE in card.abilities`, it automatically pushes a
  `PlayCharacterCard(..., PASSIVE, ...)` for you. **Do not** hand-roll this in a
  character's own `on_transfer` — earlier drafts of Barron/Carolyn did, and it caused a
  double-trigger bug (double notification, double side effect) that had to be ripped
  out once this was discovered. `on_transfer` should only ever handle **leaving play**
  (cleanup of owned listeners) for a character with a passive.
- Standard idiom for a persistent (non-one-shot) listener owned by a passive:
  ```python
  def __init__(self, ...):
      ...
      self._my_listener: MyCard._MyListener | None = None

  async def on_transfer(self, deck_from, deck_to, transfer_event) -> None:
      # Entering play is handled globally by TransferCard's own passive-trigger special case.
      entering_play = deck_to.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
      was_in_play = deck_from.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
      if was_in_play and not entering_play and self._my_listener is not None:
          self._my_listener.cleanup()
          self._my_listener = None
  ```
  and the ability's `__call__` does the idempotent attach:
  ```python
  async def __call__(self, card):
      assert isinstance(card, MyCard)
      if card._my_listener is None:
          card._my_listener = MyCard._MyListener(card)
          card.add_listener(card._my_listener)
  ```
  Important nuance (confirmed via JuanBurgos testing): a bench↔active swap is *not*
  "leaving play" — both `DeckType.ACTIVE_CARD` and `DeckType.BENCH` count as "in play,"
  so the listener should stay attached across that swap and just go dynamically inert
  via its own `match()` conditions (e.g. checking `self.owner_card.deck_type == BENCH`
  live, every time) rather than being torn down and re-created.
- One-shot (self-cleaning) listeners (e.g. Vincent Chen's heal-on-next-hit reactor):
  call `self.cleanup()` **unconditionally at the very top** of the reactor's `react()`,
  before any early-return branches. A v1 bug (found and deliberately *not* reproduced)
  only invalidated the listener on the "success" path, leaking a duplicate listener
  whenever the early-return branch was taken.

### IDs and "who is acting"
- `AVGEEngineID` fields are `calling_card: AVGECard | None`, `calling_action:
  ActionTypes`, `caller_class: type[AVGECard] | None` (renamed from
  `caller`/`action_type`/`header_class` partway through this migration — if you see the
  old names anywhere, that code is stale).
- `calling_card` must be an actual `AVGECard` or `None` — never a `User`/`AVGEPlayer`/
  `AVGEEnvironment`. All the engine's own env-level events construct their ids as
  `AVGEEngineID(None, ActionTypes.ENV, None)` or `(None, ActionTypes.PLAYER_CHOICE,
  None)`.
- `PlayCharacterCard.act()` resolves the actual attacker as: `id.calling_card` if it's an
  `AVGECharacterCard`, else `target_card` itself. This is the mechanism for "ability
  theft" (a card using a *different* card's attack/ability template) — see
  RossWilliams's `_AttackHijack` for the reference implementation: it builds
  `PlayCharacterCard(id=AVGEEngineID(actual_attacker, ...), target_card=Ross, action=ATK_1,
  cost=0, ...)`, so Ross's own `_RossAttack.__call__` runs with `card=actual_attacker`.
- Every `Attack.__call__(self, card, caller_action)` should build its event id as
  `AVGEEngineID(card, self.resolve_caller(caller_action), MyCardClass)`. `resolve_caller`
  (defined on both `Attack` and `Ability` base classes) normalizes a generic
  `ENV`/`PLAYER_CHOICE` catalyst back to the attack's own `atk_type`, but preserves a
  more specific inbound value (e.g. an ability-theft chain) as-is. Abilities don't
  receive a `caller_action` param, so their own internally-constructed ids just hardcode
  the relevant `ActionTypes` (usually `PASSIVE` or `ACTIVATE_ABILITY`).
- For "free" actions that should bypass the normal energy-cost check entirely (Ross's
  hijacked attack), pass `cost=0` to `PlayCharacterCard` — `AVGEPlayCharacterCardValidityCheck`
  only fails when `cost > len(energy_tokens)`, and `0 > anything non-negative` is always
  `False`.

### "Did X happen last turn / this turn / already this turn" checks
- History is chapter-based: `env.search_history(EventType, kwargs, increment=N,
  index_to_start=I)` searches chapter `N` back from whatever's currently in progress
  (`increment=0` = current, in-progress turn/chapter). A new chapter is cut once per
  completed `TurnEnd`, and turns alternate players, so **"my own previous turn" is
  `increment=2`, not `increment=1`** (verified against `CarolynZheng`'s Procrastinate).
  `increment=1` is the *opponent's* last turn.
- `kwargs` matching only supports flat equality against either the event's raw
  constructor kwargs or (`attribute_search=True`) a top-level `getattr`. It cannot
  filter on a nested attribute (e.g. `event.deck_from.deck_type`). For anything needing
  that, pass `kwargs=None` and manually loop with `index_to_start` bumped each miss —
  see `CarolynZheng._attacked_last_turn` or `HappyRuthJara._entered_bench_from_hand_this_turn`
  for the pattern.
- "Once per turn" for an `ACTIVATE_ABILITY` gate: search chapter `increment=0` for a
  prior `PlayCharacterCard` with `action == ACTIVATE_ABILITY` and the right acting card,
  return `False` from `can_play` if found.

### Notifications
- `BroadcastIO(message, timeout)` — no `user_for` field, since it's a plain `IOType[None]`
  rather than a `UserIOType`; used via `await env.broadcast(BroadcastIO(...))`.
  `Notification` (the `UserIOType` cousin, which *does* take a `user_for`) has been
  fully replaced by `BroadcastIO` in every migrated file — don't reintroduce it for a
  new card unless the message is genuinely meant for one player only, and even then
  double check `report()` vs `broadcast()` semantics first.

### Decks
- `AVGEDeck.get_top()` = `self[0]`. Use it instead of `deck[0]` when peeking.

### Pylance / pyright strict mode
- `pyrightconfig.json` (repo root) sets `"typeCheckingMode": "strict"`, scoped to
  `card_game_v2` only (`card_game/`, the v1 reference implementation, is untouched and
  not held to this), with `card_game_v2/testing/` explicitly excluded (test files are
  not required to be strict-clean - see Section 1). `.vscode/settings.json` mirrors
  this via `python.analysis.typeCheckingMode` so Pylance in the editor matches the CLI.
  Verify with `python3 -m pyright` from the repo root (pip-installed this session);
  it should report 0 errors for anything outside `testing/`.
- Every new/edited non-test file must come out of a session at 0 pyright errors.
  Patterns that came up migrating tools/status effects:
  - `AVGEToolCard` (and any `AVGECard`) subclass's `__init__` needs its 4 params fully
    typed: `cardID: CardID` (from `avge_abstracts.AVGEID`), `env: AVGEEnvironment`,
    `owner: User`, `deck_in: DeckType` - strict mode won't infer these from the base
    class.
  - A local closure/generator passed to `push_event`/`append_event`/`Packet(...)`
    needs an explicit `-> list[Event | Generator]` return type (both importable from
    `engine.event`), not a bare `-> list`.
  - Don't write `isinstance(x, SomeType)` when `x`'s declared type is already narrowed
    to exactly `SomeType` by an earlier `callable(...)` check or by the field's own
    type declaration (e.g. `AVGEToolHolder.parent_card: AVGECharacterCard`, no
    `Callable`/`None` union) - strict mode flags it as `reportUnnecessaryIsInstance`.
    This is different from narrowing a genuinely wider type like `AVGEEngineID.
    calling_card: AVGECard | None`, where an `isinstance(..., AVGECharacterCard)`
    check is real and should stay.
  - Don't reach into another class's `_leading_underscore` attribute from outside it
    (`reportPrivateUsage`) - add a real `@property` accessor instead (e.g.
    `AVGECardStatusChange.made_modification`, added this session to replace external
    reads of its own `_made_modification`).
  - Drop unused imports (`ResponseStatus` crept into a couple of status-effect files
    that ended up not needing it - `reportUnusedImport`).

### Engine bugs found and fixed along the way (now fixed, but worth knowing about)
- `push_event`/`append_event` ordering: fixed to preserve call order (previously
  `appendleft`-based and reversed multi-call order).
- `interrupt()` buffer clobbering: fixed by save/restore of
  `_requested_event_pushes`/`_requested_event_appends` around the nested `_run_queue`
  call, mirroring how `current_event` was already saved/restored. Verified at nesting
  depth 2.
- `append_event`'s list-argument branch was extending `_requested_event_pushes` instead
  of `_requested_event_appends` (copy-paste bug) — **fixed**, verified via the engine
  ordering smoke test (`append_event([X, Y])` now correctly lands at the back of the
  queue in call order, matching `append_event(single_event)`'s existing correct
  behavior).
- `HappyRuthJara._entered_bench_from_hand_this_turn` used `isinstance(x, AVGEDeck)` with
  `AVGEDeck` imported only under `TYPE_CHECKING` → `NameError` at runtime. Fixed by
  moving the import to module scope. **Lesson: when adding an `isinstance` check against
  a type that was previously only used in annotations, move its import out of the
  `TYPE_CHECKING` block.**
- **New engine feature (user-authored): `IOListener`.** Lets a third-party listener
  intercept and rewrite the *response* to another card's in-flight `env.report(...)`
  call — `IOListener.match(io_obj)` / `async modify(io_obj, response) -> response`,
  registered via `env.add_io_listener(...)`, applied inside `Engine.report()` after the
  real `io_manager.report()` call resolves (2+ matching listeners get reordered via a
  `IOListenerReorderIO` meta-request, mirroring how `EventListener` ordering already
  works). This is the hook that unblocks **open question 4 (JaydenBrown)** — see below.
- Two circular imports surfaced while wiring `IOListener` up (`listener.py` needed
  `IOType` only for annotations → moved to `TYPE_CHECKING`; `engine_io.py` needed
  `IOListener` as a real symbol because it appears in `IOListenerReorderIO`'s *base
  class list*, which Python evaluates eagerly regardless of
  `from __future__ import annotations` — that only defers annotations, not base-class
  expressions). Fixed by keeping `engine_io.py → listener.py` as a real top-level import
  (matching the existing `EventListener` import, used the same way by
  `ListenerReorderIO`) and `listener.py → engine_io.py` as `TYPE_CHECKING`-only. Both
  now import cleanly; verified via `python3 -c "import card_game_v2..."` across all five
  affected modules.
- `Engine.report()` now takes a required `io_id: ID` (threaded through from
  `AVGEEnvironment.report(io_type, io_id)`) so it can log an `IOEvent(io_id, io_obj,
  resp)` into history — this is what lets a future listener ask "has an IO tagged with
  this calling_card/calling_action already resolved this chapter?", the same way
  v1's `JaydenBrown` used `check_history` against `InputEvent`. When this signature
  changed, **7 existing `env.report(...)` call sites across brass/choir were left
  passing only one argument** (a `TypeError` waiting to fire the first time any of them
  actually ran): `BarronLee.py`, `FilipKaminski.py`, `VincentChen.py`, `RossWilliams.py`
  (×3), `YanwanZhu.py`, `HappyRuthJara.py` (×2). Fixed by threading each site's
  already-in-scope `_id` (or, where the `_id` was built *after* the report call,
  hoisting its construction above it) through as the new second argument. Full
  brass+choir regression suite (52 tests) re-verified green after the fix.
- `AVGEEnvironment.__init__` set `self.engine.listeners = set([...])`, but
  `Engine.add_listener` does `self.listeners.append(...)` - a set has no `.append`.
  Found while working out GOON/MAID's listener-registration ordering (see below). It
  never actually crashed in the 52 existing tests because `Engine.flush()`
  unconditionally reassigns `self.listeners` to a real list at the end of *every*
  packet, and the very first packet any test flushes (bringing a card into play)
  always completes before that card's own passive gets a chance to call
  `add_listener` - so by the time any card-driven `add_listener` call happens, the
  set has already been silently replaced. Fixed by constructing it as a plain list
  from the start (`[listener(self) for listener in core_listeners]`), removing a
  landmine that depended entirely on incidental packet ordering.
- `ReorderDeck.rollback()` (`EventCatalog.py`) asserted `self._old_order is not None`,
  but `act()` never set `_old_order` - it would always `AssertionError` instead of
  actually rolling back. Fixed by saving `self._old_order = list(self.deck.cards_holding)`
  at the top of `act()`, before overwriting it. Found while building ARRANGER (needs
  `ReorderDeck` to shuffle a card into deck at a random position) and confirmed
  nothing in the existing 52 tests exercised a `ReorderDeck` rollback path yet.
- **Registration order matters for same-`EngineGroup` listeners and is currently just
  list order in `core_listeners()`** (not re-arrangeable - only
  `EXTERNAL_MODIFIERS_1/2/3` and `EXTERNAL_REACTORS` groups get a `ListenerReorderIO`
  prompt; `INTERNAL_1` etc. run in fixed registration order). Confirmed via v1's
  actual `AVGEEnvironment`/`internal_events.py` that `AVGEWeaknessModifier` is
  attached before `MaidStatusDamageShieldModifier` on every HP-change event in v1 -
  replicated the same order in `core_listeners()` so MAID's magnitude check runs
  *after* a possible crit-double, matching v1 exactly (a crit that pushes a small hit
  over the MAID threshold is not shielded, by parity, not by accident). Worth
  remembering for any future same-group listener pair where order changes the
  outcome.
- **`TransferCard`/`AVGEDeck.transfer_card()` only ever append to the destination
  pile** - there's no positional/indexed insert. At least 10 future cards need
  "shuffle a card into deck at a random position" (DavidMan, JessicaJung, IzzyChen,
  KathySun, RachaelYuan, Camera, ConcertProgram, DressRehearsalRoster, FriedmanHall,
  plus ARRANGER). Rather than extending `TransferCard`'s widely-used signature,
  ARRANGER composes two *existing* primitives: a normal `TransferCard` (append to
  deck) immediately followed by a `ReorderDeck` whose `reordering` argument is a
  lambda (resolved lazily via `Event._resolve_kwargs()`, so it sees the deck's state
  *after* the transfer already ran) that removes the just-added card and re-inserts it
  at a random index. Same pattern should work for the other ~9 cards - no new event
  type needed, just this two-event combo.
- **v1's mutable-per-event `energy_requirement` (retreat cost) has no v2 equivalent** -
  v2 derives retreat cost from the card's fixed `retreat_cost` attribute, discarded by
  the always-present `AVGERetreatCostReactor` for exactly that many energy, full stop.
  A tool/status effect that changes retreat cost (KikisHeadband: -1, GOON: +1) can't
  just mutate a field like v1 did. GOON's "+1" is easy (an independent regulator
  re-validating `retreat_cost + 1` against the card's own energy, plus an independent
  reactor pushing one *more* discard alongside the base reactor's). KikisHeadband's
  "-1" is not symmetric: naively pushing a *refund* transfer to run after the base
  reactor's discard(s) fails whenever the card has enough for the *discounted* cost but
  not the full undiscounted one - the base reactor still tries to discard the full
  amount first, and that single discard event hard-fails (`AVGETokenTransferCheck`
  treats 0-available as REGULATE_FAIL, not a graceful no-op) before a refund ever gets
  a chance to run. Fixed by moving the token movement into the *regulator* itself
  (INTERNAL_1, guaranteed to run before the base reactor's INTERNAL_3): after
  confirming the discounted cost is affordable, it also `push_event`s a 1-energy
  top-up (env -> card) *before* returning REGULATE_PASS, so by the time the base
  reactor's fixed full-price discard runs, the card can afford it. Net effect:
  `retreat_cost - 1` paid from the player's real pool, no rollback-unsafe direct state
  mutation. See `card_game_v2/catalog/tools/KikisHeadband.py`. Worth remembering for
  any future "-1 cost" tool/status/stadium: the discount has to be injected *before*
  the group that actually spends it, not refunded after.
- **`PhasePickCard.act()` only proposes `Phase2` (and thus only continues on to
  `AtkPhase`/`TurnEnd`/the next `PhasePickCard`) when the current player's deck is
  non-empty** - both the draw-a-card packet and the Phase2 packet are queued inside
  the same `if len(deck) > 0:` guard. This means firing a raw `PhasePickCard` in a test
  with an empty deck is a complete dead end (no cascade at all, not even Phase2),
  which is *why* YanwanZhu's existing empty-deck tests terminate cleanly. The moment a
  test needs a non-empty deck (e.g. to test something that draws a card), the full
  cascade reawakens - `TurnEnd.act()` unconditionally re-queues a fresh `PhasePickCard`
  for the next player, `Phase2Finish` on round 0 goes straight to `TurnEnd` (skipping
  `AtkPhase`), and it keeps bouncing between players until *both* their decks are
  empty. Mitigation used for `AVGEShowcaseSticker`'s tests: give the *other* player an
  empty deck, so the cascade dead-ends on their turn instead of bouncing back for a
  second turn from the player actually being tested.
- **A reactor that draws from the same deck `PhasePickCard`'s own normal draw is about
  to draw from must not resolve its target eagerly.** `PhasePickCard.act()` queues the
  normal draw as a *separate*, later packet holding a reference to whatever was on top
  of the deck *at act() time* - but that packet doesn't run until every group of the
  *current* `PhasePickCard` event (including `EXTERNAL_REACTORS`) has already finished.
  A reactor that also calls `deck.get_top()` during that same event sees the deck
  *unchanged* and grabs the identical card object the normal draw already committed to,
  which then crashes (`list.remove(x): x not in list`) whichever one runs second.
  `AVGEShowcaseSticker` fixes this by deferring both the emptiness check and the
  `get_top()` lookup into a generator inside its *own*, still-later `append_packet`
  call, so it only actually looks at the deck after the normal draw has already
  happened. Any future card reacting to `PhasePickCard` and touching the deck needs
  the same deferral. The same "resolve lazily, not eagerly" issue also applies within
  a single item's own multi-draw list comprehension - see ConcertTicket below.
- **`Phase2.act()`'s item/supporter dispatch never discarded the played card.** Found
  while migrating ConcertProgram (the first item ever ported). v1's equivalent
  dispatch code (`internal_events.py`'s `next_action == 'item'`/`'supporter'`
  branches) always appends a `TransferCard(card, hand, discard)` *after* the
  `PlayNonCharacterCard` event in the same packet - v2's `Phase2.act()` was missing
  that second event entirely in both the `AVGEItemCard` and `AVGESupporterCard`
  branches, meaning a played item/supporter would just sit in hand forever. Fixed by
  adding the matching `TransferCard` to both branches, same order as v1 (resolve the
  card's effect first, discard it second, in the same packet). This also means an
  item's own `play_card()` must **not** discard itself - that's the dispatcher's job,
  same as v1.
- **Multi-draw list comprehensions must resolve `deck.get_top()` lazily, once per
  draw.** `ConcertTicket`'s "draw N cards" loop first tried
  `[TransferCard(_id, deck.get_top(), ...) for _ in range(n)]` - `deck.get_top()` is
  evaluated once, eagerly, for the whole comprehension, so every `TransferCard` ends
  up referencing the *same* not-yet-moved card, and whichever runs after the first
  crashes (`list.remove(x): x not in list`) same as the `PhasePickCard` issue above.
  Fixed with a zero-arg `lambda: deck.get_top()` per event instead (safe here because
  `deck` itself doesn't change across iterations - if it did, per-iteration closure
  capture would need the default-argument trick used elsewhere, e.g. ARRANGER's
  `_reordering_with_chosen_shuffled_in`).
- **`PhasePickCard.act()` itself had the same eager-capture bug, in the engine's own
  once-per-turn draw - found while migrating JoshuaKou.** It built its draw event as
  `TransferCard(_id, player.card_piles[DeckType.DECK][0], deck, hand, env)` and
  `append_packet`'d it - `deck[0]` resolved *once*, at `act()` time, then embedded in
  a packet that only actually runs later (after the current packet, including any
  `EXTERNAL_REACTORS`, finishes). Any reactor to that *same* `PhasePickCard` that also
  draws from the deck (JoshuaKou's Category Theory, correctly using the lazy
  `lambda: deck.get_top()` pattern) runs *first*, via `event.push_event(...)` inside
  the current packet - so by the time the engine's own appended draw packet finally
  runs, the card it captured may already be gone, crashing with
  `list.remove(x): x not in list`. This is the *same* failure shape as the
  ConcertTicket/`PhasePickCard`-reactor races already documented above, just
  triggered by the engine's own draw going stale instead of a reactor's. Fixed by
  deferring both the emptiness check and the card lookup into a lazy generator
  function (`draw_top_card() -> list[Event | Generator]`, returning `[]` if the deck
  is empty at *actual* execution time) - `card_game_v2/core/EventCatalog.py`. Verified
  via JoshuaKou's tests (reproduced the crash first, confirmed the fix, full suite
  re-verified green).
- **`AVGEConstrainer.__init__` never called `super().__init__(id)` - found while
  building LukeXu, the first card in this migration to use a `Constrainer`.** The
  base `Constrainer.__init__` sets `self.requires_cleanup = False`, but
  `AVGEConstrainer.__init__` (`avge_abstracts/AVGEConstrainer.py`) just did
  `self.id = id` and returned, silently skipping it - unlike every sibling class
  (`AVGEEventListener`, `AVGEPacketReactor`, `AVGEIOListener`) which all correctly
  call `super().__init__(...)`. Harmless until the engine's own end-of-packet cleanup
  pass ran (`self.constrainers = [c for c in self.constrainers if not
  c.requires_cleanup]`, in `Engine.flush()`) and hit `AttributeError:
  '_NullifyConstraint' object has no attribute 'requires_cleanup'` - i.e. it crashed
  the very first time *any* `AVGEConstrainer` was ever added, regardless of which
  card added it. Fixed with a one-line `super().__init__(id)` call. Reproduced via
  LukeXu's tests (crashed in `asyncSetUp`'s `put_into_play` before the fix, all 7
  green after).
- **`AVGEHPChangeReactor`'s knockout-discard-and-replace flow had its `TransferCard`
  arguments backwards in *two* places - found while building JuliaCeccarelli's
  Ricochet, the first card in this migration to actually drive a character's HP to
  exactly 0 through the real engine path.** `core/CoreListeners.py`: (1)
  `transfer_card_out` (moves the KO'd character to discard) was constructed as
  `TransferCard(id, event.target_card, player.card_piles[DeckType.DISCARD],
  player.card_piles[event.target_card.deck_type], env)` - `deck_from`/`deck_to`
  swapped, i.e. it tried to move the card *out of* discard *into* wherever it
  currently was, when the card isn't in discard yet. (2) `transfer_card_in` (promotes
  the player's chosen bench replacement into the active slot, in the same
  KO-with-bench-available branch) moved `event.target_card` (the KO'd character
  itself, still sitting in `ACTIVE_CARD`) out of the *new* card's bench pile, instead
  of moving `new_card` (the actual replacement) out of bench into active - so it tried
  to remove the KO'd character from a pile it was never in. Both crashed with
  `list.remove(x): x not in list` the instant any character actually reached 0 HP via
  a normal attack (nothing in this migration had exercised that path until now - every
  earlier "damage" test stopped short of an actual KO). Fixed by swapping
  `deck_from`/`deck_to` on `transfer_card_out` and swapping which card the
  `transfer_card_in` transfer actually moves. **Side effect worth knowing for future
  KO-related reactors**: a reactor at `EngineGroup.EXTERNAL_REACTORS` watching the
  *original* damaging `AVGECardHPChangeEvent` runs *after* `AVGEHPChangeReactor`
  (`INTERNAL_3`) has already discarded the KO'd character and reset its `.hp` back to
  `max_hp` as part of that cleanup - so checking "was this a knockout" via live
  `event.target_card.hp == 0` at that point is always false. Use the CORE-time
  snapshot `event.final_change` (set once, during `act()`, never touched again)
  instead - this is also what v1's own code did, which I'd initially deviated from for
  no good reason. Separately, splash/follow-on events pushed from that same reactor
  target character objects directly (not "whoever is currently in pile X"), so they
  still land correctly even if the engine's own mandatory bench-replacement prompt
  (which only gets *enqueued*, not yet run, by the time `EXTERNAL_REACTORS` fires) ends
  up promoting one of those same targets to active first. Reproduced and fixed via
  JuliaCeccarelli's Ricochet tests (crashed on both non-chain and chain knockout tests
  before the fix; all 5 green after, full 320-test suite re-verified green, strict
  pyright still 0 errors).
- **`AVGEBirb`'s self-damage curse could never fire, in v1.** The curse (+20 damage to
  the *owner's own* active character - confirmed by the notification text "Your active
  takes +20 damage", not a typo: the item strips the opponent's tools/statuses but
  punishes its own player for it) was gated by
  `round_id == card.player.get_next_turn()`. `get_next_turn()` on the *owner* returns
  the round when it's the **owner's own turn again** (2 rounds out, since items are
  always played on the owner's own turn) - but incoming attack damage against the owner
  can only ever land on the **opponent's** turn (1 round out). The round the curse
  waited for never coincides with an actual hit, so under normal play it's dead code.
  v2 keeps the same "scoped to one specific upcoming turn, then expires" shape (v2 does
  track rounds via `env.round`, incremented once per `TurnEnd` - same idiom as Open
  Question 6/MeyaGao's self-expiring round-scoped listeners) but fixes the actual
  number: `round_active = env.round + 1` at play time (the opponent's very next turn),
  not the owner's own next turn. `match()` self-`cleanup()`s once `env.round` passes
  `round_active` without a hit, same as it does after successfully firing once. See
  `card_game_v2/catalog/items/AVGEBirb.py`.
- **v2's `AVGECardStatusChange` REMOVE only clears one specific `giver` per event** -
  unlike v1, which had a third `StatusChangeType.REMOVE` mode that cleared *every*
  giver on a status in one shot (`ADD`/`ERASE` were the per-giver ops there). Any v2
  card that needs to strip a status entirely (e.g. `AVGEBirb` stripping all of the
  opponent's statuses) has to snapshot `character.statuses_attached[status]` (a set)
  into a list first, then push one `AVGECardStatusChange(REMOVE, ...)` per giver in it -
  not a single "clear all" event, since v2 has no such event. This isn't a bug, just a
  smaller/simpler v2 status model to design around.
- **Stadiums (and tools) don't go through `Phase2`'s `PlayNonCharacterCard` dispatch at
  all - unlike items/supporters.** `Phase2.act()`'s `match res.card:` only has
  `case AVGEItemCard()` and `case AVGESupporterCard()` branches; there's no
  `AVGEStadiumCard`/`AVGEToolCard` case. Playing a stadium (or attaching a tool)
  instead goes through the generic `Phase2CardMovement` case, which just pushes a
  plain player-initiated `TransferCard(res.card, res.deck_from, res.deck_to, ...)` -
  and it's `TransferCard.act()`'s own "Special Case 3" (`deck_to.deck_type in
  [OFFHAND, STADIUM]`) that then pushes `PlayNonCharacterCard` as a *consequence* of
  that transfer already having happened. Confirmed via grep that this is the *only*
  place `PlayNonCharacterCard` is ever constructed with a stadium/tool target - so any
  card that needs to block "playing a stadium/tool" (e.g. `BAIEmail`) should gate the
  incoming `TransferCard` (matching on `deck_to.deck_type`), not
  `PlayNonCharacterCard` - it's both the only real gate point and a cleaner one than
  v1's own approach (v1's assessor cancels `PlayNonCharacterCard`, which in v1's
  architecture still lets the card physically move into the stadium/tool slot before
  cancelling just the *effect*; gating the transfer itself stops the card from ever
  leaving hand). Worth remembering for any future tool-attach-blocking card too.
- **`EventReactor`s in the `EXTERNAL_REACTORS` group see an event's state *after* its
  own `act()` (`CORE`) has already run** - `_flush_event`'s `for group in EngineGroup:`
  loop runs groups in enum order, and `CORE` (value 7) comes before
  `EXTERNAL_REACTORS` (value 9). This matters for any reactor keyed off a state change
  the event's own `act()` makes: `TurnEnd.act()` flips `env.turn` to the *next* player
  before any `EXTERNAL_REACTORS` listener's `match()` runs, so "did the owner's own
  turn just end" has to be read post-flip as `env.turn == the owner's opponent`, not
  `env.turn == the owner`. Found while porting GraceZhao's Royalties passive - v1's
  literal condition assumes the opposite (pre-flip) evaluation order, so it was
  translated to its *intended* effect rather than copied literally. Worth checking for
  every future `TurnEnd`-reactive (or any CORE-state-mutating-event-reactive) passive.
- **Test gotcha: `Dummy` (`CardType.WOODWIND`) is weak to `CardType.PERCUSSION` per
  `type_weaknesses` in `core/CoreListeners.py`'s `AVGEWeaknessModifier`.** `TestIO`'s
  `CoinflipData` defaults to heads (`1`), and the weakness modifier's crit-check is a
  coinflip - so any PERCUSSION-type attack landing on a bare `Dummy` target
  auto-crits (doubles) by default in tests, unless `io.coinflip_results = [0]` is set
  first. Bit every percussion test file until traced back to this. The full
  `type_weaknesses` cycle (`STRING→GUITAR→WOODWIND→PERCUSSION→CHOIR→PIANO→BRASS→STRING`)
  means this same trap will resurface for CHOIR-vs-PERCUSSION-target,
  PIANO-vs-CHOIR-target, etc. - check the cycle before assuming a `Dummy`-target test's
  damage numbers need no crit handling.
- **Test gotcha: a bare `pkt.set_engine(engine); await pkt.flush()` does NOT solidify
  that packet's events into searchable (`IMMUTABLE`) history - only
  `env.engine.flush(...)` does.** `Packet.flush()` just runs the packet's own event
  pipeline; it's `Engine.flush()` (called by `env.engine.flush(lambda: False)`, what
  every shared helper in `testing/helpers.py` actually uses) that calls
  `history.solidify_records()` afterward. `search_history`'s default
  `specific_status=HistoricalStatus.IMMUTABLE` silently finds nothing for events that
  were only ever run through a bare `pkt.flush()` - no error, just an empty search
  result. Bit EugeniaAmpofo's test (`_first_attached_character_this_turn` found
  nothing until the test helper switched to `env.push_packet(pkt)` +
  `env.engine.flush(...)`). Any future test driving a `search_history`-dependent code
  path needs the engine-level flush, not a bare packet flush - the many existing
  `_deal_damage`/`_hit`-style bare-`pkt.flush()` test helpers are fine *only* because
  none of them are checked via `search_history` afterward.
- **`AVGETokenTransferCheck` REGULATE_FAILs a `PLAYER_CHOICE`-tagged
  `AVGEEnergyTransfer` into a character when that player's own
  `ENERGY_ADD_REMAINING_IN_TURN` attribute is already `0`** - this is the "you already
  used your one normal energy attach this turn" gate, and it's easy to trip by
  accident in a test: a fresh `AVGEPlayer` defaults this attribute to `0` (nothing
  resets it to `PER_TURN_TOKEN_ADD` without a real `TurnEnd` running first), so
  simulating "the normal attach already happened this turn" for something like
  EugeniaAmpofo's gate requires bumping the attribute to a nonzero value *before* the
  simulated attach (so the regulator allows it), then setting it back to `0`
  *afterward* (since nothing in the current codebase automatically decrements it on a
  successful attach yet - `Phase2`'s own energy-attach dispatch doesn't touch this
  attribute at all, only its supporter-play branch does, likely unrelated/pre-existing
  and out of scope to "fix" here).
- **v1→v2 semantic gap: `id.calling_card` is NOT the same thing as v1's `caller` field
  for a normal, self-driven attack - found while migrating DesmondRoper's streak
  counter.** v1's real attack dispatch (`AtkPhase.core()`) always constructs
  `PlayCharacterCard(active_card, atk_type, PLAYER_CHOICE, active_card, cost)` - the
  `caller` argument (4th positional) is the attacking character itself, every time.
  v2's equivalent dispatch (`AtkPhase.act()`, and every test's `run_attack` helper)
  instead builds the outer `PlayCharacterCard`'s `_id` as
  `AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)` - `calling_card` is `None` for
  a completely ordinary, player-driven attack. A history-search kwargs match that
  faithfully ports v1's `{'caller': card}` clause as `{"...": ..., }` plus a Python-side
  `event.id.calling_card is card` check therefore **never matches a normal attack** -
  it silently zeroes out any streak/history-dependent effect, no error, no crash, just
  wrong (zero) output. Caught by DesmondRoper's own test suite (streak stayed at 0
  across turns until traced down). Fix: match on `target_card` (the character that
  actually executed the move) instead, and only add a `calling_card` check if the
  card specifically needs to exclude a borrowed/forced execution (MasonYu/KeiWatanabe-
  style, where `calling_card` legitimately differs from `target_card`). Applies to
  EvelynWu's identical formula too, fixed the same way independently. **Any future
  card porting a v1 `caller: card`-style history match should default to dropping
  that clause, not translating it literally.**
- **Test-harness hang trap: chaining multiple bare `pkt.flush()` `TurnEnd`s, then
  later calling a real `env.engine.flush(...)`, can trigger a runaway draw/attack-phase
  cascade that hangs indefinitely - found while testing JordanRoosevelt's round-scoped
  buffs.** `Engine.push_packet`/`append_packet` don't touch the live queue directly -
  they buffer into `_buffered_pushes`/`_buffered_appends`, only folded in by
  `_flush_buffer()`, which a bare `Packet.flush()` never calls (only `Engine.flush()`
  does, at the top and after every successfully-completed packet). So the
  PascalKim/KatieXiang-style "several bare `TurnEnd.flush()` calls in a row, for exact
  round-math control" idiom is safe **only as long as nothing afterward calls a real
  `env.engine.flush(...)`** - each un-run `TurnEnd` leaves its own pushed draw-phase/
  attack-phase follow-up packet sitting in the buffer, and a later real flush drains
  *all* of them at once, which can cascade into a real (and, with a small enough test
  deck, apparently unbounded) sequence of `PhasePickCard`/`Phase2`/`AtkPhase`/`TurnEnd`
  events - confirmed to hang for 120+ seconds in a minimal repro before being killed.
  Fix: if a test needs a real action (e.g. `run_attack`) *after* several bare-flushed
  `TurnEnd`s, call `self.env.engine._reset_buffer()` after each bare `TurnEnd` to
  discard its unused follow-up packet before it can accumulate - this keeps the
  clean, deterministic `env.round += 1`-per-call semantics (from `TurnEnd.act()`
  itself, which runs unconditionally) while guaranteeing nothing pent-up ever fires
  later. Verified via a minimal 3-line repro script (hung with the raw buffer, resolved
  instantly with `_reset_buffer()` after each call) before fixing
  `test_jordanroosevelt.py`'s `_bare_end_turn()` helper this way.
- **Two compounding engine bugs made supporter cards 100% unplayable in real
  gameplay - found while migrating Lio, the first supporter in this migration.**
  `Phase2.act()`'s `AVGESupporterCard()` dispatch branch (`core/EventCatalog.py`):
  (1) decremented `AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN` instead of
  `SUPPORTER_USES_REMAINING_IN_TURN` - the wrong attribute entirely, meaning a real
  supporter play never actually consumed the once-per-turn supporter allowance
  (unlimited supporters playable) *and* incorrectly ate the player's separate
  per-turn energy-attach allowance as a side effect. Fixed by decrementing the
  correct attribute. (2) Even after that fix, the packet still listed the
  `AVGEPlayerAttributeChange` decrement *before* the `PlayNonCharacterCard` event -
  and `AVGEPlayNonCharacterCardValidityCheck` (`CoreListeners.py`) gates a supporter
  play on that same attribute being `!= 0` *at check time*. Since
  `PER_TURN_SUPPORTER_USE = 1`, the decrement-then-check order meant the check always
  saw the freshly-decremented value (`1 - 1 = 0`) and `REGULATE_FAIL`'d **every**
  supporter play, including the very first one of the turn - supporters were
  completely unplayable in the real game, not just missing their limit enforcement.
  Fixed by reordering the packet: `PlayNonCharacterCard` (and its validity check)
  now runs *before* the attribute decrement, so the check sees the pre-decrement
  value. Reproduced via Lio's own tests (both bugs caused the entire packet - the
  attribute change, the play, and the discard - to silently roll back with no
  exception, since a `REGULATE_FAIL` anywhere in a packet unwinds the whole thing;
  traced with a manual `push_packet` tracer before finding the root cause). Full
  suite re-verified green (453 tests) after both fixes.

## 3. Migration methodology (per card)

1. Read the v1 file in full.
2. Identify: stats, attack formulas/targets, ability/passive behavior, any custom
   listener (event type matched, `EngineGroup`, effect), any `Interrupt`/`InputEvent`
   (→ becomes a plain `await env.report(...)` in v2 — no cache/interrupt dance needed),
   any cross-file dependency (another catalog class referenced by name).
3. Check dependencies exist in v2 already (an item/tool/stadium/status-effect it
   references). If not, either migrate that dependency first or explicitly stub/skip
   and note it (see RachelChen).
4. Write the v2 file following the conventions above.
5. Write/extend a test file exercising the actual mechanic through the real engine
   (`AVGEEnvironment` + `TestIO`), not just unit-testing `can_play`/formulas in
   isolation — several real bugs (the `AVGEDeck` NameError, the turn-machinery cascade
   confounding naive tests, ordering bugs) were only caught this way.
6. For anything with a passive/listener, explicitly test: attach-on-entry,
   cleanup-on-leaving-play, and the dynamic-inert-while-active-not-benched case if
   applicable.
7. Run the *entire* existing regression suite (all previously-migrated characters),
   not just the new one — engine-level changes have broken previously-passing tests
   twice already in this migration.
8. Update this file: move the card from its "not started" list to "done," and add a
   one-line note to Section 6 (Open Questions) if anything about it was left unresolved.

## 4. Suggested staging order

The survey is now complete (all 114 files read). Full dependency graph found:

- **Status effects (GOON/ARRANGER/MAID) are infrastructure, not characters.** GOON and
  ARRANGER are enforced by listeners registered once, globally, at environment
  creation (v1 equivalent of v2's `core_listeners` list); MAID is enforced per-event,
  folded into HP-change resolution itself. This blocks: CavinXue, DanielYang† (percussion),
  RyanLi (piano), FionaLi, MasonYu (strings), BUOStand, FoldingStand (items),
  PetterutiLounge (stadium), AVGETShirt, MaidOutfit, MusescoreSubscription (tools).
  (†DanielYang references BRASS-in-play, not a status effect directly, but is grouped
  here as another "check board-wide state" precedent worth building alongside.)
- **Items block 2 characters directly**: RachelChen (choir) and SarahChen (woodwind)
  both need `ConcertProgram`/`ConcertRoster`/`ConcertTicket`. Also: `AVGEBirb` blocks
  SophiaYWang + YuelinHu (strings) + RaffleTicket (item→item); `MikuOtamatone` blocks
  MichelleKim (strings).
- **Stadiums block several characters**: `SteinertBasement`/`SteinertPracticeRoom`
  block DemiLu (piano) — and DemiLu needs those stadiums' *internal listener classes*
  importable by name, so coordinate the two migrations, don't do DemiLu in isolation
  after. `AlumnaeHall`/`SalomonDECI`/`RileyHall`/`MainHall` block MichaelTu (strings)
  and JennieWang (piano). `PetterutiLounge` blocks MatchaLatte/StrawberryMatchaLatte
  (items).
- **JennieWang (piano) is the single most cross-referenced file in the entire
  survey** — needs 5 named character classes across 4 elements (DavidMan, EvelynWu,
  BokaiBi, RobertoGonzales, LukeXu) plus 4 stadium classes. Migrate it dead last.
- **JaydenBrown (woodwind)** needs a new engine-level hook (intercepting/rewriting an
  arbitrary upcoming `CoinflipData` before it resolves) that doesn't exist in v2 yet
  and has no precedent to copy. Treat as its own mini-design-and-build task, not a
  drop-in character port; do it whenever convenient, doesn't block anything else.

Recommended order:

1. **Status effects infrastructure** (engine-level: 2 new `core_listeners` entries +
   1 addition to the HP-change core check). Small, and unblocks the most characters
   per unit of effort.
2. **Tools** (6 files) — small, and 3 of them are trivial once status effects exist
   (they just grant/revoke a status on equip/unequip); the other 3
   (`AVGEShowcaseSticker`, `KikisHeadband`, `Bucket`) are independent and easy.
3. **Items** (21 files) — unblocks RachelChen (choir, already migrated except this)
   and SarahChen (woodwind). Do `ConcertProgram`/`ConcertRoster`/`ConcertTicket` and
   `AVGEBirb` early within this batch since characters depend on them specifically.
4. ~~**Go back and finish RachelChen** (choir).~~ **DONE.**
5. **Stadiums** (10 files) — do `SteinertBasement`/`SteinertPracticeRoom` as a pair
   with an eye toward DemiLu's needs; do `AlumnaeHall`/`SalomonDECI`/`RileyHall`/
   `MainHall` before touching MichaelTu/JennieWang.
6. **Remaining character elements**, roughly easiest-to-hardest based on the survey,
   leaving cross-referencing outliers for last within each element. Note: several of
   these share near-identical logic with a sibling card (called out per-card in
   Section 5) — **per explicit user decision, do not build shared helpers for these;
   implement each one independently, in full, in every file that needs it.**
   - Guitars: OwenLandry → ChristmasKim → AntongChen/RobertoGonzales → BenCherekIII
     (needs the "self-promotion" passive design question resolved first) → GraceZhao
     (needs tools) → EdwardWibowo → MeyaGao (hardest — 3-listener retaliation lock,
     do last in this element).
   - Percussion: KevinYang/LoangChiang/HanleiGao/RyanLee → CavinXue (needs status
     effects) → DanielYang → BokaiBi/SasMajumder (reactive-passive design) →
     KeiWatanabe → EugeniaAmpofo → PascalKim (delayed-reactor idiom).
   - Pianos: CathyRong/AshleyToby-tier-simple ones first → CocoZeng/HenryWang/JoshuaKou
     (cooldown-check family) → RyanLi (needs status effects) → MatthewWang →
     LukeXu/SophiaSWang (needs the new Constrainer-nullify design for Luke) →
     KatieXiang (delayed-reactor idiom) → DemiLu (needs stadiums) → JennieWang (dead
     last, needs everything).
   - Strings: AshleyToby-tier simple ones → EmilyWang/InaMa (energy-donation family) →
     IrisYang/MichelleKim (Michelle also needs MikuOtamatone) → JessicaJung →
     MaggieLi/AliceWang → AndreaCR/GabrielChen/MasonYu (hardest control flow) →
     JuliaCeccarelli/SophiaYWang (SophiaYWang also needs AVGEBirb) → YuelinHu (needs
     AVGEBirb) → MichaelTu (needs 4 stadiums).
   - Woodwinds: HarperAitken/LucaChen/BettySolomon-tier simple ones →
     AnaliseJia/MeiyiSong → DesmondRoper/EvelynWu/RachaelYuan (streak family) →
     AnnaBrown/FelixChen/WestonPoe (apply the bug-reproduction policy — fix on sight
     and log in Section 8, since all three have a v1 quirk) → KanaTakizawa/KathySun →
     IzzyChen → JordanRoosevelt → DanielZhu (also apply the bug policy — its atk_1 is
     mistagged as ATK_2 throughout) → SarahChen (needs items) → JaydenBrown (needs
     new engine hook, do whenever convenient).
7. **Supporters** (9 files) — no character depends on these, so they can slot in
   anywhere convenient; do Emma last within this batch since it needs the
   round-scoped-listener idiom applied to an *opponent's* card, a new variant.

## 5. Per-card catalog

*(To be filled in as the survey completes. Format per card: name, HP/costs, one-line
mechanic summary, difficulty rating [straightforward / moderate / hard], migration
notes, and any cross-file dependency.)*

### Guitars (8 files) — 8/8 migrated, DONE

| Card | Stats | Summary | Difficulty | Notes |
|---|---|---|---|---|
| AntongChen | 100hp/r2/1:2,2:3 | atk_1 flips 5 coins, 20×heads dmg, blocked if atk_2 used last round; atk_2 flat 90 dmg + discards own top 2 energy | **DONE** | Migrated - `catalog/characters/guitar/AntongChen.py`. The "atk_2 last round" gate uses a plain instance field (`_last_atk2_round`, checked against `env.round - 2`) rather than a history search - simpler and sufficient since only this same card's own attacks matter. |
| BenCherekIII | 100hp/r1/1:2 (no atk_2) | Passive can self-promote from bench to active when player has no active (Yes/No prompt, swaps two cards); atk_1 50 dmg + 10 splash to own GUITAR bench | **DONE** | Migrated - `catalog/characters/guitar/BenCherekIII.py`. Per Open Question 5's resolution: fires on the normal "entering play" `PASSIVE` trigger (same hook every other passive uses), no-ops unless `card.deck_type == BENCH`; reuses HappyRuthJara's "did I just enter bench from hand" `IMMUTABLE`-history guard, independently reimplemented. |
| ChristmasKim | 100hp/r1/1:1,2:2 | atk_1 flat 20; atk_2 peeks top 5 deck, pulls GUITAR cards to hand w/ 20 dmg each, reveals them, reorders remaining peeked cards | **DONE** | Migrated - `catalog/characters/guitar/ChristmasKim.py`. Uses `RevealCards` (2nd use in the migration, after PrintedScore) and the established `TransferCard`+`ReorderDeck` combo for "put the chosen-order remainder back on top." |
| EdwardWibowo | 110hp/r2/1:2,2:3 | atk_1: coin-flip-strip opponent energy (n flips = n = opponent's current energy, remove up to heads tokens); atk_2: 40 dmg + self "next round only" GUITAR-damage +40 buff | **DONE** | Migrated - `catalog/characters/guitar/EdwardWibowo.py`. Distortion buff implemented independently from Roberto's identical one, per policy - see Section 2's round-scoped-modifier idiom note. |
| GraceZhao | 100hp/r2/1:2 (no atk_2) | Passive reacts to `TurnEnd`, deals 10 dmg to an opponent card *if it has specific tools attached* (AVGEShowcaseSticker/AVGETShirt/MaidOutfit); atk_1 50+10 splash | **DONE** | Migrated - `catalog/characters/guitar/GraceZhao.py`. First `TurnEnd`-reactive passive in v2 - required a real adaptation, not a literal port, because `EXTERNAL_REACTORS` sees `env.turn` *after* `TurnEnd.act()` already flipped it. See Section 2's new pipeline-ordering note; this will matter for every future `TurnEnd`-reactive card too. |
| MeyaGao | 120hp/r2/1:3 (no atk_2) | 3 cooperating listeners: self-buff (same as Edward's), mutual "attack-lockout after being hit" retaliation across 3 EngineGroups (Modifier, Regulator/assess, Reactor), reactive damage | **DONE** | Migrated - `catalog/characters/guitar/MeyaGao.py`. A permanent `EXTERNAL_REACTORS` reactor (added once via the standard "entering play" `PASSIVE` hook) watches for attack damage on her while active; each hit attaches two fresh round-scoped `EXTERNAL_PRECHECK_1` regulators (one on her, one on the attacker), each independently computing its own "next turn" round via the same `env.round + (2 if env.turn==player else 1)` formula as v1's `get_next_turn()` (a small file-local helper, reused twice from one call site - not a cross-file mechanic helper). |
| OwenLandry | 100hp/r2/1:2,2:3 | atk_1 50+10 splash (same pattern); atk_2 discards own energy, hits ALL opponent's in-play cards for 50 (board-wide splash) | **DONE** | Migrated - `catalog/characters/guitar/OwenLandry.py`. First guitar migrated, as planned. |
| RobertoGonzales | 110hp/r2/1:2,2:3 | atk_1: 30 dmg + discard own energy → mill opponent's deck 1:1 per token discarded; atk_2: 40 dmg + same round-scoped self-buff as Edward/Meya | **DONE** | Migrated - `catalog/characters/guitar/RobertoGonzales.py`. Deck-milling uses the lazy-`get_top()`-per-event pattern (same fix shape as ConcertTicket's multi-draw bug) since each mill must see the deck state after the prior one. |

**Cross-cutting note:** three guitar characters (Edward, Meya, Roberto) have a
byte-for-byte identical "+40 damage to this player's own GUITAR-type attacks, for
exactly one round" self-buff modifier. **Per explicit user decision, do not factor
this into a shared helper** — write the same ~20-line listener independently in each
of the three files, matching v1's own duplication.

### Percussion (11 files) — 11/11 migrated, DONE

| Card | Stats | Summary | Difficulty | Notes |
|---|---|---|---|---|
| BokaiBi | 110hp/r2/1:2 | atk_1 d6 roll, 1-4→60dmg; passive reacts to *opponent's own* play-like transfers, offers to punish if owner's hand has a matching-type card | **DONE** | Migrated - `catalog/characters/percussion/BokaiBi.py`. Found and fixed a real double-fire bug: a tool/stadium play generates *both* a `TransferCard` (hand→OFFHAND/STADIUM) *and* a follow-on `PlayNonCharacterCard` (`TransferCard.act()`'s own "Special Case 3"), and Algorithm's `_played_card()` originally matched both, firing the passive twice for one play. Fixed by excluding tools/stadiums from the `PlayNonCharacterCard` branch (already covered by the `TransferCard` branch) - see Section 2 and Section 8. |
| CavinXue | 100hp/r2/1:1 | atk_1 flat 20; passive: own SUBSTRACTIVE dmg +20 per MAID-status card anywhere in play (both sides) | **DONE** | Migrated - `catalog/characters/percussion/CavinXue.py`. |
| DanielYang | 100hp/r2/1:3 — **filed under percussion but CardType.PIANO** | atk_1 50dmg + bench splash if 3+ PIANO on bench; passive: own ATK dmg +10 flat unless a BRASS char is in play anywhere | **DONE** | Migrated - `catalog/characters/percussion/DanielYang.py` (folder/CardType mismatch resolved: kept in percussion, matching v1's actual file location - see Section 2). |
| EugeniaAmpofo | 100hp/r2/1:2, ACTIVATE_ABILITY | atk_1 20dmg + optional free bench swap; ability moves 1 energy from pool to another in-play character, once/turn, gated on "first energy attach this turn" history reconstruction | **DONE** | Migrated - `catalog/characters/percussion/EugeniaAmpofo.py`. "Once per turn" gate uses the plain-instance-field simplification (matching RachelChen/AntongChen), but the "first energy attach this turn" lookup does still use a real `search_history` reconstruction, since there's no simpler equivalent. Surfaced two new engine/testing gotchas along the way - see Section 2. |
| HanleiGao | 100hp/r2/1:2,2:3 | atk_1 20dmg + optional free bench swap; atk_2 hits every opponent card WITH a tool attached for 50dmg and strips their tools | **DONE** | Migrated - `catalog/characters/percussion/HanleiGao.py`. Strips tools to the opponent's *hand*, not discard (unlike AVGEBirb's strip-to-discard) - confirmed against v1. |
| KeiWatanabe | 100hp/r1/1:1,2:3 | atk_1 pick any opposing character, 10dmg; atk_2 "borrow" another of your own PERCUSSION character's named attack, donating Kei's energy to them | **DONE** | Migrated - `catalog/characters/percussion/KeiWatanabe.py`. "Borrowing" an attack is a plain `PlayCharacterCard(_id, chosen, action_type, chosen.attacks[action_type].cost, env)` targeting the donor character directly (no `calling_card` override needed) - energy is donated *before* that event in the same packet, so the donor's own affordability check passes normally. |
| KevinYang | 100hp/r2/1:2,2:3 | atk_1 d6, 1-4→60dmg (same as Bokai); atk_2 4 d6 rolls, dmg=40×lowest | **DONE** | Migrated - `catalog/characters/percussion/KevinYang.py`. First use of `D6Input` in this migration - `testing/helpers.py` gained `d6_results` support. |
| LoangChiang | 110hp/r1/1:2,2:3 | atk_1 20dmg + optional free bench swap; atk_2 heal all own in-play +30, discard 1 own energy as cost | **DONE** | Migrated - `catalog/characters/percussion/LoangChiang.py`. Heals via `AVGECardHPChangeEvent` with `AVGEAttributeModifier.ADDITIVE`/`CardType.ALL` (true heal, bypasses type checks) - same primitive already used for RaffleTicket's full-heal. |
| PascalKim | 100hp/r2/1:2,2:3 | atk_1 dmg scales inversely with Pascal's own HP (≤20→90, ≤50→50, else 20); atk_2 returns Pascal+tools to deck, shuffles, schedules 70dmg at opponent's *next* TurnEnd via an env-registered one-shot reactor | **DONE** | Migrated - `catalog/characters/percussion/PascalKim.py`. First delayed-cross-turn-damage card - `round_active = env.round + 2` (not v1's `+1`), same post-act-state adjustment as GraceZhao's `TurnEnd` reactor (see Section 2), verified end-to-end with real `TurnEnd` events in tests. |
| RyanLee | 100hp/r2/1:1,2:3 | atk_1 pick benched PERCUSSION char + integer amount (1-2) of energy to attach to it; atk_2 four 10dmg hits, 4th also draws a card | **DONE** | Migrated - `catalog/characters/percussion/RyanLee.py`. First use of `IntInput` in this migration - `testing/helpers.py` gained `int_input_results` support (falls back to `io.max_num`). Energy source is `env.energy_tokens` (the shared pool), matching v1's `player.energy` concept - v2 has no per-player energy pool. |
| SasMajumder | 110hp/r2/1:3 | atk_1 same four-10dmg-hits pattern as Ryan Lee's atk_2; passive reacts to the *player's own* cards being discarded specifically during the *opponent's* turn, offers to put it back on deck-top, once/round | **DONE** | Migrated - `catalog/characters/percussion/SasMajumder.py`. Once-per-round guard uses the plain-instance-field simplification again; the `env.turn`-ownership check is a plain `TransferCard` match (not `TurnEnd`-keyed), so it doesn't need the post-act-state adjustment. |

**Cross-cutting notes:**
- DanielYang's CardType/folder mismatch needs a decision (Section 6).
- BokaiBi and SasMajumder are both "watch what happens to me/around me and react" passives distinct from anything in brass/choir — worth designing one consistent v2 idiom for "reactive, opponent-action-triggered passive with a Yes/No follow-up," since more of these show up later (Arranger status effect works the same way).
- PascalKim's "delayed damage at a specific future round via an env-level reactor" recurs almost identically for KatieXiang (piano) — implement it independently both times, no shared helper (per policy).

### Pianos (12 files) — 12/12 migrated, DONE

| Card | Stats | Summary | Difficulty | Notes |
|---|---|---|---|---|
| CathyRong | 110hp/r2/1:2,2:3 | atk_1 20dmg + optional discard 1 energy from a chosen opposing bench character; atk_2 50dmg, 80 if another PIANO on own bench | **DONE** | Migrated - `catalog/characters/piano/CathyRong.py`. |
| CocoZeng | 100hp/r2/1:2,2:3 | atk_1 50dmg, blocked if used last turn; atk_2 one coinflip per card in hand, 30×heads dmg | **DONE** | Migrated - `catalog/characters/piano/CocoZeng.py`. Cooldown gate uses the plain-instance-field idiom (`_last_glissando_round == env.round - 2`), same as AntongChen, not a history search. |
| DavidMan | 100hp/r2/1:3, ACTIVATE_ABILITY | atk_1: same 20dmg packet proposed 3 separate times (3-hit); ability: once/turn, random discard card revealed and shuffled into deck at random index | **DONE** | Migrated - `catalog/characters/piano/DavidMan.py`. 3 hits collapsed into one packet, per the plan's own note. Reveal is *private* (`env.report(RevealCards(...), id)` to the owner only) - v1's audience is `[self.player.unique_id]`, not all players - see Section 2. |
| DemiLu | 90hp/r2/1:3, passive | atk_1 50dmg/80 if PIANO bench-mate; passive: full damage immunity while benched **if a specific Steinert stadium is active**, and separately nullifies/blocks that same stadium's "extra attack cost" listener from ever attaching to this card | Hard | **DONE** — Migrated - `catalog/characters/piano/DemiLu.py`. As flagged, `AVGEConstrainer` can't see per-event "attached_event" context in v2 (confirmed via LukeXu's precedent), so the cost exemption is its own compensating `AVGEEventModifier` (`_CostExemptionModifier`) that adds the energy back for Demi Lu specifically, rather than a constrainer-based block. Deliberately shares `EXTERNAL_MODIFIERS_1` with the Steinert stadiums' own `+1` surcharge modifiers (not a later group) - a first-draft test failure revealed that `INTERNAL_1`'s affordability check runs before any later group, so the exemption must land in the same early window to matter at all; net `+1`/`-1` is order-independent so sharing the group is safe. Damage immunity reuses MAID's `event.modify_magnitude(-event.magnitude)` idiom. 8 new tests in `testing/test_demilu.py`. |
| HenryWang | 100hp/r2/1:2,2:3 | atk_1 50dmg, blocked if used last turn (same Glissando pattern as Coco); atk_2 mills opponent deck-top to discard, 10dmg normally/100dmg if milled card was an item | **DONE** | Migrated - `catalog/characters/piano/HenryWang.py`. Glissando implemented fully independently from CocoZeng's, per policy. |
| JennieWang | 100hp/r2/1:2,2:3 | atk_1: count specific named characters (`DavidMan, EvelynWu, BokaiBi, RobertoGonzales, LukeXu`) anywhere in play, dmg=min(10×count,30) to **every** opponent card; atk_2 60dmg/80 if one of 4 specific stadiums active | Hard | **DONE** — Migrated - `catalog/characters/piano/JennieWang.py`. The widest cross-file coupling in the whole survey (5 character classes across piano/woodwind/percussion/guitar, plus 4 stadium classes) - all were already migrated by the time this was built, so no new sequencing surprises. 5 new tests in `testing/test_jenniewang.py`. |
| JoshuaKou | 90hp/r1/1:1, passive | atk_1 40dmg, but only if it *was* used on the owner's last turn (a "needs momentum" combo, the true inverse of Coco/Henry's cooldown - the original survey note had this backwards, see Section 2); passive: if hand<4 and deck non-empty, Yes/No draw-up-to-4 | **DONE** | Migrated - `catalog/characters/piano/JoshuaKou.py`. Category Theory's `PhasePickCard`-reactive draw surfaced a real engine bug in `PhasePickCard.act()` itself (stale eager draw-target capture) - fixed, see Section 2's new "Engine bugs" entry. |
| KatieXiang | 100hp/r2/1:2, passive | atk_1 20dmg now + 30dmg scheduled at a specific future TurnEnd (same delayed-reactor pattern as PascalKim/percussion); passive: on opponent's TurnEnd, if owner HP<50, heal whole team +20 | **DONE** | Migrated - `catalog/characters/piano/KatieXiang.py`. Delayed damage targets `env.round + 3` (one turn-boundary later than PascalKim's `+2`), since Katie schedules for the *owner's own* next turn ending, not the opponent's - see Section 2. |
| LukeXu | 90hp/r2/1:2, passive | atk_1 20dmg + halves the opponent's next attack against Luke (one-shot incoming-damage modifier); passive: while it's owner's turn and Luke is active, disables ALL of the opponent's passive/active ability attachments for the round | **DONE** | Migrated - `catalog/characters/piano/LukeXu.py`. First use of `AVGEConstrainer` in this migration - found and fixed a real engine bug in the process (`AVGEConstrainer.__init__` never called `super().__init__()`, so `requires_cleanup` was always missing) - see Section 2. Re-read v1 and confirmed the halve-modifier applies to the opponent's next attack *at all* (no target-card check), not specifically "against Luke." |
| MatthewWang | 110hp/r2/1:2, passive | atk_1 flat 40dmg; passive: at start of owner's turn (`PhasePickCard`), coinflip, heads→ Yes/No prompt to draw an extra card | **DONE** | Migrated - `catalog/characters/piano/MatthewWang.py`. First card to exercise the (now-fixed) `PhasePickCard` engine bug's fix in a genuine "extra draw" scenario, alongside the normal per-turn draw. |
| RyanLi | 90hp/r2/1:3, passive | atk_1 50dmg/80 if PIANO bench-mate; passive: allies with MAID status deal +10 dmg on their attacks | **DONE** | Migrated - `catalog/characters/piano/RyanLi.py`. Boosts *any* of the owner's own attacking characters that carry MAID (not just RyanLi himself) - distinct from CavinXue's "boost based on *other* characters having MAID." |
| SophiaSWang | 100hp/r2/1:2, passive | atk_1 20dmg + halves opponent's next attack (same modifier as LukeXu, byte-identical); passive: reacts to *receiving* energy (an `AVGEEnergyTransfer` targeting self), once/round, mills opponent's deck-top | **DONE** | Migrated - `catalog/characters/piano/SophiaSWang.py`. Halve-modifier implemented independently from LukeXu's, per policy. First `AVGEEnergyTransfer`-targeting-self reactor in this migration. |

**Cross-cutting notes:**
- LukeXu and SophiaSWang share a byte-identical "halve the opponent's next attack" one-shot modifier — same duplication situation as the guitar trio; implement independently in both, no shared helper.
- PascalKim (percussion) and KatieXiang (piano) share the "schedule damage at a specific future TurnEnd" idiom — implement once.
- Coco/Henry/Joshua's "did/didn't attack last turn" gating is now the *third* card family needing this exact check (after Carolyn in brass) — despite the repetition, reimplement the search loop independently in each file (no shared utility function, per policy).
- ~~JennieWang must be migrated last among pianos~~ — done; all 5 referenced characters and 4 stadiums existed by the time it was built.
- ~~DemiLu must wait for stadiums~~ — done; built its own compensating cost modifier rather than a constrainer, per SteinertBasement/SteinertPracticeRoom's docstring notes (see its table row).

### Strings (16 files) — 16/16 migrated, DONE

| Card | Stats | Summary | Difficulty | Notes |
|---|---|---|---|---|
| AliceWang | 110hp/r2/1:2, passive | atk_1 40dmg flat; passive: on opponent's TurnEnd, if opponent's hand > owner's, force opponent to discard down to match | Moderate | **DONE** — Migrated - `catalog/characters/strings/AliceWang.py`. Post-act-timing-corrected "opponent's turn just ended" check; opponent picks own discards via cross-player `CardSelectionQuery` with dynamic `num_selections`. |
| AndreaCR | 100hp/r1/1:1,2:3 | atk_1: peek top 3 of *opponent's* deck, branching reorder/bottom logic depending on how many cards exist; atk_2 20dmg + strip up to 2 energy from a chosen opposing character | Hard | **DONE** — Migrated - `catalog/characters/strings/AndreaCR.py`. All 3 Foresight branches (fizzle/reorder-2/bottom-1-reorder-2) implemented via `ReorderDeck`; atk_2 same shape as MaggieLi's atk_1, independent copy. |
| AshleyToby | 100hp/r1/1:2, passive | atk_1 flat 40dmg; passive: doubles own dmg if BOTH players' benches are completely full | Straightforward | **DONE** — Migrated - `catalog/characters/strings/AshleyToby.py`. Simple bench-fullness-gated damage-doubling modifier. |
| EmilyWang | 100hp/r1/1:3, ACTIVATE_ABILITY | atk_1 3 coinflips, 40dmg/heads; ability: once/turn, requires a tool attached, discards it + draws a card | Straightforward | **DONE** — Migrated - `catalog/characters/strings/EmilyWang.py`. Straightforward once/turn tool-discard-and-draw ability. |
| FionaLi | 90hp/r1/1:2, passive | atk_1 flat 40dmg; passive: grants/removes MAID status on whichever character is active on owner's side, tracking bench↔active moves | Moderate once MAID exists | **DONE** — Migrated - `catalog/characters/strings/FionaLi.py`. Passive ability does the one-time initial grant (since its own listener registration happens *after* the entry transfer already resolved); a permanent `_BenchMaidReactor` handles all subsequent bench↔active moves, own or a teammate's. |
| GabrielChen | 90hp/r2/1:1,2:2 (no atk_1 name — only atk_2 defined) | passive: below 60% HP, Yes/No prompt for 70dmg to a *random* opposing character, once; atk_2: coinflip×2 (must be double-heads), then pick 3-target/60dmg or 2-target/70dmg mode, then choose that many targets | Hard | **DONE** — Migrated - `catalog/characters/strings/GabrielChen.py`. Survey said "60% HP" but v1 source actually checks the absolute threshold `hp < 60`, not a percentage of max HP — corrected in the migration. Passive is a genuine one-shot (self-`cleanup()`s after resolving, but faithfully stays armed forever if answered "Yes" with no valid targets, matching v1 exactly). |
| InaMa | 100hp/r2/1:3, ACTIVATE_ABILITY | atk_1: same 3-coinflip/40dmg-per-heads as EmilyWang; ability: once/turn, move 1 energy from another owned STRING character (≥1 energy) to self | Straightforward | **DONE** — Migrated - `catalog/characters/strings/InaMa.py`. Near-duplicate of EmilyWang's attack (independent copy); simple energy-donation ability. |
| IrisYang | 100hp/r1/1:1,2:3 | atk_1 10dmg + draw a card, auto-play-and-discard it if it's an item; atk_2 30dmg + optional swap opponent's active with a chosen bench character | Moderate | **DONE** — Migrated - `catalog/characters/strings/IrisYang.py`. The auto-play mechanic uses a lazy zero-arg generator (draw, then conditionally push `PlayNonCharacterCard` + discard) so the drawn card is resolved at actual execution time; "Open Strings" is byte-identical to (still-deferred) MichelleKim's atk_1, implemented independently. |
| JessicaJung | 100hp/r1/1:2, ACTIVATE_ABILITY | atk_1 flat 40dmg; ability: once/turn, coinflip, heads + supporter(s) in discard → pick one, shuffle into deck at random index | Moderate | **DONE** — Migrated - `catalog/characters/strings/JessicaJung.py`. Once/turn coinflip-gated supporter-recycle-to-deck ability. |
| JuliaCeccarelli | 100hp/r1/1:1,2:3 | atk_1: reveal opponent hand, optionally force-play one of their item cards; atk_2 50dmg + KO-chain-reaction reactor (splash 30dmg to remaining opponent bench per KO caused this way, recursively) | Hard | **DONE** — Migrated - `catalog/characters/strings/JuliaCeccarelli.py`. First card in the migration to actually drive a character to 0 HP through the real engine KO path — this surfaced a real, previously-undiscovered engine bug in `AVGEHPChangeReactor`'s discard/replace flow (see Section 2). Chain-reaction reactor tracks a `pending_hits` counter, re-arming itself per splash wave; verified with a genuine 2-wave cascading-KO test. Shared verbatim with SophiaYWang, implemented independently. |
| MaggieLi | 110hp/r2/1:3, passive | atk_1 20dmg + strip up to 2 energy from chosen opponent (same as AndreaCR's atk_2); passive: on owner's `PhasePickCard`, if not full HP, Yes/No heal 10 | Straightforward | **DONE** — Migrated - `catalog/characters/strings/MaggieLi.py`. `PhasePickCard`-reactive heal-offer, same shape as MatthewWang (piano). |
| MasonYu | 100hp/r2/1:1,2:3 | atk_1: grant ARRANGER status to a chosen bench ally; atk_2: discard own energy, pick 2 characters (either side), randomly designate one as "activator," player picks one of the OTHER's two attacks by name, force-swaps the random one into active and executes that attack via `PlayCharacterCard` | Hard — flagged hardest string file | **DONE** — Migrated - `catalog/characters/strings/MasonYu.py`. Real translation bug caught by tests, not the engine: v1's `PlayCharacterCard(other, ..., card)` call omits `energy_requirement` (defaults to 0), deliberately bypassing "does the acting character have enough energy" for the borrowed attack - Mason's own energy discard is the entire cost. Porting `other.attacks[action_type].cost` as-is into v2's `PlayCharacterCard` (which gates directly on that literal `cost` against `other`'s own energy) silently `REGULATE_FAIL`ed and rolled back the whole packet with no exception - passing `cost=0` explicitly fixed it, matching v1's actual bypass. `PlayCharacterCard`'s `acting_card = id.calling_card` resolution (already established by KeiWatanabe) means the borrowed attack runs with Mason as "card", so its normal targeting resolves relative to Mason's own opponent, not `other`'s. |
| MichaelTu | 100hp/r1/1:2,2:3 | atk_1: reveal-until-first-non-STRING-character found in deck, take to hand + 30dmg, reshuffle; atk_2 60dmg/80 if one of 4 specific stadiums active | Moderate | **DONE** — Migrated - `catalog/characters/strings/MichaelTu.py`. Synchro Summon reveals via a public `RevealCards` broadcast (matching v1's `all_players` audience), then conditionally transfers+damages before a lazy post-transfer `ReorderDeck` shuffle (the `len(deck) > 1` check must happen at actual execution time, after any transfer already ran, same idiom as ConcertProgram/Camera). 5 new tests in `testing/test_michaeltu.py`. |
| MichelleKim | 100hp/r1/1:1,2:2 | atk_1: identical "Open Strings" to IrisYang (10dmg+auto-play-item); atk_2 30dmg/80 if a `MikuOtamatone` item was played this round | Moderate | **DONE** — Migrated - `catalog/characters/strings/MichelleKim.py`. Open Strings is a byte-identical independent copy of IrisYang's. VocaRock!!'s "played this round" check uses `env.search_history(PlayNonCharacterCard, None, increment=0, ...)` (the "current, in-progress chapter" convention from Section 2), looped and filtered by `isinstance(event.target_card, MikuOtamatone)` and owner match - same manual-loop shape as CarolynZheng's `_attacked_last_turn`. 3 new tests in `testing/test_michellekim.py`. **This was the last remaining card in the entire migration.** |
| SophiaYWang | 110hp/r2/1:1,2:3 | atk_1: iterative Yes/No self-damage(20)/draw loop tracking drawn cards, early-exit+full-heal if `AVGEBirb` drawn, shuffle-back-on-decline; atk_2 50dmg + same KO-chain reactor as JuliaCeccarelli | Hard | **DONE** — Migrated - `catalog/characters/strings/SophiaYWang.py`. v2's async `__call__` expresses the whole iterative draw loop as a plain Python `while` loop (planning against a local snapshot of the deck before building any events), instead of v1's cache-based continuation-passing across repeated `atk_1` invocations - dramatically simpler. Confirmed against v1 source: the self-damage from prior draws is NOT undone when cards get shuffled back, only the card transfers are reversed. Ricochet is byte-identical to JuliaCeccarelli's atk_2, independent copy. |
| YuelinHu | 100hp/r1/1:3, passive | atk_1: same 3-coinflip/40dmg-per-heads; passive: reacts to drawing `AVGEBirb` specifically, Yes/No discard it for 20dmg | Moderate | **DONE** — Migrated - `catalog/characters/strings/YuelinHu.py`. Triple Stop is an independent copy of EmilyWang's/InaMa's. v1's passive also excludes the initial hand deal (`game_phase == INIT`); v2 has no equivalent concept to port since nothing in this migration deals an initial hand via a real `TransferCard`. |

**Cross-cutting notes:**
- **JuliaCeccarelli and SophiaYWang share a byte-identical KO-chain-reaction reactor** ("Ricochet") — implement once, reuse both places.
- **IrisYang and MichelleKim share a byte-identical "draw + auto-play item" attack** ("Open Strings") — same treatment.
- Three strings characters (SophiaYWang, YuelinHu, RaffleTicket [an item]) all reference `AVGEBirb` by name — migrate `AVGEBirb` early within items.
- ~~MichelleKim needs `MikuOtamatone`; MichaelTu needs 4 stadium classes~~ — both done; see their table rows.
- MasonYu's "force any character to use one of its own named attacks" and Ross's hijack and KeiWatanabe's (percussion) "borrow a teammate's attack" are now THREE distinct variations on the same underlying `calling_card`-resolution idea. Worth writing a short shared design note (in this doc, once all three are implemented) on how they differ, since future characters will likely need a fourth variation.

### Woodwinds (18 files) — 18/18 migrated, DONE

| Card | Stats | Summary | Difficulty | Notes |
|---|---|---|---|---|
| AnaliseJia | 110hp/r1/1:2,2:3 | atk_1: find items the player played this turn no longer in hand, optional retrieve + 10dmg; atk_2: heal own team +30, plus an unclear self-energy-transfer call | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/AnaliseJia.py`. The "unclear" atk_2 energy transfer is just the established self-discard-own-energy idiom (Roberto/AndreaCR), nothing unusual. "Find items played this turn" uses `search_history(PlayNonCharacterCard, ..., increment=0)` looped with `index_to_start`, deduplicated by `id()` - independent copy of the logic MeiyiSong also needs. |
| AnnaBrown | 110hp/r2/1:3 (no atk_2), passive | passive: full dmg immunity while benched, vs opposing ATK_1/ATK_2; atk_1 d6, 30+10×roll dmg | Straightforward | **DONE** — Migrated - `catalog/characters/woodwinds/AnnaBrown.py`. v1's "invalid roll" branch (calling `generic_response(..., ATK_2)` inside `atk_1`) is dead code in v1 and has no v2 equivalent at all - v2's `D6Input` always returns an int, so there's nothing to faithfully reproduce or fix; simply omitted. |
| BettySolomon | 100hp/r1/1:1,2:3 | atk_1: search own deck for a character, move to deck-top; atk_2: 2 coinflips, HH→50dmg to all opp bench, TT→100dmg to opp active, split→nothing | Straightforward | **DONE** — Migrated - `catalog/characters/woodwinds/BettySolomon.py`. "Move to deck-top" needs `ReorderDeck` (v2's `TransferCard` with `deck_from is deck_to` would append to the end, not move to top). |
| DanielZhu | 120hp/r2/1:3 (no atk_2), passive | passive: redirect 0-N incoming damage from a teammate onto Daniel instead (player picks N via IntegerInputData), capped by Daniel's own HP-1; atk_1 same d6 formula as AnnaBrown | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/DanielZhu.py`. **Fixed a real v1 bug on sight**: v1's atk_1 is internally mistagged `ActionTypes.ATK_2` throughout (id, interrupt key, damage event) despite no `atk_2` existing at all - a copy-paste leftover with no coherent purpose. v2's architecture makes this impossible to even accidentally reproduce (attacks are keyed by their own declared `atk_type`), so this migration just tags it ATK_1 correctly like every other single-attack card. |
| DesmondRoper | 100hp/r2/1:1,2:3 | atk_1: streak-counter via history (consecutive own-turns using this atk, cap 4), dmg=10+min(40,10×streak); atk_2: 100dmg if moved into active this turn, else 40dmg | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/DesmondRoper.py`. **Important v1→v2 semantic gap found via a failing test**: v1's streak search matches `caller: card` because v1's real attack dispatch always sets `caller` to the attacking character itself; v2's normal attack dispatch (`run_attack`/`AtkPhase`) tags the outer `PlayCharacterCard`'s `id.calling_card` as `None` instead, so porting a `calling_card is card` check verbatim silently zeroed the streak every time. Fixed by matching only on `target_card`/`action` (who actually executed the move) - the same fix applies to EvelynWu's identical formula. Streak chapters step by 2 (one player's own consecutive turns are 2 history chapters apart, the opponent's intervening turn being 1). |
| EvelynWu | 100hp/r1/1:1,2:2 | atk_1 same streak formula as Desmond; atk_2: heal all damaged opponent bench cards to full, deal total-healed-amount as dmg to opponent active | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/EvelynWu.py`. Streak formula independently reimplemented with the same `calling_card`-vs-`target_card` fix as DesmondRoper's (see its note). |
| FelixChen | 90hp/r1/1:3 (no atk_2), passive — **referenced in SYSTEM_ARCHITECTURE.md, which is outdated/wrong for this card** | passive: -10 incoming dmg if Felix's whole team has all-distinct card_types; atk_1: 2 coinflips, HH→50 to all opp bench, TT→100 to opp active only (not "all bench" as the architecture doc claims) | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/FelixChen.py`. **Fixed a real v1 bug on sight**: the passive's `event_match` checked `catalyst_action not in [ATK_1, ATK_1]` (obvious copy-paste typo for `[ATK_1, ATK_2]`), so v1 silently never reduced ATK_2 damage. This migration reduces both, with a regression test proving ATK_2 is now covered. |
| HarperAitken | 100hp/r2/1:2,2:3 | atk_1: 50dmg + 10 self-recoil; atk_2: pick up to 2 opposing targets, 80dmg each, 80 self-recoil regardless | Straightforward | **DONE** — Migrated - `catalog/characters/woodwinds/HarperAitken.py`. "Up to 2" targets just iterates over however many the `CardSelectionQuery` response actually contains (0, 1, or 2) - v2 has no fixed-count requirement here. |
| IzzyChen | 110hp/r2/1:2 (no atk_2), ACTIVATE_ABILITY | atk_1 same 50+10-recoil pattern; ability: once/turn, coinflip, heads→pick a discard stadium, shuffle into deck at `random.randint` position | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/IzzyChen.py`. "Shuffle at a random position" uses the established `TransferCard` + full-deck `ReorderDeck`(`random.sample`) combo rather than v1's single-card `randint` insert - simpler, same effective randomness. Overblow is an independent copy of HarperAitken's atk_1. |
| JaydenBrown | 90hp/r1/1:3 (no atk_2), passive | passive: **globally intercepts the first CoinflipData of the round for its own controller**, offers to force it to heads, once/round; atk_1 same d6 formula | Hard | **DONE** — Migrated - `catalog/characters/woodwinds/JaydenBrown.py`. First card in the migration to actually use the `IOListener` engine hook (`card.add_io_listener(...)`) - `match()` filters to `CoinflipData` requests for the owner's own controller while active, gated once/round via a plain instance field; `modify()` is itself `async` and awaits its own follow-up `StringSelectionQuery` before deciding whether to override the already-resolved coinflip result to `1`. Confirms the hook (built ahead of time per Open Question 4) works exactly as designed. |
| JordanRoosevelt | 100hp/r1/1:1,2:2, **no has_passive at all** | atk_1 deals zero damage — only attaches two round-scoped buffs (one buffing the *opponent's* next attack +20, one buffing Jordan's own next attack +60), both self-expiring; atk_2: 30dmg + 20 self-heal | Hard | **DONE** — Migrated - `catalog/characters/woodwinds/JordanRoosevelt.py`. Confirmed the "buff the opponent" half is intentional, not a bug: it's a matched pair with Jordan's own much-bigger self-buff (+60 vs +20), a net-favorable trickster gamble. Both round-scoped modifiers self-clean inside `match()` once `env.round` passes their target, same idiom as Roberto/Edward's Distortion buffs. **Test-harness gotcha found while testing this**: chaining several bare `pkt.flush()` `TurnEnd`s (the exact-round-math idiom PascalKim/KatieXiang's tests use) leaves each one's un-run follow-up packets (draw phase, attack phase, etc.) sitting in the engine's push/append buffer; a later *real* `env.engine.flush(...)` call (e.g. from `run_attack`) drains all of them at once and can trigger a genuine runaway draw/attack-phase cascade that hangs indefinitely - see Section 2. |
| KanaTakizawa | 110hp/r2/1:3 (no atk_2), passive | passive: flat -10 incoming dmg, group EXTERNAL_MODIFIERS_3 (not _2 like most others); atk_1: repeatedly roll d6 until current+previous roll sum to 7, then deal 10dmg × number-of-rolls-taken | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/KanaTakizawa.py`. "Roll until pair sums to 7" is a plain async `while` loop, much simpler than v1's cache-based reentry - each of the `roll_count` hits is pushed as its own separate 10dmg event (not one combined `roll_count*10` hit), matching v1 exactly, since per-hit damage shields (e.g. MAID's ≤10 immunity) would behave very differently against N small hits vs. one big one. `EXTERNAL_MODIFIERS_3` group kept as specified in v1, faithfully. |
| KathySun | 100hp/r1/1:1,2:3 | atk_1: opponent picks up to 2 own hand cards to shuffle into their own deck at random positions; atk_2: same "roll until pair sums to 7" mechanic as Kana | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/KathySun.py`. v1's per-choice `lambda chosen=choice: ...` late-binding-avoidance trick has no v2 equivalent needed - the response list from one `CardSelectionQuery` is just iterated directly. Flutter Tongue (atk_2) is an independent copy of Kana's atk_1. |
| LucaChen | 90hp/r1/1:2,2:3 | atk_1: 30dmg + 20 self-heal; atk_2: 40dmg, +50 bonus if Luca is the only WOODWIND anywhere in play | Straightforward | **DONE** — Migrated - `catalog/characters/woodwinds/LucaChen.py`. "Only WOODWIND in play" counts both sides, including opponent's own characters - `Dummy` (the test double) is itself WOODWIND-typed, so tests need a non-Dummy opponent (`AshleyToby`) to exercise the "gets the bonus" path. Sparkling Run is an independent copy of JordanRoosevelt's atk_2. |
| MeiyiSong | 90hp/r1/1:2,2:2 | atk_1: identical "find items played this turn" mechanic as AnaliseJia (implement independently, no shared helper); atk_2: same "only woodwind in play" bonus pattern as LucaChen (20 base +50 bonus) | Straightforward | **DONE** — Migrated - `catalog/characters/woodwinds/MeiyiSong.py`. Both mechanics independently reimplemented from AnaliseJia's/LucaChen's. |
| RachaelYuan | 100hp/r2/1:1,2:3 | atk_1 same streak formula as Desmond/Evelyn; atk_2: pure disruption, no damage — if opponent bench <2, no-op; else optionally shuffle a chosen opposing bench character into their deck | Straightforward | **DONE** — Migrated - `catalog/characters/woodwinds/RachaelYuan.py`. Streak formula uses the same `target_card`-only match fix as Desmond/Evelyn. |
| SarahChen | 100hp/r1/1:1,2:3 | atk_1: proposes the same 10dmg packet twice via two separate calls (20dmg total, structurally odd); atk_2: multi-stage — pick any number of owned `ConcertProgram`/`ConcertRoster`/`ConcertTicket` cards from hand to discard, then per-selection pick an opposing target for 40dmg each | Hard | **DONE** — Migrated - `catalog/characters/woodwinds/SarahChen.py`. Double Tongue collapsed into one packet with 2 damage events. Artist Alley's "any number" discard selection and "one target per discard, targets may repeat" selection both use flexible-length `CardSelectionQuery` responses, same technique as HarperAitken's Wipeout. |
| WestonPoe | 110hp/r2/1:2 (no atk_2), passive — **referenced in SYSTEM_ARCHITECTURE.md, which is outdated for this card** | passive: reflects incoming ATK_1/ATK_2 damage ≥60 back onto the attacker, using the *actual post-modifier* damage dealt (not the raw pre-modifier magnitude); atk_1 same 50+10-recoil pattern | Moderate | **DONE** — Migrated - `catalog/characters/woodwinds/WestonPoe.py`. Uses `original_hp`/`final_change` (both set once during `act()`, at CORE time) to recompute actual HP lost, exactly matching v1's `old_amt`/`final_change` re-derivation. **Deliberately has no "still in play" gate** unlike most other permanent listeners in this migration - by the time this `EXTERNAL_REACTORS` listener sees a lethal hit, the engine's own `INTERNAL_3` discard flow has already moved the owner out of play, so gating on current `deck_type` would wrongly block reflection on the exact hit that KO'd them (caught by a failing test before removing the gate). |

**Cross-cutting notes:**
- **Likely v1 bugs found in this batch** (AnnaBrown's ATK_2 response call inside atk_1, DanielZhu's whole atk_1 mistagged as ATK_2, FelixChen's `[ATK_1, ATK_1]` duplicate excluding ATK_2): this is now common enough to need a **stated policy**, not a per-card judgment call — see Open Questions.
- **SYSTEM_ARCHITECTURE.md is confirmed stale/illustrative for at least FelixChen and WestonPoe** (uses a different, simplified API shape than the real files, and gets one factual detail wrong for Felix). Treat it as background flavor only, never as a migration source for any card — the real `.py` files are the only source of truth. Worth a one-line callout at the top of this doc so nobody re-derives a wrong implementation from it later.
- JaydenBrown's "intercept any upcoming coinflip system-wide" passive is the single hardest new mechanic found across the *entire* survey — it needs an engine-level design conversation before attempting, not just a character-file implementation. Recommend punting it to last among woodwinds, or explicitly designing the needed hook first as its own mini-project.
- AnaliseJia/MeiyiSong ("find items played this turn") and LucaChen/MeiyiSong ("only woodwind in play bonus") and KanaTakizawa/KathySun ("roll until pair sums to 7") are three more instances of the "byte-identical logic duplicated across 2 files" pattern already seen repeatedly in guitars/pianos/strings — by now this is clearly not a coincidence but a v1 authoring convention (copy the sibling file, tweak numbers). **Per explicit user decision: do NOT build shared helpers for these** — re-derive each one independently in every character file that needs it, matching v1's own duplication rather than introducing v2-side abstraction.
- SarahChen's item dependency confirms (again) that items block 2 characters, not 1.

### Items (21 files) — 21/21 migrated, DONE

| Item | Summary | Difficulty | Notes |
|---|---|---|---|
| AVGEBirb | Strips all opponent tools + all opponent status effects; curses the *owner's own* active with +20 damage on its next hit taken | **DONE** | Migrated - `catalog/items/AVGEBirb.py`. Referenced by name from SophiaYWang, YuelinHu (strings) and RaffleTicket (item). Found and fixed a real v1 bug where the self-damage curse could never fire (bad round-number gating) - see Section 2. |
| AnnotatedScore | Owner (not opponent) picks a revealed opponent hand card to discard, then a different opponent discard card to return to the opponent's hand | **DONE** | Migrated - `catalog/items/AnnotatedScore.py`. The plan's original one-line gloss ("owner takes a different card back from discard") was imprecise — re-read v1: both TransferCards land in the *opponent's* piles, both picks made by the owner. Net effect is an owner-directed swap within the opponent's own hand/discard, nothing comes to the owner. |
| BAIEmail | Discards active stadium, searches deck for a new one, locks out playing any stadium until next turn | **DONE** | Migrated - `catalog/items/BAIEmail.py`. Gates on the incoming `TransferCard` (`deck_to.deck_type == STADIUM`) rather than `PlayNonCharacterCard` - see Section 2 for why that's the correct (and only) gate point in v2. `round_until = env.round + 2` (the owner's own next turn) - re-derived the math and confirmed this ISN'T the same bug pattern as AVGEBirb's curse: the lock is global (blocks either player), so there's no per-player condition that could make it unsatisfiable. |
| BUOStand | Discard 1 own energy, next attack +20 (+10 more if GOON) | **DONE** | Migrated - `catalog/items/BUOStand.py`. Same `env.round`-based fire-once self-expiring modifier idiom as FoldingStand, implemented fully independently. Note: unlike FoldingStand, v1's BUOStand has no `change_type == CardType.ALL` exclusion - it also buffs true damage - replicated faithfully, not "fixed" (an intentional-but-unusual difference between the two cards, not a bug). |
| Camera | Shuffle a chosen own discard supporter/stadium into deck at random position | **DONE** | Migrated - `catalog/items/Camera.py`. Same `TransferCard` + `ReorderDeck`(random-insert-lambda) combo as ARRANGER (see Section 2). Added `DummySupporter` to `testing/helpers.py` alongside the existing `DummyStadium`, since no real supporter exists yet to test eligibility filtering against. |
| CastReserve | Owner picks 3 uniquely-typed items from deck; opponent picks 2 to reshuffle back; the leftover one goes to owner's hand | **DONE** | Migrated - `catalog/items/CastReserve.py`. v2 has no retry/re-validate loop for `CardSelectionQuery` (unlike v1's custom validity-callback interrupts), so the type-uniqueness requirement is enforced structurally instead: the owner is only ever *offered* one representative item per distinct type, so any 3 picks from that list are automatically unique - no possibility of an invalid submission, same end result as v1's validated version. A no-op if fewer than 3 distinct item types exist in the deck. |
| ConcertProgram | Peek top 5, take a character to hand, reshuffle rest | **DONE** | Migrated - `catalog/items/ConcertProgram.py` |
| ConcertRoster | Peek top 3, take a tool/stadium to hand | **DONE** | Migrated - `catalog/items/ConcertRoster.py` |
| ConcertTicket | Draw up to 4 in hand; can't play as the only hand card | **DONE** | Migrated - `catalog/items/ConcertTicket.py`. Note: v1's "can't play as only card" is a *full* cancel (card never even discarded); v2's item-dispatch always discards separately (see Section 2's `Phase2.act()` bug note), so this only skips the draw effect, the card still gets discarded - a disclosed simplification, not a faithfulness bug. |
| CorruptedMusescoreFile | Optional: discard a tool from one of your characters; optional: search deck for an item | **DONE** | Migrated - `catalog/items/CorruptedMusescoreFile.py`. Declining the tool discard (or having nothing to discard) ends the card - no item search either, matching v1 exactly. |
| DressRehearsalRoster | Strip 1 energy each from 1-2 chosen characters (validated); reshuffle up to 4 random discard cards into deck | **DONE** | Migrated - `catalog/items/DressRehearsalRoster.py`. Same "no retry loop" adaptation as CastReserve: rather than replicating v1's custom same-or-different-target validity callback, this just trusts the 2 picks and leans on `AVGEEnergyTransfer`'s own built-in no-op-if-empty behavior - an under-resourced pick discards less than 2 total energy instead of being rejected. |
| FoldingStand | Next attack +10 (+10 more if GOON), no cost | **DONE** | Migrated - `catalog/items/FoldingStand.py`. Round-scoped, fire-once self-expiring `AVGEEventModifier` on `AVGECardHPChangeEvent`, same idiom as AVGEBirb's curse (same round as play time here, not +1, since the buffed attack is the *owner's own*, happening the same turn the item was played). Excludes `CardType.ALL` (true damage), matching v1. |
| IceSkates | Swap active with a chosen bench character | **DONE** | Migrated - `catalog/items/IceSkates.py`. Two `TransferCard`s in one packet (bench→active, then active→bench); tagged `NONCHAR` like v1 so the normal swap-cost/retreat-cost regulators (which only gate `PLAYER_CHOICE`-tagged transfers) don't apply. |
| MatchaLatte | Heal all own in-play +10 (+10 more if `PetterutiLounge` active) | Straightforward once that stadium exists | **DONE** — Migrated - `catalog/items/MatchaLatte.py`. Found and fixed a real v1 bug on sight: v1 checks `isinstance(card.env.stadium_cardholder, PetterutiLounge)`, but `stadium_cardholder` is the pile/cardholder container itself, never an instance of a specific stadium card class — this check was always `False` and the bonus could never actually apply. Fixed by checking the card actually occupying the stadium slot (`env.stadium_cardholder.cards_holding[0]`) instead. |
| MikuOtamatone | Requires one of 4 named stadiums active + not turn 0; reduces next attack's energy cost by 2 | Moderate | **DONE** — Migrated - `catalog/items/MikuOtamatone.py`. Found and fixed a real v1 bug on sight (see cross-cutting notes below): v1 imports `FriedmanHall` but its gating tuple only checks 4 of the 5 imported stadium classes, silently excluding it. All 5 are equally "performance hall"-themed with no plausible reason to import `FriedmanHall` for nothing else, so v2 includes all 5 (`AlumnaeHall, FriedmanHall, RileyHall, MainHall, SalomonDECI`). Referenced by MichelleKim (strings, still deferred). |
| Otamatone | Same as MikuOtamatone but no stadium requirement, -1 cost instead of -2 | **DONE** | Migrated - `catalog/items/Otamatone.py`. Modifies `PlayCharacterCard.cost` directly (a real, already-mutable field used exactly this way by the existing `AVGEPlayCharacterCardValidityCheck` affordability regulator - no new engine primitive needed). Round-scoped self-expiring listener, same `env.round`-based idiom as AVGEBirb's curse/Open Question 6, but *without* a fire-once self-invalidate - it stays live for every qualifying attack for the rest of the turn, matching v1's own `event_match`/`update_status` split exactly (v1 has no per-use invalidation here, unlike its AVGEBirb counterpart). |
| PrintedScore | Opponent (not owner) reveals hand and discards a card from it | **DONE** | Migrated - `catalog/items/PrintedScore.py`. The plan's original summary had this backwards ("owner's choice") - re-read v1: the `InputEvent` recipient is the *opponent*, so the opponent picks which of their own revealed hand cards to discard, not the owner. Corrected here. Uses v2's existing `RevealCards` IO type (broadcast to all players) for the first time in this migration. |
| RaffleTicket | Draw deck-bottom card; if it's `AVGEBirb`, also fully heal a chosen own character | **DONE** | Migrated - `catalog/items/RaffleTicket.py`. Reads `deck.cards_holding[-1]` directly for the bottom card; heal uses `AVGECardHPChangeEvent` with `AVGEAttributeModifier.SET_STATE` to `max_hp`, same primitive already used elsewhere for HP-reset-on-discard. |
| StandardMusescoreFile | Optional: discard a tool; optional: search deck for a non-item card | **DONE** | Migrated - `catalog/items/StandardMusescoreFile.py`. Near-twin of CorruptedMusescoreFile, implemented fully independently per policy. One divergence from a literal v1 port: v1 always prompted for the second (non-item) pick even when the deck has zero non-item cards (a pointless empty-choice prompt); v2 skips that prompt when there's nothing to choose, same convention already used for ConcertRoster/Camera. |
| StrawberryMatchaLatte | Heal one chosen own character 20 (30 if `PetterutiLounge` active) | Straightforward once that stadium exists | **DONE** — Migrated - `catalog/items/StrawberryMatchaLatte.py`. Same real v1 bug fix as MatchaLatte's identical (always-`False`) `isinstance(stadium_cardholder, PetterutiLounge)` check, applied independently. |
| VideoCamera | Move a chosen own discard item to the very top of the deck | **DONE** | Migrated - `catalog/items/VideoCamera.py`. Same `TransferCard` + `ReorderDeck` combo as Camera/ARRANGER, but a fixed "move to index 0" reordering lambda instead of a random one. |

**Cross-cutting notes:**
- **ConcertProgram/ConcertRoster/ConcertTicket must be migrated to unblock BOTH RachelChen (choir) and SarahChen (woodwind)** — confirmed by grep, this isn't choir-only as originally assumed.
- `AVGEBirb` needed by 2 strings characters + RaffleTicket.
- `MikuOtamatone` needed by MichelleKim (strings); `PetterutiLounge` (stadium) needed by MatchaLatte + StrawberryMatchaLatte.
- CorruptedMusescoreFile and StandardMusescoreFile are near-identical "optional tool discard + optional deck search" templates — implement each independently in full, no shared helper (per policy).
- MikuOtamatone imports `FriedmanHall` but never checked it in v1's stadium-gating tuple — resolved as a real v1 bug and fixed in v2 (all 5 imported stadiums are now checked). See table row above.

### Stadiums (10 files) — 10/10 migrated, DONE

| Stadium | Summary | Difficulty | Notes |
|---|---|---|---|
| AlumnaeHall | On play, purges all hands' item cards (if not turn 0); persistent: drawing a card deals 10dmg to the drawer's whole board | Moderate | **DONE** — Migrated - `catalog/stadiums/AlumnaeHall.py`. Damage per draw is capped so nobody drops below 1 HP, same idiom as RileyHall. |
| FriedmanHall | Once/turn at pick-card phase, reveal top 2 of active player's deck, opponent picks which one they keep, other is shuffled back | Hard | **DONE** — Migrated - `catalog/stadiums/FriedmanHall.py`. **Redesigned rather than ported literally**: v1's re-entrant "cancel `PhasePickCard`, re-inject a fresh `Phase2`, self-recursion-guard via a `temp_cache` flag" dance has no safe v2 equivalent (`REGULATE_FAIL` rolls back the *entire enclosing packet*, not just one event, so using it to cancel-and-replace a single event the way v1's assessor model could is unsafe). Instead, this reactor runs *before* the engine's own already-queued normal draw (which lazily reads `deck.get_top()` only when its own later-appended packet actually runs) and just reorders the deck so the opponent's chosen card is on top - the normal draw then naturally draws it, with no double-draw risk and no recursion to guard against in the first place. Net player-visible behavior is identical to v1's. |
| LindemannPracticeRoom | -1 energy cost on an attack if the attacker's whole bench matches its active's type | Straightforward | **DONE** — Migrated - `catalog/stadiums/LindemannPracticeRoom.py`. Kept the vacuous-truth-on-empty-bench behavior faithfully (not a clear enough bug to justify changing) - reduces `PlayCharacterCard.cost` directly, same established pattern as Otamatone. Tests confirm/verify via whether the resulting `PlayCharacterCard` actually lands in history (`env.engine.flush()` doesn't propagate a per-packet success/fail status to its caller - a useful thing to know for any future stadium/cost-modifier test). |
| MainHall | Limits each player to 3 non-character plays per round, starting the round after it's played | Moderate | **DONE** — Migrated - `catalog/stadiums/MainHall.py`. Uses `AVGEEventRegulator` (v2's `respond() -> ResponseStatus`) for the first time in this migration outside `CoreListeners.py` - `REGULATE_FAIL`s the 4th+ qualifying play once 3 are already recorded this round. v1 fully cancels its own play if played on turn 0; v2's `play_card() -> None` has no "cancel myself" channel, so this migration just skips registering the effect instead (same simplification already established by Otamatone's identical restriction) - the stadium still occupies the slot but does nothing that game. |
| PetterutiLounge | 3 simultaneous effects: MAID attacker +10dmg; MAID retreat -1 cost; reveal a random opponent hand card after any attack | Hard | **DONE** — Migrated - `catalog/stadiums/PetterutiLounge.py`. First card in the whole migration to use the packet-level `AVGEPacketReactor` API (`packet.event_log` - the packet's own list of every event it actually ran - is how the reactor finds the real attacking character, since the packet's own `id.calling_card` is `None` for a normal player-driven attack, same gotcha as DesmondRoper's streak). The MAID retreat discount reuses KikisHeadband's exact "verify the discounted cost, then top up 1 free energy so the base full-price discard still succeeds" trick, since v2 has no `TransferCard.energy_requirement` field to directly mutate like v1 does. |
| RedRoom | +10dmg for GUITAR/PIANO/CHOIR/PERCUSSION attackers, -10dmg for WOODWIND/BRASS | Straightforward | **DONE** — Migrated - `catalog/stadiums/RedRoom.py`. STRING attackers are entirely unaffected (v1's allowlist is 6 of 7 types, STRING excluded). Established `self.deck_type == DeckType.STADIUM` as the v2 equivalent of v1's `_is_active_stadium()`, used for every stadium listener's match-gate + self-cleanup from here on. |
| RileyHall | At start of active player's turn, 10dmg per empty bench slot to their whole board | Straightforward | **DONE** — Migrated - `catalog/stadiums/RileyHall.py`. `PhasePickCard`-reactive, same hook several characters already use; damage is capped per-character so it can never reduce anyone below 1 HP, matching v1's `min(current_hp - 1, ...)` exactly. |
| SalomonDECI | Same type-based table as RedRoom's "supported" types, plus a d6 roll for an extra -30dmg reduction | Moderate | **DONE** — Migrated - `catalog/stadiums/SalomonDECI.py`. **Correction to this survey row**: re-reading the real v1 source, there is no separate "type-based +/- table" here at all - it's purely the d6-roll -30dmg-on-3+ mechanic for the 4 "supported" types (GUITAR/PIANO/CHOIR/PERCUSSION), nothing else. Rolls fresh every qualifying hit rather than replicating v1's seemingly-never-cleared per-stadium-lifetime cache (Open Question, resolved this way - a forever-cached single roll reads as almost certainly unintended). |
| SteinertBasement | Bonus draw at 2-cards-in-play; +1 energy cost on all attacks | Moderate | **DONE** — Migrated - `catalog/stadiums/SteinertBasement.py`. Exports `_AttackExtraCostModifier` for DemiLu (still deferred) to reference - flagged in its docstring that v2's `AVGEConstrainer` can't see per-event context like v1's could (confirmed via LukeXu's precedent), so DemiLu will most likely need its own compensating modifier rather than a constrainer exclusion. Duo Queue's extra draw uses the same lazy `deck.get_top()` pattern as the engine's own (already-fixed) normal draw, since both compete for the same deck. |
| SteinertPracticeRoom | On play, forces both players to discard down to 2 benched (interactive, sequential per-player); persistent 2-bench cap + attacks cost +1 energy | Hard — flagged hardest stadium | **DONE** — Migrated - `catalog/stadiums/SteinertPracticeRoom.py`. v2's `play_card()` being one async coroutine turns v1's cache-based re-entrant two-player resolution into two plain sequential `await`s - dramatically simpler. Confirmed a real, deliberate difference from SteinertBasement's otherwise-identical cost modifier: this one has no `PLAYER_CHOICE` gate, so it surcharges even a borrowed/forced attack. |

**Cross-cutting notes:**
- **Migrate SteinertBasement and SteinertPracticeRoom together, and coordinate with DemiLu (piano)** — DemiLu imports their internal assessor classes directly, so the v2 versions' internal listener class names/shapes need to be decided with DemiLu in mind.
- **Migrate AlumnaeHall, SalomonDECI, RileyHall, MainHall before MichaelTu (strings) and JennieWang (piano)**, which both check for these 4 specific stadiums being active.
- **Migrate PetterutiLounge before MatchaLatte/StrawberryMatchaLatte (items).**
- PetterutiLounge is the one card in the *entire* survey (so far) that needs the packet-level listener API (`AVGEPacketReactor`) — worth a small standalone smoke test of that API path before relying on it here, similar to how the engine-ordering bugs were only found via dedicated smoke tests.

### Status effects, tools, supporters (18 files) — status effects 3/3 DONE, tools 6/6 DONE, supporters 9/9 DONE

**How status effects actually work (important — this is infrastructure, not "3 small files"):**
- `statuses_attached: dict[StatusEffect, set[...]]` already exists on `AVGECharacterCard` in v2 (seen it in `AVGECard.py` — `{effect: set([]) for effect in StatusEffect}`), and v2's `constants.py` already defines the `StatusEffect` enum (ARRANGER/GOON/MAID) and `AVGECardStatusChange` exists in v2's `EventCatalog.py`. So the *data model* is already there.
- What's missing is the **consequence listeners**. In v1, GOON and ARRANGER are enforced by listeners registered **globally, once, directly in `AVGEEnvironment.__init__`** (not per-card) — i.e. they're closer to v2's `CoreListeners.py` (engine-wide rules) than to a character's own passive. MAID, by contrast, is enforced **per-event**, attached fresh to every `AVGECardHPChange` event's own internal listener setup (alongside the existing weakness/crit modifier) — i.e. MAID's consequence lives inside what would be v2's `AVGECardHPChangeEvent` machinery or a core listener matching every such event, not a `core_listeners` list entry.
- **This means "migrate status_effects/" isn't 3 independent character-style files** — it's 2 new entries in v2's `core_listeners` list (Goon's cost+HP reactor, Arranger's shuffle-offer reactor) plus one addition to `CoreListeners.py` itself (a Maid damage-immunity check, likely folded into or alongside `AVGEHPChangeCheck`/`AVGEWeaknessModifier`). **Recommend treating this as an engine-layer task, reviewed like the `push_event` engine fix was, not a catalog-file task.**
- Consumers found so far (beyond the 3 status/tool files themselves): `BUOStand`/`FoldingStand` (items, GOON bonus), `PetterutiLounge` (stadium, MAID bonus), `RyanLi`/`CavinXue` (piano/percussion, MAID dmg buff), `MasonYu` (strings, grants ARRANGER), `FionaLi` (strings, dynamically grants/revokes MAID based on board state — this is the "producer" pattern to mirror for how a character-driven status effect should look in v2, as opposed to tool-driven).

| Tool | Summary | Difficulty |
|---|---|---|
| AVGEShowcaseSticker | Coinflip at equipped character's turn start, heads draws a card | Moderate — `PhasePickCard`-reactive, same hook as several characters |
| AVGETShirt | Grants GOON on equip, revokes on unequip | Straightforward (once GOON enforcement exists) |
| Bucket | Changes equipped character's CardType to PERCUSSION while equipped, reverts after | Straightforward |
| KikisHeadband | -1 retreat energy cost while equipped | Straightforward |
| MaidOutfit | Grants MAID on equip, revokes on unequip | Straightforward (once MAID enforcement exists) |
| MusescoreSubscription | Grants ARRANGER on equip, revokes on unequip | Straightforward (once ARRANGER enforcement exists) |

| Supporter | Summary | Difficulty |
|---|---|---|
| Angel | Grants GOON to all own in-play; discards all opponent tools | **DONE** — Migrated - `catalog/supporters/Angel.py`. |
| Emma | Forces an opponent bench swap; **leaves a persistent listener locking that character from retreating until the opponent's next round** | **DONE** — Migrated - `catalog/supporters/Emma.py`. `round_active = env.round + 1` (it's always the caster's own turn when Emma is played, so the opponent's next turn is always exactly one round later) - a plain `AVGEEventRegulator` `REGULATE_FAIL`s a matching retreat attempt, self-cleaning once `env.round` passes it. Verified end-to-end with real chained `TurnEnd`s that the lock blocks the retreat during the opponent's very next turn and no longer blocks it the turn after. |
| Johann | Pick up to 3 discard cards (1 supporter/1 item-or-tool/1 stadium max) back to hand, then ends the turn | **DONE** — Migrated - `catalog/supporters/Johann.py`. v1's single combined query + custom retry-validator (enforcing "at most 1 per category") has no v2 equivalent (same limitation already solved for CastReserve) - replaced with three independent, separately-scoped queries, one per category, which structurally guarantees the same result with no validation needed. Mid-resolution `TurnEnd` confirmed safe - verified end-to-end that `env.turn` actually flips. |
| Lio | Shuffle hand into deck, draw 4 | **DONE** — Migrated - `catalog/supporters/Lio.py`. This is where the two supporter-dispatch engine bugs were found and fixed (see Section 2) - the "shuffle hand into deck" step is lazy (evaluated only once this event actually runs, in a later packet) since Lio itself is still sitting in hand at `play_card()` time, and an eager snapshot would wrongly include Lio itself in the cards to shuffle. |
| Lucas | Sequential: reveal a deck character (by type not on board), optionally reveal a second (different type), both to hand | **DONE** — Migrated - `catalog/supporters/Lucas.py`. **Correction to this survey row**: re-reading v1 source, the *first* pick is revealed and placed on **top of the deck**, not taken to hand - only the *second* pick goes to hand. |
| Michelle | Opponent (not caster) picks one hand card to keep, rest discarded | **DONE** — Migrated - `catalog/supporters/Michelle.py`. Can't be played on the first turn - v2's `play_card() -> None` has no "cancel myself" channel, so this skips the effect instead (same simplification as Otamatone/MainHall). |
| Richard | Swap discard and deck piles entirely (each independently reshuffled) | **DONE** — Migrated - `catalog/supporters/Richard.py`. Both piles' contents are snapshotted before any transfers happen, since transferring discard->deck first would otherwise contaminate the "original deck" snapshot needed for the second half of the swap. |
| Victoria | Pick a CardType, then optionally a matching deck character to reveal-to-top, then optionally a second to hand | **DONE** — Migrated - `catalog/supporters/Victoria.py`. Same top-deck/hand shape as Lucas, independently implemented, gated by an explicit type choice instead of "not on board". |
| Will | Shuffle all discarded items back into deck | **DONE** — Migrated - `catalog/supporters/Will.py`. |

**Cross-cutting notes:**
- **Status effects should be scheduled as an engine-layer task, done once, before any character/tool/item that reads or grants a status.** This affects at minimum: CavinXue, RyanLi (piano), FionaLi, MasonYu (strings), DanielYang's BRASS-check is unrelated but similarly a "check board-wide state" pattern; BUOStand, FoldingStand (items); PetterutiLounge (stadium); AVGETShirt, MaidOutfit, MusescoreSubscription (tools).
- Emma (supporter) is the one card whose "one-shot" classification is misleading — treat it like a character passive for migration purposes, not like the other 8 supporters.

## 6. Open questions (need a decision, not just an implementation)

Items 1-3 were decided this session (see the note at the top of this file and the
date-stamped entry in Section 7). Remaining items are ranked roughly by how much they
block, not by discovery order.

1. ~~Test infrastructure location + framework~~ — **DECIDED**:
   `unittest.IsolatedAsyncioTestCase` files, real `card_game_v2/testing/` package.
   **Location superseded later in the same session**: originally colocated with each
   production file, now all consolidated into `card_game_v2/testing/` as one flat
   folder, separate from "game elements" — see Section 1's superseded-decision note
   and Section 7's progress log for when/why this changed. Any new test file goes in
   `card_game_v2/testing/`, not next to the card/tool/listener it exercises.
2. ~~Bug-reproduction policy~~ — **DECIDED: fix bugs on sight.** Do not replicate a v1
   bug faithfully just because it's in the source; fix it as part of migrating that
   card, and log it in Section 8 (Bugs Fixed) with enough detail that the user can
   review the change later. This applies to the ~5 already-found candidates
   (`AnnaBrown`'s stray `ATK_2` response call, `DanielZhu`'s whole `atk_1` mistagged as
   `ATK_2`, `FelixChen`'s `[ATK_1, ATK_1]` duplicate excluding `ATK_2`,
   `MikuOtamatone`'s unused `FriedmanHall` import/dead gating slot,
   `LindemannPracticeRoom`'s vacuously-true empty-bench check) and to anything else
   found later. Use judgment on what counts as a "bug" vs. an intentional-but-unusual
   design (e.g. Jordan Roosevelt's atk_1 buffing the *opponent's* next attack reads
   oddly but may well be intentional flavor, not a bug — don't "fix" things that are
   just surprising).
3. ~~Shared-helpers module~~ — **DECIDED: no shared helpers.** Every near-duplicate
   mechanic (round-scoped self-buff ×3 guitars, halve-next-attack ×2 pianos, "did/
   didn't attack last/this turn" ×5, "roll until pair sums to 7" ×2 woodwinds, etc.)
   gets implemented independently and in full in every file that needs it, matching
   v1's own duplication. Do not factor these into a shared v2 module or base class.
4. ~~JaydenBrown's global-coinflip-interception passive~~ — **RESOLVED** by the new
   `IOListener` engine feature (see Section 2). Re-read v1's actual file: Jayden's
   reactor only intercepts *his own controller's* coinflips (not truly "global"), only
   the first one each round (checked via history search), and only while he's active.
   In v2 this becomes a card-scoped `AVGEIOListener` subclass: `match()` checks
   `isinstance(io_obj, CoinflipData)` + Jayden active + no prior matching `IOEvent` in
   the current chapter (via `env.search_history(IOEvent, ...)`, mirroring the new
   `io_id`-tagged history records); `modify()` awaits its own nested
   `env.report(StringSelectionQuery(...))` ("treat as heads?") and returns either the
   original response or a forced `1`. Confirmed this doesn't deadlock: by the time
   `modify()` runs, `Engine.report()`'s underlying `_dispatch` for that user has already
   popped its `pending` slot, so the nested report to the *same* user is safe. No
   further engine work needed here — this is now a normal (if novel) character port,
   still fine to leave last per the staging order since it's a good end-to-end test of
   the new feature.
5. ~~BenCherekIII's self-promotion passive~~ — **RESOLVED**. Confirmed `passive()`
   only ever fires once, on entering play (same `TransferCard`-post-transfer hook v2
   already uses for every other card's PASSIVE — no new hook needed). Also confirmed
   (checked `AVGEEnvironment.check_history` in v1: it searches
   `HistoryState.FORMALIZED` only, same as v2's `HistoricalStatus.IMMUTABLE` default)
   that the "skip if already transferred hand→bench this round" guard does **not**
   see the very transfer that's currently triggering this same `passive()` call (that
   transfer isn't solidified into history yet) — so on a normal single hand-play the
   guard passes through and the promotion offer fires as expected; it only suppresses
   a *second*, separate hand→bench entry for Ben later in the same round. v2 port:
   same guard, `env.search_history(TransferCard, {...}, specific_status=IMMUTABLE)`
   (the default), no special handling needed.
6. ~~MeyaGao's mutual-attack-lockout mechanic~~ — **de-risked**, no new primitive
   needed. Re-read v1: the "round-scoped" listeners (`_MeyaGuitarBoost`,
   `_MeyaAttackBlockAssessor`) use v1's `update_status()`/`invalidate()` tick, which v2
   doesn't have an equivalent callback for. Translate by folding the round check into
   `match()` itself (`if self.env.round != self.round_active: self.cleanup(); return
   False`) — the same self-expiring-listener idiom already used elsewhere in the
   migrated brass/choir cards. Still 3 interacting listeners worth care, but no design
   conversation blocker remains.
7. **DemiLu's coupling to Steinert stadiums' internal classes** (piano) — needs those
   stadiums migrated with an eye toward what DemiLu will need to import/reference by
   name; coordinate rather than doing DemiLu cold afterward.
8. **LukeXu's "nullify all of the opponent's ability-listener-attachments for a
   round"** (piano) — v1 uses `AVGEConstraint`; v2 already has the matching primitive
   (`AVGEConstrainer`/`Constrainer.match(listener)`), just never exercised by any
   migrated card yet. Should work, but worth a small standalone smoke test of the
   Constrainer path before leaning on it for this card, same reasoning as the
   engine-ordering smoke tests already done.
9. **PetterutiLounge's packet-level listener** (stadium) — the one card needing
   `AVGEPacketReactor`/`add_packet_listener` instead of the usual event-level listener.
   v2 has this API but it's never been exercised. Smoke-test it standalone first.
10. **SYSTEM_ARCHITECTURE.md is confirmed stale** for at least FelixChen and WestonPoe
    (older/simplified API shape, and one factual error in Felix's description). Not a
    migration blocker, just don't use it as a source for those two cards or trust it
    uncritically for anything else — the real `.py` files are the only ground truth.
11. ~~Two v1 cards use raw, unseeded `random.randint`/`random.choice`~~ — **DECIDED:
    plain `random` is fine.** No determinism/replay requirement for this kind of
    decision; keep porting it as-is.
12. ~~`Phase2`/`AtkPhase` bypassing `Engine.report()`~~ — **DECIDED + FIXED**: brought
    both in line so all IO goes through one consistent chokepoint. `Phase2.act()` and
    `AtkPhase.act()` now call `self.env.report(io_obj, self.id)` instead of
    `self.env.io_manager.report(io_obj)` directly (`EventCatalog.py`).
13. ~~Pylance/pyright type-checking rigor~~ — **DECIDED: strict mode, always-clean.**
    Every non-test file in `card_game_v2` must have zero Pylance/pyright diagnostics
    before moving on, checked via `python3 -m pyright` (strict mode is on repo-wide
    for `card_game_v2` via `pyrightconfig.json` + `.vscode/settings.json`, scoped to
    exclude `card_game_v2/testing/` — test files are not held to this). See Section 2's
    "Pylance / pyright strict mode" subsection for the config details and the
    recurring patterns (typed `__init__` params, `list[Event | Generator]` return
    types, `reportUnnecessaryIsInstance`, `reportPrivateUsage`) to watch for when
    writing new files.

## 7. Progress log

Append one line every time this file is opened — when a session starts, when resuming
after 3 cards, and whenever a card/task finishes. Newest at the bottom.

- 2026-09-06 — Full survey of all 114 remaining files complete (8 parallel research
  passes: guitars, percussion, pianos, strings, woodwinds, items, stadiums,
  status_effects+tools+supporters). This file's Sections 4-6 written up from that
  survey. User decided: formalize tests into the repo
  (`unittest.IsolatedAsyncioTestCase`, colocated with production files), fix bugs on
  sight (log them below), do not build shared helpers for duplicated mechanics. About
  to: set up `card_game_v2/testing/helpers.py` and migrate the 9 existing
  characters' scratchpad tests into colocated, real test files.
- 2026-09-06 — Formalized tests: `card_game_v2/testing/helpers.py` built, all 9
  existing characters (brass ×5, choir ×4) migrated to colocated
  `unittest.IsolatedAsyncioTestCase` files, 52 tests green. User independently built a
  new `IOListener` engine feature to unblock JaydenBrown (open question 4). Reviewed it
  across two rounds, found and the user fixed 6 of 7 issues; fixed the 7th (circular
  import) directly since it was purely mechanical, which surfaced a second circular
  import (base-class eager evaluation) — also fixed. User then made a further change to
  how `IOEvent`s get logged into history, which changed `Engine.report()`'s signature
  to require an `io_id`; found and fixed the resulting missing-argument break across 7
  call sites in already-migrated brass/choir cards (52 tests re-verified green). Used
  the pause to re-read the actual v1 source for open questions 4-6 and resolved all
  three without needing new engine primitives (see Section 6) — flagged one new
  question (12, `Phase2`/`AtkPhase` bypassing `Engine.report()`) and refined question 5
  into a concrete judgment call for the user. Character migration proper (guitars etc.)
  has not resumed yet — this whole entry was IOListener-review/engine-stabilization
  work.
- 2026-09-06 (same session, continued) — Closed out all remaining Section 6 open
  questions except 7-10 (coordination/smoke-test notes, not decisions): user decided
  `Phase2`/`AtkPhase` should route through `Engine.report()` like everything else
  (fixed in `EventCatalog.py`), decided plain `random` is fine for v1's two
  non-deterministic RNG cards, and asked for a deeper look at BenCherekIII - confirmed
  via v1 `AVGEEnvironment.check_history`'s `HistoryState.FORMALIZED`-only search that
  his guard behaves as a normal "once per round" safeguard, not a permanent
  self-block. All 52 brass+choir tests still green after the `Phase2`/`AtkPhase`
  change. Section 6 now only has non-blocking notes left (7, 8, 9, 10) - next session
  can resume actual character migration per Section 4's staging order (status effects
  -> tools -> items -> RachelChen -> stadiums -> remaining character elements ->
  supporters) without further design detours.
- 2026-09-06 (same session, continued) - Migrated status effects (GOON, MAID,
  ARRANGER), the first item in Section 4's staging order. Confirmed (per the plan's
  own note) this is engine-layer infrastructure, not catalog files:
  `card_game_v2/core/StatusEffectListeners.py` (new file) holds GOON's retreat-cost
  regulator+reactor and status-change HP reactor, plus ARRANGER's shuffle-offer
  reactor; `AVGEMaidDamageShieldModifier` added directly to `CoreListeners.py`. Found
  and fixed 2 more latent engine bugs along the way (`engine.listeners` set-vs-list,
  `ReorderDeck` rollback never saving `_old_order` - see Section 2) and confirmed via
  v1 source exactly how MAID's registration order relative to `AVGEWeaknessModifier`
  needs to work. Also resolved the "how do we shuffle a card into deck at a random
  position" question that blocks ~10 future cards, using two existing primitives
  (`TransferCard` + `ReorderDeck` with a lazily-resolved lambda) rather than adding a
  new event type. 15 new tests in `card_game_v2/core/test_status_effects.py`; full
  suite is now 79 tests, all green, re-run 5x to rule out the RNG-order flakiness one
  test initially had (fixed - see the test file, `test_triggers_on_attached_tool_discard`).
  Next: tools (6 files) per the staging order - 3 are trivial now that status effects
  exist (grant/revoke on equip/unequip).
- 2026-09-06 (same session, continued) - Migrated all 6 tools (AVGETShirt, MaidOutfit,
  MusescoreSubscription, Bucket, KikisHeadband, AVGEShowcaseSticker) into
  `card_game_v2/catalog/tools/`. The 3 status-granting ones were straightforward once
  GOON/MAID/ARRANGER existed. KikisHeadband's "-1 retreat cost" needed a real design
  (see Section 2) since v2's fixed-attribute retreat-cost model doesn't support a
  naive refund-after-the-fact the way it does GOON's "+1". AVGEShowcaseSticker
  surfaced a genuine `PhasePickCard`/reactor-deck race (also logged in Section 2) -
  worth remembering for any future card reacting to `PhasePickCard` that also touches
  the deck. 11 new tests in `card_game_v2/catalog/tools/test_tools.py`; full suite now
  90 tests, all green (re-run 3x). Tools are done - next per Section 4's staging order
  is items (21 files), starting with `ConcertProgram`/`ConcertRoster`/`ConcertTicket`
  and `AVGEBirb` since characters depend on them specifically.
- 2026-09-06 (same session, continued) - User asked for two changes before pausing
  (items migration deferred until they say to continue): (1) reorganized status
  effects out of the flat `card_game_v2/core/StatusEffectListeners.py` into their own
  `card_game_v2/core/status_effects/` package - `Goon.py`, `Maid.py`, `Arranger.py`,
  `__init__.py` re-exporting all three, plus the colocated test file moved in too
  (`core/status_effects/test_status_effects.py`). `AVGEMaidDamageShieldModifier` came
  out of `CoreListeners.py` entirely - it now lives in `Maid.py` alongside GOON/
  ARRANGER instead of mixed into the generic core-engine-rule file. `testing/
  helpers.py`'s imports updated to match; full 90-test suite re-verified green after
  the move. (2) User asked to always confirm Pylance/the IDE's diagnostics check out
  clean - added as a standing process rule below (see "Process").
- 2026-09-06 (same session, continued) - Two more user requests: (1) moved status
  effects again, this time from `core/status_effects/` to `catalog/status_effects/`
  (still its own package, GOON/MAID/ARRANGER not folded into `CoreListeners.py` -
  that part of the prior decision stands, only the parent directory changed). (2) User
  asked for full Pylance **strict** mode across card_game_v2, with all test files
  consolidated into one folder apart from "game elements." Did both together: `pip
  install pyright` (CLI-verifiable strict checking - no local pyright before this),
  added `pyrightconfig.json` (strict, scoped to `card_game_v2`, excluding
  `card_game_v2/testing/`) and mirrored it in `.vscode/settings.json`; moved all 9
  characters' test files plus `test_status_effects.py` and `test_tools.py` out of
  their colocated homes into `card_game_v2/testing/` (alongside `helpers.py`), fixing
  every file's relative imports for the new depth - see Section 1's superseded-decision
  note. Ran strict pyright against everything outside `testing/`: 905 errors before
  the testing-folder exclude (almost entirely pre-existing test-file noise + 25 in
  today's tool/status-effect files), 0 after excluding tests and fixing the 25 real
  ones (missing `__init__` param types, unnecessary `isinstance` checks, a
  `reportPrivateUsage` on `AVGECardStatusChange._made_modification` - fixed by adding
  a public `made_modification` property - and a couple of unused imports). Full
  90-test suite re-verified green after the whole move. See Section 2's new "Pylance /
  pyright strict mode" subsection for the patterns to watch for in every future file.

- 2026-09-06 (same session, continued) - Resumed the actual staged migration: items
  (21 files), starting with ConcertProgram/ConcertRoster/ConcertTicket per Section 4's
  staging order (they unblock RachelChen and SarahChen). All 3 done -
  `card_game_v2/catalog/items/`. Found and fixed a real gap in `Phase2.act()`'s
  item/supporter dispatch (never discarded the played card - v1 does this at the
  dispatcher level, not inside the card's own `play_card()`) and a lazy-resolution
  bug in ConcertTicket's own multi-draw loop (same shape as the earlier
  `PhasePickCard` reactor race) - both logged in Section 2. Added a `play_item()` test
  helper to `testing/helpers.py` mirroring the real (now-fixed) dispatch. 8 new tests
  in `testing/test_items.py`; full suite now 98 tests, all green (re-run 3x); strict
  pyright still 0 errors outside `testing/`. Next: continue through the remaining 18
  items - AVGEBirb next (unblocks 2 strings characters + RaffleTicket), per Section
  4/5's notes.

- 2026-09-06 (same session, continued) - Migrated `AVGEBirb` (`card_game_v2/catalog/items/AVGEBirb.py`):
  strips every tool and status effect off all of the opponent's characters in play
  (active + bench), then curses the *owner's own* active with +20 damage on the next
  ATK hit it takes. Found and fixed a real v1 bug in the process: the self-damage curse
  was gated by a round-number check (`round_id == player.get_next_turn()`) that could
  never actually be satisfied by a real incoming hit, so it was dead code in v1 - see
  Section 2 for the full reasoning. First pass replaced the round check entirely with a
  "match the next qualifying hit whenever it lands" modifier; revised before finishing
  this batch to instead keep v1's original "scoped to one specific upcoming turn, then
  expires" shape (v2 *does* track rounds via `env.round`, same idiom already resolved
  for MeyaGao in Open Question 6) but with the round number fixed:
  `round_active = env.round + 1` (the opponent's next turn) instead of the owner's own
  next turn. More faithful to the original design intent and added a
  `test_curse_expires_if_the_turn_passes_without_a_hit` test to lock in the expiry
  behavior. Also confirmed and documented that v2's
  `AVGECardStatusChange` has no v1-style "clear every giver at once" REMOVE mode - had
  to snapshot-and-loop per giver instead (see Section 2). 8 tests in
  `testing/test_items.py` (tool stripping from both active+bench, multi-giver status
  stripping, own-side is untouched, curse doesn't apply before the opponent's turn
  arrives, curse fires once during that turn, curse expires if the turn passes without
  a hit, curse only applies to the owner's own active, curse ignores non-attack
  damage). Strict pyright 0 errors outside `testing/`.

- 2026-09-06 (same session, continued) - Migrated `AnnotatedScore` and `Camera`
  (`card_game_v2/catalog/items/`), both straightforward and unblocked. AnnotatedScore:
  re-read v1 closely and found the plan's own one-line summary was imprecise - both
  picks (a revealed opponent hand card to discard, then a different opponent discard
  card to return to hand) are made by the *owner*, but both resulting cards land back
  in the *opponent's* piles; nothing comes to the owner's own hand. Corrected the
  Section 5 summary to match the actual code. Camera: reused the `TransferCard` +
  `ReorderDeck`(random-insert-lambda) combo already established for ARRANGER (Section
  2) to shuffle a chosen discard Supporter/Stadium into the deck at a random position.
  Added a `DummySupporter` to `testing/helpers.py` (alongside the existing
  `DummyStadium`) since no real supporter exists yet to test eligibility filtering
  against - ordinary shared test infrastructure, not a mechanics helper. 6 new tests
  across the two cards. Full suite now 113 tests, all green; strict pyright still 0
  errors outside `testing/`. Next: continue through the remaining 15 items per Section
  5's table (no more name-blocking dependencies among the easy ones; RaffleTicket is
  now unblocked too since it needs AVGEBirb, which is done).

- 2026-09-07 - Migrated `CorruptedMusescoreFile`, `StandardMusescoreFile`, and
  `IceSkates` (`card_game_v2/catalog/items/`). The Musescore File pair are near-twins
  ("optionally discard a tool from one of your characters, then optionally search deck
  for a[n] {item / non-item} card") - implemented each fully independently per policy,
  not factored into a shared helper. Both preserve v1's "declining the tool discard (or
  having nothing to discard) ends the whole card, no search offered" structure.
  StandardMusescoreFile's second pick additionally skips its own prompt when the deck
  has zero non-item cards to offer - v1 always prompted even then (a pointless
  empty-choice prompt, same class of issue as ConcertRoster/Camera already fixed).
  IceSkates: a straightforward two-`TransferCard` active/bench swap, tagged `NONCHAR`
  like v1 so it bypasses the normal swap-cost/retreat-cost regulators (which only gate
  `PLAYER_CHOICE`-tagged transfers) - confirmed no assertion anywhere requires
  `ACTIVE_CARD` to hold at most one card transiently mid-packet, so ordering
  bench→active then active→bench (same order as v1) is safe. Extended `TestIO` in
  `testing/helpers.py` with a `card_answer_sequence` list (mirrors the existing
  `string_answers` list) so a test can drive two sequential `CardSelectionQuery` calls
  within one card differently - including declining just one of them - which the old
  single `card_answer_index`/`select_none` flags couldn't do. 10 new tests. Full suite
  now 123 tests, all green; strict pyright still 0 errors outside `testing/`. Next:
  continue through the remaining 12 items per Section 5's table.

- 2026-09-07 (continued) - Migrated `PrintedScore`, `VideoCamera`, and `Otamatone`
  (`card_game_v2/catalog/items/`). PrintedScore: re-read v1 and found the plan's
  original summary had the picker backwards ("owner's choice") - v1's `InputEvent`
  recipient is the *opponent*, so the opponent chooses which of their own revealed hand
  cards to discard; corrected the Section 5 summary. First use of v2's existing
  `RevealCards` IO type (broadcast to all players) in this migration - it was already
  defined but unused until now. VideoCamera: same `TransferCard` + `ReorderDeck` combo
  as Camera/ARRANGER, with a fixed "insert at index 0" lambda instead of a random one.
  Otamatone: modifies `PlayCharacterCard.cost` directly - confirmed it's a real,
  already-mutable field that the existing `AVGEPlayCharacterCardValidityCheck`
  affordability regulator reads, so no new engine primitive was needed. Same
  `env.round`-based self-expiring-listener idiom as AVGEBirb's curse, but *without* a
  fire-once self-invalidate - re-read v1 closely and confirmed Otamatone's modifier has
  no `on_packet_completion` override (unlike AVGEBirb's), so it stays live for every
  qualifying attack for the rest of the turn, not just the first one; replicated that
  distinction faithfully rather than assuming the two cards work the same way. Added an
  `Attacker` test double to `testing/helpers.py` (a `Dummy` with one real no-op `ATK_1`
  attack) so energy-cost-modifier tests have something to drive a genuine
  `PlayCharacterCard` against - will be reused for FoldingStand/BUOStand later. 10 new
  tests. Full suite now 133 tests, all green; strict pyright still 0 errors outside
  `testing/`. Next: continue through the remaining 9 items - FoldingStand and BUOStand
  are next up (GOON exists, and now so does the `Attacker` test double they'll need);
  RaffleTicket, DressRehearsalRoster, and CastReserve remain after that; MikuOtamatone,
  MatchaLatte, and StrawberryMatchaLatte stay blocked on stadiums.

- 2026-09-07 (continued) - Migrated `FoldingStand` and `BUOStand`
  (`card_game_v2/catalog/items/`), both GOON-scaling own-attack damage buffs. Both use
  the same round-scoped, fire-once self-expiring `AVGEEventModifier` idiom as
  AVGEBirb's curse (`round_played = env.round` at play time, `match()` self-`cleanup()`s
  once `env.round` passes it, `modify()` also self-`cleanup()`s after firing once) -
  implemented fully independently per policy, not factored into a shared base. One
  faithfully-preserved difference between the two: FoldingStand excludes
  `CardType.ALL` (true damage) from its buff, but BUOStand's v1 source has no such
  exclusion - re-read v1 to confirm this wasn't a copy-paste omission worth "fixing" on
  sight, just an intentional difference between the two cards, so BUOStand also buffs
  true damage. BUOStand additionally discards 1 energy from the owner's active as a
  cost (via the existing `AVGEEnergyTransfer` event, `active -> env`) and no-ops with a
  broadcast if the active has none. 10 new tests (5 each, covering the base buff, the
  GOON-scaled buff, fire-once expiry, turn-passes expiry, and their card-specific
  extra: FoldingStand's true-damage exclusion / opponent's-attack exclusion, BUOStand's
  no-energy guard). Full suite now 144 tests, all green; strict pyright still 0 errors
  outside `testing/`. Next: continue through the remaining 7 items - RaffleTicket,
  DressRehearsalRoster, and CastReserve are unblocked; MikuOtamatone, MatchaLatte, and
  StrawberryMatchaLatte stay blocked on stadiums (not yet migrated).

- 2026-09-07 (continued) - Migrated `RaffleTicket`, `DressRehearsalRoster`, and
  `CastReserve` (`card_game_v2/catalog/items/`), clearing every unblocked item except
  BAIEmail. RaffleTicket: straightforward once `AVGEBirb` existed, reads
  `deck.cards_holding[-1]` directly for the bottom card. The other two both hit the
  same structural gap: v1's `InputEvent` supports a custom validity-callback that
  re-prompts on an invalid combination of picks (distinct-or-same-character-with-
  enough-energy for DressRehearsalRoster; distinct item *types* for CastReserve); v2's
  `CardSelectionQuery` has no retry loop at all - whatever the IO manager returns is
  final. Rather than trying to bolt a re-prompt loop onto the engine for two cards,
  adapted each to v2's simpler model: DressRehearsalRoster just trusts its 2 picks and
  leans on `AVGEEnergyTransfer`'s existing built-in no-op-if-empty behavior (an
  under-resourced pick discards less than 2 total energy rather than being rejected);
  CastReserve pre-filters the offered item list down to one representative per
  distinct type, so *any* 3 picks from it are automatically valid by construction, with
  no possibility of an invalid submission - a cleaner solution than v1's retry-until-
  valid, not just a workaround. Both documented as disclosed adaptations in Section 5,
  not silent behavior changes. Extended `testing/helpers.py`'s `TestIO` further:
  `card_answer_sequence` entries can now be a `list[int]` (one index per selection
  slot) in addition to the existing `None`/single-`int` forms, needed to drive
  CastReserve's two-different-multi-select-queries-in-one-card test. 10 new tests
  (3 RaffleTicket, 4 DressRehearsalRoster, 3 CastReserve) - two of the
  DressRehearsalRoster reshuffle tests initially failed because they forgot the played
  item itself also ends up in discard via `play_item`'s own dispatch, same as every
  other item; fixed the assertions, not the production code. Full suite now 154 tests,
  all green (re-run 5x for the two cards using `random`); strict pyright still 0
  errors outside `testing/`. Next: BAIEmail is the only remaining unblocked item -
  needs a new "block this NONCHAR category for a scoped duration" regulator, similar
  in shape to `AVGEPlayNonCharacterCardValidityCheck`'s existing supporter-use-limit
  check. After that, items pauses on the 3 stadium-blocked cards until stadiums are
  migrated - a good point to switch to stadiums next, or to RachelChen/SarahChen
  (choir/woodwind) which are now fully unblocked since all their item dependencies are
  done.

- 2026-09-07 (continued) - Migrated `BAIEmail` (`card_game_v2/catalog/items/BAIEmail.py`),
  clearing every item except the 3 stadium-blocked ones. User asked, correctly, whether
  the stadium-play lock could gate the `TransferCard` that precedes a stadium being
  played rather than `PlayNonCharacterCard` (v1's own gate point) - traced
  `Phase2.act()` and confirmed: stadiums (and tools) have no `PlayNonCharacterCard`
  dispatch branch in `Phase2` at all (only items/supporters do), they're played via the
  generic `Phase2CardMovement` case's plain `TransferCard`, and grepped the whole
  codebase to confirm that transfer's own "Special Case 3" is the *only* place
  `PlayNonCharacterCard` is ever constructed with a stadium/tool target. So the
  suggested gate point isn't just valid, it's the sole one that exists, and cleaner
  than v1's (stops the card leaving hand at all) - documented as a new architectural
  note in Section 2 for future tool-attach-blocking cards too. Re-derived
  `round_until = env.round + 2` (owner's own next turn) and confirmed this ISN'T the
  same bug pattern as AVGEBirb's curse - the lock is global (either player is blocked),
  so there's no per-player condition making it unsatisfiable, unlike AVGEBirb's
  self-referential one. 6 new tests (discard old stadium, optional deck search +
  decline, blocks both players' stadium plays, lock stays active through the owner's
  own next turn, lock expires after). Full suite now 160 tests, all green; strict
  pyright still 0 errors outside `testing/`. Items are now fully done except
  MikuOtamatone/MatchaLatte/StrawberryMatchaLatte (stadiums). Next: switch to stadiums
  (10 files) to unblock those 3, or pivot to RachelChen/SarahChen (choir/woodwind),
  now fully unblocked since every item they depend on is done.

- 2026-09-07 (continued) - User asked to begin work on characters. Per Section 4 step
  4, migrated `RachelChen` (choir) - `card_game_v2/catalog/characters/choir/RachelChen.py`,
  the last remaining choir character (5/5 now). Her "once per turn" ability gate
  (`can_play()`) doesn't replicate v1's `check_history`-based search; instead uses a
  plain instance field (`_active_last_used_round`, set in `__call__`, compared against
  `env.round` in `can_play()`) - the same round-scoped idiom already used for
  self-expiring listeners (AVGEBirb, FoldingStand/BUOStand, BAIEmail), just applied
  directly to an `Ability` instead of a temporary `AVGEEventListener`. Her active
  ability ("Program Production": retrieve a Concert Program/Roster/Ticket from discard
  to the top of deck) reuses the `TransferCard` + `ReorderDeck`("move to index 0")
  combo already established for VideoCamera - implemented independently, per policy.
  SATB (atk_1) deals 20 damage to `choir_count` chosen opposing targets (repeats
  allowed), where `choir_count` = the owner's own in-play CHOIR-type character count;
  noted but did not "fix" that v1's `choir_count <= 0` no-op guard is effectively dead
  code for this specific card (RachelChen herself is always CHOIR-typed and must be
  active to attack at all, so the count is always >= 1 in practice) - kept the guard
  for fidelity since it's not incorrect, just unreachable, matching the "don't fix
  what's just surprising" policy. 7 new tests in `testing/test_rachelchen.py`
  (`can_play()` gating ×4, the ability's actual effect, decline-still-marks-used, and
  the attack's repeat-target damage) - one test initially flaked because
  `AVGEEnvironment.__init__` picks a random starting `env.turn`, same as an existing
  precedent in `test_happyruthjara.py`; fixed by explicitly setting `env.turn =
  User.PLAYER_1` in `asyncSetUp`, re-run 8x clean after. Full suite now 167 tests, all
  green; strict pyright still 0 errors outside `testing/`. Next: SarahChen (woodwind)
  is the other item-unblocked character; after that, stadiums (10 files) to unblock
  the last 3 items, or continue further into choir's sibling elements per Section 4's
  staging order.

- 2026-09-07 (continued) - User asked to move faster on characters (larger batches,
  10+ per pass). Migrated 7 of 8 guitars in one push: OwenLandry, ChristmasKim,
  AntongChen, RobertoGonzales, BenCherekIII, GraceZhao, EdwardWibowo -
  `card_game_v2/catalog/characters/guitar/` (only `MeyaGao`, the hardest, deliberately
  left for last per Section 4's staging order). Notable finds along the way (both
  logged as their own Section 2 entries): (1) Roberto's and Edward's "+40 GUITAR
  damage on your own next turn" Distortion buffs are byte-identical in v1 -
  implemented fully independently in each file per the no-shared-helpers policy, both
  using the round-scoped-modifier idiom first established for AVGEBirb's curse, but
  *without* AVGEBirb's fire-once self-invalidate (neither v1 source has an
  `on_packet_completion` override, so both stay live for every qualifying attack all
  turn). (2) GraceZhao's `TurnEnd`-reactive Royalties passive is the first
  `EXTERNAL_REACTORS` listener keyed off a state change the event's own `act()` makes -
  discovered that v2's engine runs `CORE` (an event's `act()`) *before*
  `EXTERNAL_REACTORS` in its group-processing loop, so `env.turn` has already flipped
  to the opponent by the time the reactor's `match()` runs; translated v1's literal
  (pre-flip-assuming) condition to its intended effect instead of copying it as-is -
  new standing note in Section 2 for every future `TurnEnd`-reactive card. Also reused
  two already-established idioms rather than re-deriving them: BenCherekIII's
  self-promotion guard reuses HappyRuthJara's "did I just enter bench from hand"
  history search (Open Question 5's prior resolution), and AntongChen's
  "blocked the turn after my own atk_2" gate uses a plain instance field instead of a
  history search, matching RachelChen's precedent. 25 new tests across 7 new test
  files. Full suite now 192 tests, all green; strict pyright still 0 errors outside
  `testing/`. Next: `MeyaGao` to finish guitars (8/8), then likely percussion's easy
  tier (KevinYang/LoangChiang/HanleiGao/RyanLee) to keep momentum on the "10+ per
  batch" pace, or SarahChen (woodwind, item-unblocked) if the user wants that instead.

- 2026-09-07 (continued) - User asked to keep methodically going through until all
  cards are done. Finished guitars with `MeyaGao` (8/8, DONE) - her 3-listener mutual
  attack-lockout retaliation, detailed in Section 5's table row. Then did all of
  percussion in one continuous push (11/11, DONE): KevinYang/LoangChiang/HanleiGao/
  RyanLee (easy tier) → CavinXue/DanielYang (status-effect/board-scan modifiers) →
  PascalKim/EugeniaAmpofo/KeiWatanabe/BokaiBi/SasMajumder (the hard tier). Two new
  engine/testing gotchas surfaced and are now logged in Section 2 for future
  reference: a `pkt.flush()`-vs-`env.engine.flush()` history-solidification trap
  (only the latter calls `history.solidify_records()`, so `search_history` silently
  finds nothing after a bare packet flush), and `AVGETokenTransferCheck`'s
  `ENERGY_ADD_REMAINING_IN_TURN` gate on `PLAYER_CHOICE`-tagged energy attaches (a
  fresh test player defaults to `0` = "already used", so simulating a normal attach
  needs a temporary bump). Found and fixed one real bug: BokaiBi's Algorithm passive
  double-fired on tool/stadium plays (`TransferCard`'s own "Special Case 3" produces a
  follow-on `PlayNonCharacterCard` for the same play, and Algorithm originally matched
  both) - fixed by excluding tools/stadiums from the `PlayNonCharacterCard` branch.
  27 new tests across the percussion batch (on top of MeyaGao's own 6). Full suite now
  233 tests, all green (re-run 5x); strict pyright still 0 errors outside `testing/`.
  Two full character elements are now completely done (guitar, percussion). Next:
  pianos (12 files) is the next element in Section 4's staging order, or SarahChen
  (woodwind, item-unblocked) remains available as an alternative branch.

- 2026-09-07 (continued) - Started pianos, the next element per Section 4's staging
  order. Migrated 6 of 12: CathyRong, CocoZeng, HenryWang, JoshuaKou, RyanLi, DavidMan
  (leaving DemiLu and JennieWang for after stadiums/everything-else per their known
  cross-file dependencies, and MatthewWang/LukeXu/SophiaSWang/KatieXiang for a
  follow-up batch). Found and corrected a backwards survey note (JoshuaKou's Separate
  Hands is a "needs momentum from last turn" combo, not an inverse-cooldown as
  originally written) by re-reading v1's actual code rather than trusting the old
  gloss - same class of correction as PrintedScore/AnnotatedScore earlier. The
  significant find this batch: JoshuaKou's `PhasePickCard`-reactive Category Theory
  passive **crashed on first run**, and tracing it down turned up a real,
  previously-undiscovered bug in the engine's own `PhasePickCard.act()` - it eagerly
  captured `deck[0]` into its once-per-turn draw event, so a reactor to that same
  event drawing from the same deck (via the *correct* lazy pattern) could invalidate
  that stale reference first, crashing the engine's own draw. Fixed in
  `core/EventCatalog.py` with the same lazy-generator pattern already established
  elsewhere - logged as a new "Engine bugs found and fixed" entry in Section 2, and
  the reproduction-then-fix is preserved in `testing/test_joshuakou.py`'s test history
  (the crash, the fix, then corrected assertions once the underlying draw ordering
  was made visible). 22 new tests. Full suite now 255 tests, all green (re-run 4x);
  strict pyright still 0 errors outside `testing/`. Next: MatthewWang, LukeXu,
  SophiaSWang, and KatieXiang to continue pianos (LukeXu needs a new
  `AVGEConstrainer`-based design, flagged hardest in this element).

- 2026-09-07 (continued) - Finished the piano batch: MatthewWang, SophiaSWang,
  KatieXiang, and LukeXu (10/12 pianos done - only DemiLu and JennieWang remain,
  both correctly deferred for their cross-file dependencies). LukeXu was the hardest
  piano file as flagged, and the first card anywhere in this migration to use
  `AVGEConstrainer` - building it turned up a **second** real, previously-undiscovered
  engine bug: `AVGEConstrainer.__init__` never called `super().__init__(id)`, leaving
  every instance silently missing `requires_cleanup`, crashing with `AttributeError`
  the moment the engine's own cleanup pass touched *any* constrainer for the first
  time (reproduced via LukeXu's own test setup, which crashed in `put_into_play`
  before the one-line fix). KatieXiang reuses PascalKim's delayed-cross-turn-damage
  idiom but needed its own round-math derivation (`env.round + 3`, one turn-boundary
  later than PascalKim's `+2`) since it targets the *owner's own* next turn ending,
  not the opponent's - verified end-to-end with real chained `TurnEnd` events.
  LukeXu/SophiaSWang's shared halve-next-attack modifier turned out to apply to the
  opponent's next attack *at all* (no target-card check), not "against this
  character" as a looser reading might suggest - confirmed against v1's source before
  porting. 19 new tests. Full suite now 274 tests, all green (re-run 3x); strict
  pyright still 0 errors outside `testing/`. Two full character elements now done
  (guitar, percussion), plus piano at 10/12 (blocked only by deliberately-deferred
  cross-file cards). Next: strings (16 files) is the next element per Section 4's
  staging order, or SarahChen (woodwind, item-unblocked) remains available.

- 2026-09-07 (continued) - Started strings: AshleyToby, EmilyWang, InaMa, AliceWang,
  MaggieLi, JessicaJung (6/16 strings done). No new bugs found this batch. AliceWang's
  passive needed the same post-act-reactor-timing fix as GraceZhao/PascalKim/KatieXiang
  (checks `env.turn == opponent`, not owner, since `TurnEnd.act()` flips `env.turn`
  before reactors run) plus a new shape: the opponent (not the owner) makes the
  discard-down-to-match picks, via a cross-player `CardSelectionQuery`. MaggieLi's
  `PhasePickCard`-reactive heal-offer reuses MatthewWang's (piano) shape exactly,
  independently implemented. 20 new tests. Full suite now 294 tests, all green
  (re-run 3x); strict pyright still 0 errors outside `testing/`. Next: continuing
  strings per user's explicit "keep going until all cards are done" instruction -
  AndreaCR, FionaLi, GabrielChen, IrisYang, JuliaCeccarelli, SophiaYWang, YuelinHu
  next (MasonYu last, flagged hardest; MichaelTu/MichelleKim deferred for stadiums).

- 2026-09-07 (continued) - Second strings batch: AndreaCR, FionaLi, GabrielChen,
  IrisYang, JuliaCeccarelli (11/16 strings done). JuliaCeccarelli's Ricochet was the
  first card anywhere in this migration to actually drive a character to exactly 0 HP
  through the real engine KO path, which surfaced a genuine, previously-undiscovered
  engine bug: `AVGEHPChangeReactor`'s knockout discard-and-replace flow
  (`core/CoreListeners.py`) had `TransferCard` arguments backwards in two separate
  places (the discard transfer's `deck_from`/`deck_to` were swapped, and the
  bench-replacement transfer moved the wrong card) - both fixed; see Section 2 for the
  full writeup, including a new timing gotcha for any future KO-reacting listener
  (`event.target_card.hp` is back to `max_hp` by the time an `EXTERNAL_REACTORS`
  listener sees the event - use the CORE-time `event.final_change` snapshot instead).
  GabrielChen's passive threshold turned out to be an absolute `hp < 60` in v1, not
  60% of max HP as the survey gloss said. FionaLi's MAID-granting passive needed the
  same "do the initial grant directly in the ability call, since the reactor is
  registered too late to see the transfer that triggered it" pattern established for
  BenCherekIII/GraceZhao-style entry effects. 26 new tests. Full suite now 320 tests,
  all green (re-run after the engine fix); strict pyright still 0 errors outside
  `testing/`. Next: SophiaYWang and YuelinHu (both need `AVGEBirb`, already done),
  then MasonYu last (flagged hardest); MichaelTu/MichelleKim remain deferred for
  stadiums.

- 2026-09-07 (continued) - Finished strings: SophiaYWang, YuelinHu, MasonYu (14/16 -
  only MichaelTu/MichelleKim remain, deferred for stadiums). No new engine bugs, but a
  real translation bug caught by MasonYu's own tests: v2's `PlayCharacterCard` gates
  directly on its literal `cost` param against the *target* character's own energy,
  but v1's equivalent call for "We Play God" passes no `energy_requirement` (defaults
  to 0) specifically to bypass that gate - Mason's own energy discard is the whole
  cost, and the borrowed character needn't have any energy of its own. Porting the
  borrowed attack's real cost silently `REGULATE_FAIL`ed and rolled back the entire
  packet with no exception, which took some tracing (added temporary instrumentation
  around `env.report`/`env.push_packet` to see the packet was built correctly but
  never took effect) before finding the root cause in `AVGEPlayCharacterCardValidityCheck`;
  fixed by passing `cost=0` explicitly. SophiaYWang's Gacha Gaming loop translates much
  more simply in v2 than v1's cache-based continuation-passing shape - a plain Python
  `while` loop suffices since `Attack.__call__` is already an async coroutine that can
  just `await` each Yes/No query in sequence. 18 new tests. Full suite now 338 tests,
  all green (re-run after the MasonYu fix); strict pyright still 0 errors outside
  `testing/`. Strings is now effectively done - only MichaelTu/MichelleKim remain,
  both deferred until stadiums exist. Next per the user's "get through all remaining
  work" instruction: woodwinds (18 files) is the next unblocked element per Section
  4's staging order.

- 2026-09-07 (continued) - Started woodwinds: AnaliseJia, AnnaBrown, BettySolomon,
  DanielZhu, DesmondRoper, EvelynWu, FelixChen, HarperAitken (8/18). Fixed two more
  obvious v1 typo-bugs on sight (DanielZhu's whole atk_1 internally mistagged ATK_2;
  FelixChen's passive checking `[ATK_1, ATK_1]` instead of `[ATK_1, ATK_2]`). Found and
  documented a real v1→v2 semantic gap (not a bug in either codebase, just a porting
  trap) while testing DesmondRoper's streak counter: v2's normal attack dispatch tags
  `id.calling_card` as `None`, unlike v1's `caller` which is always the attacker itself
  - a literal port of v1's `caller: card` history-match silently zeroes the streak;
  fixed by matching on `target_card` instead (see Section 2, flagged for any future
  card doing similar history-based self-matching). 33 new tests. Full suite now 371
  tests, all green; strict pyright still 0 errors outside `testing/`. Next: IzzyChen,
  JordanRoosevelt, KanaTakizawa, KathySun, LucaChen, MeiyiSong, RachaelYuan, SarahChen,
  WestonPoe (all unblocked), then JaydenBrown last (needs the already-designed
  `IOListener` engine hook from Open Question 4).

- 2026-09-07 (continued) - Continued woodwinds: IzzyChen, JordanRoosevelt,
  KanaTakizawa, KathySun (12/18). No new engine bugs, but found and fixed a real
  test-harness hang trap while testing JordanRoosevelt's round-scoped Trickster buffs:
  chaining several bare-`flush()` `TurnEnd`s (the established PascalKim/KatieXiang
  exact-round-math idiom) followed by a later *real* `env.engine.flush(...)` call
  (e.g. from `run_attack`) can drain all their un-run follow-up packets at once and
  cascade into a hanging draw/attack-phase loop - reproduced in a minimal script,
  fixed by resetting the engine's push/append buffer after each bare `TurnEnd` (see
  Section 2 for the full writeup - this is a durable lesson for any future test that
  chains bare-flushed `TurnEnd`s and later needs a real action to run). 16 new tests.
  Full suite now 387 tests, all green; strict pyright still 0 errors outside
  `testing/`. Next: LucaChen, MeiyiSong, RachaelYuan, SarahChen, WestonPoe (all
  unblocked), then JaydenBrown last (needs the already-designed `IOListener` engine
  hook from Open Question 4).

- 2026-09-07 (continued) - Finished all remaining unblocked woodwinds: LucaChen,
  MeiyiSong, RachaelYuan, SarahChen, WestonPoe (17/18 - only JaydenBrown left, deferred
  for its new-engine-hook need). No new engine bugs. One test-design lesson (not a
  code bug): WestonPoe's "Right Back At You!" reflection reactor needed its "still in
  play" gate removed after a failing test showed the engine's own KO-and-discard flow
  (`INTERNAL_3`, running before this `EXTERNAL_REACTORS` listener) already moves a
  lethally-hit owner out of play by the time the reactor sees the event - the same
  general post-act-reactor-timing lesson as JuliaCeccarelli's KO chain, applied to a
  different card. 18 new tests. Full suite now 406 tests, all green; strict pyright
  still 0 errors outside `testing/`. Woodwinds is now effectively done - only
  JaydenBrown remains, needing the already-designed `IOListener` engine hook (Open
  Question 4) to actually build. Next per the user's "get through all remaining work"
  instruction: attempt JaydenBrown (build the `IOListener`-based coinflip-intercept
  hook), then move to stadiums (10 files, to unblock DemiLu/JennieWang/MichaelTu/
  MichelleKim/MikuOtamatone/MatchaLatte/StrawberryMatchaLatte) and supporters (9
  files, no dependencies).

- 2026-09-07 (continued) - Finished JaydenBrown (18/18 woodwinds - element complete).
  This card just needed the already-designed `IOListener` hook wired up on the
  character side; the engine hook itself needed no changes and worked exactly as
  designed on first try. `card.add_io_listener(...)` registers a listener matching
  `CoinflipData` requests for its own controller (active, once/round via a plain
  instance field); its `modify()` awaits its own follow-up Yes/No query before
  deciding whether to override the resolved coinflip. Verified end-to-end via a
  direct `env.report(CoinflipData(...))` test exercising intercept-and-override,
  pass-through, once-per-round, and inactive-card cases. 5 new tests. Full suite now
  411 tests, all green; strict pyright still 0 errors outside `testing/`. **All 18
  woodwinds done - the whole element is complete.** Next per the user's "get through
  all remaining work" instruction: stadiums (10 files) is the next element per
  Section 4's staging order, to unblock DemiLu/JennieWang (piano), MichaelTu/
  MichelleKim (strings), and MikuOtamatone/MatchaLatte/StrawberryMatchaLatte (items);
  supporters (9 files, no dependencies) can slot in anytime after or interleaved.

- 2026-09-07 (continued) - Started stadiums: RedRoom, RileyHall,
  LindemannPracticeRoom (3/10). Established `self.deck_type == DeckType.STADIUM` as
  the v2 equivalent of v1's `_is_active_stadium()` check (a stadium's own `deck_type`
  attribute tracks which pile it's actually in, same as any other card) - every
  stadium listener from here on gates on this and self-cleans via it. Kept
  LindemannPracticeRoom's vacuous-truth-on-empty-bench behavior faithfully (Open
  Question, not clearly enough a bug to justify a fix). Learned `env.engine.flush()`
  doesn't propagate a per-packet success/fail status to its caller - tests that need
  to distinguish a successful `PlayCharacterCard` from a `REGULATE_FAIL`'d one should
  check `search_history` afterward instead of trusting `flush()`'s return value.
  Added a `play_stadium()` test helper to `testing/helpers.py` (mirrors `play_item`).
  13 new tests. Full suite now 424 tests, all green; strict pyright still 0 errors
  outside `testing/`. Next: AlumnaeHall, SalomonDECI, MainHall (must precede
  MichaelTu/JennieWang), then PetterutiLounge (needs the `AVGEPacketReactor` API,
  never yet exercised), then SteinertBasement + SteinertPracticeRoom together
  (coordinate with DemiLu), then FriedmanHall last (flagged hardest stadium).

- 2026-09-07 (continued) - AlumnaeHall, SalomonDECI, MainHall (6/10 stadiums).
  Corrected a survey imprecision while migrating SalomonDECI: re-reading the real v1
  source, it has no separate flat +/- type-based damage table like RedRoom - just the
  d6-roll -30dmg mechanic for its 4 supported types. MainHall is the first card
  outside `CoreListeners.py` to use `AVGEEventRegulator`, confirming that path works
  correctly for a stadium-level play-count limiter. Found a recurring pyright
  narrowing gotcha: `TransferCard`/`PlayCharacterCard`/`PlayNonCharacterCard` all
  assign `self.id = id` *without* an explicit type annotation (unlike
  `AVGECardHPChangeEvent`, which does), so pyright falls back to the abstract base
  `Event.id: ID` and rejects `.calling_action`/`.calling_card` access even after
  narrowing the event type via `isinstance` - needs an explicit `assert
  isinstance(event.id, AVGEEngineID)` first. 11 new tests. Full suite now 435 tests,
  all green; strict pyright still 0 errors outside `testing/`. Next: PetterutiLounge
  (needs the `AVGEPacketReactor` API, never yet exercised), then SteinertBasement +
  SteinertPracticeRoom together (coordinate with DemiLu), then FriedmanHall last
  (flagged hardest stadium).

- 2026-09-07 (continued) - PetterutiLounge (7/10 stadiums). First card in the whole
  migration to use the packet-level `AVGEPacketReactor` API - confirmed it works
  exactly as designed on first try. Its "reveal a random card after any attack"
  effect needed `packet.event_log` (the packet's own record of every event it
  actually ran) to find the real attacking character, since the packet's own
  `id.calling_card` is `None` for a normal player-driven attack - the same
  DesmondRoper-streak gotcha, now confirmed to apply at the packet level too, not
  just the event level. The MAID retreat discount reuses KikisHeadband's exact
  "verify discounted cost, then top up 1 free energy" trick rather than trying to
  replicate v1's direct `energy_requirement` mutation (no v2 equivalent field). 5 new
  tests. Full suite now 440 tests, all green; strict pyright still 0 errors outside
  `testing/`. Next: SteinertBasement + SteinertPracticeRoom together (coordinate with
  DemiLu, which imports their internal listener classes), then FriedmanHall last
  (flagged hardest stadium).

- 2026-09-07 (continued) - SteinertBasement + SteinertPracticeRoom together (9/10
  stadiums - only FriedmanHall left). Both export their `_AttackExtraCostModifier` by
  name for DemiLu (still deferred) to reference later, with a docstring flag that
  v2's `AVGEConstrainer` can't see per-event context the way v1's could (confirmed by
  LukeXu's precedent) - DemiLu will most likely need its own compensating modifier
  instead of a constrainer-based exclusion. Confirmed a real, deliberate difference
  between the two otherwise-identical cost modifiers: SteinertPracticeRoom's has no
  `PLAYER_CHOICE` gate (surcharges even a borrowed/forced attack), SteinertBasement's
  does. SteinertPracticeRoom's on-play sequential two-player discard resolution -
  v1's hardest-flagged mechanic, a cache-based re-entrant dance - collapsed to two
  plain sequential `await`s in v2, since `play_card()` is just one async coroutine.
  8 new tests. Full suite now 448 tests, all green; strict pyright still 0 errors
  outside `testing/`. Next: FriedmanHall (flagged hardest stadium - needs a clean v2
  idiom for re-injecting `Phase2` with a self-recursion guard), then this migration's
  stadiums are complete.

- 2026-09-07 (continued) - FriedmanHall (10/10 stadiums - **element complete**).
  Redesigned rather than literally porting v1's hardest-flagged mechanic: v1 cancels
  `PhasePickCard`'s own resolution and re-injects a fresh `Phase2`, guarded by a
  `temp_cache` flag against re-triggering itself. v2's `REGULATE_FAIL` rolls back the
  *entire enclosing packet* (confirmed by reading `Engine.flush()`'s handling), not
  just the one event, so using it to cancel-and-replace a single event the way v1's
  assessor model could is unsafe. Instead, this reactor runs before the engine's own
  already-queued normal draw (which lazily reads `deck.get_top()` only when its own
  later-appended packet actually runs) and just reorders the deck so the opponent's
  chosen card ends up on top - the normal draw then naturally draws it. Net
  player-visible behavior matches v1 exactly, with no double-draw risk and nothing to
  guard against, since nothing gets re-injected. 3 new tests. Full suite now 451
  tests, all green; strict pyright still 0 errors outside `testing/`. **All 10
  stadiums done - the whole element is complete.** Next per the user's "get through
  all remaining work" instruction: supporters (9 files, no dependencies), then
  revisit the 4 deferred cards now unblocked by stadiums existing - DemiLu/JennieWang
  (piano), MichaelTu/MichelleKim (strings).

- 2026-09-07 (continued) - Started supporters: Lio, Will, Richard, Michelle (4/9).
  **Found and fixed two compounding, severe engine bugs while migrating Lio, the
  first supporter in this migration - supporters were 100% unplayable in real
  gameplay before this fix** (see Section 2 for the full writeup): `Phase2.act()`'s
  supporter dispatch decremented the wrong player attribute entirely, *and*
  sequenced that decrement *before* the validity check that gates on it, so the
  check always saw the just-zeroed value and failed every single supporter play,
  including the first one of the turn. Both fixed in `core/EventCatalog.py`. Lio's
  own "shuffle hand into deck" needed to be lazy (not an eager snapshot) since Lio
  itself is still in hand at `play_card()` time. Added `play_supporter()` to
  `testing/helpers.py` (bumps `SUPPORTER_USES_REMAINING_IN_TURN` first, same
  established gotcha as `ENERGY_ADD_REMAINING_IN_TURN`). 9 new tests. Full suite now
  460 tests, all green; strict pyright still 0 errors outside `testing/`. Next:
  Lucas, Victoria, Johann, Angel, then Emma last (flagged hardest supporter - the
  only "one-shot" supporter that isn't actually one-shot).

- 2026-09-07 (continued) - Lucas, Victoria, Johann, Angel (8/9 supporters - only
  Emma left, flagged hardest). Corrected a survey imprecision for Lucas: re-reading
  v1 source, its *first* pick goes to the top of the deck, not to hand - only the
  *second* pick actually goes to hand (Victoria, independently implemented, does the
  same top-deck/hand shape correctly). Johann's "at most 1 supporter, 1 item-or-tool,
  1 stadium" constraint - previously enforced via v1's custom retry-validated single
  query, with no v2 equivalent (same limitation as CastReserve) - is instead
  structurally guaranteed via three independent, separately-scoped queries, one per
  category. Confirmed Johann's mid-resolution `TurnEnd` (a side effect flagged as
  needing verification) actually flips `env.turn` correctly end-to-end. 11 new tests.
  Full suite now 468 tests, all green; strict pyright still 0 errors outside
  `testing/`. Next: Emma (flagged hardest supporter - the only "one-shot" supporter
  that isn't actually one-shot, needs a round-scoped lock attached to an *opponent's*
  card), then this migration's supporters are complete.

- 2026-09-07 (continued) - Emma (9/9 supporters - **element complete**). The one
  "one-shot" supporter that leaves a persistent effect behind: forces an opponent
  bench swap, then locks the newly-forced-active character from retreating during
  the opponent's very next turn only (`round_active = env.round + 1`, since it's
  always the caster's own turn when a supporter is played). A plain
  `AVGEEventRegulator` handles the lock, self-cleaning once `env.round` passes it -
  no new engine primitive needed, just the same round-scoped-listener idiom used
  throughout this migration, adapted to lock instead of buff and to target an
  opponent's card instead of the caster's own. Verified end-to-end with real chained
  `TurnEnd`s that the block applies exactly one turn and no longer. 4 new tests. Full
  suite now 472 tests, all green; strict pyright still 0 errors outside `testing/`.
  **All 9 supporters done - status effects, tools, and supporters are now all fully
  complete.** Every character element (guitar, percussion, woodwinds) plus stadiums
  and supporters are now 100% done. Only 4 deferred characters (DemiLu, JennieWang,
  MichaelTu, MichelleKim) and 3 stadium-blocked items (MikuOtamatone, MatchaLatte,
  StrawberryMatchaLatte) remain in the entire migration - both now unblocked since
  stadiums exist. Next per the user's "get through all remaining work" instruction:
  the 3 remaining items, then the 4 deferred characters (coordinating DemiLu with
  SteinertBasement/SteinertPracticeRoom's exported cost-modifier classes, and
  MichaelTu/MichelleKim/JennieWang with whichever specific stadiums/items they check
  for).

- 2026-09-07 (continued) - MikuOtamatone, MatchaLatte, StrawberryMatchaLatte (21/21
  items - **element complete**). All three were genuinely blocked on stadiums, now
  unblocked. All three turned up real v1 bugs on sight (see Section 5's Items table
  and Section 2): MikuOtamatone's stadium-gating tuple silently excluded the imported
  `FriedmanHall` (fixed - all 5 imported "performance hall" stadiums are now checked);
  MatchaLatte and StrawberryMatchaLatte both checked
  `isinstance(env.stadium_cardholder, PetterutiLounge)`, which is always `False` since
  `stadium_cardholder` is the pile container itself, never a stadium card instance -
  fixed by checking `env.stadium_cardholder.cards_holding[0]` instead, independently
  in both files. First-draft tests for all three initially failed with
  `list.remove(x): x not in list` - root cause was the tests never appending the
  newly-constructed item card to `player.card_piles[DeckType.HAND].cards_holding`
  before calling `play_item()` (unlike the stadium tests, which correctly append
  before calling `play_stadium()`) - `play_item()`'s own `TransferCard` expects the
  card already physically in hand. Fixed by adding the missing `.append(item)` call
  to all 5 new test methods that invoke `play_item`. 7 new tests. Full suite now 479
  tests, all green; strict pyright still 0 errors outside `testing/` (156 files
  analyzed). **All 21 items done - items are now fully complete.** Every character
  element plus stadiums, status effects, tools, supporters, and items are now 100%
  done. Only the 4 deferred characters remain in the entire migration: DemiLu,
  JennieWang, MichaelTu, MichelleKim - all now fully unblocked. Next: work through
  these 4 in turn (DemiLu first, coordinating with SteinertBasement/
  SteinertPracticeRoom's exported `_AttackExtraCostModifier` classes per their
  docstring notes; then JennieWang and MichaelTu, both checking the same 4 named
  stadiums; then MichelleKim, needing MikuOtamatone's history-searchable play and an
  independent copy of IrisYang's "Open Strings" atk_1). This is the last remaining
  work item in the whole migration.

- 2026-09-07 (continued) - **DemiLu, JennieWang, MichaelTu, MichelleKim (all 4
  deferred characters) - THE ENTIRE MIGRATION IS NOW COMPLETE.** Worked through all
  four in the planned order:
  - **DemiLu** (piano): full damage immunity while benched under either Steinert
    stadium (`event.modify_magnitude(-event.magnitude)`, same idiom as MAID's
    shield), plus a `_CostExemptionModifier` that adds the Steinert `+1` attack-cost
    surcharge back for itself specifically. Confirmed by a first-draft test failure
    that this exemption *must* share `EXTERNAL_MODIFIERS_1` with the Steinert
    modifiers themselves (not a later group like `EXTERNAL_MODIFIERS_3`, tried
    first) - `INTERNAL_1`'s affordability check reads `event.cost` before any later
    group runs, so a later-group exemption arrives too late to matter. A same-group
    `+1`/`-1` pair is order-independent regardless of `ListenerReorderIO`'s
    arbitrary same-group ordering, so this is safe. 8 new tests.
  - **JennieWang** (piano) and **MichaelTu** (strings): both needed the same 4 named
    stadiums (AlumnaeHall/SalomonDECI/RileyHall/MainHall) for their atk_2 boost -
    all already migrated, no new sequencing issues. JennieWang's atk_1 needed 5
    other character classes across piano/woodwind/percussion/guitar, also all
    already done. MichaelTu's Synchro Summon uses a public `RevealCards` broadcast
    then a lazy post-transfer `ReorderDeck`, matching the established
    reveal/transfer/reshuffle idiom. 5 tests each.
  - **MichelleKim** (strings, last card in the whole migration): Open Strings is a
    byte-identical independent copy of IrisYang's atk_1 (as flagged). VocaRock!!'s
    "was MikuOtamatone played this turn" check uses the documented
    `increment=0`/manual-loop history-search convention (Section 2), the same shape
    as CarolynZheng's `_attacked_last_turn`. 3 tests.
  - All 4 files needed a `base_abilities() -> {}` override that was initially
    forgotten for the two attack-only cards (DemiLu/JennieWang have passives so
    didn't hit this) - MichaelTu and JennieWang both initially crashed at
    environment construction with `Can't instantiate abstract class ... without an
    implementation for abstract method 'base_abilities'` until the empty-dict
    override was added, matching the pattern already established by attack-only
    guitar cards (AntongChen, OwenLandry, etc.).
  - 21 new tests across the 4 cards. Full suite now 500 tests, all green; strict
    pyright 0 errors across 160 files outside `testing/`.
  - **Every character (all 7 elements), every stadium, every item, every status
    effect, every tool, and every supporter is now migrated to `card_game_v2`. The
    v1-to-v2 migration described by this entire document is complete.** No further
    per-card work remains; any future work on this codebase is genuinely new
    feature work, not migration.

## 8. Bugs fixed

Log every bug fixed during migration here, even ones that seem minor — this is the
durable record for the user to review later, since "fix on sight" (Section 6, item 2)
means these happen inline rather than being batched up for a single review pass.

*(Engine-level bugs are logged in Section 2's "Engine bugs found and fixed"
subsection instead. Per-card catalog bugs found and fixed via "fix on sight" are
mostly logged inline in Section 5's per-card table notes and Section 0/7's batch
summaries; the most recent batch's are also summarized here as a durable record.)*

- **MikuOtamatone (item)**: v1 imports `FriedmanHall` but its stadium-gating
  `isinstance` tuple only checked 4 of the 5 imported stadium classes, silently
  excluding `FriedmanHall`. Fixed in v2 by including all 5 imported "performance
  hall" stadiums in the gating tuple.
- **MatchaLatte (item)**: v1 checks `isinstance(card.env.stadium_cardholder,
  PetterutiLounge)` — `stadium_cardholder` is the pile/cardholder container itself,
  never an instance of a specific stadium card class, so this check was always
  `False` and the PetterutiLounge bonus could never actually apply. Fixed by checking
  the card actually occupying the stadium slot
  (`env.stadium_cardholder.cards_holding[0]`) instead.
- **StrawberryMatchaLatte (item)**: identical always-`False`
  `isinstance(stadium_cardholder, PetterutiLounge)` bug as MatchaLatte, fixed the
  same way, independently.
