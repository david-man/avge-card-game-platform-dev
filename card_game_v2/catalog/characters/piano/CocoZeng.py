from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CoinflipData, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class CocoZeng(AVGECharacterCard):
    '''Glissando (atk_1)'s "not the turn after I last used it" gate uses a plain
    instance field, same simplification established for AntongChen (guitar).'''

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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Glissando(), ActionTypes.ATK_2: self._InventoryManagement()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Glissando(Attack):
        def __init__(self):
            super().__init__(
                name="Glissando",
                description="Deal 50 damage to the opposing active. Cannot be used the turn after it was last used.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            return isinstance(action_card, CocoZeng) and action_card._last_glissando_round != acting_card.env.round - 2

        def unavailable_reason(self, action_card: AVGECard, acting_card: AVGECard) -> str | None:
            return "Glissando cannot be used on the turn after it was last used."

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            if not isinstance(action_card, CocoZeng):
                raise TypeError("Glissando's definition card must be CocoZeng")
            env = card.env
            if action_card._last_glissando_round == env.round - 2:
                await env.report(Notification(
                    card.owner, "Glissando cannot be used this turn.", default_timeout,
                ), AVGEEngineID(card, self.action_type, CocoZeng))
                return

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, CocoZeng)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
            action_card._last_glissando_round = env.round

    class _InventoryManagement(Attack):
        def __init__(self):
            super().__init__(
                name="Inventory Management",
                description="Flip a coin for each card in your hand. Deal 30 damage per head.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            n = len(player.card_piles[DeckType.HAND])
            _id = AVGEEngineID(card, self.action_type, CocoZeng)
            if n <= 0:
                await env.report(Notification(
                    card.owner,
                    "Inventory Management, but there was no inventory to manage...", default_timeout,
                ), _id)
                return
            heads = 0
            for _ in range(n):
                heads += await env.report(CoinflipData(card.owner, "Inventory Management: Flip a coin for each card in your hand."), _id)
            if heads <= 0:
                return

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 30 * heads, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
