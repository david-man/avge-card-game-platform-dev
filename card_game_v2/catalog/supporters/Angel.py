from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGESupporterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, StatusEffect, AVGEStatusModifier
from ...core.EventCatalog import AVGECardStatusChange, TransferCard
from ...engine.event import Event, Generator, Packet


class Angel(AVGESupporterCard):
    '''Grant GOON to all of your own in-play characters. Discard every tool attached
    to any of the opponent's in-play characters.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        opponent = env.get_opponent(self.owner)
        opponent_discard = opponent.card_piles[DeckType.DISCARD]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Angel)

        own_chars: list[AVGECharacterCard] = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        opp_chars: list[AVGECharacterCard] = [
            c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]

        events: list[Event | Generator] = [
            AVGECardStatusChange(_id, character, self, StatusEffect.GOON, AVGEStatusModifier.ADD, env)
            for character in own_chars
        ]
        for character in opp_chars:
            for tool in list(character.tools_attached.cards_holding):
                events.append(TransferCard(_id, tool, character.tools_attached, opponent_discard, env))

        if events:
            env.push_packet(Packet(_id, events))
