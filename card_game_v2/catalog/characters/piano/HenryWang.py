from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType, AVGEItemCard
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class HenryWang(AVGECharacterCard):
    '''Byte-identical Glissando to CocoZeng's, implemented independently per policy.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._last_glissando_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Glissando(), ActionTypes.ATK_2: self._Improv()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Glissando(Attack):
        def __init__(self):
            super().__init__(
                name="Glissando",
                description="Deal 50 damage to the opposing active. Cannot be used the turn after it was last used.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            assert isinstance(card, HenryWang)
            env = card.env
            if card._last_glissando_round == env.round - 2:
                await env.broadcast(BroadcastIO("Glissando cannot be used this turn.", default_timeout))
                return

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), HenryWang)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
            card._last_glissando_round = env.round

    class _Improv(Attack):
        def __init__(self):
            super().__init__(
                name="Improv",
                description="Mill the top card of the opponent's deck to their discard. Deal 10 damage to the opposing active, or 100 if the milled card was an item.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            deck = opponent.card_piles[DeckType.DECK]
            discard = opponent.card_piles[DeckType.DISCARD]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), HenryWang)

            events: list[Event | Generator] = []
            damage = 10
            if len(deck) > 0:
                top = deck.cards_holding[0]
                events.append(TransferCard(_id, top, deck, discard, env))
                if isinstance(top, AVGEItemCard):
                    damage = 100

            events.append(AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            ))
            env.push_packet(Packet(_id, events))
