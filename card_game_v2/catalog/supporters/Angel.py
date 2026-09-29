from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGESupporterCard, Ability
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Angel",
                description=Angel.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Angel):
                raise TypeError("Angel action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            opponent = env.get_opponent(acting_card.owner)
            opponent_discard = opponent.card_piles[DeckType.DISCARD]
            _id = AVGEEngineID(acting_card, self.action_type, Angel)

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
                AVGECardStatusChange(_id, character, action_card, StatusEffect.GOON, AVGEStatusModifier.ADD, env)
                for character in own_chars
            ]
            for character in opp_chars:
                for tool in list(character.tools_attached.cards_holding):
                    events.append(TransferCard(_id, tool, character.tools_attached, opponent_discard, env))

            if events:
                env.push_packet(Packet(_id, events))
