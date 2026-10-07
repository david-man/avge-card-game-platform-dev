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
from ...catalog.stadiums.AlumnaeHall import AlumnaeHall
from ...catalog.stadiums.FriedmanHall import FriedmanHall
from ...catalog.stadiums.RileyHall import RileyHall
from ...catalog.stadiums.MainHall import MainHall
from ...catalog.stadiums.SalomonDECI import SalomonDECI

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID


_PERFORMANCE_HALLS = (AlumnaeHall, FriedmanHall, RileyHall, MainHall, SalomonDECI)


class MikuOtamatone(AVGEItemCard):
    '''Requires one of 5 named "performance hall" stadiums active, and can't be
    played on the first turn. Gives the character active when played two effective
    energy for attacks and retreat this turn, without creating tokens. **Fixed a real v1 bug on sight**:
    v1 imports `FriedmanHall` but its actual gating tuple only checks
    `(AlumnaeHall, RileyHall, MainHall, SalomonDECI)` - 4 of the 5 imported classes,
    silently excluding FriedmanHall. All 5 are equally "performance hall"-themed and
    there's no plausible reason to deliberately exclude the one literally named
    "Hall" while importing it for no other purpose - this reads as a forgotten
    addition to the tuple, not intentional design, so this migration includes all 5.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="MikuOtamatone",
                description=MikuOtamatone.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            env = acting_card.env
            stadium = env.stadium_cardholder.cards_holding[0] if len(env.stadium_cardholder) > 0 else None
            return env.round > 0 and isinstance(stadium, _PERFORMANCE_HALLS)

        def unavailable_reason(self, action_card: AVGECard, acting_card: AVGECard) -> str | None:
            env = acting_card.env
            if env.round == 0:
                return "Miku Otamatone cannot be played on the first turn."
            return "Miku Otamatone requires a performance hall stadium in play."

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, MikuOtamatone):
                raise TypeError("MikuOtamatone action requires its defining card")
            env = acting_card.env
            _id = AVGEEngineID(acting_card, self.action_type, MikuOtamatone)
            if env.round == 0:
                await env.report(Notification(
                    acting_card.owner, "Cannot play Miku Otamatone on the first turn.", default_timeout,
                ), _id)
                return

            stadium = env.stadium_cardholder.cards_holding[0] if len(env.stadium_cardholder) > 0 else None
            if not isinstance(stadium, _PERFORMANCE_HALLS):
                await env.report(Notification(
                    acting_card.owner, "Miku Otamatone can only be played in performance halls.", default_timeout,
                ), _id)
                return

            active = env.get_player_active(acting_card.owner)
            acting_card.add_listener(MikuOtamatone._ThisTurnEnergyDiscount(active, env))
            acting_card.add_listener(MikuOtamatone._ThisTurnRetreatDiscount(active, env))


    class _ThisTurnEnergyDiscount(AVGEEventModifier):
        '''Same shape as Otamatone's identical -1 discount, independently
        implemented here with -2 and an active-character-only restriction.'''

        def __init__(self, active: AVGECharacterCard, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, MikuOtamatone), env, EngineGroup.EXTERNAL_MODIFIERS_1)
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
            assert isinstance(event.id, AVGEEngineID)
            if event.id.calling_action != ActionTypes.PLAYER_CHOICE:
                return False
            if event.action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            return event.target_card is self.active and self.active.deck_type == DeckType.ACTIVE_CARD

        async def modify(self, event: Event) -> None:
            assert isinstance(event, PlayCharacterCard)
            assert not callable(event.cost)
            event.cost -= 2
            await self.env.broadcast(BroadcastIO(
                "Miku Otamatone reduces this character's attack cost by 2 this turn.", default_timeout,
            ))

    class _ThisTurnRetreatDiscount(AVGEEventModifier):
        def __init__(self, active: AVGECharacterCard, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, MikuOtamatone), env, EngineGroup.EXTERNAL_MODIFIERS_1)
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
            event.cost -= 2
