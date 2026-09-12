import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import User, ActionTypes, AVGEAttributeModifier, AVGEPlayerAttribute, StatusEffect, AVGEStatusModifier
from ...avge_abstracts.AVGECard import CardType
from ...avge_abstracts.AVGEEnvironment import EnergyToken
from ...engine.event import Packet
from ...core.EventCatalog import (
    AVGECardHPChangeEvent, AVGECardMaxHPChangeEvent, AVGECardTypeChange, AVGECardStatusChange,
    AVGEEnergyTransfer, AVGEPlayerAttributeChange, ReorderDeck, PhasePickCard, Phase2, AtkPhase,
    TurnEnd, Broadcast, GameEnd,
)
from ...core.AVGEIOManager import (
    HPChangeUpdate, MaxHPChangeUpdate, CardTypeChangeUpdate, StatusChangeUpdate,
    EnergyTransferUpdate, PlayerAttributeUpdate, CardMovedUpdate, DeckReorderedUpdate,
    CharacterActionUpdate, NonCharacterPlayUpdate, TurnEndUpdate, PhaseChangedUpdate, BroadcastIO,
)
from ...testing.helpers import (
    Dummy, Attacker, TestIO, core_listeners, put_into_play, bench, run_attack, play_stadium,
)
from ...catalog.stadiums.RedRoom import RedRoom
from ..event_broadcasting import event_to_update_io, action_rejected_update


class EventToUpdateIoTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = AVGEEnvironment(TestIO(), {
            User.PLAYER_1: [Dummy, Dummy, Attacker],
            User.PLAYER_2: [Dummy, Dummy],
        }, core_listeners())
        self.env.turn = User.PLAYER_1
        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]
        self.active = await put_into_play(self.env, self.p1)
        self.benched = await bench(self.env, self.p1)
        self.opp_active = await put_into_play(self.env, self.p2)

    async def _flush_single_event(self, event) -> None:
        '''For non-cascading events (no follow-up packets pushed by their own act()) - a plain
        push_packet + engine flush is safe and simplest.'''
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [event]))
        await self.env.engine.flush(lambda: False)

    async def _flush_single_event_no_cascade(self, event) -> None:
        '''For events whose own act() pushes further packets (PhasePickCard/Phase2/AtkPhase/
        TurnEnd all queue follow-up phases) - flush the packet directly, bypassing
        Engine.flush()'s own buffer-draining loop, so the pushed follow-up packets are never
        actually processed (same idiom used to avoid the documented TurnEnd-buffer test-hang
        trap elsewhere in this migration).'''
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        pkt = Packet(_id, [event])
        pkt.set_engine(self.env.engine)
        await pkt.flush()

    async def test_hp_change_update(self):
        event = AVGECardHPChangeEvent(
            AVGEEngineID(None, ActionTypes.ENV, None), self.opp_active, 20,
            AVGEAttributeModifier.SUBSTRACTIVE, CardType.ALL, self.env,
        )
        await self._flush_single_event(event)
        update = event_to_update_io(event)
        assert isinstance(update, HPChangeUpdate)
        self.assertIs(update.target_card, self.opp_active)
        self.assertEqual(update.magnitude, 20)
        self.assertEqual(update.original_hp, self.opp_active.hp + 20)
        self.assertEqual(update.final_change, self.opp_active.hp)
        self.assertFalse(update.is_crit)

    async def test_max_hp_change_update(self):
        event = AVGECardMaxHPChangeEvent(
            AVGEEngineID(None, ActionTypes.ENV, None), self.active, 10,
            AVGEAttributeModifier.ADDITIVE, CardType.ALL, self.env,
        )
        starting_max = self.active.max_hp
        await self._flush_single_event(event)
        update = event_to_update_io(event)
        assert isinstance(update, MaxHPChangeUpdate)
        self.assertEqual(update.original_max_hp, starting_max)
        self.assertEqual(update.final_max_hp, starting_max + 10)

    async def test_card_type_change_update(self):
        event = AVGECardTypeChange(AVGEEngineID(None, ActionTypes.ENV, None), self.active, CardType.BRASS, self.env)
        original = self.active.card_type
        await self._flush_single_event(event)
        update = event_to_update_io(event)
        assert isinstance(update, CardTypeChangeUpdate)
        self.assertEqual(update.original_type, original)
        self.assertEqual(update.new_type, CardType.BRASS)

    async def test_status_change_update(self):
        event = AVGECardStatusChange(
            AVGEEngineID(None, ActionTypes.ENV, None), self.active, self.env,
            StatusEffect.MAID, AVGEStatusModifier.ADD, self.env,
        )
        await self._flush_single_event(event)
        update = event_to_update_io(event)
        assert isinstance(update, StatusChangeUpdate)
        self.assertIs(update.target, self.active)
        self.assertEqual(update.status, StatusEffect.MAID)
        self.assertEqual(update.change, AVGEStatusModifier.ADD)
        self.assertTrue(update.made_modification)

    async def test_energy_transfer_update(self):
        self.active.energy_tokens.append(EnergyToken("e1"))
        event = AVGEEnergyTransfer(AVGEEngineID(None, ActionTypes.ENV, None), self.active, self.benched, self.env)
        await self._flush_single_event(event)
        update = event_to_update_io(event)
        assert isinstance(update, EnergyTransferUpdate)
        self.assertIs(update.token_from, self.active)
        self.assertIs(update.token_to, self.benched)

    async def test_player_attribute_update(self):
        event = AVGEPlayerAttributeChange(
            AVGEEngineID(None, ActionTypes.ENV, None), self.p1, AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN,
            AVGEAttributeModifier.SET_STATE, 1, self.env,
        )
        await self._flush_single_event(event)
        update = event_to_update_io(event)
        assert isinstance(update, PlayerAttributeUpdate)
        self.assertIs(update.player, self.p1)
        self.assertEqual(update.new_value, 1)

    async def test_card_moved_update(self):
        captured: list = []

        async def record(event):
            captured.append(event)

        self.env.engine.on_event_committed = record
        deck_card = self.p1.card_piles[DeckType.DECK].cards_holding[0]
        moved = await bench(self.env, self.p1, deck_card)
        transfer_events = [e for e in captured if type(e).__name__ == "TransferCard" and getattr(e, "card", None) is moved]
        self.assertEqual(len(transfer_events), 1)
        update = event_to_update_io(transfer_events[0])
        assert isinstance(update, CardMovedUpdate)
        self.assertIs(update.card, moved)

    async def test_deck_reordered_update(self):
        deck = self.p1.card_piles[DeckType.DECK]
        new_order = list(reversed(deck.cards_holding))
        event = ReorderDeck(AVGEEngineID(None, ActionTypes.ENV, None), deck, new_order, self.env)
        await self._flush_single_event(event)
        update = event_to_update_io(event)
        assert isinstance(update, DeckReorderedUpdate)
        self.assertIs(update.deck, deck)
        self.assertEqual(update.new_order, new_order)

    async def test_character_action_update(self):
        # Move the Attacker into active so it can attack.
        swapped = await self._swap_attacker_into_active()
        captured: list = []

        async def record(event):
            captured.append(event)

        self.env.engine.on_event_committed = record
        await run_attack(self.env, swapped, ActionTypes.ATK_1)
        play_events = [e for e in captured if type(e).__name__ == "PlayCharacterCard"]
        self.assertEqual(len(play_events), 1)
        update = event_to_update_io(play_events[0])
        assert isinstance(update, CharacterActionUpdate)
        self.assertIs(update.target_card, swapped)
        self.assertEqual(update.action, ActionTypes.ATK_1)

    async def test_non_character_play_update(self):
        captured: list = []

        async def record(event):
            captured.append(event)

        self.env.engine.on_event_committed = record
        stadium = RedRoom("rr", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.append(stadium)
        await play_stadium(self.env, self.p1, stadium)
        play_events = [e for e in captured if type(e).__name__ == "PlayNonCharacterCard"]
        self.assertEqual(len(play_events), 1)
        update = event_to_update_io(play_events[0])
        assert isinstance(update, NonCharacterPlayUpdate)
        self.assertIs(update.target_card, stadium)

    async def test_turn_end_update(self):
        event = TurnEnd(AVGEEngineID(None, ActionTypes.ENV, None), self.env)
        starting_turn = self.env.turn
        await self._flush_single_event_no_cascade(event)
        self.assertNotEqual(self.env.turn, starting_turn)  # TurnEnd.act() flipped it
        update = event_to_update_io(event)
        assert isinstance(update, TurnEndUpdate)
        self.assertEqual(update.new_turn, self.env.turn)
        self.assertEqual(update.new_round, self.env.round)

    async def test_phase_pick_card_update(self):
        event = PhasePickCard(AVGEEngineID(None, ActionTypes.ENV, None), self.env)
        await self._flush_single_event_no_cascade(event)
        update = event_to_update_io(event)
        self.assertEqual(update, PhaseChangedUpdate(phase="draw"))

    async def test_phase2_update(self):
        event = Phase2(AVGEEngineID(None, ActionTypes.ENV, None), self.env)
        await self._flush_single_event_no_cascade(event)
        update = event_to_update_io(event)
        self.assertEqual(update, PhaseChangedUpdate(phase="main"))

    async def test_atk_phase_update(self):
        self.env.round = 1  # AtkPhase only makes sense past turn 0
        event = AtkPhase(AVGEEngineID(None, ActionTypes.ENV, None), self.env)
        await self._flush_single_event_no_cascade(event)
        update = event_to_update_io(event)
        self.assertEqual(update, PhaseChangedUpdate(phase="attack"))

    async def test_broadcast_event_returns_none(self):
        event = Broadcast(AVGEEngineID(None, ActionTypes.ENV, None), self.env, BroadcastIO("hi", None))
        await self._flush_single_event_no_cascade(event)
        self.assertIsNone(event_to_update_io(event))

    async def test_game_end_event_returns_none(self):
        # GameEnd is handled separately (reuses the existing GameEndIO), not via this function.
        from ...constants import WinReasons
        event = GameEnd(AVGEEngineID(None, ActionTypes.ENV, None), User.PLAYER_1, WinReasons.ALL_KOS, self.env)
        await self._flush_single_event_no_cascade(event)
        self.assertIsNone(event_to_update_io(event))

    async def _swap_attacker_into_active(self):
        from ...core.EventCatalog import TransferCard
        attacker = self.p1.card_piles[DeckType.DECK].cards_holding[0]
        assert isinstance(attacker, Attacker)
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        pkt = Packet(_id, [
            TransferCard(_id, self.active, self.p1.card_piles[DeckType.ACTIVE_CARD], self.p1.card_piles[DeckType.BENCH], self.env),
            TransferCard(_id, attacker, self.p1.card_piles[DeckType.DECK], self.p1.card_piles[DeckType.ACTIVE_CARD], self.env),
        ])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)
        return attacker


class ActionRejectedUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = AVGEEnvironment(TestIO(), {
            User.PLAYER_1: [Dummy],
            User.PLAYER_2: [Dummy],
        }, core_listeners())
        self.env.turn = User.PLAYER_1

    async def test_rejected_for_the_current_turn_player(self):
        update = action_rejected_update(self.env)
        self.assertEqual(update.rejected_for, User.PLAYER_1)


if __name__ == "__main__":
    unittest.main()
