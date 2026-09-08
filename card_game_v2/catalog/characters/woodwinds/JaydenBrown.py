from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEIOListener
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Packet
from ....engine.engine_io import IOType
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import D6Input, CoinflipData, StringSelectionQuery, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class JaydenBrown(AVGECharacterCard):
    '''Four-leaf Clover is the first card in this migration to use the `IOListener`
    engine hook (built for exactly this: intercepting and rewriting the *response* to
    another card's in-flight `env.report(...)` call, since v2's own `await
    env.report(...)` calls are otherwise inline/synchronous from the requester's own
    code - see Open Question 4 / Section 2 for the hook's design). The listener's
    `modify()` itself awaits a follow-up Yes/No query before deciding whether to
    override the coinflip result - `IOListener.modify()` is async specifically so this
    is possible.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._four_leaf_clover: JaydenBrown._FourLeafCloverListener | None = None
        self._four_leaf_clover_last_used_round: int | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._HyperVentilation()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._FourLeafCloverPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _FourLeafCloverPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Four-leaf Clover",
                description="Once per round, while active, may force your first coinflip of the round to heads.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, JaydenBrown)
            if card._four_leaf_clover is None:
                card._four_leaf_clover = JaydenBrown._FourLeafCloverListener(card, card.env)
                card.add_io_listener(card._four_leaf_clover)

    class _FourLeafCloverListener(AVGEIOListener):
        def __init__(self, owner_card: JaydenBrown, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, JaydenBrown), env)
            self.owner_card = owner_card

        def match(self, io_obj: IOType[object]) -> bool:
            if not isinstance(io_obj, CoinflipData):
                return False
            if io_obj.user_for != self.owner_card.owner:
                return False
            if self.owner_card.deck_type != DeckType.ACTIVE_CARD:
                return False
            return self.owner_card._four_leaf_clover_last_used_round != self.env.round

        async def modify(self, io_obj: IOType[object], response: object) -> object:
            owner = self.owner_card
            owner._four_leaf_clover_last_used_round = self.env.round
            _id = AVGEEngineID(owner, ActionTypes.PASSIVE, JaydenBrown)

            choice = await self.env.report(StringSelectionQuery(
                owner.owner,
                "Four-leaf Clover: Treat this first coin flip as heads?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                return response

            await self.env.broadcast(BroadcastIO(
                "Four-leaf Clover! Turned the first coin flip to heads", default_timeout,
            ))
            return 1

    class _HyperVentilation(Attack):
        def __init__(self):
            super().__init__(
                name="Hyper-Ventilation!",
                description="Roll a D6. Deal 30 + 10 per pip damage to the opposing active.",
                atk_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), JaydenBrown)

            roll = await env.report(D6Input(card.owner, "Hyper-Ventilation!: Roll a D6."), _id)
            damage = 30 + (10 * roll)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))
