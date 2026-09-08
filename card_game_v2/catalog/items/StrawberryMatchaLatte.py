from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, CardType
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, AVGEAttributeModifier
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ...core.AVGEIOManager import CardSelectionQuery
from ...engine.event import Packet
from ...catalog.stadiums.PetterutiLounge import PetterutiLounge

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class StrawberryMatchaLatte(AVGEItemCard):
    '''Heal one chosen own character +20 (+10 more, so +30 total, if PetterutiLounge
    is active). Same real v1 bug fix as MatchaLatte's identical (always-`False`)
    `isinstance(stadium_cardholder, PetterutiLounge)` check - see that file's
    docstring.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, StrawberryMatchaLatte)

        targets: list[AVGECharacterCard] = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        if not targets:
            return

        picked = await env.report(CardSelectionQuery(
            self.owner,
            "Strawberry Matcha Latte: Choose one of your characters to heal.",
            1,
            cast(list[AVGECard], targets),
            cast(list[AVGECard], targets),
            False,
            False,
        ), _id)
        target = picked[0]
        assert isinstance(target, AVGECharacterCard)

        stadium = env.stadium_cardholder.cards_holding[0] if len(env.stadium_cardholder) > 0 else None
        heal = 30 if isinstance(stadium, PetterutiLounge) else 20

        env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
            _id, target, heal, AVGEAttributeModifier.ADDITIVE, CardType.ALL, env,
        )]))
