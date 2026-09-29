from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType, AVGECard
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import ActionTypes, EngineGroup, ResponseStatus, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEDeck import AVGEDeck
    from ....constants import User


class VincentChen(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 120

    def base_max_hp(self) -> int:
        return 120

    def base_card_type(self) -> CardType:
        return CardType.BRASS

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Fanfare(), ActionTypes.ATK_2: self._CherryFlavoredValveOil()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    class _HealReactor(AVGEEventReactor):
        '''One-shot: heals a benched character for however much damage this ATK_2 just dealt.'''

        def __init__(self, owner_card: AVGECharacterCard):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.ATK_2, VincentChen),
                owner_card.env,
                EngineGroup.EXTERNAL_REACTORS,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if event.id.calling_action != ActionTypes.ATK_2:
                return False
            if event.id.calling_card != self.owner_card:
                return False
            return True

        async def react(self, event: Event) -> ResponseStatus | None:
            assert isinstance(event, AVGECardHPChangeEvent)
            self.cleanup()

            heal_amt = event.magnitude
            player = self.env.players[self.owner_card.owner]
            bench_chars = [c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)]
            if not bench_chars:
                return None

            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, VincentChen)
            chosen = await self.env.report(CardSelectionQuery(
                self.owner_card.owner,
                "Cherry Flavored Valve Oil: Pick a card to heal",
                1,
                cast(list[AVGECard], bench_chars),
                cast(list[AVGECard], bench_chars),
                False,
                False,
            ), _id)
            target = chosen[0]
            assert isinstance(target, AVGECharacterCard)
            self.env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id,
                target,
                heal_amt,
                AVGEAttributeModifier.ADDITIVE,
                CardType.ALL,
                self.env,
            )]))
            await self.env.broadcast(BroadcastIO(
                "Cherry Flavored Valve Oil: Healed a card",
                default_timeout,
            ))
            return None

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _Fanfare(Attack):
        def __init__(self):
            super().__init__(
                name="Fanfare",
                description="Deal 20 damage to the opposing active character.",
                action_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, VincentChen)

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    env,
                )
            ]
            env.push_packet(Packet(_id, events))

    class _CherryFlavoredValveOil(Attack):
        def __init__(self):
            super().__init__(
                name="Cherry Flavored Valve Oil",
                description="Deal 40 damage to the opposing active character, then heal a benched character for that much.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)

            card.add_listener(VincentChen._HealReactor(card))

            _id = AVGEEngineID(card, self.action_type, VincentChen)
            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    env,
                )
            ]
            env.push_packet(Packet(_id, events))
