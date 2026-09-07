from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType, AVGECard
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck, TurnEnd
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class PascalKim(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Ragebaited(), ActionTypes.ATK_2: self._OminousChimes()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Ragebaited(Attack):
        def __init__(self):
            super().__init__(
                name="Ragebaited",
                description="Deal damage scaling inversely with your own current HP: <=20 HP -> 90, <=50 HP -> 50, else 20.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            if card.hp <= 20:
                dmg = 90
            elif card.hp <= 50:
                dmg = 50
            else:
                dmg = 20

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), PascalKim)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, dmg, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]))

    class _OminousChimes(Attack):
        def __init__(self):
            super().__init__(
                name="Ominous Chimes",
                description="Return this character (and its tools) to your deck, shuffle. At the end of the opponent's next turn, deal 70 damage to their active.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            deck = player.card_piles[DeckType.DECK]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), PascalKim)

            events: list[Event | Generator] = []
            for tool in list(card.tools_attached.cards_holding):
                events.append(TransferCard(_id, tool, card.tools_attached, deck, env))
            source = player.card_piles[card.deck_type]
            events.append(TransferCard(_id, card, source, deck, env))

            def _shuffled_order(deck: AVGEDeck = deck):
                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                return gen
            events.append(ReorderDeck(_id, deck, _shuffled_order(), env))

            env.push_packet(Packet(_id, events))
            env.add_listener(PascalKim._OminousChimesDelayedReactor(card.owner, env.round + 2, env))

    class _OminousChimesDelayedReactor(AVGEEventReactor):
        '''Fires once, at the end of the opponent's next turn. `round_active` is
        computed as `env.round + 2` (not v1's `opponent.get_next_turn()` value of
        `env.round + 1`) because `TurnEnd.act()` (CORE) increments `env.round` before
        this `EXTERNAL_REACTORS` listener's `match()` ever runs - by the time the
        opponent's own turn-ending `TurnEnd` reaches this listener, `env.round` has
        already advanced past the round during which that turn was played. Same
        post-act-state adjustment as GraceZhao's Royalties passive - see Section 2.'''

        def __init__(self, owner: User, round_active: int, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, PascalKim), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner = owner
            self.round_active = round_active

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_active:
                self.cleanup()
                return False
            return isinstance(event, TurnEnd) and self.env.round == self.round_active

        async def react(self, event: Event) -> None:
            self.cleanup()
            opponent = self.env.get_opponent(self.owner)
            target = self.env.get_player_active(opponent)
            _id = AVGEEngineID(None, ActionTypes.NONCHAR, PascalKim)
            await self.env.broadcast(BroadcastIO("Ominous Chimes: 70 damage", default_timeout))
            event.push_event([AVGECardHPChangeEvent(
                _id, target, 70, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, self.env,
            )])
