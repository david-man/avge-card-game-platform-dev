from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....core.AVGEIOManager import CoinflipData, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class AntongChen(AVGECharacterCard):
    '''Fingerstyle (atk_1) is blocked if Power Chord (atk_2) was used on this
    character's own previous turn - tracked with a plain instance field
    (`_last_atk2_round`, set when atk_2 resolves, checked against `env.round - 2`,
    since with 2 players trading turns 1-for-1, "my previous turn" is always exactly 2
    rounds back), rather than replicating v1's `check_history` search.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._last_atk2_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.GUITAR

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Fingerstyle(), ActionTypes.ATK_2: self._PowerChord()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Fingerstyle(Attack):
        def __init__(self):
            super().__init__(
                name="Fingerstyle",
                description="Cannot be used the turn after Power Chord. Flip 5 coins, deal 20 damage per head.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            return isinstance(action_card, AntongChen) and action_card._last_atk2_round != acting_card.env.round - 2

        def unavailable_reason(self, action_card: AVGECard, acting_card: AVGECard) -> str | None:
            return "Fingerstyle cannot be used on the turn after Power Chord."

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            if not isinstance(action_card, AntongChen):
                raise TypeError("Fingerstyle's definition card must be AntongChen")
            env = card.env
            _id = AVGEEngineID(card, self.action_type, AntongChen)
            if action_card._last_atk2_round == env.round - 2:
                await env.report(Notification(
                    card.owner, "Fingerstyle couldn't be used the turn after Power Chord!", default_timeout,
                ), _id)
                return

            heads = 0
            for _ in range(5):
                result = await env.report(CoinflipData(card.owner, "Fingerstyle: Flip a coin!"), _id)
                heads += result

            if heads <= 0:
                await env.report(Notification(
                    card.owner, "Fingerstyle rolled 0 heads...", default_timeout,
                ), _id)
                return

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 20 * heads, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]))

    class _PowerChord(Attack):
        def __init__(self):
            super().__init__(
                name="Power Chord",
                description="Deal 90 damage to the opposing active. Discard up to 2 of your own energy.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            if not isinstance(action_card, AntongChen):
                raise TypeError("Power Chord's definition card must be AntongChen")
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, AntongChen)

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, 90, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env),
                AVGEEnergyTransfer(_id, card, env, env),
                AVGEEnergyTransfer(_id, card, env, env),
            ]
            env.push_packet(Packet(_id, events))
            action_card._last_atk2_round = env.round
