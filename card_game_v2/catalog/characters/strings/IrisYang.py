from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEItemCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, PlayNonCharacterCard
from ....core.AVGEIOManager import CardSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class IrisYang(AVGECharacterCard):
    '''Byte-identical "Open Strings" to MichelleKim's atk_1 (implemented independently
    here). MichelleKim itself is deferred (needs MikuOtamatone), but this attack has no
    such dependency.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._OpenStrings(), ActionTypes.ATK_2: self._Spike()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _OpenStrings(Attack):
        def __init__(self):
            super().__init__(
                name="Open Strings",
                description="Deal 10 damage to the opposing active. Draw a card - if it's an item, play it immediately and discard it.",
                action_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]
            discard = player.card_piles[DeckType.DISCARD]
            _id = AVGEEngineID(card, self.action_type, IrisYang)

            def draw_and_maybe_play_item() -> list[Event | Generator]:
                if len(deck) == 0:
                    return []
                top = deck.get_top()
                events: list[Event | Generator] = [TransferCard(_id, top, deck, hand, env)]
                if isinstance(top, AVGEItemCard):
                    events.append(PlayNonCharacterCard(_id, top, env))
                    events.append(TransferCard(_id, top, hand, discard, env))
                return events

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env),
                draw_and_maybe_play_item,
            ]
            env.push_packet(Packet(_id, events))

    class _Spike(Attack):
        def __init__(self):
            super().__init__(
                name="Spike",
                description="Deal 30 damage to the opposing active. You may switch it with one of the opponent's benched characters.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.action_type, IrisYang)
            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [
                AVGECardHPChangeEvent(_id, target, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env),
                IrisYang._SpikeSwitchEvent(_id, card, env),
            ]))

    class _SpikeSwitchEvent(Event):
        """Ask for the optional switch after damage and any KO promotion resolve."""

        def __init__(self, id: AVGEEngineID, attacker: AVGECharacterCard, env: AVGEEnvironment):
            super().__init__(id, attacker=attacker, env=env)
            self.attacker = attacker
            self.env = env

        async def act(self) -> None:
            opponent = self.env.get_opponent(self.attacker.owner)
            active_deck = opponent.card_piles[DeckType.ACTIVE_CARD]
            bench_deck = opponent.card_piles[DeckType.BENCH]
            if len(active_deck) == 0:
                return
            candidates = [c for c in bench_deck if isinstance(c, AVGECharacterCard)]
            if not candidates:
                return
            picked = await self.env.report(CardSelectionQuery(
                self.attacker.owner,
                "Spike: You may switch the opponent's Active with one of their Benched characters.",
                1,
                cast(list[AVGECard], candidates),
                cast(list[AVGECard], candidates),
                True,
                False,
            ), self.id)
            if not picked:
                return
            active = active_deck[0]
            chosen = picked[0]
            if isinstance(active, AVGECharacterCard) and chosen in bench_deck.cards_holding:
                self.push_event([
                    TransferCard(self.id, active, active_deck, bench_deck, self.env),
                    TransferCard(self.id, chosen, bench_deck, active_deck, self.env),
                ])

        def rollback(self) -> None:
            pass
