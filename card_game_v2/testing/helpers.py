"""Shared async test harness for card_game_v2 character/item/stadium tests.

Not part of the production catalog - imported by colocated `test_*.py` files under
`card_game_v2/catalog/...`. See V2_MIGRATION_PLAN.md Section 1 for the conventions
these tests follow.
"""
from __future__ import annotations

import contextlib

from ..avge_abstracts.AVGEDeck import DeckType
from ..avge_abstracts.AVGEEnvironment import EnergyToken
from ..avge_abstracts.AVGECard import AVGECharacterCard, CardType, AVGEStadiumCard, AVGESupporterCard, AVGEToolCard, AVGECard, Ability, Attack
from ..constants import User, ActionTypes, StatusEffect, AVGEStatusModifier, AVGEPlayerAttribute, AVGEAttributeModifier
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..engine.event import Packet
from ..core.EventCatalog import (
    TransferCard, PlayCharacterCard, AVGECardStatusChange, PhasePickCard, PlayNonCharacterCard,
    AVGEPlayerAttributeChange,
)
from ..core.AVGEIOManager import (
    AVGEIO, CardSelectionQuery, StringSelectionQuery, Notification, BroadcastIO, CoinflipData,
    Phase2IO, Phase2Finish, AtkPhaseIO, D6Input, IntInput,
)
from ..engine.engine_io import ListenerReorderIO
from ..core.CoreListeners import (
    AVGETokenTransferCheck, AVGEHPChangeCheck, AVGEHPChangeReactor, AVGEWeaknessModifier,
    AVGEPlayerAttributeChangeReactor, AVGETransferValidityCheck,
    AVGEStadiumReplaceReactor, AVGEPlayCardValidityCheck, AVGETransferSourceCheck,
)
from ..catalog.status_effects.Goon import (
    AVGEGoonRetreatCostModifier, AVGEGoonStatusChangeReactor,
)
from ..catalog.status_effects.Maid import AVGEMaidDamageShieldRegulator
from ..catalog.status_effects.Arranger import AVGEArrangerStatusReactor


class Dummy(AVGECharacterCard):
    '''A generic, attack/ability-less character for use as an inert opponent/teammate.'''
    _hp = 300

    def base_hp(self):
        return self._hp

    def base_max_hp(self):
        return self._hp

    def base_card_type(self):
        return CardType.WOODWIND

    def base_retreat_cost(self):
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({}), **({})}


    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return


class _NoOpAttack(Attack):
    async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
        card = acting_card
        return


class Attacker(AVGECharacterCard):
    '''Like Dummy, but with a real (no-op) ATK_1 attack so tests can drive a genuine
    `PlayCharacterCard` through the engine (e.g. to test an energy-cost modifier)
    instead of hand-constructing one against a card with no attacks.'''
    _hp = 300

    def base_hp(self):
        return self._hp

    def base_max_hp(self):
        return self._hp

    def base_card_type(self):
        return CardType.WOODWIND

    def base_retreat_cost(self):
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: _NoOpAttack('Dummy Attack', 'Does nothing.', ActionTypes.ATK_1, 3)}), **({})}


    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return


class DummyStadium(AVGEStadiumCard):
    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="DummyStadium",
                description=DummyStadium.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, DummyStadium):
                raise TypeError("DummyStadium action requires its defining card")
            return



class DummySupporter(AVGESupporterCard):
    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="DummySupporter",
                description=DummySupporter.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, DummySupporter):
                raise TypeError("DummySupporter action requires its defining card")
            return



class DummyTool(AVGEToolCard):
    '''A no-op tool, for tests that just need to drive a real TransferCard into a character's
    tools_attached without any actual attach-time effect.'''
    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="DummyTool",
                description=DummyTool.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, DummyTool):
                raise TypeError("DummyTool action requires its defining card")
            return



def core_listeners():
    return [
        AVGETokenTransferCheck, AVGEHPChangeCheck, AVGEHPChangeReactor, AVGEWeaknessModifier,
        AVGEMaidDamageShieldRegulator, AVGEPlayerAttributeChangeReactor, AVGETransferValidityCheck,
        AVGEStadiumReplaceReactor, AVGEPlayCardValidityCheck, AVGETransferSourceCheck,
        AVGEGoonRetreatCostModifier, AVGEGoonStatusChangeReactor,
        AVGEArrangerStatusReactor,
    ]


class TestIO(AVGEIO):
    '''A fake IO manager that answers every request type used by the migrated cards so
    far. Configure a scenario by setting the relevant attribute before firing an event;
    everything defaults to a harmless/deterministic answer.'''

    def __init__(self):
        super().__init__()
        self.string_answer = None
        self.string_answers = None  # optional list consumed in order, one per StringSelectionQuery call
        self._string_i = 0
        self.string_query_count = 0  # increments on every StringSelectionQuery, regardless of mode
        self.card_answer_index = 0
        self.card_answer_indices = None  # optional list of indices, one per selection slot
        self.card_answer_sequence = None  # optional list consumed in order, one per CardSelectionQuery call; each entry is None (decline), an int (single index, repeated for every slot), or a list[int] (one index per slot, for a distinct multi-select)
        self._card_i = 0
        self.select_none = False
        self.coinflip_results = None  # optional list consumed in order; falls back to 1 (heads)
        self._coinflip_i = 0
        self.d6_results = None  # optional list consumed in order; falls back to 6
        self._d6_i = 0
        self.int_input_results = None  # optional list consumed in order; falls back to io.max_num
        self._int_i = 0

    def resolve_users(self, io):
        return User.PLAYER_1

    async def send(self, user, io):
        if isinstance(io, CardSelectionQuery):
            if self.card_answer_sequence is not None:
                entry = self.card_answer_sequence[self._card_i % len(self.card_answer_sequence)]
                self._card_i += 1
                if entry is None:
                    result = []
                elif isinstance(entry, list):
                    result = [io.allowed_selections[i] for i in entry]
                else:
                    result = [io.allowed_selections[entry] for _ in range(io.num_selections)]
            elif self.select_none and io.allows_none:
                result = []
            elif self.card_answer_indices is not None:
                result = [io.allowed_selections[i] for i in self.card_answer_indices]
            else:
                result = [io.allowed_selections[self.card_answer_index] for _ in range(io.num_selections)]
        elif isinstance(io, StringSelectionQuery):
            self.string_query_count += 1
            if self.string_answers is not None:
                answer = self.string_answers[self._string_i % len(self.string_answers)]
                self._string_i += 1
            elif self.string_answer is not None:
                answer = self.string_answer
            else:
                answer = io.allowed_selections[0]
            result = [answer]
        elif isinstance(io, CoinflipData):
            if self.coinflip_results is not None:
                result = self.coinflip_results[self._coinflip_i % len(self.coinflip_results)]
                self._coinflip_i += 1
            else:
                result = 1
        elif isinstance(io, D6Input):
            if self.d6_results is not None:
                result = self.d6_results[self._d6_i % len(self.d6_results)]
                self._d6_i += 1
            else:
                result = 6
        elif isinstance(io, IntInput):
            if self.int_input_results is not None:
                result = self.int_input_results[self._int_i % len(self.int_input_results)]
                self._int_i += 1
            else:
                result = io.max_num
        elif isinstance(io, (Notification, BroadcastIO)):
            result = None
        elif isinstance(io, Phase2IO):
            result = Phase2Finish()
        elif isinstance(io, AtkPhaseIO):
            result = ActionTypes.SKIP
        elif isinstance(io, ListenerReorderIO):
            result = io.listeners
        else:
            result = None
        self.pending[user].future_obj.set_result(result)

    async def retry(self, user, io, error):
        raise error

    def deserialize(self, io, data):
        return data


async def put_into_play(env, player, card=None):
    if card is None:
        card = player.card_piles[DeckType.DECK][0]
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    pkt = Packet(_id, [TransferCard(_id, card, player.card_piles[DeckType.DECK], player.card_piles[DeckType.ACTIVE_CARD], env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)
    return card


async def bench(env, player, card=None):
    if card is None:
        card = player.card_piles[DeckType.DECK][0]
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    pkt = Packet(_id, [TransferCard(_id, card, player.card_piles[DeckType.DECK], player.card_piles[DeckType.BENCH], env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)
    return card


async def discard(env, player, card=None):
    if card is None:
        card = player.card_piles[DeckType.DECK][0]
    deck_from = player.card_piles[card.deck_type]
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    pkt = Packet(_id, [TransferCard(_id, card, deck_from, player.card_piles[DeckType.DISCARD], env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)
    return card


async def attach_tool(env, player, tool, character):
    player.card_piles[DeckType.HAND].cards_holding.append(tool)
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    pkt = Packet(_id, [TransferCard(_id, tool, player.card_piles[DeckType.HAND], character.tools_attached, env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)
    return tool


async def detach_tool(env, player, tool):
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    pkt = Packet(_id, [TransferCard(_id, tool, tool.parent_card.tools_attached, player.card_piles[DeckType.DISCARD], env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)
    return tool


async def retreat(env, player, incoming=None):
    '''Drives a real retreat: the exact two-TransferCard packet shape
    core/EventCatalog.py's Phase2CardMovement case builds for a BENCH -> ACTIVE_CARD
    move - the incoming bench card swaps in, the outgoing active card swaps out to
    bench, carrying its own retreat_cost as that leg's cost (see TransferCard's own
    cost field and A2's retreat-cost fix), both tagged PLAYER_CHOICE in one packet.
    Constructing a single bare TransferCard(ACTIVE_CARD -> BENCH) directly instead -
    an easy trap, since that's the event that actually pays the cost - bypasses the
    swap-in leg entirely and every EXTERNAL_MODIFIERS_1 cost modifier that only
    matches the real two-event shape (Kiki's tool, GOON's status, Petteruti's
    stadium), so it doesn't exercise real cost-discount/surcharge card effects at
    all. Returns the outgoing card, so callers can assert on its resulting deck_type
    and energy_tokens - engine.flush() itself doesn't return a usable ResponseStatus
    (only the lower-level Packet.flush() does), so a rejected retreat has to be
    read off board state instead: the outgoing card stays active with its energy
    untouched, rather than landing on the bench with energy charged.'''
    outgoing = player.card_piles[DeckType.ACTIVE_CARD][0]
    assert isinstance(outgoing, AVGECharacterCard)
    if incoming is None:
        incoming = player.card_piles[DeckType.BENCH][0]
    bench_deck = player.card_piles[DeckType.BENCH]
    active_deck = player.card_piles[DeckType.ACTIVE_CARD]
    _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    pkt = Packet(_id, [
        TransferCard(_id, incoming, bench_deck, active_deck, env),
        TransferCard(_id, outgoing, active_deck, bench_deck, env, outgoing.retreat_cost),
    ])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)
    return outgoing


async def play_item(env, player, item):
    '''Plays an item card from hand, mirroring Phase2.act()'s real dispatch: resolve
    its effect, then discard it - see EventCatalog.py's AVGEItemCard branch.'''
    _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    pkt = Packet(_id, [
        PlayNonCharacterCard(_id, item, env),
        TransferCard(_id, item, player.card_piles[DeckType.HAND], player.card_piles[DeckType.DISCARD], env),
    ])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)


async def play_stadium(env, player, stadium):
    '''Plays a stadium from hand into the single global stadium slot
    (`env.stadium_cardholder`) - `TransferCard`'s own "Special Case 3" fires the
    resulting `PlayNonCharacterCard` automatically, unlike items which need it added
    explicitly (see `play_item`). Caller is responsible for discarding any
    previously-active stadium first (no automatic replacement happens at the engine
    level - each stadium/tool that replaces one explicitly does so itself, e.g.
    BAIEmail).'''
    _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    pkt = Packet(_id, [TransferCard(_id, stadium, player.card_piles[DeckType.HAND], env.stadium_cardholder, env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)


async def play_supporter(env, player, supporter):
    '''Plays a supporter card from hand, mirroring `Phase2.act()`'s real dispatch:
    decrement `SUPPORTER_USES_REMAINING_IN_TURN` (bumped to 1 first, since a fresh
    `AVGEPlayer` defaults it to 0 - same gotcha as `ENERGY_ADD_REMAINING_IN_TURN`),
    resolve the supporter's effect, then discard it.'''
    player.attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] = 1
    _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    pkt = Packet(_id, [
        PlayNonCharacterCard(_id, supporter, env),
        AVGEPlayerAttributeChange(
            _id, player, AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN,
            AVGEAttributeModifier.SUBSTRACTIVE, 1, env,
        ),
        TransferCard(_id, supporter, player.card_piles[DeckType.HAND], player.card_piles[DeckType.DISCARD], env),
    ])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)


@contextlib.asynccontextmanager
async def phase_pick_card_limit(env, n=1):
    '''Async context manager: bounds whatever runs inside the `with` block to stop the
    moment the (n+1)th PhasePickCard would commit, instead of running to natural
    completion. An empty deck is no longer, on its own, a natural stopping point for a
    PhasePickCard cascade (PhasePickCard.act() now always reaches Phase2 regardless of
    deck size - see the deck-out fix), so any scenario with both players' decks already
    empty by design - directly firing PhasePickCard, or reaching a TurnEnd some other
    way, e.g. a card whose own effect ends the turn directly like Johann's or
    RossWilliams' - will flip turn back and forth forever instead of terminating on its
    own. n=1 (the default) lets exactly one player's own turn resolve, which is what
    almost every scenario actually wants; conftest.py's autouse fixture also wraps
    every Engine.flush() call with a generous event-count safety net as a backstop, but
    that alone isn't precise enough for assertions that care about the exact board
    state (a large-but-finite cap still eventually reaches a second, "unintended" turn,
    which can make an assertion pass for the wrong reason). AVGEShowcaseSticker's own
    tests used to need n=2 for this reason (its bonus draw was append_packet'd behind
    PhasePickCard's own draw/Phase2, needing an extra turn's headroom to run at all
    before this stopped the cascade) - now push_packet'd like every other card, it
    resolves within the same n=1 turn; see test_tools.py's
    test_heads_draws_an_extra_card_resolves_within_the_same_turn.'''
    seen = 0
    previous_hook = env.engine.on_event_committed

    async def stop_after_nth_turn(event):
        nonlocal seen
        if isinstance(event, PhasePickCard):
            seen += 1
            if seen > n:
                env.engine.terminate_flag = True
        if previous_hook is not None:
            await previous_hook(event)

    env.engine.on_event_committed = stop_after_nth_turn
    try:
        yield
    finally:
        env.engine.on_event_committed = previous_hook
        env.engine.terminate_flag = False


async def fire_phase_pick_card(env, n=1):
    '''Fires a bare PhasePickCard and lets it cascade through the real draw/Phase2/
    AtkPhase/TurnEnd machinery (TestIO auto-answers Phase2Finish/SKIP), bounded by
    phase_pick_card_limit (see its own docstring for why this needs bounding at all,
    and when the n=1 default isn't the right value).'''
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    async with phase_pick_card_limit(env, n=n):
        env.push_packet(Packet(_id, [PhasePickCard(_id, env)]))
        await env.engine.flush(lambda: False)


async def fire_phase_pick_card_for_n_turns(env, n=1):
    '''Alias for fire_phase_pick_card(env, n=n) - kept for callers that spell out the
    turn count explicitly.'''
    await fire_phase_pick_card(env, n=n)


async def give_status(env, card, status: StatusEffect, giver=None):
    giver = giver if giver is not None else env
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    pkt = Packet(_id, [AVGECardStatusChange(_id, card, giver, status, AVGEStatusModifier.ADD, env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)


async def remove_status(env, card, status: StatusEffect, giver=None):
    giver = giver if giver is not None else env
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    pkt = Packet(_id, [AVGECardStatusChange(_id, card, giver, status, AVGEStatusModifier.REMOVE, env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)


async def run_attack(env, attacker, action=ActionTypes.ATK_1, energy=5):
    attacker.energy_tokens = attacker.energy_tokens + [EnergyToken(f"e{i}") for i in range(energy)]
    _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    pkt = Packet(_id, [PlayCharacterCard(_id, attacker, action, attacker.actions[action].cost, env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)


async def activate_ability(env, card):
    _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    pkt = Packet(_id, [PlayCharacterCard(_id, card, ActionTypes.ACTIVATE_ABILITY, 0, env)])
    env.push_packet(pkt)
    response = await env.engine.flush(lambda: False)
    return response
