from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class CathyRong(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._RacketSmash(), ActionTypes.ATK_2: self._FourHands()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _RacketSmash(Attack):
        def __init__(self):
            super().__init__(
                name="Racket Smash",
                description="Deal 20 damage to the opposing active. Optionally discard 1 energy from a chosen opposing benched character.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), CathyRong)

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]

            bench_candidates = [
                c for c in opponent.card_piles[DeckType.BENCH]
                if isinstance(c, AVGECharacterCard) and len(c.energy_tokens) >= 1
            ]
            if bench_candidates:
                picked = await env.report(CardSelectionQuery(
                    card.owner,
                    "Racket Smash: Choose an opposing benched character to discard 1 energy from.",
                    1,
                    cast(list[AVGECard], bench_candidates),
                    list(opponent.card_piles[DeckType.BENCH].cards_holding),
                    True,
                    False,
                ), _id)
                if picked:
                    chosen = picked[0]
                    assert isinstance(chosen, AVGECharacterCard)
                    events.append(AVGEEnergyTransfer(_id, chosen, env, env))

            env.push_packet(Packet(_id, events))

    class _FourHands(Attack):
        def __init__(self):
            super().__init__(
                name="Four Hands",
                description="Deal 50 damage to the opposing active (80 if another PIANO character is on your bench).",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), CathyRong)

            has_piano_benchmate = any(
                isinstance(c, AVGECharacterCard) and c is not card and c.card_type == CardType.PIANO
                for c in player.card_piles[DeckType.BENCH]
            )
            dmg = 80 if has_piano_benchmate else 50
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, dmg, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
