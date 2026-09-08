from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECharacterCard, AVGEStadiumCard
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEPlayer import AVGEPlayer
from ...constants import ActionTypes, EngineGroup, default_timeout
from ...core.EventCatalog import PlayCharacterCard, TransferCard
from ...core.AVGEIOManager import BroadcastIO
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class LindemannPracticeRoom(AVGEStadiumCard):
    '''"Sectionals": -1 energy cost on an attack if the attacker's whole bench shares
    its active's card type. v1's bench-check is a vacuous truth on an empty bench (the
    `for` loop over zero benched characters never finds a mismatch) - replicated
    faithfully, not fixed, since nothing in the card's wording requires a *minimum*
    number of benched characters and this reads as plausible intentional design
    (Open Question, left unresolved either way in practice).'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self) -> None:
        self.add_listener(_SectionalsModifier(self, self.env))


class _SectionalsModifier(AVGEEventModifier):
    def __init__(self, owner_card: LindemannPracticeRoom, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, LindemannPracticeRoom), env, EngineGroup.EXTERNAL_MODIFIERS_1)
        self.owner_card = owner_card

    def _bench_shares_active_type(self, player: AVGEPlayer) -> bool:
        active = self.env.get_player_active(player.id)
        bench = [c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)]
        return all(c.card_type == active.card_type for c in bench)

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
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
        player = self.env.players[event.target_card.owner]
        return self._bench_shares_active_type(player)

    async def modify(self, event: Event) -> None:
        assert isinstance(event, PlayCharacterCard)
        assert not callable(event.cost)
        event.cost = max(0, event.cost - 1)
        await self.env.broadcast(BroadcastIO("Lindemann Practice Room: Sectionals", default_timeout))
