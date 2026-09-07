from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck
from ....core.AVGEIOManager import CardSelectionQuery, RevealCards, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class ChristmasKim(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.GUITAR

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Strum(), ActionTypes.ATK_2: self._SurpriseDelivery()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Strum(Attack):
        def __init__(self):
            super().__init__(name="Strum", description="Deal 20 damage to the opposing active.", atk_type=ActionTypes.ATK_1, cost=1)

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), ChristmasKim)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]))

    class _SurpriseDelivery(Attack):
        '''Peek the top 5 of your deck. Take any revealed GUITAR characters to hand,
        dealing 20 damage to the opposing active for each one found. If more than 1
        non-GUITAR card was among those peeked, choose an order to put them back on top
        of the deck.'''

        def __init__(self):
            super().__init__(
                name="Surprise Delivery",
                description="Peek the top 5 of your deck. Take any revealed GUITAR characters to hand, dealing 20 damage to the opposing active for each one found. If more than 1 non-GUITAR card was among those peeked, choose an order to put them back on top of the deck.",
                atk_type=ActionTypes.ATK_2,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), ChristmasKim)

            n = min(5, len(deck))
            if n == 0:
                await env.broadcast(BroadcastIO("Surprise Delivery, but there were no cards in deck.", default_timeout))
                return

            top_cards = list(deck.cards_holding[:n])
            guitar_chars = [c for c in top_cards if isinstance(c, AVGECharacterCard) and c.card_type == CardType.GUITAR]
            remaining_cards = [c for c in top_cards if c not in guitar_chars]
            target = env.get_player_active(opponent)

            events: list[Event | Generator] = []
            for c in guitar_chars:
                events.append(TransferCard(_id, c, deck, hand, env))
                events.append(AVGECardHPChangeEvent(
                    _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
                ))

            if guitar_chars:
                await env.broadcast(RevealCards(card.owner, cast(list[AVGECard], guitar_chars)))

            if len(remaining_cards) > 1:
                chosen_order = await env.report(CardSelectionQuery(
                    card.owner,
                    "Surprise Delivery: Choose an order to put the remaining revealed cards back on top of your deck.",
                    len(remaining_cards),
                    remaining_cards,
                    remaining_cards,
                    False,
                    False,
                ), _id)

                def _reordering_with_chosen_on_top(
                    deck: AVGEDeck = deck,
                    taken: tuple[AVGECard, ...] = tuple(guitar_chars),
                    chosen_order: tuple[AVGECard, ...] = tuple(chosen_order),
                ):
                    def gen() -> list[AVGECard]:
                        rest = [c for c in deck.cards_holding if c not in taken and c not in chosen_order]
                        return list(chosen_order) + rest
                    return gen

                events.append(ReorderDeck(_id, deck, _reordering_with_chosen_on_top(), env))

            env.push_packet(Packet(_id, events))
