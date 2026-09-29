from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard, ReorderDeck
from ....core.AVGEIOManager import CardSelectionQuery, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class AndreaCR(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Foresight(), ActionTypes.ATK_2: self._SnapPizz()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Foresight(Attack):
        '''Peek the top 3 cards of the opponent deck. With 3, choose one to send to the
        bottom and reorder the remaining 2 on top; with 2, just reorder them; with 1 or
        fewer, this fizzles.'''

        def __init__(self):
            super().__init__(
                name="Foresight",
                description="Peek the top 3 cards of the opponent's deck and choose how to reorder them.",
                action_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            opponent_deck = opponent.card_piles[DeckType.DECK]
            _id = AVGEEngineID(card, self.action_type, AndreaCR)

            consider_count = min(3, len(opponent_deck))
            if consider_count <= 1:
                await env.report(Notification(
                    card.owner,
                    "Foresight fizzled: not enough cards in the opponent's deck.", default_timeout,
                ), _id)
                return

            top_cards = list(opponent_deck.cards_holding[:consider_count])

            if consider_count == 2:
                chosen_order = await env.report(CardSelectionQuery(
                    card.owner,
                    "Foresight: Reorder the top 2 cards of your opponent's deck.",
                    2,
                    top_cards,
                    top_cards,
                    False,
                    False,
                ), _id)

                def _make_order(deck: AVGEDeck = opponent_deck, top: tuple[AVGECard, ...] = tuple(top_cards), chosen: tuple[AVGECard, ...] = tuple(chosen_order)):
                    def gen() -> list[AVGECard]:
                        rest = [c for c in deck.cards_holding if c not in top]
                        return list(chosen) + rest
                    return gen

                env.push_packet(Packet(_id, [ReorderDeck(_id, opponent_deck, _make_order(), env)]))
                return

            bottom_pick = await env.report(CardSelectionQuery(
                card.owner,
                "Foresight: Choose one of the top 3 cards to send to the bottom of your opponent's deck.",
                1,
                top_cards,
                top_cards,
                False,
                False,
            ), _id)
            bottom_card = bottom_pick[0]
            remaining_top_cards = [c for c in top_cards if c != bottom_card]

            chosen_order = await env.report(CardSelectionQuery(
                card.owner,
                "Foresight: Reorder the remaining 2 cards.",
                2,
                remaining_top_cards,
                remaining_top_cards,
                False,
                False,
            ), _id)

            def _make_order3(deck: AVGEDeck = opponent_deck, top: tuple[AVGECard, ...] = tuple(top_cards), chosen: tuple[AVGECard, ...] = tuple(chosen_order), bottom: AVGECard = bottom_card):
                def gen() -> list[AVGECard]:
                    rest = [c for c in deck.cards_holding if c not in top]
                    return list(chosen) + rest + [bottom]
                return gen

            env.push_packet(Packet(_id, [ReorderDeck(_id, opponent_deck, _make_order3(), env)]))

    class _SnapPizz(Attack):
        def __init__(self):
            super().__init__(
                name="Snap Pizz",
                description="Deal 20 damage to the opposing active. Strip up to 2 energy from a chosen opposing character.",
                action_type=ActionTypes.ATK_2,
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
            _id = AVGEEngineID(card, self.action_type, AndreaCR)
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
