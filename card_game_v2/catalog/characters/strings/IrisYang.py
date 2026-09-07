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

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._OpenStrings(), ActionTypes.ATK_2: self._Spike()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _OpenStrings(Attack):
        def __init__(self):
            super().__init__(
                name="Open Strings",
                description="Deal 10 damage to the opposing active. Draw a card - if it's an item, play it immediately and discard it.",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]
            discard = player.card_piles[DeckType.DISCARD]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), IrisYang)

            def draw_and_maybe_play_item() -> list[Event | Generator]:
                if len(deck) == 0:
                    return []
                top = deck.get_top()
                events: list[Event | Generator] = [TransferCard(_id, top, deck, hand, env)]
                if isinstance(top, AVGEItemCard):
                    events.append(PlayNonCharacterCard(_id, top, ActionTypes.ATK_1, env))
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
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            opponent_bench: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), IrisYang)

            selected_bench: AVGECharacterCard | None = None
            if opponent_bench:
                picked = await env.report(CardSelectionQuery(
                    card.owner,
                    "Spike: You may switch your opponent's Active character with one of their Benched characters.",
                    1,
                    cast(list[AVGECard], opponent_bench),
                    cast(list[AVGECard], opponent_bench),
                    True,
                    False,
                ), _id)
                if picked:
                    assert isinstance(picked[0], AVGECharacterCard)
                    selected_bench = picked[0]

            def gen_damage() -> list[Event | Generator]:
                target = env.get_player_active(opponent)
                return [AVGECardHPChangeEvent(_id, target, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env)]

            events: list[Event | Generator] = [gen_damage]

            if selected_bench is not None:
                chosen_bench = selected_bench

                def gen_switch() -> list[Event | Generator]:
                    active_deck = opponent.card_piles[DeckType.ACTIVE_CARD]
                    bench_deck = opponent.card_piles[DeckType.BENCH]
                    if len(active_deck) == 0:
                        return []
                    active = active_deck[0]
                    if not isinstance(active, AVGECharacterCard):
                        return []
                    if chosen_bench not in bench_deck.cards_holding:
                        return []
                    return [
                        TransferCard(_id, active, active_deck, bench_deck, env),
                        TransferCard(_id, chosen_bench, bench_deck, active_deck, env),
                    ]
                events.append(gen_switch)

            env.push_packet(Packet(_id, events))
