from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType, AVGEStadiumCard
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import StringSelectionQuery, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEDeck import AVGEDeck
    from ....constants import User


class FilipKaminski(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.BRASS

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {
            ActionTypes.ATK_1: self._HeartOfTheCards(),
            ActionTypes.ATK_2: self._IntenseEcho(),
        }

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _HeartOfTheCards(Attack):
        _ZONES = (DeckType.DECK, DeckType.BENCH, DeckType.HAND, DeckType.ACTIVE_CARD, DeckType.DISCARD)

        def __init__(self):
            super().__init__(
                name="Heart of the Cards",
                description="Name a card, then draw the top card of your deck. If it matches, deal 50 damage to the opposing active character.",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            deck = player.card_piles[DeckType.DECK]

            if len(deck) == 0:
                await env.broadcast(BroadcastIO(
                    "Heart of the Cards, but it did nothing...",
                    default_timeout,
                ))
                return

            possible_names = sorted({
                type(c).__name__
                for zone in self._ZONES
                for c in player.card_piles[zone]
            })

            _id = AVGEEngineID(card, self.resolve_caller(caller_action), FilipKaminski)
            result = await env.report(StringSelectionQuery(
                card.owner,
                "Heart of the Cards: Name a card.",
                1,
                possible_names,
                possible_names,
                False,
                False,
            ), _id)
            chosen_name = result[0]
            events: list[Event | Generator] = [
                TransferCard(_id, deck.get_top(), deck, player.card_piles[DeckType.HAND], env)
            ]

            if type(deck.get_top()).__name__ == chosen_name:
                opponent = env.get_opponent(card.owner)
                target = env.get_player_active(opponent)
                events.append(AVGECardHPChangeEvent(
                    _id,
                    target,
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    env,
                ))
                message = "Heart of the Cards and it HIT!"
            else:
                message = "Heart of the Cards, but it didn't hit..."

            env.push_packet(Packet(_id, events))
            await env.broadcast(BroadcastIO(message, default_timeout))

    class _IntenseEcho(Attack):
        def __init__(self):
            super().__init__(
                name="Intense Echo",
                description="Deal 50 damage to the opposing active character. If you have a stadium in play, also deal 20 damage to each of the opponent's benched characters.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), FilipKaminski)

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    env,
                )
            ]

            stadium = env.stadium_cardholder
            if len(stadium) > 0 and isinstance(stadium[0], AVGEStadiumCard) and stadium[0].owner == card.owner:
                opponent_bench = [c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)]
                for bench_card in opponent_bench:
                    events.append(AVGECardHPChangeEvent(
                        _id,
                        bench_card,
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.BRASS,
                        env,
                    ))

            env.push_packet(Packet(_id, events))
