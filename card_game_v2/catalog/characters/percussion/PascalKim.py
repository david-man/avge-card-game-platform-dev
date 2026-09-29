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
from ....core.AVGEIOManager import BroadcastIO, CardSelectionQuery

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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Ragebaited(), ActionTypes.ATK_2: self._OminousChimes()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Ragebaited(Attack):
        def __init__(self):
            super().__init__(
                name="Ragebaited",
                description="Deal damage scaling inversely with your own current HP: <=20 HP -> 90, <=50 HP -> 50, else 20.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            if card.hp <= 20:
                dmg = 90
            elif card.hp <= 50:
                dmg = 50
            else:
                dmg = 20

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, PascalKim)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, dmg, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]))

    class _OminousChimes(Attack):
        def __init__(self):
            super().__init__(
                name="Ominous Chimes",
                description="Return this character (and its tools) to your deck, shuffle. At the end of the opponent's next turn, deal 70 damage to their active.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            bench = player.card_piles[DeckType.BENCH]
            _id = AVGEEngineID(card, self.action_type, PascalKim)

            if len(bench) == 0:
                # Nothing to promote to active - fizzle rather than leaving the player
                # with an empty ACTIVE_CARD pile (get_player_active() indexes into it
                # unconditionally, which would crash the next attack/swap).
                return

            resp = await env.report(CardSelectionQuery(
                card.owner,
                "Ominous Chimes: choose a benched character to become your new active:",
                1,
                [c for c in bench],
                [c for c in bench],
                False,
                False,
            ), _id)
            new_active = resp[0]
            assert isinstance(new_active, AVGECharacterCard)

            deck = player.card_piles[DeckType.DECK]
            active_pile = player.card_piles[DeckType.ACTIVE_CARD]

            events: list[Event | Generator] = [
                # Promote the new active FIRST, before Pascal himself leaves - so
                # get_player_active() never observes an empty ACTIVE_CARD pile. Same
                # in->then->out ordering as MasonYu's "We Play God" bench swap.
                TransferCard(_id, new_active, bench, active_pile, env),
            ]
            for tool in list(card.tools_attached.cards_holding):
                events.append(TransferCard(_id, tool, card.tools_attached, deck, env))
            events.append(TransferCard(_id, card, active_pile, deck, env))

            def _shuffled_order(deck: AVGEDeck = deck):
                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                return gen
            events.append(ReorderDeck(_id, deck, _shuffled_order(), env))

            env.push_packet(Packet(_id, events))
            env.add_listener(PascalKim._OminousChimesDelayedReactor(card, env.round + 2, env))

    class _OminousChimesDelayedReactor(AVGEEventReactor):
        '''Fires once, at the end of the opponent's next turn. `round_active` is
        computed as `env.round + 2` (not v1's `opponent.get_next_turn()` value of
        `env.round + 1`) because `TurnEnd.act()` (CORE) increments `env.round` before
        this `EXTERNAL_REACTORS` listener's `match()` ever runs - by the time the
        opponent's own turn-ending `TurnEnd` reaches this listener, `env.round` has
        already advanced past the round during which that turn was played. Same
        post-act-state adjustment as GraceZhao's Royalties passive - see Section 2.'''

        def __init__(self, attacker: AVGECharacterCard, round_active: int, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, PascalKim), env, EngineGroup.EXTERNAL_REACTORS)
            self.attacker = attacker
            self.owner = attacker.owner
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
            # calling_card=self.attacker (not None) so AVGEWeaknessModifier's own
            # isinstance(event.id.calling_card, AVGECharacterCard) check offers the
            # crit coinflip for this delayed hit too. Safe even though this card has
            # since been shuffled back into the deck - the modifier only needs
            # .owner and the isinstance check, and change_type is passed explicitly
            # below, not derived from the card live.
            _id = AVGEEngineID(self.attacker, ActionTypes.NONCHAR, PascalKim)
            await self.env.broadcast(BroadcastIO("Ominous Chimes: 70 damage", default_timeout))
            event.push_event([AVGECardHPChangeEvent(
                _id, target, 70, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, self.env,
            )])
