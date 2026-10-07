from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, Ability
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, StatusEffect, AVGEStatusModifier, User, default_timeout
from ...core.EventCatalog import AVGECardHPChangeEvent, AVGECardStatusChange, TransferCard
from ...core.AVGEIOManager import BroadcastIO
from ...engine.event import Event, Generator, Packet

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEDeck import AVGEDeck
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment


class AVGEBirb(AVGEItemCard):
    '''Strips every tool and status effect off all of the opponent's characters in play,
    then makes the owner's active take +20 damage from the first attack that hits it
    during the owner's next turn.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="AVGEBirb",
                description=AVGEBirb.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, AVGEBirb):
                raise TypeError("AVGEBirb action requires its defining card")
            env = acting_card.env
            opponent = env.get_opponent(acting_card.owner)
            opponent_discard = opponent.card_piles[DeckType.DISCARD]

            opposing_chars: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]

            _id = AVGEEngineID(acting_card, self.action_type, AVGEBirb)
            events: list[Event | Generator] = []
            for character in opposing_chars:
                for tool in list(character.tools_attached.cards_holding):
                    events.append(TransferCard(_id, tool, character.tools_attached, opponent_discard, env))
                for status in StatusEffect:
                    for giver in list(character.statuses_attached[status]):
                        events.append(AVGECardStatusChange(_id, character, giver, status, AVGEStatusModifier.REMOVE, env))

            if events:
                env.push_packet(Packet(_id, events))

            acting_card.add_listener(AVGEBirb._NextAttackDamageCurse(acting_card.owner, env))


    class _NextAttackDamageCurse(AVGEEventModifier):
        '''Adds +20 to the first qualifying ATK damage the owner's active character
        takes during the owner's next turn, then self-invalidates - either by
        firing once, or by the turn passing without a hit. Re-resolves the owner's
        active card at match time (rather than pinning a fixed card), matching v1's own
        dynamic `get_active_card()` re-check - the curse follows the owner's active
        through retreats/swaps for that one turn.'''

        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, AVGEBirb), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner = owner
            self.round_active = env.round + 2

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_active:
                self.cleanup()
                return False
            if self.env.round != self.round_active:
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.target_card) or callable(event.magnitude) or callable(event.modifier_type):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            return event.target_card is self.env.get_player_active(self.owner)

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(20)
            self.cleanup()
            await self.env.broadcast(BroadcastIO(
                "AVGEBirb: This character takes +20 damage from this attack.", default_timeout,
            ))
