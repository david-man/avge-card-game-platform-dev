from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class DanielYang(AVGECharacterCard):
    '''Filed under percussion (matching v1's actual file location,
    `card_game/catalog/characters/percussion/DanielYang.py`) despite being
    CardType.PIANO - a v1 folder/CardType mismatch, kept as-is since the v2 file
    location is just migration-bookkeeping organization and has no bearing on the
    card's actual `base_card_type()`.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._no_brass_boost: DanielYang._NoBrassBoost | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._EightHandsPiano()}), **({ActionTypes.PASSIVE: self._DelicateEarsPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _DelicateEarsPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Delicate Ears",
                description="This character's own attacks deal +10 damage, unless a BRASS character is in play anywhere.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, DanielYang)
            if card._no_brass_boost is None:
                card._no_brass_boost = DanielYang._NoBrassBoost(card, card.env)
                card.add_listener(card._no_brass_boost)

    class _NoBrassBoost(AVGEEventModifier):
        def __init__(self, owner_card: DanielYang, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, DanielYang), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner_card = owner_card

        def _any_brass_in_play(self) -> bool:
            for player in self.env.players.values():
                for pile in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                    for c in player.card_piles[pile]:
                        if isinstance(c, AVGECharacterCard) and c.card_type == CardType.BRASS:
                            return True
            return False

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
            if event.id.calling_card is not self.owner_card:
                return False
            return not self._any_brass_in_play()

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(10)
            await self.env.broadcast(BroadcastIO("Delicate Ears: +10 damage", default_timeout))

    class _EightHandsPiano(Attack):
        def __init__(self):
            super().__init__(
                name="Eight Hands Piano",
                description="Deal 50 damage to the opposing active. If you have 3+ PIANO characters on your bench, also deal 30 damage to each opposing benched character.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, DanielYang)

            piano_count = sum(
                1 for c in player.card_piles[DeckType.BENCH]
                if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PIANO
            )

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]
            if piano_count >= 3:
                for b in opponent.card_piles[DeckType.BENCH]:
                    if isinstance(b, AVGECharacterCard):
                        events.append(AVGECardHPChangeEvent(
                            _id, b, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
                        ))
            env.push_packet(Packet(_id, events))
