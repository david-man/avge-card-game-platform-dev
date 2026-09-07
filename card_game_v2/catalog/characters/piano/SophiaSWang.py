from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier, AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class SophiaSWang(AVGECharacterCard):
    '''"The Original is Always Better"'s once-per-round guard uses a plain instance
    field, same simplification established elsewhere, rather than a history search.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._energy_reactor: SophiaSWang._TheOriginalIsAlwaysBetter | None = None
        self._last_triggered_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._DamperPedal()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._TheOriginalIsAlwaysBetterPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _TheOriginalIsAlwaysBetterPassive(Ability):
        def __init__(self):
            super().__init__(
                name="The Original is Always Better",
                description="Once per round, whenever this character receives energy, mill the top card of the opponent's deck to their discard.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, SophiaSWang)
            if card._energy_reactor is None:
                card._energy_reactor = SophiaSWang._TheOriginalIsAlwaysBetter(card, card.env)
                card.add_listener(card._energy_reactor)

    class _TheOriginalIsAlwaysBetter(AVGEEventReactor):
        def __init__(self, owner_card: SophiaSWang, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, SophiaSWang), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            if not isinstance(event, AVGEEnergyTransfer):
                return False
            if callable(event.token_to):
                return False
            if event.token_to is not self.owner_card:
                return False
            if self.owner_card._last_triggered_round == self.env.round:
                return False
            opponent = self.env.get_opponent(self.owner_card.owner)
            return len(opponent.card_piles[DeckType.DECK]) > 0

        async def react(self, event: Event) -> None:
            self.owner_card._last_triggered_round = self.env.round
            opponent = self.env.get_opponent(self.owner_card.owner)
            deck = opponent.card_piles[DeckType.DECK]
            discard = opponent.card_piles[DeckType.DISCARD]
            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, SophiaSWang)

            def mill_top() -> list[Event | Generator]:
                if len(deck) == 0:
                    return []
                return [TransferCard(_id, deck.get_top(), deck, discard, self.env)]

            event.push_event([mill_top])

    class _DamperPedal(Attack):
        '''Byte-identical to LukeXu's, implemented independently per policy.'''

        def __init__(self):
            super().__init__(
                name="Damper Pedal",
                description="Deal 20 damage to the opposing active. Halve (round up) the opponent's next attack, whenever it lands.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), SophiaSWang)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
            card.add_listener(SophiaSWang._NextAttackHalved(card.owner, env))

    class _NextAttackHalved(AVGEEventModifier):
        '''Fires once, on the opponent's very next qualifying attack, whenever it
        lands - no round scoping at all (unlike AVGEBirb's curse), matching v1's own
        `LukeNextAttackHalvedModifier`/`SophiaNextAttackHalvedModifier` exactly (no
        `update_status` expiry, just `on_packet_completion` -> fire-once).'''

        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, SophiaSWang), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner = owner

        def match(self, event: Event) -> bool:
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
            return attacker.owner == self.env.get_opponent(self.owner).id

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            assert not callable(event.magnitude)
            event.modify_magnitude(-math.floor(event.magnitude / 2))
            self.cleanup()
            await self.env.broadcast(BroadcastIO("Damper Pedal: Incoming damage halved.", default_timeout))
