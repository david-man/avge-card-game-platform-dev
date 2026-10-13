import asyncio
import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment, EnergyToken
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, AVGEAttributeModifier, AVGEPlayerAttribute, User, KOS_TO_WIN
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ...core.AVGEIOManager import Phase2IO
from ...engine.engine_io import IOException
from ...engine.event import Packet
from ...testing.helpers import Dummy, DummyStadium, DummySupporter, DummyTool, bench, core_listeners, put_into_play
from ..io_adapter import NetworkIO


def _id() -> AVGEEngineID:
    return AVGEEngineID(None, ActionTypes.ENV, None)


class OwnershipAndLegalityTestBase(unittest.IsolatedAsyncioTestCase):
    '''Both players get enough Dummy cards for an active + bench + extra hand card each, so
    every ownership combination (own vs. opponent's card/deck) has something real to name.'''

    async def asyncSetUp(self):
        self.sent: list[tuple[User, dict]] = []

        async def send_message(user, message):
            self.sent.append((user, message))
            if message.get("io_type") == "Notification":
                asyncio.create_task(self.io.receive(user, {}))

        async def on_failure(user):
            pass

        self.io = NetworkIO(send_message, on_failure)
        self.env = AVGEEnvironment(self.io, {
            User.PLAYER_1: [Dummy, Dummy, Dummy],
            User.PLAYER_2: [Dummy, Dummy, Dummy],
        }, core_listeners())
        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]
        self.env.turn = User.PLAYER_1

        self.p1_active = await put_into_play(self.env, self.p1)
        self.p1_bench = await bench(self.env, self.p1)
        self.p2_active = await put_into_play(self.env, self.p2)
        self.p2_bench = await bench(self.env, self.p2)
        # put_into_play/bench both pull straight from DECK - move each player's third (and last)
        # Dummy from DECK to HAND manually for HAND-sourced tests, rather than pulling in
        # perform_initial_setup's much larger CARDS_PER_DECK-sized deck requirement.
        self.p1_hand_card = self.p1.card_piles[DeckType.DECK].cards_holding[0]
        self.p2_hand_card = self.p2.card_piles[DeckType.DECK].cards_holding[0]
        for player, card in ((self.p1, self.p1_hand_card), (self.p2, self.p2_hand_card)):
            pkt = Packet(_id(), [TransferCard(
                _id(), card, player.card_piles[DeckType.DECK], player.card_piles[DeckType.HAND], self.env,
            )])
            self.env.push_packet(pkt)
            await self.env.engine.flush(lambda: False)

    def assert_player_notification(self, reason: str) -> None:
        notices = [(user, message) for user, message in self.sent if message.get("io_type") == "Notification"]
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][0], User.PLAYER_1)
        self.assertEqual(notices[0][1]["payload"]["message"], reason)


class CardMovementOwnershipTests(OwnershipAndLegalityTestBase):
    def _deck_ref(self, owner: User, deck_type: str) -> dict:
        return {"owner": owner.name, "deck_type": deck_type}

    async def test_naming_opponents_card_is_rejected(self):
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "card_movement", "card_id": self.p2_bench.cardID,
                "deck_from": self._deck_ref(User.PLAYER_2, "BENCH"),
                "deck_to": self._deck_ref(User.PLAYER_2, "ACTIVE_CARD"),
            })

    async def test_deck_from_claiming_opponents_pile_is_rejected_even_for_your_own_card(self):
        # card_id is genuinely mine, but deck_from claims to be the opponent's pile - the wire
        # owner field and the resolved card's real owner are independent values that must both
        # check out.
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "card_movement", "card_id": self.p1_bench.cardID,
                "deck_from": self._deck_ref(User.PLAYER_2, "BENCH"),
                "deck_to": self._deck_ref(User.PLAYER_1, "ACTIVE_CARD"),
            })

    async def test_deck_to_targeting_opponents_pile_is_rejected(self):
        # Dumping my own card onto the opponent's board.
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "card_movement", "card_id": self.p1_bench.cardID,
                "deck_from": self._deck_ref(User.PLAYER_1, "BENCH"),
                "deck_to": self._deck_ref(User.PLAYER_2, "BENCH"),
            })

    async def test_legal_own_card_own_deck_transfer_still_works(self):
        result = self.io.deserialize(Phase2IO(self.env.turn), {
            "kind": "card_movement", "card_id": self.p1_hand_card.cardID,
            "deck_from": self._deck_ref(User.PLAYER_1, "HAND"),
            "deck_to": self._deck_ref(User.PLAYER_1, "BENCH"),
        })
        self.assertIs(result.card, self.p1_hand_card)

    async def test_active_card_vacate_rejected_for_every_destination_not_just_bench(self):
        for deck_type in ("BENCH", "DISCARD", "HAND", "DECK"):
            with self.subTest(deck_type=deck_type):
                with self.assertRaises(IOException):
                    self.io.deserialize(Phase2IO(self.env.turn), {
                        "kind": "card_movement", "card_id": self.p1_active.cardID,
                        "deck_from": self._deck_ref(User.PLAYER_1, "ACTIVE_CARD"),
                        "deck_to": self._deck_ref(User.PLAYER_1, deck_type),
                    })

    async def test_stadium_cannot_be_removed_via_direct_card_movement(self):
        stadium = DummyStadium("stad1", self.env, User.PLAYER_1, DeckType.STADIUM)
        self.env.stadium_cardholder.cards_holding.append(stadium)
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "card_movement", "card_id": stadium.cardID,
                "deck_from": {"owner": None, "deck_type": "STADIUM"},
                "deck_to": self._deck_ref(User.PLAYER_1, "HAND"),
            })

    async def test_bench_size_cap_is_enforced(self):
        # Fill the bench to MAX_BENCH_SIZE, then try to add one more from hand.
        from ...constants import MAX_BENCH_SIZE
        env2 = AVGEEnvironment(self.io, {
            User.PLAYER_1: [Dummy] * (MAX_BENCH_SIZE + 2),
            User.PLAYER_2: [Dummy],
        }, core_listeners())
        env2.turn = User.PLAYER_1
        p1 = env2.players[User.PLAYER_1]
        await put_into_play(env2, p1)
        for _ in range(MAX_BENCH_SIZE):
            await bench(env2, p1)
        self.assertEqual(len(p1.card_piles[DeckType.BENCH]), MAX_BENCH_SIZE)
        overflow_card = p1.card_piles[DeckType.DECK].cards_holding[0]
        # Move it to hand first (put_into_play/bench both pull straight from DECK, so nothing's
        # actually in HAND yet), then attempt the real HAND -> BENCH transfer the cap gates -
        # tagged PLAYER_CHOICE, matching what a real client-initiated card_movement produces
        # (AVGETransferValidityCheck only matches PLAYER_CHOICE-tagged transfers).
        setup_id = AVGEEngineID(None, ActionTypes.ENV, None)
        env2.push_packet(Packet(setup_id, [TransferCard(
            setup_id, overflow_card, p1.card_piles[DeckType.DECK], p1.card_piles[DeckType.HAND], env2,
        )]))
        await env2.engine.flush(lambda: False)

        player_choice_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        pkt = Packet(player_choice_id, [TransferCard(
            player_choice_id, overflow_card, p1.card_piles[DeckType.HAND], p1.card_piles[DeckType.BENCH], env2,
        )])
        env2.push_packet(pkt)
        await env2.engine.flush(lambda: False)

        self.assertIn(overflow_card, p1.card_piles[DeckType.HAND].cards_holding)
        self.assertEqual(len(p1.card_piles[DeckType.BENCH]), MAX_BENCH_SIZE)
        self.assertIsNotNone(pkt.rejection_reason)
        self.assert_player_notification(pkt.rejection_reason)

    async def test_a_tool_card_cannot_be_moved_to_the_bench_via_the_deserializer(self):
        # Unreachable with the old all-character preset pool (nothing but a character ever passed
        # the isinstance(card, (AVGECharacterCard, AVGEToolCard, AVGEStadiumCard)) filter with a
        # BENCH/ACTIVE_CARD destination available at all) - a mixed deck-builder deck makes it
        # reachable: a tool card is a legal card_movement subject (for OFFHAND), so it passes that
        # first filter, and must be separately rejected from landing on the bench/active slot.
        tool = DummyTool("tool1", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.append(tool)
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "card_movement", "card_id": tool.cardID,
                "deck_from": self._deck_ref(User.PLAYER_1, "HAND"),
                "deck_to": self._deck_ref(User.PLAYER_1, "BENCH"),
            })

    async def test_a_tool_card_cannot_be_moved_to_active_via_the_deserializer(self):
        tool = DummyTool("tool1", self.env, User.PLAYER_1, DeckType.BENCH)
        self.p1.card_piles[DeckType.BENCH].cards_holding.append(tool)
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "card_movement", "card_id": tool.cardID,
                "deck_from": self._deck_ref(User.PLAYER_1, "BENCH"),
                "deck_to": self._deck_ref(User.PLAYER_1, "ACTIVE_CARD"),
            })

    async def test_a_non_character_transfer_to_bench_is_regulate_failed_at_the_engine_level(self):
        # The authoritative guard, independent of io_adapter.py's deserializer - proves
        # AVGETransferValidityCheck itself rejects this for any PLAYER_CHOICE-tagged transfer,
        # matching the bench-size-cap test's own pattern above.
        tool = DummyTool("tool1", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.append(tool)

        player_choice_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        pkt = Packet(player_choice_id, [TransferCard(
            player_choice_id, tool, self.p1.card_piles[DeckType.HAND],
            self.p1.card_piles[DeckType.BENCH], self.env,
        )])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)

        self.assertIn(tool, self.p1.card_piles[DeckType.HAND].cards_holding)
        self.assertNotIn(tool, self.p1.card_piles[DeckType.BENCH].cards_holding)
        self.assertIsNotNone(pkt.rejection_reason)
        self.assert_player_notification(pkt.rejection_reason)

    async def test_a_non_stadium_transfer_to_stadium_is_regulate_failed_at_the_engine_level(self):
        # The authoritative engine-level guard for the STADIUM destination, mirroring the
        # BENCH/ACTIVE_CARD test above - without it, a mismatched card/destination pairing built
        # by any future TransferCard-constructing code path (not just a raw client request) would
        # hit TransferCard.act()'s isinstance assert instead of a clean rejection, crashing the
        # engine and ending the match with reason="server_error" for both players.
        player_choice_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        pkt = Packet(player_choice_id, [TransferCard(
            player_choice_id, self.p1_hand_card, self.p1.card_piles[DeckType.HAND],
            self.env.stadium_cardholder, self.env,
        )])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)

        self.assertIn(self.p1_hand_card, self.p1.card_piles[DeckType.HAND].cards_holding)
        self.assertNotIn(self.p1_hand_card, self.env.stadium_cardholder.cards_holding)
        self.assertIsNotNone(pkt.rejection_reason)
        self.assert_player_notification(pkt.rejection_reason)

    async def test_a_non_tool_transfer_to_offhand_is_regulate_failed_at_the_engine_level(self):
        # Same guard, for the OFFHAND destination.
        player_choice_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        pkt = Packet(player_choice_id, [TransferCard(
            player_choice_id, self.p1_hand_card, self.p1.card_piles[DeckType.HAND],
            self.p1_active.tools_attached, self.env,
        )])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)

        self.assertIn(self.p1_hand_card, self.p1.card_piles[DeckType.HAND].cards_holding)
        self.assertNotIn(self.p1_hand_card, self.p1_active.tools_attached.cards_holding)
        self.assertIsNotNone(pkt.rejection_reason)
        self.assert_player_notification(pkt.rejection_reason)


class PlayCardOwnershipTests(OwnershipAndLegalityTestBase):
    async def test_naming_opponents_supporter_is_rejected(self):
        supporter = DummySupporter("sup1", self.env, User.PLAYER_2, DeckType.HAND)
        self.p2.card_piles[DeckType.HAND].cards_holding.append(supporter)
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "play_card", "card_id": supporter.cardID,
            })

    async def test_naming_your_own_supporter_not_in_hand_is_rejected(self):
        supporter = DummySupporter("sup2", self.env, User.PLAYER_1, DeckType.DISCARD)
        self.p1.card_piles[DeckType.DISCARD].cards_holding.append(supporter)
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "play_card", "card_id": supporter.cardID,
            })

    async def test_legal_own_supporter_in_hand_still_works(self):
        supporter = DummySupporter("sup3", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.append(supporter)
        result = self.io.deserialize(Phase2IO(self.env.turn), {
            "kind": "play_card", "card_id": supporter.cardID,
        })
        self.assertIs(result.card, supporter)


class ActivateAbilityOwnershipTests(OwnershipAndLegalityTestBase):
    async def test_naming_opponents_character_is_rejected(self):
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "activate_ability", "card_id": self.p2_active.cardID,
            })


class EnergyAttachOwnershipTests(OwnershipAndLegalityTestBase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.p2_active.energy_tokens = [EnergyToken("p2_e1")]

    async def test_token_from_opponents_character_is_rejected(self):
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "energy_attach",
                "token_from": self.p2_active.cardID, "token_to": self.p1_active.cardID,
            })

    async def test_token_to_opponents_character_is_rejected(self):
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "energy_attach", "token_from": "ENV", "token_to": self.p2_active.cardID,
            })

    async def test_endpoint_not_in_play_is_rejected(self):
        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "energy_attach", "token_from": "ENV", "token_to": self.p1_hand_card.cardID,
            })

    async def test_legal_env_to_own_active_still_works(self):
        result = self.io.deserialize(Phase2IO(self.env.turn), {
            "kind": "energy_attach", "token_from": "ENV", "token_to": self.p1_active.cardID,
        })
        self.assertIs(result.token_to, self.p1_active)


class StadiumReplaceTests(OwnershipAndLegalityTestBase):
    async def test_playing_a_new_stadium_discards_the_old_one_to_its_owners_pile(self):
        outgoing = DummyStadium("stad_old", self.env, User.PLAYER_2, DeckType.STADIUM)
        self.env.stadium_cardholder.cards_holding.append(outgoing)
        incoming = DummyStadium("stad_new", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.append(incoming)

        # Tagged PLAYER_CHOICE, matching a real client-initiated stadium play -
        # AVGEStadiumReplaceReactor only matches PLAYER_CHOICE-tagged transfers.
        player_choice_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        pkt = Packet(player_choice_id, [TransferCard(
            player_choice_id, incoming, self.p1.card_piles[DeckType.HAND], self.env.stadium_cardholder, self.env,
        )])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)

        self.assertEqual(
            [c.cardID for c in self.env.stadium_cardholder.cards_holding], [incoming.cardID],
        )
        self.assertIn(outgoing, self.p2.card_piles[DeckType.DISCARD].cards_holding)


class ToolAttachTests(OwnershipAndLegalityTestBase):
    async def test_tool_attaches_to_the_named_characters_own_holder(self):
        from ...testing.helpers import DummyTool  # local import: only this test needs it
        tool = DummyTool("tool1", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.append(tool)

        result = self.io.deserialize(Phase2IO(self.env.turn), {
            "kind": "card_movement", "card_id": tool.cardID,
            "deck_from": {"owner": "PLAYER_1", "deck_type": "HAND"},
            "deck_to": {"owner": "PLAYER_1", "deck_type": "OFFHAND", "parent_card_id": self.p1_active.cardID},
        })
        self.assertIs(result.deck_to, self.p1_active.tools_attached)

    async def test_attaching_to_opponents_character_is_rejected_even_with_owner_me_claimed(self):
        from ...testing.helpers import DummyTool
        tool = DummyTool("tool2", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.append(tool)

        with self.assertRaises(IOException):
            self.io.deserialize(Phase2IO(self.env.turn), {
                "kind": "card_movement", "card_id": tool.cardID,
                "deck_from": {"owner": "PLAYER_1", "deck_type": "HAND"},
                # owner claims "me" (PLAYER_1) but parent_card_id names the opponent's character -
                # the two must be cross-checked, not just the wire-level owner field.
                "deck_to": {"owner": "PLAYER_1", "deck_type": "OFFHAND", "parent_card_id": self.p2_active.cardID},
            })

    async def test_second_tool_attach_is_rejected(self):
        from ...testing.helpers import DummyTool
        first = DummyTool("tool3", self.env, User.PLAYER_1, DeckType.HAND)
        second = DummyTool("tool4", self.env, User.PLAYER_1, DeckType.HAND)
        self.p1.card_piles[DeckType.HAND].cards_holding.extend([first, second])
        # Tagged PLAYER_CHOICE, matching a real client-initiated tool attach -
        # AVGETransferValidityCheck (which now also rejects a second tool) only matches
        # PLAYER_CHOICE-tagged transfers.
        player_choice_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)

        pkt1 = Packet(player_choice_id, [TransferCard(
            player_choice_id, first, self.p1.card_piles[DeckType.HAND], self.p1_active.tools_attached, self.env,
        )])
        self.env.push_packet(pkt1)
        await self.env.engine.flush(lambda: False)
        self.assertEqual(len(self.p1_active.tools_attached), 1)

        pkt2 = Packet(player_choice_id, [TransferCard(
            player_choice_id, second, self.p1.card_piles[DeckType.HAND], self.p1_active.tools_attached, self.env,
        )])
        self.env.push_packet(pkt2)
        await self.env.engine.flush(lambda: False)
        self.assertEqual(len(self.p1_active.tools_attached), 1)
        self.assertIn(second, self.p1.card_piles[DeckType.HAND].cards_holding)
        self.assert_player_notification("That character already has a tool attached.")


class KOWinConditionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent: list[tuple[User, dict]] = []

        async def send_message(user, message):
            self.sent.append((user, message))

        async def on_failure(user):
            pass

        self.io = NetworkIO(send_message, on_failure)
        self.env = AVGEEnvironment(self.io, {
            User.PLAYER_1: [Dummy],
            User.PLAYER_2: [Dummy],
        }, core_listeners())
        self.env.turn = User.PLAYER_1
        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]
        self.p1_active = await put_into_play(self.env, self.p1)

    async def test_winning_ko_still_discards_the_kod_character(self):
        # Regression test: the winning-KO branch used to omit transfer_card_out, leaving a
        # permanently un-discarded 0-HP character even though the game ends anyway. p1's active
        # card is what gets KO'd, so it's p2 (the opponent, credited with the KO) whose KO_COUNT
        # must already be one below the win threshold to reach the "winning KO" branch.
        self.p2.attributes[AVGEPlayerAttribute.KO_COUNT] = KOS_TO_WIN - 1

        # AVGEHPChangeReactor's KO handling explicitly excludes ENV-tagged HP changes
        # (`calling_action != ActionTypes.ENV`) - has to be tagged as a real attack would be.
        player_choice_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        pkt = Packet(player_choice_id, [AVGECardHPChangeEvent(
            player_choice_id, self.p1_active, 9999, AVGEAttributeModifier.SUBSTRACTIVE,
            self.p1_active.card_type, self.env,
        )])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)

        self.assertIn(self.p1_active, self.p1.card_piles[DeckType.DISCARD].cards_holding)
        self.assertNotIn(self.p1_active, self.p1.card_piles[DeckType.ACTIVE_CARD].cards_holding)


if __name__ == "__main__":
    unittest.main()
