from __future__ import annotations

import random
from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEStadiumCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck
from ....core.AVGEIOManager import CardSelectionQuery, CoinflipData, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class IzzyChen(AVGECharacterCard):
    '''Overblow (atk_1) is byte-identical to HarperAitken's, implemented
    independently. BAI Wrangler's "once per turn" gate uses a plain instance field,
    same simplification established elsewhere, rather than replicating v1's
    `check_history` search.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._wrangler_last_used_round: int | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Overblow()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.ACTIVATE_ABILITY: self._BAIWrangler()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _BAIWrangler(Ability):
        def __init__(self):
            super().__init__(
                name="BAI Wrangler",
                description="Once per turn, flip a coin - heads, you may shuffle a stadium from your discard into your deck.",
                ability_type=ActionTypes.ACTIVATE_ABILITY,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            assert isinstance(card, IzzyChen)
            if card.env.turn != card.owner:
                return False
            return card._wrangler_last_used_round != card.env.round

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, IzzyChen)
            env = card.env
            player = env.players[card.owner]
            discard = player.card_piles[DeckType.DISCARD]
            deck = player.card_piles[DeckType.DECK]
            card._wrangler_last_used_round = env.round
            _id = AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, IzzyChen)

            flip = await env.report(CoinflipData(card.owner, "BAI Wrangler: Flip a coin."), _id)
            if flip != 1:
                await env.broadcast(BroadcastIO(
                    "Izzy Chen used BAI Wrangler, but she did not roll heads...", default_timeout,
                ))
                return

            stadiums: list[AVGEStadiumCard] = [c for c in discard.cards_holding if isinstance(c, AVGEStadiumCard)]
            if not stadiums:
                return

            picked = await env.report(CardSelectionQuery(
                card.owner,
                "BAI Wrangler: Choose a stadium in your discard to shuffle into your deck.",
                1,
                cast(list[AVGECard], stadiums),
                cast(list[AVGECard], stadiums),
                True,
                False,
            ), _id)
            if not picked:
                return
            chosen = picked[0]
            assert isinstance(chosen, AVGEStadiumCard)

            def _make_shuffle(deck: AVGEDeck = deck):
                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                return gen

            events: list[Event | Generator] = [
                TransferCard(_id, chosen, discard, deck, env),
                ReorderDeck(_id, deck, _make_shuffle(), env),
            ]
            env.push_packet(Packet(_id, events))

    class _Overblow(Attack):
        def __init__(self):
            super().__init__(
                name="Overblow",
                description="Deal 50 damage to the opposing active. Deal 10 recoil damage to yourself.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), IzzyChen)

            env.push_packet(Packet(_id, [
                AVGECardHPChangeEvent(_id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
                AVGECardHPChangeEvent(_id, card, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
            ]))
