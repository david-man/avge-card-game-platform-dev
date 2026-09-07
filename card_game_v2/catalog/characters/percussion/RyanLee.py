from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery, IntInput

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class RyanLee(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._PercussionEnsemble(), ActionTypes.ATK_2: self._FourMallets()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _PercussionEnsemble(Attack):
        def __init__(self):
            super().__init__(
                name="Percussion Ensemble",
                description="Attach up to 2 free energy to a chosen benched PERCUSSION character.",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            bench = player.card_piles[DeckType.BENCH]
            candidates = [c for c in bench.cards_holding if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PERCUSSION]
            max_attach = min(2, len(env.energy_tokens))
            if not candidates or max_attach == 0:
                return

            _id = AVGEEngineID(card, self.resolve_caller(caller_action), RyanLee)
            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Percussion Ensemble: Choose a benched percussion character.",
                1,
                cast(list[AVGECard], candidates),
                list(bench.cards_holding),
                False,
                False,
            ), _id)
            chosen = picked[0]
            assert isinstance(chosen, AVGECharacterCard)

            amount = await env.report(IntInput(card.owner, "Choose energy to attach (up to 2)", 1, max_attach), _id)
            transfer_count = min(amount, max_attach)
            if transfer_count <= 0:
                return

            events: list[Event | Generator] = [
                AVGEEnergyTransfer(_id, env, chosen, env) for _ in range(transfer_count)
            ]
            env.push_packet(Packet(_id, events))

    class _FourMallets(Attack):
        def __init__(self):
            super().__init__(
                name="Four Mallets",
                description="Deal 10 damage 4 times to the opposing active. The 4th hit also draws a card.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), RyanLee)

            events: list[Event | Generator] = []
            for i in range(4):
                events.append(AVGECardHPChangeEvent(
                    _id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
                ))
                if i == 3 and len(deck) > 0:
                    events.append(TransferCard(_id, lambda: deck.get_top(), deck, hand, env))
            env.push_packet(Packet(_id, events))
