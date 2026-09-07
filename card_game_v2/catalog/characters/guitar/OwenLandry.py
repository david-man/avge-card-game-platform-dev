from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class OwenLandry(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.GUITAR

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._FeedbackLoop(), ActionTypes.ATK_2: self._DomainExpansion()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _FeedbackLoop(Attack):
        def __init__(self):
            super().__init__(
                name="Feedback Loop",
                description="Deal 50 damage to the opposing active. Also deal 10 damage to each of your own benched GUITAR characters.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), OwenLandry)

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]
            for c in player.card_piles[DeckType.BENCH]:
                if isinstance(c, AVGECharacterCard) and c.card_type == CardType.GUITAR:
                    events.append(AVGECardHPChangeEvent(
                        _id, c, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
                    ))
            env.push_packet(Packet(_id, events))

    class _DomainExpansion(Attack):
        def __init__(self):
            super().__init__(
                name="Domain Expansion",
                description="Discard all of your own energy. Deal 50 damage to each of the opponent's in-play characters.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), OwenLandry)

            events: list[Event | Generator] = [
                AVGEEnergyTransfer(_id, card, env, env) for _ in card.energy_tokens
            ]
            opposing_chars: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            for c in opposing_chars:
                events.append(AVGECardHPChangeEvent(
                    _id, c, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
                ))
            env.push_packet(Packet(_id, events))
