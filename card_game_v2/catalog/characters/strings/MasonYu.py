from __future__ import annotations

import random
from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, StatusEffect, AVGEStatusModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardStatusChange, AVGEEnergyTransfer, TransferCard, PlayCharacterCard
from ....core.AVGEIOManager import CardSelectionQuery, StringSelectionQuery, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class MasonYu(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Arrangement(), ActionTypes.ATK_2: self._WePlayGod()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Arrangement(Attack):
        def __init__(self):
            super().__init__(
                name="Arrangement",
                description="Choose one of your benched characters to give the ARRANGER status.",
                action_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            bench: list[AVGECharacterCard] = [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            _id = AVGEEngineID(card, self.action_type, MasonYu)
            if not bench:
                await env.report(Notification(
                    card.owner,
                    "Arrangement failed: no benched characters on your side.", default_timeout,
                ), _id)
                return

            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Arrangement: Choose one benched character to give Arranger status.",
                1,
                cast(list[AVGECard], bench),
                cast(list[AVGECard], bench),
                False,
                False,
            ), _id)
            chosen = picked[0]
            assert isinstance(chosen, AVGECharacterCard)

            env.push_packet(Packet(_id, [AVGECardStatusChange(
                _id, chosen, card, StatusEffect.ARRANGER, AVGEStatusModifier.ADD, env,
            )]))

    class _WePlayGod(Attack):
        '''Choose any two characters in play (either side). One is randomly selected to
        be swapped into their own controller's active slot (if not already there); the
        other is forced to execute one of its own attacks - "acting as" Mason (Mason is
        passed as the id's calling_card, which `PlayCharacterCard.act()` uses as the
        acting card), matching v1's `PlayCharacterCard(other, action_type, ATK_2,
        card)` exactly, so the borrowed attack's own targeting (usually "the opposing
        active") resolves relative to Mason's owner, not the borrowed character's.'''

        def __init__(self):
            super().__init__(
                name="We Play God",
                description="Discard 1 of your own energy. Choose any two characters in play - one is randomly swapped into their controller's active slot, the other is forced to use one of its own attacks (acting as you).",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            _id = AVGEEngineID(card, self.action_type, MasonYu)

            if len(card.energy_tokens) == 0:
                await env.report(Notification(
                    card.owner,
                    "We Play God didn't play: Mason Yu has no energy to discard.", default_timeout,
                ), _id)
                return

            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            chars_in_play: list[AVGECharacterCard] = [
                c
                for p in (player, opponent)
                for pile in (DeckType.ACTIVE_CARD, DeckType.BENCH)
                for c in p.card_piles[pile]
                if isinstance(c, AVGECharacterCard)
            ]

            picked = await env.report(CardSelectionQuery(
                card.owner,
                "We Play God: Choose any two characters in play.",
                2,
                cast(list[AVGECard], chars_in_play),
                cast(list[AVGECard], chars_in_play),
                False,
                False,
            ), _id)
            chosen_1, chosen_2 = picked[0], picked[1]
            assert isinstance(chosen_1, AVGECharacterCard) and isinstance(chosen_2, AVGECharacterCard)

            random_selected = random.choice([chosen_1, chosen_2])
            other = chosen_2 if random_selected is chosen_1 else chosen_1

            available_names = [
                other.actions[a].name for a in (ActionTypes.ATK_1, ActionTypes.ATK_2) if a in other.actions
            ]
            if not available_names:
                return

            attack_choice = (await env.report(StringSelectionQuery(
                card.owner,
                f"We Play God: Choose an attack from {other}.",
                1,
                available_names,
                available_names,
                False,
                False,
            ), _id))[0]
            action_type = (
                ActionTypes.ATK_1
                if ActionTypes.ATK_1 in other.actions and other.actions[ActionTypes.ATK_1].name == attack_choice
                else ActionTypes.ATK_2
            )

            def gen_swap() -> list[Event | Generator]:
                if random_selected.deck_type != DeckType.BENCH:
                    return []
                owner_player = env.players[random_selected.owner]
                active_deck = owner_player.card_piles[DeckType.ACTIVE_CARD]
                bench_deck = owner_player.card_piles[DeckType.BENCH]
                current_active = active_deck[0]
                return [
                    TransferCard(_id, random_selected, bench_deck, active_deck, env),
                    TransferCard(_id, current_active, active_deck, bench_deck, env),
                ]

            events: list[Event | Generator] = [
                AVGEEnergyTransfer(_id, card, env, env),
                gen_swap,
                # cost=0, not other.actions[action_type].cost: v1 calls this with no
                # `energy_requirement` (defaults to 0), deliberately bypassing the
                # normal "does the acting character have enough energy" gate - Mason's
                # own energy discard above is the entire cost for this maneuver, and
                # `other` need not have any energy of its own attached.
                PlayCharacterCard(_id, other, action_type, 0, env),
            ]
            env.push_packet(Packet(_id, events))
