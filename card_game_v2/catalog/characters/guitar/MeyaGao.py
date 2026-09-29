from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier, AVGEEventRegulator, AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, ResponseStatus, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, PlayCharacterCard, TransferCard
from ....core.AVGEIOManager import BroadcastIO, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


def _next_turn_round(env: AVGEEnvironment, player: User) -> int:
    '''Same formula as v1's `AVGEPlayer.get_next_turn()`: the round when it's next
    `player`'s own turn - `env.round + 2` if it's currently their turn (so this counts
    their turn *after* the current one), else `env.round + 1`. Local to this file
    (needed twice, for two different players, from the same call site), not a shared
    cross-file helper.'''
    return env.round + (2 if env.turn == player else 1)


class MeyaGao(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._damage_reactor: MeyaGao._DamageReactor | None = None

    def base_hp(self) -> int:
        return 120

    def base_max_hp(self) -> int:
        return 120

    def base_card_type(self) -> CardType:
        return CardType.GUITAR

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Distortion()}), **({ActionTypes.PASSIVE: self._ISeeYourSoul()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _ISeeYourSoul(Ability):
        def __init__(self):
            super().__init__(
                name="I See Your Soul",
                description="Whenever this character, while active, takes attack damage, both it and the attacker are locked out of attacking on their own next turn.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, MeyaGao)
            if card._damage_reactor is None:
                card._damage_reactor = MeyaGao._DamageReactor(card, card.env)
                card.add_listener(card._damage_reactor)

    class _DamageReactor(AVGEEventReactor):
        '''Permanent (no expiry) - watches for attack damage landing on the owner
        while active, and on each hit attaches a fresh, round-scoped attack-lockout
        regulator to both the owner and the attacker.'''

        def __init__(self, owner_card: MeyaGao, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, MeyaGao), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type != DeckType.ACTIVE_CARD:
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.target_card):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.target_card is not self.owner_card:
                return False
            return event.id.calling_card is not None and isinstance(event.id.calling_card, AVGECharacterCard)

        async def react(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            attacker = event.id.calling_card
            assert isinstance(attacker, AVGECharacterCard)

            self.owner_card.add_listener(MeyaGao._AttackLockout(
                self.owner_card, _next_turn_round(self.env, self.owner_card.owner), self.env,
            ))
            attacker.add_listener(MeyaGao._AttackLockout(
                attacker, _next_turn_round(self.env, attacker.owner), self.env,
            ))

    class _AttackLockout(AVGEEventRegulator):
        def __init__(self, card_blocked: AVGECharacterCard, round_active: int, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(card_blocked, ActionTypes.PASSIVE, MeyaGao), env, EngineGroup.EXTERNAL_PRECHECK_1)
            self.card_blocked = card_blocked
            self.round_active = round_active

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_active:
                self.cleanup()
                return False
            if self.env.round != self.round_active:
                return False
            if not isinstance(event, PlayCharacterCard):
                return False
            if callable(event.action) or callable(event.target_card):
                return False
            if event.action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            acting_card = (
                event.id.calling_card
                if isinstance(event.id.calling_card, AVGECharacterCard)
                else event.target_card
            )
            return acting_card is self.card_blocked

        async def respond(self, event: Event) -> ResponseStatus:
            assert isinstance(event.id, AVGEEngineID)
            if event.id.calling_action == ActionTypes.PLAYER_CHOICE:
                await self.env.report(Notification(
                    self.card_blocked.owner,
                    "Cannot attack this round due to Meya Gao's I See Your Soul!", default_timeout,
                ), event.id)
                return ResponseStatus.REGULATE_FAIL
            return ResponseStatus.REGULATE_IGNORE

    class _Distortion(Attack):
        def __init__(self):
            super().__init__(
                name="Distortion",
                description="Deal 40 damage to the opposing active. Your next GUITAR attack on your own following turn deals +40 damage.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, MeyaGao)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]))
            card.add_listener(MeyaGao._GuitarBoost(card.owner, env))

    class _GuitarBoost(AVGEEventModifier):
        '''+40 damage on the owner's own GUITAR attacks during the owner's own next
        turn. Same idiom as Roberto/Edward's Distortion buffs, independently
        implemented per policy.'''

        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, MeyaGao), env, EngineGroup.EXTERNAL_MODIFIERS_2)
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
