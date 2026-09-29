from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, CardType, Ability
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="StrawberryMatchaLatte",
                description=StrawberryMatchaLatte.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, StrawberryMatchaLatte):
                raise TypeError("StrawberryMatchaLatte action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            _id = AVGEEngineID(acting_card, self.action_type, StrawberryMatchaLatte)

            targets: list[AVGECharacterCard] = [
                c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            if not targets:
                return

            picked = await env.report(CardSelectionQuery(
                acting_card.owner,
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
