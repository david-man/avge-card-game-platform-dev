from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEDeck import AVGEDeck
    from ....constants import User
    from ....core.EventCatalog import TransferCard


class RyanDu(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.CHOIR

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._TabemonoKing(), ActionTypes.ATK_2: self._Chorus()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _TabemonoKing(Attack):
        def __init__(self):
            super().__init__(
                name="Tabemono King",
                description="Deal 30 damage for each energy on this character, then discard all of it.",
                action_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)

            current_energy = len(card.energy_tokens)
            _id = AVGEEngineID(
                card, self.action_type, RyanDu)

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    30 * current_energy,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.CHOIR,
                    env,
                )
            ]
            events += [AVGEEnergyTransfer(_id, card, env, env)
                       for _ in range(current_energy)]

            env.push_packet(Packet(_id, events))

    class _Chorus(Attack):
        def __init__(self):
            super().__init__(
                name="Chorus",
                description="Deal 20 damage, plus 10 more for each character on your bench.",
                action_type=ActionTypes.ATK_2,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)

            player = env.players[card.owner]
            bench_count = len(player.card_piles[DeckType.BENCH])
            damage = 20 + 10 * bench_count

            _id = AVGEEngineID(
                card, self.action_type, RyanDu)
            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.CHOIR,
                    env,
                )
            ]

            env.push_packet(Packet(_id, events))
