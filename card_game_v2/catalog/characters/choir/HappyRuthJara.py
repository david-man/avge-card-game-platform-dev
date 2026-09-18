from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CoinflipData, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class HappyRuthJara(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.CHOIR

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Coloratura()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.ACTIVATE_ABILITY: self._LeaveRehearsalEarly()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    # ------------------------------------------------------------------
    # Abilities
    # ------------------------------------------------------------------

    class _LeaveRehearsalEarly(Ability):
        def __init__(self):
            super().__init__(
                name="Leave Rehearsal Early",
                description="Once per turn, if you haven't just benched this character, return it to your hand.",
                ability_type=ActionTypes.ACTIVATE_ABILITY,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            # Ownership is verified centrally, server-side, before Phase2ActivateAbility is ever
            # constructed (server/io_adapter.py's _deserialize_phase2).
            if card.deck_type != DeckType.BENCH:
                return False
            if len(card.tools_attached) > 0:
                return False
            return not self._entered_bench_from_hand_this_turn(card)

        def _entered_bench_from_hand_this_turn(self, card: AVGECharacterCard) -> bool:
            index = 0
            while True:
                event, index = card.env.search_history(
                    TransferCard, None, increment=0, index_to_start=index)
                if event is None:
                    return False
                if (event.card == card
                    and isinstance(event.deck_from, AVGEDeck)
                    and isinstance(event.deck_to, AVGEDeck)
                    and event.deck_from.deck_type == DeckType.HAND
                        and event.deck_to.deck_type == DeckType.BENCH):
                    return True
                index += 1

        async def __call__(self, card: AVGECharacterCard) -> None:
            env = card.env
            player = env.players[card.owner]
            _id = AVGEEngineID(
                card, ActionTypes.ACTIVATE_ABILITY, HappyRuthJara)
            env.push_packet(Packet(_id, [TransferCard(
                _id,
                card,
                player.card_piles[DeckType.BENCH],
                player.card_piles[DeckType.HAND],
                env,
            )]))
            await env.broadcast(BroadcastIO("Left rehearsal early...", default_timeout))

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _Coloratura(Attack):
        def __init__(self):
            super().__init__(
                name="Coloratura",
                description="Flip 2 coins. Deal 30 damage. If both are heads, deal 40 more.",
                atk_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            _id = AVGEEngineID(card, self.resolve_caller(
                caller_action), HappyRuthJara)
            r0 = await env.report(CoinflipData(card.owner, "Coloratura: Flip 2 coins."), _id)
            r1 = await env.report(CoinflipData(card.owner, "Coloratura: Flip 2 coins."), _id)
            damage = 30 + (40 if r0 == 1 and r1 == 1 else 0)

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id,
                target,
                damage,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.CHOIR,
                env,
            )]))
