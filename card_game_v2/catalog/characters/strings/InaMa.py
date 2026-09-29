from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....core.AVGEIOManager import CoinflipData, CardSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class InaMa(AVGECharacterCard):
    '''Byte-identical Triple Stop to EmilyWang's, implemented independently per
    policy. "Borrow a Bow"'s once-per-turn gate uses a plain instance field.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._borrow_a_bow_last_used_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._TripleStop()}), **({ActionTypes.ACTIVATE_ABILITY: self._BorrowABow()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def _candidates(self) -> list[AVGECharacterCard]:
        player = self.env.players[self.owner]
        own_chars: list[AVGECharacterCard] = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        return [c for c in own_chars if c is not self and c.card_type == CardType.STRING and len(c.energy_tokens) >= 1]

    class _BorrowABow(Ability):
        def __init__(self):
            super().__init__(
                name="Borrow a Bow",
                description="Once per turn, move 1 energy from another of your own STRING characters to this one.",
                action_type=ActionTypes.ACTIVATE_ABILITY,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            card = action_card
            assert isinstance(card, InaMa)
            # Ownership is verified centrally, server-side, before Phase2ActivateAbility is ever
            # constructed (server/io_adapter.py's _deserialize_phase2).
            if card._borrow_a_bow_last_used_round == card.env.round:
                return False
            return len(card._candidates()) > 0

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, InaMa)
            env = card.env
            candidates = card._candidates()
            card._borrow_a_bow_last_used_round = env.round
            if not candidates:
                return

            _id = AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, InaMa)
            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Borrow a Bow: Move 1 energy from one of your String characters to this character.",
                1,
                cast(list[AVGECard], candidates),
                cast(list[AVGECard], candidates),
                False,
                False,
            ), _id)
            chosen = picked[0]
            assert isinstance(chosen, AVGECharacterCard)
            if len(chosen.energy_tokens) <= 0:
                return
            env.push_packet(Packet(_id, [AVGEEnergyTransfer(_id, chosen, card, env)]))

    class _TripleStop(Attack):
        def __init__(self):
            super().__init__(name="Triple Stop", description="Flip 3 coins. Deal 40 damage to the opposing active per head.", action_type=ActionTypes.ATK_1, cost=3)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            _id = AVGEEngineID(card, self.action_type, InaMa)
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
