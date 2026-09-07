from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEConstrainer import AVGEConstrainer
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier, AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Packet
from ....engine.listener import EventListener
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class LukeXu(AVGECharacterCard):
    '''Nullify's "already activated this round" dedup uses a plain instance field,
    same simplification established elsewhere.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._nullify_reactor: LukeXu._NullifyTransferReactor | None = None
        self._nullify_activated_round: int | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._DamperPedal()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._NullifyPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def _activate_nullify_for_turn(self) -> None:
        if self._nullify_activated_round == self.env.round:
            return
        self._nullify_activated_round = self.env.round
        self.add_constrainer(LukeXu._NullifyConstraint(self, self.owner, self.env.round))

    class _NullifyPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Nullify",
                description="While active on your own turn, opposing characters' passive/active abilities have no effect for the rest of this turn.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, LukeXu)
            if card._nullify_reactor is None:
                card._nullify_reactor = LukeXu._NullifyTransferReactor(card, card.env)
                card.add_listener(card._nullify_reactor)

            # The reactor below only catches *future* bench->active moves - it isn't
            # attached yet in time to see the very transfer that triggered this same
            # PASSIVE call (that transfer already finished before PASSIVE fires), so
            # this handles Luke entering active directly too.
            if card.env.turn == card.owner and card.deck_type == DeckType.ACTIVE_CARD:
                card._activate_nullify_for_turn()

    class _NullifyTransferReactor(AVGEEventReactor):
        '''Watches for Luke being retreated/swapped into active on his own turn
        (after the initial entry, which `_NullifyPassive.__call__` handles directly).'''

        def __init__(self, owner_card: LukeXu, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, LukeXu), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if self.env.turn != self.owner_card.owner:
                return False
            if not isinstance(event, TransferCard):
                return False
            if callable(event.card) or callable(event.deck_to):
                return False
            if event.card is not self.owner_card:
                return False
            return event.deck_to.deck_type == DeckType.ACTIVE_CARD and event.deck_to.deck_owner is self.env.players[self.owner_card.owner]

        async def react(self, event: Event) -> None:
            self.owner_card._activate_nullify_for_turn()
            await self.env.broadcast(BroadcastIO("Nullify: Opponent abilities have no effect this turn.", default_timeout))

    class _NullifyConstraint(AVGEConstrainer):
        '''Disables any PASSIVE/ACTIVATE_ABILITY listener belonging to an opposing
        character, for the rest of the round it was created in.'''

        def __init__(self, owner_card: LukeXu, owner: User, round_created: int):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, LukeXu))
            self.owner = owner
            self.round_created = round_created
            self.env = owner_card.env

        def match(self, obj: object) -> bool:
            if self.env.round != self.round_created or self.env.turn != self.owner:
                self.cleanup()
                return False
            if not isinstance(obj, EventListener) or isinstance(obj, AVGEConstrainer):
                return False
            listener_id = getattr(obj, "id", None)
            if listener_id is None or listener_id.calling_action not in (ActionTypes.PASSIVE, ActionTypes.ACTIVATE_ABILITY):
                return False
            owner_card = listener_id.calling_card
            if not isinstance(owner_card, AVGECharacterCard):
                return False
            return owner_card.owner == self.env.get_opponent(self.owner).id

    class _DamperPedal(Attack):
        '''Byte-identical to SophiaSWang's, implemented independently per policy.'''

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
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), LukeXu)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
            card.add_listener(LukeXu._NextAttackHalved(card.owner, env))

    class _NextAttackHalved(AVGEEventModifier):
        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.ATK_1, LukeXu), env, EngineGroup.EXTERNAL_MODIFIERS_2)
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
