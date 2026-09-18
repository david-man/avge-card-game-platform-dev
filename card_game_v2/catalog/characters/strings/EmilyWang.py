from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CoinflipData

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class EmilyWang(AVGECharacterCard):
    '''Profit Margins (the active ability)'s "once per turn" gate uses a plain
    instance field, same simplification established elsewhere.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._profit_margins_last_used_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._TripleStop()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.ACTIVATE_ABILITY: self._ProfitMargins()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _ProfitMargins(Ability):
        def __init__(self):
            super().__init__(
                name="Profit Margins",
                description="Once per turn, if you have a tool attached, discard it and draw a card.",
                ability_type=ActionTypes.ACTIVATE_ABILITY,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            assert isinstance(card, EmilyWang)
            # Ownership is verified centrally, server-side, before Phase2ActivateAbility is ever
            # constructed (server/io_adapter.py's _deserialize_phase2).
            if len(card.tools_attached.cards_holding) == 0:
                return False
            return card._profit_margins_last_used_round != card.env.round

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, EmilyWang)
            env = card.env
            player = env.players[card.owner]
            card._profit_margins_last_used_round = env.round

            if len(card.tools_attached.cards_holding) == 0:
                return
            tool = card.tools_attached.cards_holding[0]
            discard = player.card_piles[DeckType.DISCARD]
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]
            _id = AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, EmilyWang)

            events: list[Event | Generator] = [TransferCard(_id, tool, card.tools_attached, discard, env)]
            if len(deck) > 0:
                events.append(TransferCard(_id, lambda: deck.get_top(), deck, hand, env))
            env.push_packet(Packet(_id, events))

    class _TripleStop(Attack):
        def __init__(self):
            super().__init__(name="Triple Stop", description="Flip 3 coins. Deal 40 damage to the opposing active per head.", atk_type=ActionTypes.ATK_1, cost=3)

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), EmilyWang)
            heads = 0
            for _ in range(3):
                heads += await env.report(CoinflipData(card.owner, "Triple Stop: Flip 3 coins."), _id)
            if heads <= 0:
                return

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env)
                for _ in range(heads)
            ]
            env.push_packet(Packet(_id, events))
