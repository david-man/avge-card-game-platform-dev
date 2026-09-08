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


class MeiyiSong(AVGECharacterCard):
    '''"Find items played this turn" is byte-identical to AnaliseJia's atk_1,
    implemented independently. "Only woodwind in play" bonus is the same shape as
    LucaChen's atk_2, independently reimplemented.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._ReedReplenishment(), ActionTypes.ATK_2: self._ClarinetSolo()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _ReedReplenishment(Attack):
        def __init__(self):
            super().__init__(
                name="Reed Replenishment",
                description="Deal 10 damage to the opposing active. You may put an Item card you played this turn into your hand.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        def _played_items_this_turn(self, card: AVGECharacterCard) -> list[AVGEItemCard]:
            env = card.env
            played: list[AVGEItemCard] = []
            seen: set[int] = set()
            index = 0
            while True:
                event, index = env.search_history(PlayNonCharacterCard, None, increment=0, index_to_start=index)
                if event is None:
                    break
                index += 1
                if callable(event.target_card):
                    continue
                if not isinstance(event.target_card, AVGEItemCard):
                    continue
                if event.target_card.owner != card.owner:
                    continue
                if id(event.target_card) in seen:
                    continue
                seen.add(id(event.target_card))
                played.append(event.target_card)
            return played

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), MeiyiSong)

            played = self._played_items_this_turn(card)
            retrievable = [i for i in played if i.deck_type != DeckType.HAND]

            chosen: AVGECard | None = None
            if retrievable:
                picked = await env.report(CardSelectionQuery(
                    card.owner,
                    "Reed Replenishment: You may put an Item card you played this turn into your hand.",
                    1,
                    cast(list[AVGECard], retrievable),
                    cast(list[AVGECard], retrievable),
                    True,
                    False,
                ), _id)
                if picked:
                    chosen = picked[0]

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]
            if chosen is not None:
                assert isinstance(chosen, AVGEItemCard)
                current_pile = player.card_piles[chosen.deck_type]
                hand = player.card_piles[DeckType.HAND]
                events.append(TransferCard(_id, chosen, current_pile, hand, env))

            env.push_packet(Packet(_id, events))

    class _ClarinetSolo(Attack):
        def __init__(self):
            super().__init__(
                name="Clarinet Solo",
                description="Deal 20 damage to the opposing active (70 if Meiyi is the only WOODWIND character anywhere in play).",
                atk_type=ActionTypes.ATK_2,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), MeiyiSong)

            all_chars = [
                c for p in (player, opponent)
                for pile in (DeckType.ACTIVE_CARD, DeckType.BENCH)
                for c in p.card_piles[pile]
                if isinstance(c, AVGECharacterCard)
            ]
            other_ww_count = sum(
                1 for c in all_chars if c is not card and c.card_type == CardType.WOODWIND
            )
            damage = 20 + (50 if other_ww_count == 0 else 0)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))
