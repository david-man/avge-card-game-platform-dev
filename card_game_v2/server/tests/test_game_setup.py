import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEEventListener import AVGEEventReactor
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...catalog import registry
from ...catalog.characters.guitar.BenCherekIII import BenCherekIII
from ...catalog.items.AVGEBirb import AVGEBirb
from ...constants import User, ActionTypes, AVGEPlayerAttribute, EngineGroup, INITIAL_HAND_SIZE, NO_STARTING_ACTIVE_CARDS
from ...core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer
from ...avge_abstracts.AVGECard import CardType
from ...constants import AVGEAttributeModifier
from ...engine.event import Packet
from ...testing.helpers import Dummy, DummySupporter, TestIO, core_listeners
from .. import serialization
from ..decks import CARDS_PER_DECK
from ..game_setup import perform_initial_setup
from ..io_adapter import NetworkIO
from ...core.AVGEIOManager import HPChangeUpdate


class PerformInitialSetupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent: list[tuple[User, dict]] = []

        async def send_message(user, message):
            self.sent.append((user, message))

        async def on_failure(user):
            pass

        self.io = NetworkIO(send_message, on_failure)
        self.env = AVGEEnvironment(self.io, {
            User.PLAYER_1: [Dummy] * CARDS_PER_DECK,
            User.PLAYER_2: [Dummy] * CARDS_PER_DECK,
        }, core_listeners())
        self.env.turn = User.PLAYER_1

    async def test_deals_active_and_hand_for_both_players(self):
        await perform_initial_setup(self.env)
        for user in (User.PLAYER_1, User.PLAYER_2):
            player = self.env.players[user]
            self.assertEqual(len(player.card_piles[DeckType.ACTIVE_CARD]), 1)
            self.assertEqual(len(player.card_piles[DeckType.HAND]), INITIAL_HAND_SIZE)
            self.assertEqual(len(player.card_piles[DeckType.DECK]), CARDS_PER_DECK - 1 - INITIAL_HAND_SIZE)

    async def test_dealt_cards_are_distinct(self):
        await perform_initial_setup(self.env)
        player = self.env.players[User.PLAYER_1]
        active = player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        hand_ids = {c.cardID for c in player.card_piles[DeckType.HAND].cards_holding}
        self.assertNotIn(active.cardID, hand_ids)
        self.assertEqual(len(hand_ids), INITIAL_HAND_SIZE)

    async def test_catalog_event_broadcasts_after_setup(self):
        await perform_initial_setup(self.env)
        self.assertTrue(self.env.event_updates_enabled)
        self.assertIsNotNone(self.env.engine.on_packet_failed)

        target = self.env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
            _id, target, 15, AVGEAttributeModifier.SUBSTRACTIVE, CardType.ALL, self.env,
        )]))
        await self.env.engine.flush(lambda: False)

        updates = [m for _, m in self.sent if m.get("io_type") == "HPChangeUpdate"]
        self.assertEqual(len(updates), 2)  # broadcast to both players
        self.assertEqual(updates[0]["type"], "event_update")
        self.assertEqual(updates[0]["payload"]["magnitude"], 15)

    async def test_initial_deal_sends_no_event_updates(self):
        await perform_initial_setup(self.env)
        self.assertEqual(self.sent, [])

    async def test_board_update_precedes_post_core_reactor(self):
        await perform_initial_setup(self.env)
        sent = self.sent

        class ObserveHit(AVGEEventReactor):
            def match(self, event):
                return isinstance(event, AVGECardHPChangeEvent)

            async def react(self, event):
                self.assert_sent = any(
                    message.get("io_type") == "HPChangeUpdate" for _, message in sent
                )
                return None

        observer = ObserveHit(
            AVGEEngineID(None, ActionTypes.ENV, None),
            self.env,
            EngineGroup.INTERNAL_4,
        )
        self.env.engine.add_listener(observer)
        target = self.env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
            _id, target, 15, AVGEAttributeModifier.SUBSTRACTIVE, CardType.ALL, self.env,
        )]))
        await self.env.engine.flush(lambda: False)
        self.assertTrue(observer.assert_sent)
        self.assertEqual(sum(
            message.get("io_type") == "HPChangeUpdate" for _, message in self.sent
        ), 2)

    async def test_regulate_fail_broadcasts_the_regulators_reason_and_a_resync_snapshot(self):
        '''AVGETokenTransferCheck (core/CoreListeners.py) REGULATE_FAILs an AVGEEnergyTransfer
        when the destination player has already used up their once-per-turn energy attach - the
        exact "attach energy with none available" scenario used to use the *source* card having
        no energy instead, but that branch is REGULATE_IGNORE now (a legitimately-already-empty
        source is a no-op, not a failure - see A6), so this uses the still-REGULATE_FAIL branch
        instead, purely as a convenient trigger for what this test actually covers: the live
        per-event broadcast (none here, since nothing committed before the failure) plus the
        single combined ActionRejectedUpdate carrying both the regulator's own reason and a
        post-rollback state snapshot.'''
        await perform_initial_setup(self.env)
        p1 = self.env.players[User.PLAYER_1]
        active = p1.card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        p1.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] = 0

        _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        self.env.push_packet(Packet(_id, [AVGEEnergyTransfer(_id, self.env, active, self.env)]))
        await self.env.engine.flush(lambda: False)

        rejected = [m for _, m in self.sent if m.get("io_type") == "ActionRejectedUpdate"]
        self.assertEqual(len(rejected), 2)  # broadcast to both players
        payload = rejected[0]["payload"]
        self.assertEqual(payload["reason"], "You've already attached energy this turn.")
        self.assertEqual(payload["snapshot"], serialization.snapshot(self.env))

    async def test_extra_on_packet_failed_runs_alongside_the_broadcast(self):
        '''Regression test for the hook-chaining refactor: on_packet_failed used to get set here
        and then wrapped a second time by GameSession._wire_packet_rejection_logging(), with
        correctness depending on call order between two separate files. extra_on_packet_failed is
        now composed in at the single call site instead - this proves both the broadcast and a
        caller-supplied extra hook actually fire, in order, on the same rejection.'''
        calls: list[str] = []

        async def extra(packet: Packet) -> None:
            calls.append("extra")

        await perform_initial_setup(self.env, extra_on_packet_failed=extra)
        p1 = self.env.players[User.PLAYER_1]
        active = p1.card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        p1.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] = 0

        _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        self.env.push_packet(Packet(_id, [AVGEEnergyTransfer(_id, self.env, active, self.env)]))
        await self.env.engine.flush(lambda: False)

        rejected = [m for _, m in self.sent if m.get("io_type") == "ActionRejectedUpdate"]
        self.assertEqual(len(rejected), 2)  # the broadcast still ran
        self.assertEqual(calls, ["extra"])  # and the extra hook ran too


class MixedDeckDealingTests(unittest.IsolatedAsyncioTestCase):
    '''Covers the fix for decks that can now contain non-character cards - _deal_starting_hand
    must find A character for the active slot, not just assume deck.cards_holding[0] is one.'''

    async def asyncSetUp(self):
        self.sent: list[tuple[User, dict]] = []

        async def send_message(user, message):
            self.sent.append((user, message))

        async def on_failure(user):
            pass

        self.io = NetworkIO(send_message, on_failure)

    def _make_env(self, p1_deck: list[type], p2_deck: list[type] | None = None) -> AVGEEnvironment:
        env = AVGEEnvironment(self.io, {
            User.PLAYER_1: p1_deck,
            User.PLAYER_2: p2_deck if p2_deck is not None else [Dummy] * CARDS_PER_DECK,
        }, core_listeners())
        env.turn = User.PLAYER_1
        return env

    async def test_character_not_at_the_top_of_the_deck_still_becomes_active(self):
        deck = [DummySupporter] * 7 + [Dummy] + [DummySupporter] * (CARDS_PER_DECK - 8)
        env = self._make_env(deck)
        await perform_initial_setup(env)
        active = env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding
        self.assertEqual(len(active), 1)
        self.assertIsInstance(active[0], Dummy)

    async def test_character_only_at_the_very_end_of_the_deck_still_becomes_active(self):
        deck = [DummySupporter] * (CARDS_PER_DECK - 1) + [Dummy]
        env = self._make_env(deck)
        await perform_initial_setup(env)
        active = env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding
        self.assertEqual(len(active), 1)
        self.assertIsInstance(active[0], Dummy)

    async def test_hand_and_deck_sizes_unaffected_by_where_the_character_was(self):
        deck = [DummySupporter] * (CARDS_PER_DECK - 1) + [Dummy]
        env = self._make_env(deck)
        await perform_initial_setup(env)
        player = env.players[User.PLAYER_1]
        self.assertEqual(len(player.card_piles[DeckType.HAND]), INITIAL_HAND_SIZE)
        self.assertEqual(
            len(player.card_piles[DeckType.DECK]), CARDS_PER_DECK - 1 - INITIAL_HAND_SIZE,
        )

    async def test_no_character_in_the_deck_raises_a_clear_error(self):
        deck = [DummySupporter] * CARDS_PER_DECK
        env = self._make_env(deck)
        with self.assertRaises(ValueError):
            await perform_initial_setup(env)

    async def test_no_card_is_duplicated_or_lost_across_active_hand_and_deck(self):
        deck = [DummySupporter] * 7 + [Dummy] + [DummySupporter] * (CARDS_PER_DECK - 8)
        env = self._make_env(deck)
        original_ids = {c.cardID for c in env.players[User.PLAYER_1].card_piles[DeckType.DECK].cards_holding}
        await perform_initial_setup(env)
        player = env.players[User.PLAYER_1]
        after_ids = (
            {c.cardID for c in player.card_piles[DeckType.ACTIVE_CARD].cards_holding}
            | {c.cardID for c in player.card_piles[DeckType.HAND].cards_holding}
            | {c.cardID for c in player.card_piles[DeckType.DECK].cards_holding}
        )
        self.assertEqual(original_ids, after_ids)
        self.assertEqual(len(original_ids), CARDS_PER_DECK)

    async def test_excluded_character_is_skipped_even_when_it_is_first_in_the_deck(self):
        deck = [BenCherekIII, Dummy] + [DummySupporter] * (CARDS_PER_DECK - 2)
        env = self._make_env(deck)
        await perform_initial_setup(env)
        active = env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding
        self.assertEqual(len(active), 1)
        self.assertIsInstance(active[0], Dummy)

    async def test_deck_whose_only_characters_are_excluded_raises_a_clear_error(self):
        deck = [BenCherekIII] + [DummySupporter] * (CARDS_PER_DECK - 1)
        env = self._make_env(deck)
        with self.assertRaises(ValueError):
            await perform_initial_setup(env)


class _PromptRecordingIO(TestIO):
    def __init__(self):
        super().__init__()
        self.prompts: list[object] = []

    async def send(self, user, io):
        self.prompts.append(io)
        await super().send(user, io)


class StartingActivePromptSweepTests(unittest.IsolatedAsyncioTestCase):
    '''The opening deal runs before the clients know the game started, so no character allowed to start
    (see constants.NO_STARTING_ACTIVE_CARDS) may ask the player anything during it.
    A deck of [character] + AVGE Birbs makes that character the starter and fills the opening hand
    with the card that Yuelin Hu's draw-reactor watches for.'''

    async def _prompts_for_starter(self, starter: type, *, as_player: User) -> list[object]:
        io = _PromptRecordingIO()
        filler = [Dummy] * CARDS_PER_DECK
        decks = {User.PLAYER_1: list(filler), User.PLAYER_2: list(filler)}
        decks[as_player] = [starter] + [AVGEBirb] * (CARDS_PER_DECK - 1)
        env = AVGEEnvironment(io, decks, core_listeners())
        env.turn = as_player
        await perform_initial_setup(env)
        self.assertIsInstance(
            env.players[as_player].card_piles[DeckType.ACTIVE_CARD].cards_holding[0], starter,
        )
        return io.prompts

    async def test_every_character_allowed_to_start_deploys_without_a_prompt(self):
        for entry in registry.all_entries():
            if entry.kind is not registry.CardKind.CHARACTER:
                continue
            if entry.class_name in NO_STARTING_ACTIVE_CARDS:
                continue
            for as_player in (User.PLAYER_1, User.PLAYER_2):
                with self.subTest(character=entry.class_name, player=as_player.name):
                    prompts = await self._prompts_for_starter(entry.card_class, as_player=as_player)
                    self.assertEqual(prompts, [])
