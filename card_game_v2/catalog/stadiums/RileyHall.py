from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECharacterCard, AVGEStadiumCard, CardType
from ...avge_abstracts.AVGEEventListener import AVGEEventReactor
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, MAX_BENCH_SIZE
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard, PhasePickCard
from ...engine.event import Event, Generator

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class RileyHall(AVGEStadiumCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self) -> None:
        self.add_listener(_AttendancePolicyReactor(self, self.env))


class _AttendancePolicyReactor(AVGEEventReactor):
    '''At the start of the active player's turn, deals 10 damage per empty bench slot
    to every one of their own characters in play - capped so no character can ever be
    reduced below 1 HP by this effect (confirmed against v1's `min(current_hp - 1,
    damage_per_character)`).'''

    def __init__(self, owner_card: RileyHall, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, RileyHall), env, EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        return isinstance(event, PhasePickCard)

    async def react(self, event: Event) -> None:
        assert isinstance(event, PhasePickCard)
        env = self.env
        player = env.players[env.turn]

        empty_bench_slots = max(0, MAX_BENCH_SIZE - len(player.card_piles[DeckType.BENCH]))
        if empty_bench_slots == 0:
            return

        damage_per_character = 10 * empty_bench_slots
        own_chars: list[AVGECharacterCard] = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]

        _id = AVGEEngineID(self.owner_card, ActionTypes.NONCHAR, RileyHall)
        events: list[Event | Generator] = [
            AVGECardHPChangeEvent(
                _id, character, max(0, min(character.hp - 1, damage_per_character)),
                AVGEAttributeModifier.SUBSTRACTIVE, CardType.ALL, env,
            )
            for character in own_chars
        ]
        event.push_event(events)
