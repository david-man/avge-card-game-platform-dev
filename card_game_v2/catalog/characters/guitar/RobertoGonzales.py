from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class RobertoGonzales(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.GUITAR

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._GuitarShredding(), ActionTypes.ATK_2: self._Distortion()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _GuitarShredding(Attack):
        def __init__(self):
            super().__init__(
                name="Guitar Shredding",
                description="Deal 30 damage to the opposing active. Discard all your own energy; for each token discarded, mill the top card of the opponent's deck to their discard.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, RobertoGonzales)

            energy_count = len(card.energy_tokens)
            opp_deck = opponent.card_piles[DeckType.DECK]
            opp_discard = opponent.card_piles[DeckType.DISCARD]

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env),
            ]
            events.extend(AVGEEnergyTransfer(_id, card, env, env) for _ in range(energy_count))
            mill_count = min(energy_count, len(opp_deck))
            events.extend(
                TransferCard(_id, lambda: opp_deck.get_top(), opp_deck, opp_discard, env) for _ in range(mill_count)
            )
            env.push_packet(Packet(_id, events))

    class _Distortion(Attack):
        def __init__(self):
            super().__init__(
                name="Distortion",
                description="Deal 40 damage to the opposing active. Your next GUITAR attack on your own following turn deals +40 damage.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, RobertoGonzales)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]))
            card.add_listener(RobertoGonzales._GuitarBoost(card.owner, env))

    class _GuitarBoost(AVGEEventModifier):
        '''+40 damage on the owner's own GUITAR attacks, scoped to the owner's own next
        turn (`env.round + 2` at play time, since it's necessarily the owner's own turn
        when this attaches). Unlike AVGEBirb's curse, this does NOT self-invalidate
        after firing once - v1's `_RobertoGuitarBoost` has no `on_packet_completion`
        override, so it stays live for every qualifying attack during that turn, same
        shape as Otamatone's discount, not AVGEBirb's one-shot curse.'''

        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, RobertoGonzales), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner = owner
            self.round_active = env.round + 2

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_active:
                self.cleanup()
                return False
            if self.env.round != self.round_active:
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.change_type):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.change_type != CardType.GUITAR:
                return False
            return event.id.calling_card is not None and event.id.calling_card.owner == self.owner

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(40)
            await self.env.broadcast(BroadcastIO("Distortion: +40 damage!", default_timeout))
