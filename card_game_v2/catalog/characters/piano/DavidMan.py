from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck
from ....core.AVGEIOManager import RevealCards

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class DavidMan(AVGECharacterCard):
    '''Reverse Heist (the active ability)'s "once per turn" gate uses a plain instance
    field, same simplification established for RachelChen/AntongChen.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._reverse_heist_last_used_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._ThreeHandTechnique()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.ACTIVATE_ABILITY: self._ReverseHeist()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _ReverseHeist(Ability):
        def __init__(self):
            super().__init__(
                name="Reverse Heist",
                description="Once per turn, reveal a random discard card (to yourself only) and shuffle it into your deck.",
                ability_type=ActionTypes.ACTIVATE_ABILITY,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            assert isinstance(card, DavidMan)
            if card.env.turn != card.owner:
                return False
            player = card.env.players[card.owner]
            if len(player.card_piles[DeckType.DISCARD]) == 0:
                return False
            return card._reverse_heist_last_used_round != card.env.round

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, DavidMan)
            env = card.env
            player = env.players[card.owner]
            discard = player.card_piles[DeckType.DISCARD]
            deck = player.card_piles[DeckType.DECK]
            card._reverse_heist_last_used_round = env.round

            if len(discard) == 0:
                return
            chosen = random.choice(list(discard.cards_holding))

            _id = AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, DavidMan)
            await env.report(RevealCards(card.owner, [chosen]), _id)

            def _shuffled_order(deck: AVGEDeck = deck):
                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                return gen

            events: list[Event | Generator] = [
                TransferCard(_id, chosen, discard, deck, env),
                ReorderDeck(_id, deck, _shuffled_order(), env),
            ]
            env.push_packet(Packet(_id, events))

    class _ThreeHandTechnique(Attack):
        def __init__(self):
            super().__init__(name="Three Hand Technique", description="Deal 20 damage to the opposing active, 3 times.", atk_type=ActionTypes.ATK_1, cost=3)

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), DavidMan)
            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env)
                for _ in range(3)
            ]
            env.push_packet(Packet(_id, events))
