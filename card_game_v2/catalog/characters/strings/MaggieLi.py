from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, PhasePickCard, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery, StringSelectionQuery, BroadcastIO, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class MaggieLi(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._midday_nap: MaggieLi._MiddayNap | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._SnapPizz()}), **({ActionTypes.PASSIVE: self._MiddayNapPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _MiddayNapPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Midday Nap",
                description="At the start of your turn, if not at full HP, may heal 10.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, MaggieLi)
            if card._midday_nap is None:
                card._midday_nap = MaggieLi._MiddayNap(card, card.env)
                card.add_listener(card._midday_nap)

    class _MiddayNap(AVGEEventReactor):
        def __init__(self, owner_card: MaggieLi, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, MaggieLi), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, PhasePickCard):
                return False
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            if self.owner_card.hp >= self.owner_card.max_hp:
                return False
            return self.env.turn == self.owner_card.owner

        async def react(self, event: Event) -> None:
            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, MaggieLi)
            location = "active"
            if self.owner_card.deck_type == DeckType.BENCH:
                bench = self.env.players[self.owner_card.owner].card_piles[DeckType.BENCH]
                if self.owner_card in bench.cards_holding:
                    location = f"bench {bench.cards_holding.index(self.owner_card) + 1}"
            choice = await self.env.report(StringSelectionQuery(
                self.owner_card.owner,
                f"Midday Nap: Heal 10 damage from Maggie Li ({location})?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                return
            await self.env.broadcast(BroadcastIO("Midday Nap: Maggie Li healed 10 HP", default_timeout))
            event.push_event([AVGECardHPChangeEvent(
                _id, self.owner_card, 10, AVGEAttributeModifier.ADDITIVE, CardType.STRING, self.env,
            )])

    class _SnapPizz(Attack):
        def __init__(self):
            super().__init__(
                name="Snap Pizz",
                description="Deal 20 damage to the opposing active. Strip up to 2 energy from a chosen opposing character.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            targets: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            _id = AVGEEngineID(card, self.action_type, MaggieLi)
            if not targets:
                await env.report(Notification(
                    card.owner, "Snap Pizz failed: no opposing characters are in play.", default_timeout,
                ), _id)
                return
            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Snap Pizz: Choose one opposing character to remove up to 2 energy from.",
                1,
                cast(list[AVGECard], targets),
                cast(list[AVGECard], targets),
                False,
                False,
            ), _id)
            chosen = picked[0]
            assert isinstance(chosen, AVGECharacterCard)

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]
            strip_count = min(2, len(chosen.energy_tokens))
            events.extend(AVGEEnergyTransfer(_id, chosen, env, env) for _ in range(strip_count))
            env.push_packet(Packet(_id, events))
