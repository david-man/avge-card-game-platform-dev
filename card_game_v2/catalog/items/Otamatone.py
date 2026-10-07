from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, EngineGroup, default_timeout
from ...core.EventCatalog import PlayCharacterCard, TransferCard
from ...core.AVGEIOManager import BroadcastIO, Notification
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment


class Otamatone(AVGEItemCard):
    '''The character active when played has one extra effective energy for attacks
    and retreat this turn, implemented as two cost modifiers without creating a token.
    Cannot be played on the first turn.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Otamatone",
                description=Otamatone.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            return acting_card.env.round > 0

        def unavailable_reason(self, action_card: AVGECard, acting_card: AVGECard) -> str | None:
            return "Otamatone cannot be played on the first turn."

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Otamatone):
                raise TypeError("Otamatone action requires its defining card")
            env = acting_card.env
            if env.round == 0:
                await env.report(Notification(
                    acting_card.owner, "Cannot play Otamatone on the first turn.", default_timeout,
                ), AVGEEngineID(acting_card, self.action_type, Otamatone))
                return

            active = env.get_player_active(acting_card.owner)
            acting_card.add_listener(Otamatone._ThisTurnEnergyDiscount(active, env))
            acting_card.add_listener(Otamatone._ThisTurnRetreatDiscount(active, env))


    class _ThisTurnEnergyDiscount(AVGEEventModifier):
        '''Reduces the energy cost of a matching attack by 1 (floor 0). Matches any
        qualifying attack played by the owner's active character during the same round
        Otamatone was played, then self-invalidates once the round moves on.'''

        def __init__(self, active: AVGECharacterCard, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, Otamatone), env, EngineGroup.EXTERNAL_MODIFIERS_1)
            self.active = active
            self.round_played = env.round

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_played:
                self.cleanup()
                return False
            if self.env.round != self.round_played:
                return False
            if not isinstance(event, PlayCharacterCard):
                return False
            if callable(event.target_card) or callable(event.action) or callable(event.cost):
                return False
            if event.id.calling_action != ActionTypes.PLAYER_CHOICE:
                return False
            if event.action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            return event.target_card is self.active and self.active.deck_type == DeckType.ACTIVE_CARD

        async def modify(self, event: Event) -> None:
            assert isinstance(event, PlayCharacterCard)
            assert not callable(event.cost)
            event.cost -= 1
            await self.env.broadcast(BroadcastIO(
                "Otamatone reduces this character's attack cost by 1 this turn.", default_timeout,
            ))

    class _ThisTurnRetreatDiscount(AVGEEventModifier):
        def __init__(self, active: AVGECharacterCard, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, Otamatone), env, EngineGroup.EXTERNAL_MODIFIERS_1)
            self.active = active
            self.round_played = env.round

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_played:
                self.cleanup()
                return False
            if self.env.round != self.round_played or not isinstance(event, TransferCard):
                return False
            if callable(event.card) or callable(event.deck_from) or callable(event.deck_to) or callable(event.cost):
                return False
            return (
                event.id.calling_action == ActionTypes.PLAYER_CHOICE
                and event.card is self.active
                and event.deck_from.deck_type == DeckType.ACTIVE_CARD
                and event.deck_to.deck_type == DeckType.BENCH
            )

        async def modify(self, event: Event) -> None:
            assert isinstance(event, TransferCard)
            assert not callable(event.cost)
            event.cost -= 1
