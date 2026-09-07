"""Shared async test harness for card_game_v2 character/item/stadium tests.

Not part of the production catalog - imported by colocated `test_*.py` files under
`card_game_v2/catalog/...`. See V2_MIGRATION_PLAN.md Section 1 for the conventions
these tests follow.
"""
from __future__ import annotations

from ..avge_abstracts.AVGEDeck import DeckType
from ..avge_abstracts.AVGEEnvironment import EnergyToken
from ..avge_abstracts.AVGECard import AVGECharacterCard, CardType, AVGEStadiumCard, AVGESupporterCard, AVGECard, Attack
from ..constants import User, ActionTypes, StatusEffect, AVGEStatusModifier
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..engine.event import Packet
from ..core.EventCatalog import TransferCard, PlayCharacterCard, AVGECardStatusChange, PhasePickCard, PlayNonCharacterCard
from ..core.AVGEIOManager import (
    AVGEIO, CardSelectionQuery, StringSelectionQuery, Notification, BroadcastIO, CoinflipData,
    Phase2IO, Phase2Finish, AtkPhaseIO, D6Input, IntInput,
)
from ..engine.engine_io import ListenerReorderIO
from ..core.CoreListeners import (
    AVGETokenTransferCheck, AVGEHPChangeCheck, AVGEHPChangeReactor, AVGEWeaknessModifier,
    AVGEPlayerAttributeChangeReactor, AVGETransferValidityCheck,
    AVGERetreatCostReactor, AVGEPlayCharacterCardValidityCheck, AVGEPlayNonCharacterCardValidityCheck,
)
from ..catalog.status_effects.Goon import (
    AVGEGoonRetreatCostRegulator, AVGEGoonRetreatCostReactor, AVGEGoonStatusChangeReactor,
)
from ..catalog.status_effects.Maid import AVGEMaidDamageShieldModifier
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

    def base_attacks(self):
        return {}

    def base_abilities(self):
        return {}

    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return


class _NoOpAttack(Attack):
    async def __call__(self, calling_card, caller_action):
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

    def base_attacks(self):
        return {ActionTypes.ATK_1: _NoOpAttack("Dummy Attack", "Does nothing.", ActionTypes.ATK_1, 3)}

    def base_abilities(self):
        return {}

    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return


class DummyStadium(AVGEStadiumCard):
    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return

    async def play_card(self):
        return


class DummySupporter(AVGESupporterCard):
    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return

    async def play_card(self, card: AVGECard, caller_action) -> None:
        return


def core_listeners():
    return [
        AVGETokenTransferCheck, AVGEHPChangeCheck, AVGEHPChangeReactor, AVGEWeaknessModifier,
        AVGEMaidDamageShieldModifier, AVGEPlayerAttributeChangeReactor, AVGETransferValidityCheck,
        AVGERetreatCostReactor, AVGEPlayCharacterCardValidityCheck, AVGEPlayNonCharacterCardValidityCheck,
        AVGEGoonRetreatCostRegulator, AVGEGoonRetreatCostReactor, AVGEGoonStatusChangeReactor,
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


async def play_item(env, player, item):
    '''Plays an item card from hand, mirroring Phase2.act()'s real dispatch: resolve
    its effect, then discard it - see EventCatalog.py's AVGEItemCard branch.'''
    _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    pkt = Packet(_id, [
        PlayNonCharacterCard(_id, item, ActionTypes.PLAYER_CHOICE, env),
        TransferCard(_id, item, player.card_piles[DeckType.HAND], player.card_piles[DeckType.DISCARD], env),
    ])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)


async def fire_phase_pick_card(env):
    '''Fires a bare PhasePickCard. Caller should size decks so both players are already
    empty by this point - otherwise this cascades through the real draw/Phase2/AtkPhase/
    TurnEnd machinery (TestIO auto-answers Phase2Finish/SKIP), eventually flipping turn
    back and firing a second, unintended PhasePickCard.'''
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    env.push_packet(Packet(_id, [PhasePickCard(_id, env)]))
    await env.engine.flush(lambda: False)


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
    pkt = Packet(_id, [PlayCharacterCard(_id, attacker, action, attacker.attacks[action].cost, env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)


async def activate_ability(env, card):
    _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    pkt = Packet(_id, [PlayCharacterCard(_id, card, ActionTypes.ACTIVATE_ABILITY, 0, env)])
    env.push_packet(pkt)
    response = await env.engine.flush(lambda: False)
    return response
