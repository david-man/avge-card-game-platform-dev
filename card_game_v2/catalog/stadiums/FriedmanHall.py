from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECard, AVGEStadiumCard, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventReactor
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup
from ...core.EventCatalog import TransferCard, PhasePickCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery, RevealCards
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class FriedmanHall(AVGEStadiumCard):
    '''Once per turn at the draw phase, reveals the active player's top 2 deck cards;
    the *opponent* picks which one the active player keeps. Re-implemented for v2
    without v1's re-entrant "cancel PhasePickCard's normal draw, re-inject a fresh
    Phase2, and guard against re-triggering ourselves" dance (`temp_cache` flag +
    `ResponseType.FAST_FORWARD`) - v2's `REGULATE_FAIL` is packet-wide (it rolls back
    the *entire* enclosing packet, not just one event, so using it to "cancel and
    replace" a single event the way v1's assessor model could is unsafe here).
    Instead, this reactor runs *before* the engine's own already-queued normal draw
    (which lazily reads `deck.get_top()` only when its own later packet actually
    runs) and simply reorders the deck so the opponent's chosen card is on top and
    everything else (including the unchosen card) is shuffled beneath it - the
    normal draw then naturally draws the chosen card, with no risk of a double draw
    and no recursion to guard against in the first place.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="FriedmanHall",
                description=FriedmanHall.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, FriedmanHall):
                raise TypeError("FriedmanHall action requires its defining card")
            acting_card.add_listener(_ChoosyDrawReactor(action_card, acting_card.env))



class _ChoosyDrawReactor(AVGEEventReactor):
    def __init__(self, owner_card: FriedmanHall, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, FriedmanHall), env, EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        return isinstance(event, PhasePickCard)

    async def react(self, event: Event) -> None:
        env = self.env
        active_player = env.players[env.turn]
        opponent = env.get_opponent(env.turn)
        deck = active_player.card_piles[DeckType.DECK]
        if len(deck) < 2:
            return

        top_two = list(deck.cards_holding[:2])
        _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, FriedmanHall)

        await env.broadcast(RevealCards(active_player.id, top_two))
        picked = await env.report(CardSelectionQuery(
            opponent.id,
            "Friedman Hall: Opponent chooses one card for you to keep.",
            1,
            top_two,
            top_two,
            False,
            False,
        ), _id)
        chosen = picked[0]

        def _make_order(deck: AVGEDeck = deck, chosen: AVGECard = chosen):
            def gen() -> list[AVGECard]:
                rest = [c for c in deck.cards_holding if c is not chosen]
                return [chosen] + random.sample(rest, len(rest))
            return gen

        event.push_event([ReorderDeck(_id, deck, _make_order(), env)])
