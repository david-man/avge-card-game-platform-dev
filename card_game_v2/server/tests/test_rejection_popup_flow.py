"""Player-choice rejection popups and the packet resync that follows them."""
from __future__ import annotations

import asyncio
import contextlib
import unittest

from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, AVGEPlayerAttribute, User
from ...core.EventCatalog import AtkPhase, PlayCharacterCard, PlayNonCharacterCard, TransferCard
from ...engine.event import Packet
from ...testing.helpers import Attacker, Dummy, DummySupporter, core_listeners
from ...catalog.stadiums.MainHall import MainHall
from ...catalog.supporters.Michelle import Michelle
from ..decks import CARDS_PER_DECK
from ..game_setup import perform_initial_setup
from ..io_adapter import NetworkIO


class RejectionPopupFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.sent: list[tuple[User, dict]] = []

        async def send_message(user: User, message: dict) -> None:
            self.sent.append((user, message))

        async def on_failure(user: User) -> None:
            self.fail(f"Unexpected transport failure for {user}")

        self.io = NetworkIO(send_message, on_failure)
        self.env = AVGEEnvironment(self.io, {
            User.PLAYER_1: [Attacker] * CARDS_PER_DECK,
            User.PLAYER_2: [Dummy] * CARDS_PER_DECK,
        }, core_listeners())
        self.env.turn = User.PLAYER_1
        await perform_initial_setup(self.env)
        self.active = self.env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD][0]
        self.flush_task: asyncio.Task[None] | None = None

    async def asyncTearDown(self) -> None:
        if self.flush_task is not None and not self.flush_task.done():
            self.flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.flush_task

    async def _wait_for(self, io_type: str, count: int = 1) -> list[tuple[User, dict]]:
        for _ in range(200):
            matches = [(user, message) for user, message in self.sent if message.get("io_type") == io_type]
            if len(matches) >= count:
                return matches
            await asyncio.sleep(0)
        self.fail(f"Expected {count} {io_type} message(s)")

    async def _assert_rejected_with_popup(self, event, expected_reason: str) -> None:
        self.sent.clear()
        self.env.push_packet(Packet(event.id, [event]))
        task = asyncio.create_task(self.env.engine.flush(lambda: False))
        notice = (await self._wait_for("Notification"))[0]
        self.assertEqual(notice[0], User.PLAYER_1)
        self.assertEqual(notice[1]["payload"]["message"], expected_reason)
        self.assertFalse(any(m.get("io_type") == "ActionRejectedUpdate" for _, m in self.sent))
        await self.io.receive(User.PLAYER_1, {})
        await asyncio.wait_for(task, 1)
        rejections = await self._wait_for("ActionRejectedUpdate", 2)
        self.assertEqual({user for user, _ in rejections}, set(User))
        self.assertEqual(rejections[0][1]["payload"]["reason"], expected_reason)

    async def test_insufficient_energy_attack_popups_then_resyncs_and_reprompts(self) -> None:
        self.env.round = 1
        self.assertEqual(len(self.active.energy_tokens), 0)
        initial_attacks = self.env.players[User.PLAYER_1].attributes[AVGEPlayerAttribute.ATTACKS_LEFT]
        phase_id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(phase_id, [AtkPhase(phase_id, self.env)]))
        self.flush_task = asyncio.create_task(self.env.engine.flush(lambda: False))

        await self._wait_for("AtkPhaseIO")
        await self.io.receive(User.PLAYER_1, {"action": "ATK_1"})
        notices = await self._wait_for("Notification")
        self.assertEqual(notices[0][0], User.PLAYER_1)
        self.assertEqual(notices[0][1]["payload"], {
            "message": "Not enough energy attached to use that.", "timeout": 5,
        })
        self.assertFalse(any(m.get("io_type") == "ActionRejectedUpdate" for _, m in self.sent))

        await self.io.receive(User.PLAYER_1, {})  # acknowledge the popup
        rejections = await self._wait_for("ActionRejectedUpdate", 2)
        self.assertEqual({user for user, _ in rejections}, set(User))
        self.assertEqual(rejections[0][1]["payload"]["reason"], notices[0][1]["payload"]["message"])
        await self._wait_for("AtkPhaseIO", 2)
        self.assertEqual(
            self.env.players[User.PLAYER_1].attributes[AVGEPlayerAttribute.ATTACKS_LEFT],
            initial_attacks,
        )
        self.assertIs(self.env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD][0], self.active)

    async def test_internal_invalid_action_does_not_create_popup_or_rejection(self) -> None:
        effect_id = AVGEEngineID(None, ActionTypes.PASSIVE, None)
        self.env.push_packet(Packet(effect_id, [
            PlayCharacterCard(effect_id, self.active, ActionTypes.ATK_2, 0, self.env),
        ]))
        await self.env.engine.flush(lambda: False)
        self.assertFalse(any(
            m.get("io_type") in {"Notification", "ActionRejectedUpdate"}
            for _, m in self.sent
        ))

    async def test_stadium_and_card_action_rejections_use_their_existing_reasons(self) -> None:
        choice_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        hand = self.env.players[User.PLAYER_1].card_piles[DeckType.HAND]
        stadium = MainHall("restricted-stadium", self.env, User.PLAYER_1, DeckType.HAND)
        hand.cards_holding.append(stadium)
        await self._assert_rejected_with_popup(
            TransferCard(choice_id, stadium, hand, self.env.stadium_cardholder, self.env),
            "Main Hall cannot be played on the first turn.",
        )
        self.assertIn(stadium, hand.cards_holding)

        await self._assert_rejected_with_popup(
            PlayCharacterCard(choice_id, self.active, ActionTypes.ATK_2, 0, self.env),
            "That card doesn't have this action.",
        )

        restricted_supporter = Michelle("restricted-supporter", self.env, User.PLAYER_1, DeckType.HAND)
        hand.cards_holding.append(restricted_supporter)
        await self._assert_rejected_with_popup(
            PlayNonCharacterCard(choice_id, restricted_supporter, self.env),
            "Michelle cannot be played on the first turn.",
        )

        supporter = DummySupporter("second-supporter", self.env, User.PLAYER_1, DeckType.HAND)
        hand.cards_holding.append(supporter)
        self.env.players[User.PLAYER_1].attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] = 0
        await self._assert_rejected_with_popup(
            PlayNonCharacterCard(choice_id, supporter, self.env),
            "You've already played a supporter card this turn.",
        )


if __name__ == "__main__":
    unittest.main()
