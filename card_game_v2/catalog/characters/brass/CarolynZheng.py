from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, PlayCharacterCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEDeck import AVGEDeck
    from ....constants import User
    from ....core.EventCatalog import TransferCard


class CarolynZheng(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._attack_modifier: CarolynZheng._AttackModifier | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.BRASS

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Blast()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._Procrastinate()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        # Entering play is handled globally by TransferCard's own passive-trigger special case.
        entering_play = deck_to.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
        was_in_play = deck_from.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
        if was_in_play and not entering_play and self._attack_modifier is not None:
            self._attack_modifier.cleanup()
            self._attack_modifier = None

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    class _AttackModifier(AVGEEventModifier):
        '''Buffs Carolyn Zheng's own attack damage by 30 if she did not attack on her last turn.'''

        def __init__(self, owner_card: CarolynZheng):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, CarolynZheng),
                owner_card.env,
                EngineGroup.EXTERNAL_MODIFIERS_2,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            if event.id.calling_card != self.owner_card:
                return False
            if not isinstance(event.target_card, AVGECharacterCard):
                return False
            if event.target_card.owner == self.owner_card.owner:
                return False
            if event.magnitude == 0:
                return False
            return True

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            if self._attacked_last_turn():
                return
            event.modify_magnitude(30)
            await self.env.broadcast(BroadcastIO(
                "Procrastinate: Carolyn Zheng buffed her own attack by 30 damage!",
                default_timeout,
            ))

        def _attacked_last_turn(self) -> bool:
            # Chapters advance once per completed turn (TurnEnd), alternating players, so this
            # player's own previous turn is 2 chapters back from whatever is currently in progress.
            index = 0
            while True:
                event, index = self.env.search_history(PlayCharacterCard, None, increment=2, index_to_start=index)
                if event is None:
                    return False
                if event.action in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                    # Mirrors PlayCharacterCard.act()'s own acting_card resolution, so a stolen
                    # attack is correctly attributed to whoever actually played it.
                    acting_card = event.id.calling_card if isinstance(event.id.calling_card, AVGECharacterCard) else event.target_card
                    if acting_card == self.owner_card:
                        return True
                index += 1

    # ------------------------------------------------------------------
    # Abilities
    # ------------------------------------------------------------------

    class _Procrastinate(Ability):
        def __init__(self):
            super().__init__(
                name="Procrastinate",
                description="If Carolyn Zheng did not attack during her last turn, her attack deals 30 more damage.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, CarolynZheng)
            if card._attack_modifier is None:
                card._attack_modifier = CarolynZheng._AttackModifier(card)
                card.add_listener(card._attack_modifier)

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _Blast(Attack):
        def __init__(self):
            super().__init__(
                name="Blast",
                description="Deal 70 damage to the opposing active character.",
                atk_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), CarolynZheng)

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    70,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    env,
                )
            ]

            env.push_packet(Packet(_id, events))
