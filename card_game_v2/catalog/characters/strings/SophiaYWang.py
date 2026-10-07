from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck
from ....core.AVGEIOManager import StringSelectionQuery
from ....catalog.items.AVGEBirb import AVGEBirb

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class SophiaYWang(AVGECharacterCard):
    '''The KO-chain-reaction reactor in Ricochet's atk_2 is byte-identical to
    JuliaCeccarelli's atk_2, implemented independently here.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._GachaGaming(), ActionTypes.ATK_2: self._Ricochet()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _GachaGaming(Attack):
        '''Repeatedly offers to draw a card at 20 fixed self-damage (never below 1 HP),
        stopping when the deck runs out, HP drops to 20 or below, or the player
        declines. Drawing the cursed AVGEBirb card ends the loop immediately, heals to
        full, and keeps everything drawn so far. Any other ending shuffles every card
        drawn this attack back into the deck at random - but the self-damage already
        taken is NOT undone (confirmed against v1 source: `_shuffle_drawn_cards_back`
        only reverses the card transfers, never the HP changes).'''

        def __init__(self):
            super().__init__(
                name="Gacha Gaming",
                description="Repeatedly draw a card for 20 self-damage (min 1 HP) until you stop, run out of deck, or drop to 20 HP. Landing AVGEBirb ends the streak, heals you to full, and keeps everything drawn.",
                action_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            _id = AVGEEngineID(card, self.action_type, SophiaYWang)
            env.push_packet(Packet(_id, [SophiaYWang._GachaLoop(_id, card, env)]))

    class _GachaLoop(Event):
        def __init__(self, event_id: AVGEEngineID, card: AVGECharacterCard, env: AVGEEnvironment):
            super().__init__(event_id)
            self.card = card
            self.env = env

        async def act(self) -> None:
            card = self.card
            env = self.env
            player = env.players[card.owner]
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]
            drawn_cards: list[AVGECard] = []
            hit_birb = False

            while deck.cards_holding and card.hp > 20:
                choice = await env.report(StringSelectionQuery(
                    card.owner,
                    "Gacha Gaming: Draw a card and take 20 fixed damage? (You cannot self-KO.)",
                    1,
                    ["Yes", "No"],
                    ["Yes", "No"],
                    False,
                    False,
                ), self.id)
                if choice[0] != "Yes":
                    break
                next_card = deck.cards_holding[0]
                if isinstance(next_card, AVGEBirb):
                    hit_birb = True
                    await self.interrupt([
                        TransferCard(self.id, next_card, deck, hand, env),
                        AVGECardHPChangeEvent(
                            self.id, card, card.max_hp, AVGEAttributeModifier.SET_STATE, CardType.STRING, env,
                        ),
                    ])
                    break
                drawn_cards.append(next_card)
                await self.interrupt([
                    TransferCard(self.id, next_card, deck, hand, env),
                    AVGECardHPChangeEvent(
                        self.id, card, max(1, card.hp - 20),
                        AVGEAttributeModifier.SET_STATE, CardType.STRING, env,
                    ),
                ])

            if drawn_cards and not hit_birb:
                events: list[Event | Generator] = [
                    TransferCard(self.id, drawn, hand, deck, env) for drawn in drawn_cards
                ]

                def _make_shuffle(deck: AVGEDeck = deck):
                    def gen() -> list[AVGECard]:
                        return random.sample(deck.cards_holding, len(deck.cards_holding))
                    return gen
                events.append(ReorderDeck(self.id, deck, _make_shuffle(), env))
                await self.interrupt(events)

        def rollback(self) -> None:
            return

    class _Ricochet(Attack):
        def __init__(self):
            super().__init__(
                name="Ricochet",
                description="Deal 50 damage to the opposing active. Each knockout dealt this way splashes 30 damage to every remaining opposing bench character, recursively.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, SophiaYWang)

            card.add_listener(SophiaYWang._KnockoutChainReactor(card, env, 1))
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))

    class _KnockoutChainReactor(AVGEEventReactor):
        '''Lives only for the duration of one Ricochet resolution chain: starts armed
        for exactly 1 pending hit (the initial 50-damage strike), decrements on every
        subsequent qualifying hit, and re-arms itself by the number of new splash hits
        whenever one of those hits is a knockout - so a KO chain can cascade through
        the whole opposing bench. Self-removes once no pending hits remain.'''

        def __init__(self, owner_card: AVGECharacterCard, env: AVGEEnvironment, pending_hits: int):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.ATK_2, SophiaYWang), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card
            self.pending_hits = pending_hits

        def match(self, event: Event) -> bool:
            if self.pending_hits <= 0:
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.target_card):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_card is not self.owner_card:
                return False
            if event.id.calling_action != ActionTypes.ATK_2:
                return False
            return event.target_card.owner == self.env.get_opponent(self.owner_card.owner).id

        async def react(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            assert not callable(event.target_card)
            owner = self.owner_card
            env = self.env
            _id = AVGEEngineID(owner, ActionTypes.ATK_2, SophiaYWang)

            self.pending_hits -= 1
            knocked_out = event.target_card

            # Use the snapshot taken at CORE-time (`final_change`), not the live
            # `.hp` - by the time this EXTERNAL_REACTORS-group reactor runs, the
            # engine's own INTERNAL_4 discard-and-replace flow has already discarded
            # a KO'd character and reset its HP back to max as part of cleanup.
            if event.final_change == 0:
                opponent = env.get_opponent(owner.owner)
                targets = [
                    t for t in opponent.card_piles[DeckType.BENCH]
                    if isinstance(t, AVGECharacterCard) and t.hp > 0 and t is not knocked_out
                ]
                if targets:
                    self.pending_hits += len(targets)
                    event.push_event([AVGECardHPChangeEvent(
                        _id, t, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
                    ) for t in targets])

            if self.pending_hits <= 0:
                self.cleanup()
