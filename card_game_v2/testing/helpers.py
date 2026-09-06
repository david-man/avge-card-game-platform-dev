"""Shared async test harness for card_game_v2 character/item/stadium tests.

Not part of the production catalog - imported by colocated `test_*.py` files under
`card_game_v2/catalog/...`. See V2_MIGRATION_PLAN.md Section 1 for the conventions
these tests follow.
"""
from __future__ import annotations

from ..avge_abstracts.AVGEDeck import DeckType
from ..avge_abstracts.AVGEEnvironment import EnergyToken
from ..avge_abstracts.AVGECard import AVGECharacterCard, CardType, AVGEStadiumCard
from ..constants import User, ActionTypes
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..engine.event import Packet
from ..core.EventCatalog import TransferCard, PlayCharacterCard
from ..core.AVGEIOManager import (
    AVGEIO, CardSelectionQuery, StringSelectionQuery, Notification, BroadcastIO, CoinflipData,
    Phase2IO, Phase2Finish, AtkPhaseIO,
)
from ..engine.engine_io import ListenerReorderIO
from ..core.CoreListeners import (
    AVGETokenTransferCheck, AVGEHPChangeCheck, AVGEHPChangeReactor, AVGEWeaknessModifier,
    AVGEPlayerAttributeChangeReactor, AVGETransferValidityCheck, AVGERetreatCostReactor,
    AVGEPlayCharacterCardValidityCheck, AVGEPlayNonCharacterCardValidityCheck,
)


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


class DummyStadium(AVGEStadiumCard):
    async def on_transfer(self, deck_from, deck_to, transfer_event):
        return

    async def play_card(self):
        return


def core_listeners():
    return [
        AVGETokenTransferCheck, AVGEHPChangeCheck, AVGEHPChangeReactor, AVGEWeaknessModifier,
        AVGEPlayerAttributeChangeReactor, AVGETransferValidityCheck, AVGERetreatCostReactor,
        AVGEPlayCharacterCardValidityCheck, AVGEPlayNonCharacterCardValidityCheck,
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
        self.select_none = False
        self.coinflip_results = None  # optional list consumed in order; falls back to 1 (heads)
        self._coinflip_i = 0

    def resolve_users(self, io):
        return User.PLAYER_1

    async def send(self, user, io):
        if isinstance(io, CardSelectionQuery):
            if self.select_none and io.allows_none:
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
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    pkt = Packet(_id, [TransferCard(_id, card, player.card_piles[DeckType.DECK], player.card_piles[DeckType.DISCARD], env)])
    env.push_packet(pkt)
    await env.engine.flush(lambda: False)
    return card


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
