from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEStadiumCard, CardType, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier, AVGEPacketReactor
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, StatusEffect
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard, PlayCharacterCard
from ...core.AVGEIOManager import RevealCards, StringSelectionQuery
from ...engine.event import Event, Packet

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class PetterutiLounge(AVGEStadiumCard):
    '''"Matcha Maid Cafe": while active, MAID attackers deal +10 damage and MAID
    characters retreat for 1 less energy. "Powerpoint Night": after any attack,
    the attacker may privately reveal a random card from the opponent's hand.
    This is the first stadium (and first card in this migration) to use
    the packet-level `AVGEPacketReactor` API, per Open Question / cross-cutting note.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="PetterutiLounge",
                description=PetterutiLounge.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, PetterutiLounge):
                raise TypeError("PetterutiLounge action requires its defining card")
            env = acting_card.env
            acting_card.add_listener(_MaidDamageModifier(action_card, env))
            acting_card.add_listener(_MaidRetreatDiscountModifier(action_card, env))
            action_card.add_packet_listener(_PowerpointNightPacketReactor(action_card, env))



class _MaidDamageModifier(AVGEEventModifier):
    def __init__(self, owner_card: PetterutiLounge, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, PetterutiLounge), env, EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if not isinstance(event, AVGECardHPChangeEvent):
            return False
        if callable(event.modifier_type) or callable(event.change_type):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.change_type == CardType.ALL:
            return False
        if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
            return False
        attacker = event.id.calling_card
        if not isinstance(attacker, AVGECharacterCard):
            return False
        return len(attacker.statuses_attached[StatusEffect.MAID]) > 0

    async def modify(self, event: Event) -> None:
        assert isinstance(event, AVGECardHPChangeEvent)
        event.modify_magnitude(10)


class _MaidRetreatDiscountModifier(AVGEEventModifier):
    '''-1 to a MAID-status character's own ACTIVE_CARD -> BENCH retreat leg's cost
    field (see TransferCard's own cost field and A2's retreat-cost fix) - a plain
    EXTERNAL_MODIFIERS_1 modifier, replacing the old regulator-plus-top-up-event
    trick this needed when the only thing available to adjust was the reactor's own
    always-full-price discard. No internal clamp - see KikisHeadband's identical
    modifier for why.'''

    def __init__(self, owner_card: PetterutiLounge, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.NONCHAR, PetterutiLounge), env, EngineGroup.EXTERNAL_MODIFIERS_1)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if not isinstance(event, TransferCard):
            return False
        if callable(event.card) or callable(event.deck_from) or callable(event.deck_to) or callable(event.cost):
            return False
        if not isinstance(event.card, AVGECharacterCard):
            return False
        if event.deck_from.deck_type != DeckType.ACTIVE_CARD or event.deck_to.deck_type != DeckType.BENCH:
            return False
        return len(event.card.statuses_attached[StatusEffect.MAID]) > 0

    async def modify(self, event: Event) -> None:
        assert isinstance(event, TransferCard)
        assert not callable(event.cost)
        event.cost -= 1


class _PowerpointNightPacketReactor(AVGEPacketReactor):
    def __init__(self, owner_card: PetterutiLounge, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, PetterutiLounge), env)
        self.owner_card = owner_card

    def _attacking_character(self, packet: Packet) -> AVGECharacterCard | None:
        for event in packet.event_log:
            if not isinstance(event, PlayCharacterCard):
                continue
            if callable(event.target_card) or callable(event.action):
                continue
            if event.action in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return event.target_card
        return None

    def match(self, packet: Packet) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        return self._attacking_character(packet) is not None

    async def react(self, packet: Packet) -> None:
        attacker = self._attacking_character(packet)
        assert attacker is not None
        _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, PetterutiLounge)
        # The attack may have queued its damage in a child packet. Queue this
        # prompt after those packets so the reveal appears after the hit.
        self.env.push_packet(Packet(_id, [_PowerpointNightReveal(_id, attacker, self.env)]))


class _PowerpointNightReveal(Event):
    def __init__(self, event_id: AVGEEngineID, attacker: AVGECharacterCard, env: AVGEEnvironment):
        super().__init__(event_id)
        self.attacker = attacker
        self.env = env

    async def act(self) -> None:
        opponent = self.env.get_opponent(self.attacker.owner)
        opponent_hand = opponent.card_piles[DeckType.HAND]
        if not opponent_hand.cards_holding:
            return
        choice = await self.env.report(StringSelectionQuery(
            self.attacker.owner,
            "Petteruti Lounge: Reveal a random card from your opponent's hand?",
            1,
            ["Yes", "No"],
            ["Yes", "No"],
            False,
            False,
        ), self.id)
        if choice[0] == "Yes":
            revealed = random.choice(opponent_hand.cards_holding)
            await self.env.report(RevealCards(
                self.attacker.owner, [revealed], "Petteruti Lounge: Powerpoint Night",
            ), self.id)

    def rollback(self) -> None:
        return
