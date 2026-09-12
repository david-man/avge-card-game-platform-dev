import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import User, ActionTypes
from ...engine.event import Packet
from ...core.EventCatalog import TransferCard
from ...testing.helpers import (
    Dummy, TestIO, core_listeners, put_into_play, bench, discard, attach_tool, play_stadium,
)
from ...catalog.tools.AVGETShirt import AVGETShirt
from ...catalog.stadiums.RedRoom import RedRoom
from ..serialization import snapshot, card_to_wire, resolve_card, resolve_deck


class SerializationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = AVGEEnvironment(TestIO(), {
            User.PLAYER_1: [Dummy, Dummy, Dummy],
            User.PLAYER_2: [Dummy, Dummy],
        }, core_listeners())
        self.env.turn = User.PLAYER_1
        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]
        self.active = await put_into_play(self.env, self.p1)
        self.benched = await bench(self.env, self.p1)
        await put_into_play(self.env, self.p2)

    async def test_card_to_wire_includes_core_fields(self):
        self.active.hp -= 20
        wire = card_to_wire(self.active)
        self.assertEqual(wire["id"], self.active.cardID)
        self.assertEqual(wire["class_name"], "Dummy")
        self.assertEqual(wire["owner"], User.PLAYER_1.name)
        self.assertEqual(wire["deck_type"], "ACTIVE_CARD")
        self.assertEqual(wire["hp"], self.active.hp)
        self.assertEqual(wire["max_hp"], self.active.max_hp)
        self.assertEqual(wire["energy_count"], 0)
        self.assertEqual(wire["statuses"], [])
        self.assertEqual(wire["tools"], [])

    async def test_card_to_wire_includes_attached_tools(self):
        tool = await attach_tool(
            self.env, self.p1, AVGETShirt("t", self.env, User.PLAYER_1, DeckType.HAND), self.active,
        )
        wire = card_to_wire(self.active)
        self.assertEqual(len(wire["tools"]), 1)
        self.assertEqual(wire["tools"][0]["id"], tool.cardID)

    async def test_snapshot_shape_and_hand_deck_discard(self):
        snap = snapshot(self.env)
        self.assertEqual(snap["turn"], User.PLAYER_1.name)
        self.assertEqual(snap["round"], 0)
        self.assertIsNone(snap["stadium"])

        p1_state = snap["players"][User.PLAYER_1.name]
        self.assertEqual(p1_state["active"]["id"], self.active.cardID)
        self.assertEqual([c["id"] for c in p1_state["bench"]], [self.benched.cardID])
        self.assertEqual(len(p1_state["deck"]), 1)  # 3 dealt, 2 in play, 1 left
        self.assertEqual(p1_state["discard"], [])
        self.assertEqual(p1_state["hand"], [])

    async def test_snapshot_sends_full_hand_with_no_redaction(self):
        deck_card = self.p1.card_piles[DeckType.DECK].cards_holding[0]
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        pkt = Packet(_id, [TransferCard(
            _id, deck_card, self.p1.card_piles[DeckType.DECK], self.p1.card_piles[DeckType.HAND], self.env,
        )])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)

        snap = snapshot(self.env)
        p1_state = snap["players"][User.PLAYER_1.name]
        self.assertEqual(len(p1_state["hand"]), 1)
        self.assertEqual(p1_state["hand"][0]["id"], deck_card.cardID)

    async def test_snapshot_includes_discard(self):
        discarded = await discard(self.env, self.p1, self.benched)
        snap = snapshot(self.env)
        p1_state = snap["players"][User.PLAYER_1.name]
        self.assertEqual([c["id"] for c in p1_state["discard"]], [discarded.cardID])

    async def test_snapshot_includes_active_stadium(self):
        stadium = RedRoom("rr", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.append(stadium)
        await play_stadium(self.env, self.p1, stadium)

        snap = snapshot(self.env)
        self.assertIsNotNone(snap["stadium"])
        assert snap["stadium"] is not None
        self.assertEqual(snap["stadium"]["id"], stadium.cardID)

    async def test_resolve_card_finds_active_bench_and_tools(self):
        self.assertIs(resolve_card(self.env, self.active.cardID), self.active)
        self.assertIs(resolve_card(self.env, self.benched.cardID), self.benched)
        self.assertIsNone(resolve_card(self.env, "not-a-real-id"))

        tool = await attach_tool(
            self.env, self.p1, AVGETShirt("t2", self.env, User.PLAYER_1, DeckType.HAND), self.active,
        )
        self.assertIs(resolve_card(self.env, tool.cardID), tool)

    async def test_resolve_deck_round_trips_with_owner_and_type_name(self):
        deck = resolve_deck(self.env, User.PLAYER_1, "BENCH")
        self.assertIs(deck, self.p1.card_piles[DeckType.BENCH])

        # STADIUM has no owning player - matches how io_adapter._wire_deck_ref encodes it
        # (owner=None on the wire), and owner is ignored here regardless of what's passed.
        stadium_deck = resolve_deck(self.env, None, "STADIUM")
        self.assertIs(stadium_deck, self.env.stadium_cardholder)

        stadium_deck = resolve_deck(self.env, User.PLAYER_1, "STADIUM")
        self.assertIs(stadium_deck, self.env.stadium_cardholder)


if __name__ == "__main__":
    unittest.main()
