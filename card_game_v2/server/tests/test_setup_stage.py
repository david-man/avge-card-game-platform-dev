from __future__ import annotations

import asyncio
import unittest

from ...avge_abstracts.AVGECard import Ability
from ...avge_abstracts.AVGEDeck import DeckType, transfer_card
from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...catalog import registry
from ...catalog.characters.guitar.BenCherekIII import BenCherekIII
from ...catalog.characters.piano.JoshuaKou import JoshuaKou
from ...catalog.characters.strings.PhilipYao import PhilipYao
from ...catalog.characters.strings.YuelinHu import YuelinHu
from ...catalog.items.AVGEBirb import AVGEBirb
from ...constants import ActionTypes, AVGEPlayerAttribute, PER_TURN_SWAPS, SETUP_BLOCKED_CARDS, User
from ...core.AVGEIOManager import StringSelectionQuery
from ...core.EventCatalog import TransferCard
from ...testing.helpers import Dummy, DummySupporter, TestIO
from ..listeners import default_core_listeners
from ..session import GameSession
from ..setup_stage import SetupPromptError, build_final_environment, deal_preview


class FakeTransport:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        return


class PromptOnEntry(Dummy):
    class _Prompt(Ability):
        def __init__(self):
            super().__init__("Setup prompt", "Asks on entry.", ActionTypes.PASSIVE)

        async def __call__(self, action_card, acting_card):
            await action_card.env.report(StringSelectionQuery(
                action_card.owner, "Choose", 1, ["Yes"], ["Yes"], False, False,
            ), AVGEEngineID(action_card, ActionTypes.PASSIVE, PromptOnEntry))

    def base_actions(self):
        return {ActionTypes.PASSIVE: self._Prompt()}


class SetupStageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = GameSession("setup-test", lambda _id: None)
        self.transports = {user: FakeTransport() for user in User}
        for user in User:
            self.session.attach(user, self.transports[user])

    async def asyncTearDown(self):
        if not self.session.finished:
            await self.session.force_end(User.PLAYER_1, "concede")

    async def prepare(self, p1_deck: list[type] | None = None):
        self.session.seats[User.PLAYER_1].deck = p1_deck or [Dummy] * 20
        self.session.seats[User.PLAYER_2].deck = [Dummy] * 20
        self.session.configure_decks()
        await self.session.prepare()

    def active_id(self, user: User) -> str:
        return self.session.env.players[user].card_piles[DeckType.ACTIVE_CARD][0].cardID

    async def test_preview_is_five_cards_and_both_players_can_arrange_before_gameplay(self):
        await self.prepare()
        self.assertEqual(self.session.stage, "setup")
        self.assertIsNone(self.session.task)
        for user in User:
            player = self.session.env.players[user]
            self.assertEqual(len(player.card_piles[DeckType.HAND]), 5)
            self.assertEqual(len(player.card_piles[DeckType.BENCH]), 0)
        self.assertIsNone(await self.session.submit_setup(User.PLAYER_1, self.active_id(User.PLAYER_1), []))
        resumed = self.session.setup_start_message(User.PLAYER_1)
        self.assertTrue(resumed["self_ready"])
        self.assertEqual(resumed["blocked_card_classes"], sorted(SETUP_BLOCKED_CARDS))
        self.assertEqual(resumed["submitted_setup"]["active_card_id"], self.active_id(User.PLAYER_1))
        self.assertFalse(self.session.setup_start_message(User.PLAYER_2)["self_ready"])
        self.assertIsNone(self.session.task)
        self.assertEqual(
            [m["self_ready"] for m in self.transports[User.PLAYER_1].sent if m["type"] == "setup_state"],
            [True],
        )
        self.assertEqual(
            [m["opponent_ready"] for m in self.transports[User.PLAYER_2].sent if m["type"] == "setup_state"],
            [True],
        )
        self.assertIsNone(await self.session.submit_setup(User.PLAYER_2, self.active_id(User.PLAYER_2), []))
        self.assertEqual(self.session.stage, "playing")
        self.assertEqual(self.session.env.round, 0)
        self.assertEqual(len(self.session.env.players[User.PLAYER_1].card_piles[DeckType.HAND]), 5)
        self.assertEqual(len(self.session.env.players[User.PLAYER_1].card_piles[DeckType.DECK]), 14)
        await asyncio.sleep(0)
        self.assertFalse(any(
            m.get("io_type") == "PhaseChangedUpdate" and m.get("payload", {}).get("phase") == "draw"
            for transport in self.transports.values() for m in transport.sent
        ))

    async def test_rejects_foreign_duplicate_and_cards_outside_the_opening_deal(self):
        await self.prepare([Dummy, BenCherekIII, DummySupporter] + [Dummy] * 17)
        p1 = self.session.env.players[User.PLAYER_1]
        ben = next(card for card in p1.card_piles[DeckType.DECK] if isinstance(card, BenCherekIII))
        active = self.active_id(User.PLAYER_1)
        foreign = self.active_id(User.PLAYER_2)
        self.assertIn("opening character", await self.session.submit_setup(User.PLAYER_1, foreign, []))
        self.assertIn("only one", await self.session.submit_setup(User.PLAYER_1, active, [active]))
        self.assertIn("at most", await self.session.submit_setup(User.PLAYER_1, active, ["x"] * 6))
        self.assertIn("opening character", await self.session.submit_setup(User.PLAYER_1, active, [ben.cardID]))
        self.assertIn("opening character", await self.session.submit_setup(User.PLAYER_1, ben.cardID, []))
        noncharacter = p1.card_piles[DeckType.HAND][0]
        self.assertIn("opening character", await self.session.submit_setup(User.PLAYER_1, active, [noncharacter.cardID]))
        self.assertIsNone(self.session.setup_submissions[User.PLAYER_1])

    async def test_joshua_stays_in_deck_during_setup(self):
        await self.prepare([Dummy, JoshuaKou] + [Dummy] * 18)
        p1 = self.session.env.players[User.PLAYER_1]
        joshua = next(card for card in p1.card_piles[DeckType.DECK] if isinstance(card, JoshuaKou))
        hand = p1.card_piles[DeckType.HAND].cards_holding
        active = self.active_id(User.PLAYER_1)
        self.assertNotIn(joshua, hand)
        self.assertIn("opening character", await self.session.submit_setup(
            User.PLAYER_1, active, [joshua.cardID, hand[0].cardID],
        ))
        self.assertIn("opening character", await self.session.submit_setup(
            User.PLAYER_1, active, [joshua.cardID],
        ))
        self.assertIn("opening character", await self.session.submit_setup(User.PLAYER_1, joshua.cardID, []))

    async def test_blocked_characters_are_skipped_for_the_preview_active(self):
        for card_class in (BenCherekIII, JoshuaKou):
            with self.subTest(character=card_class.__name__):
                session = GameSession(f"active-{card_class.__name__}", lambda _id: None)
                session.seats[User.PLAYER_1].deck = [card_class, Dummy] + [Dummy] * 18
                session.seats[User.PLAYER_2].deck = [Dummy] * 20
                session.configure_decks()
                await session.prepare()
                player = session.env.players[User.PLAYER_1]
                self.assertIsInstance(player.card_piles[DeckType.ACTIVE_CARD][0], Dummy)
                self.assertFalse(any(isinstance(card, card_class) for card in player.card_piles[DeckType.HAND]))
                self.assertTrue(any(isinstance(card, card_class) for card in player.card_piles[DeckType.DECK]))
                active_1 = player.card_piles[DeckType.ACTIVE_CARD][0].cardID
                active_2 = session.env.players[User.PLAYER_2].card_piles[DeckType.ACTIVE_CARD][0].cardID
                self.assertIsNone(await session.submit_setup(User.PLAYER_1, active_1, []))
                self.assertIsNone(await session.submit_setup(User.PLAYER_2, active_2, []))
                final = session.env.players[User.PLAYER_1]
                self.assertFalse(any(isinstance(card, card_class) for card in final.card_piles[DeckType.HAND]))
                self.assertTrue(any(isinstance(card, card_class) for card in final.card_piles[DeckType.DECK]))
                await session.force_end(User.PLAYER_1, "concede")

    async def test_yuelin_can_start_with_birbs_in_the_opening_hand(self):
        await self.prepare([YuelinHu] + [AVGEBirb] * 19)
        active = self.active_id(User.PLAYER_1)
        self.assertIsNone(await self.session.submit_setup(User.PLAYER_1, active, []))
        self.assertIsNone(await self.session.submit_setup(
            User.PLAYER_2, self.active_id(User.PLAYER_2), [],
        ))
        player = self.session.env.players[User.PLAYER_1]
        self.assertEqual(player.card_piles[DeckType.ACTIVE_CARD][0].cardID, active)
        self.assertEqual(len(player.card_piles[DeckType.HAND]), 5)
        self.assertEqual(self.session.stage, "playing")

    async def test_eligible_passive_runs_once_on_confirmed_bench(self):
        await self.prepare([Dummy, PhilipYao] + [Dummy] * 18)
        p1 = self.session.env.players[User.PLAYER_1]
        philip_id = p1.card_piles[DeckType.HAND][0].cardID
        self.assertFalse(any(type(listener).__name__ == "_RotationReactor" for listener in self.session.env.engine.listeners))
        await self.session.submit_setup(User.PLAYER_1, self.active_id(User.PLAYER_1), [philip_id])
        await self.session.submit_setup(User.PLAYER_2, self.active_id(User.PLAYER_2), [])
        bench = self.session.env.players[User.PLAYER_1].card_piles[DeckType.BENCH]
        self.assertEqual([card.cardID for card in bench.cards_holding], [philip_id])
        listeners = [listener for listener in self.session.env.engine.listeners
                     if type(listener).__name__ == "_RotationReactor"]
        self.assertEqual(len(listeners), 1)
        self.assertEqual(len(self.session.env.players[User.PLAYER_1].card_piles[DeckType.HAND]), 4)

    async def test_swapping_active_during_setup_costs_nothing_and_keeps_old_active_on_bench(self):
        await self.prepare([Dummy, PhilipYao] + [Dummy] * 18)
        old_active = self.active_id(User.PLAYER_1)
        new_active = self.session.env.players[User.PLAYER_1].card_piles[DeckType.HAND][0].cardID
        await self.session.submit_setup(User.PLAYER_1, new_active, [old_active])
        await self.session.submit_setup(User.PLAYER_2, self.active_id(User.PLAYER_2), [])
        player = self.session.env.players[User.PLAYER_1]
        self.assertEqual(player.card_piles[DeckType.ACTIVE_CARD][0].cardID, new_active)
        self.assertEqual(player.card_piles[DeckType.BENCH][0].cardID, old_active)
        self.assertEqual(len(player.card_piles[DeckType.ACTIVE_CARD][0].energy_tokens), 0)
        self.assertEqual(player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN], PER_TURN_SWAPS)

        transfers = [event for chapter in self.session.env.engine.history.records
                     for _, event in chapter if isinstance(event, TransferCard)]
        new_active_path = [
            (event.deck_from.deck_type, event.deck_to.deck_type, event.id.calling_action)
            for event in transfers if event.card.cardID == new_active
        ]
        self.assertEqual(new_active_path, [
            (DeckType.DECK, DeckType.HAND, ActionTypes.ENV),
            (DeckType.HAND, DeckType.BENCH, ActionTypes.PLAYER_CHOICE),
            (DeckType.BENCH, DeckType.ACTIVE_CARD, ActionTypes.ENV),
        ])
        old_active_path = [
            (event.deck_from.deck_type, event.deck_to.deck_type)
            for event in transfers if event.card.cardID == old_active
        ]
        self.assertEqual(old_active_path, [
            (DeckType.DECK, DeckType.HAND),
            (DeckType.HAND, DeckType.BENCH),
        ])
        self.assertEqual(sum(type(listener).__name__ == "_RotationReactor"
                             for listener in self.session.env.engine.listeners), 1)

    async def test_hand_to_bench_passive_prompts_are_detected(self):
        for blocked in (BenCherekIII, JoshuaKou):
            with self.subTest(character=blocked.__name__):
                decks = {
                    User.PLAYER_1: [Dummy, blocked] + [Dummy] * 18,
                    User.PLAYER_2: [Dummy] * 20,
                }
                preview = AVGEEnvironment(TestIO(), decks, default_core_listeners())
                deal_preview(preview)
                p1, p2 = preview.players[User.PLAYER_1], preview.players[User.PLAYER_2]
                # Bypass the deal filter to prove the blocked passive would request input.
                blocked_card = next(card for card in p1.card_piles[DeckType.DECK] if isinstance(card, blocked))
                displaced = p1.card_piles[DeckType.HAND][0]
                transfer_card(displaced, p1.card_piles[DeckType.HAND], p1.card_piles[DeckType.DECK])
                displaced.deck_type = DeckType.DECK
                transfer_card(blocked_card, p1.card_piles[DeckType.DECK], p1.card_piles[DeckType.HAND])
                blocked_card.deck_type = DeckType.HAND
                hand = p1.card_piles[DeckType.HAND].cards_holding
                bench_ids = [blocked_card.cardID]
                if blocked is JoshuaKou:
                    bench_ids.extend(card.cardID for card in hand[:2])
                submissions = {
                    User.PLAYER_1: {
                        "active_card_id": p1.card_piles[DeckType.ACTIVE_CARD][0].cardID,
                        "bench_card_ids": bench_ids,
                    },
                    User.PLAYER_2: {
                        "active_card_id": p2.card_piles[DeckType.ACTIVE_CARD][0].cardID,
                        "bench_card_ids": [],
                    },
                }
                with self.assertRaises(SetupPromptError):
                    await build_final_environment(preview, decks, submissions)

    async def test_full_bench_still_allows_the_active_to_pass_through_bench(self):
        await self.prepare()
        p1 = self.session.env.players[User.PLAYER_1]
        original_active = p1.card_piles[DeckType.ACTIVE_CARD][0].cardID
        hand_ids = [card.cardID for card in p1.card_piles[DeckType.HAND].cards_holding]
        self.assertIsNone(await self.session.submit_setup(
            User.PLAYER_1, hand_ids[0], [original_active, *hand_ids[1:]],
        ))
        self.assertIsNone(await self.session.submit_setup(
            User.PLAYER_2, self.active_id(User.PLAYER_2), [],
        ))
        final = self.session.env.players[User.PLAYER_1]
        self.assertEqual(final.card_piles[DeckType.ACTIVE_CARD][0].cardID, hand_ids[0])
        self.assertEqual(len(final.card_piles[DeckType.BENCH]), 5)
        self.assertEqual(len(final.card_piles[DeckType.HAND]), 0)
        self.assertEqual(final.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN], PER_TURN_SWAPS)

    async def test_every_catalog_character_can_enter_its_allowed_setup_positions(self):
        for entry in registry.all_entries():
            if entry.kind is not registry.CardKind.CHARACTER or entry.class_name in SETUP_BLOCKED_CARDS:
                continue
            for position in ("active", "bench"):
                with self.subTest(character=entry.class_name, position=position):
                    decks = {
                        User.PLAYER_1: [Dummy, entry.card_class] + [Dummy] * 18,
                        User.PLAYER_2: [Dummy] * 20,
                    }
                    preview = AVGEEnvironment(TestIO(), decks, default_core_listeners())
                    deal_preview(preview)
                    p1, p2 = preview.players[User.PLAYER_1], preview.players[User.PLAYER_2]
                    starter = p1.card_piles[DeckType.ACTIVE_CARD][0].cardID
                    candidate = p1.card_piles[DeckType.HAND][0].cardID
                    other_hand_ids = [card.cardID for card in p1.card_piles[DeckType.HAND][1:]]
                    submissions = {
                        User.PLAYER_1: {
                            "active_card_id": candidate if position == "active" else starter,
                            "bench_card_ids": [starter if position == "active" else candidate,
                                               *other_hand_ids],
                        },
                        User.PLAYER_2: {
                            "active_card_id": p2.card_piles[DeckType.ACTIVE_CARD][0].cardID,
                            "bench_card_ids": [],
                        },
                    }
                    final = await build_final_environment(preview, decks, submissions)
                    self.assertEqual(len(final.players[User.PLAYER_1].card_piles[DeckType.BENCH]), 5)
                    if position == "active":
                        self.assertEqual(final.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD][0].cardID,
                                         candidate)

    async def test_unexpected_prompt_discards_candidate_and_unlocks_both(self):
        await self.prepare([Dummy, PromptOnEntry] + [Dummy] * 18)
        preview = self.session.env
        prompt_id = preview.players[User.PLAYER_1].card_piles[DeckType.HAND][0].cardID
        await self.session.submit_setup(User.PLAYER_1, self.active_id(User.PLAYER_1), [prompt_id])
        self.assertIsNone(await self.session.submit_setup(User.PLAYER_2, self.active_id(User.PLAYER_2), []))
        for transport in self.transports.values():
            errors = [m for m in transport.sent if m["type"] == "error"]
            self.assertEqual(errors[-1]["code"], "setup_finalize_failed")
        self.assertIs(self.session.env, preview)
        self.assertEqual(self.session.stage, "setup")
        self.assertTrue(all(choice is None for choice in self.session.setup_submissions.values()))
        self.assertFalse(any(m["type"] == "game_start" for t in self.transports.values() for m in t.sent))
        self.assertIsNone(await self.session.submit_setup(User.PLAYER_1, self.active_id(User.PLAYER_1), []))
        self.assertIsNone(await self.session.submit_setup(User.PLAYER_2, self.active_id(User.PLAYER_2), []))
        self.assertEqual(self.session.stage, "playing")
        self.assertTrue(all(any(m["type"] == "game_start" for m in t.sent)
                            for t in self.transports.values()))


if __name__ == "__main__":
    unittest.main()
