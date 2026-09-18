from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard
from ...avge_abstracts.AVGEDeck import AVGEDeck
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, EngineGroup, User, default_timeout
from ...core.EventCatalog import PlayCharacterCard, TransferCard
from ...core.AVGEIOManager import BroadcastIO, Notification
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment


class Otamatone(AVGEItemCard):
    '''Reduces the energy cost of the owner's active character's next attack by 1, for
    the rest of this turn. Cannot be played on the first turn. Unlike AVGEBirb's
    one-shot curse, this doesn't self-invalidate after a single use within the same
    turn - it stays live (and would discount every qualifying attack) until the turn
    actually ends, matching v1's own `update_status`/`event_match` split (no
    `on_packet_completion` invalidation here, unlike AVGEBirb's curse).'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        if env.round == 0:
            await env.report(Notification(
                self.owner, "Cannot play Otamatone on the first turn.", default_timeout,
            ), AVGEEngineID(self, ActionTypes.NONCHAR, Otamatone))
            return

        self.add_listener(Otamatone._ThisTurnEnergyDiscount(self.owner, env))

    class _ThisTurnEnergyDiscount(AVGEEventModifier):
        '''Reduces the energy cost of a matching attack by 1 (floor 0). Matches any
        qualifying attack played by the owner's active character during the same round
        Otamatone was played, then self-invalidates once the round moves on.'''

        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, Otamatone), env, EngineGroup.EXTERNAL_MODIFIERS_1)
            self.owner = owner
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
            if event.cost <= 0:
                return False
            return event.target_card is self.env.get_player_active(self.owner)

        async def modify(self, event: Event) -> None:
            assert isinstance(event, PlayCharacterCard)
            assert not callable(event.cost)
            event.cost = max(0, event.cost - 1)
            await self.env.broadcast(BroadcastIO(
                "Otamatone: Active has +1 effective energy this turn.", default_timeout,
            ))
