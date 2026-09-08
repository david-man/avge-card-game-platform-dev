from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, AVGEItemCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import ActionTypes, AVGEAttributeModifier
from ....core.EventCatalog import AVGECardHPChangeEvent, PlayNonCharacterCard, TransferCard
from ....engine.event import Event, Generator, Packet
from ....catalog.items.MikuOtamatone import MikuOtamatone

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class MichelleKim(AVGECharacterCard):
    '''"Open Strings" is byte-identical to IrisYang's atk_1 (implemented independently
    here, per policy). "VocaRock!!" needs `MikuOtamatone` (item, now migrated) to check
    whether the owner played it earlier this turn.'''

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
        return {ActionTypes.ATK_1: self._OpenStrings(), ActionTypes.ATK_2: self._VocaRock()}

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
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), MichelleKim)

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

    class _VocaRock(Attack):
        def __init__(self):
            super().__init__(
                name="VocaRock!!",
                description="Deal 30 damage to the opposing active (80 instead if you played Miku Otamatone earlier this turn).",
                atk_type=ActionTypes.ATK_2,
                cost=2,
            )

        def _miku_used_this_turn(self, card: AVGECharacterCard) -> bool:
            index = 0
            while True:
                event, index = card.env.search_history(PlayNonCharacterCard, None, increment=0, index_to_start=index)
                if event is None:
                    return False
                if callable(event.target_card):
                    index += 1
                    continue
                if isinstance(event.target_card, MikuOtamatone) and event.target_card.owner == card.owner:
                    return True
                index += 1

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), MichelleKim)

            dmg = 80 if self._miku_used_this_turn(card) else 30
            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, dmg, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))
