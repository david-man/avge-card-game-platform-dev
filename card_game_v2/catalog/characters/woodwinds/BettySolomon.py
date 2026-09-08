from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck
from ....core.AVGEIOManager import CardSelectionQuery, CoinflipData

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class BettySolomon(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Outreach(), ActionTypes.ATK_2: self._Multiphonics()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Outreach(Attack):
        def __init__(self):
            super().__init__(
                name="Outreach",
                description="Search your deck for any character card and put it on top.",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            deck = player.card_piles[DeckType.DECK]
            character_cards: list[AVGECharacterCard] = [
                c for c in deck.cards_holding if isinstance(c, AVGECharacterCard)
            ]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), BettySolomon)

            if not character_cards:
                return

            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Outreach: Search for any character card and put it on top of your deck.",
                1,
                cast(list[AVGECard], character_cards),
                deck.cards_holding,
                True,
                False,
            ), _id)
            if not picked:
                return
            chosen = picked[0]

            def _make_order(deck: AVGEDeck = deck, chosen: AVGECard = chosen):
                def gen() -> list[AVGECard]:
                    rest = [c for c in deck.cards_holding if c is not chosen]
                    return [chosen] + rest
                return gen

            env.push_packet(Packet(_id, [ReorderDeck(_id, deck, _make_order(), env)]))

    class _Multiphonics(Attack):
        def __init__(self):
            super().__init__(
                name="Multiphonics",
                description="Flip 2 coins. Both heads: 50 damage to all opposing bench. Both tails: 100 damage to the opposing active. Split: nothing.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), BettySolomon)

            heads = 0
            for _ in range(2):
                heads += await env.report(CoinflipData(card.owner, "Multiphonics: Flip 2 coins."), _id)

            events: list[Event | Generator] = []
            if heads == 2:
                bench_targets = [c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)]
                for target in bench_targets:
                    events.append(AVGECardHPChangeEvent(
                        _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
                    ))
            elif heads == 0:
                target = env.get_player_active(opponent)
                events.append(AVGECardHPChangeEvent(
                    _id, target, 100, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
                ))

            if events:
                env.push_packet(Packet(_id, events))
