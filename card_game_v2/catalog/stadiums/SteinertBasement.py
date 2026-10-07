from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEStadiumCard, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier, AVGEEventReactor
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, default_timeout
from ...core.EventCatalog import TransferCard, PlayCharacterCard, PhasePickCard
from ...core.AVGEIOManager import BroadcastIO
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class SteinertBasement(AVGEStadiumCard):
    '''Duo Queue: At the start of each turn, a player with exactly two characters
    in play draws one additional card. 15 Minute Walk: attacks cost one additional
    energy.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Duo Queue / 15 Minute Walk",
                description=SteinertBasement.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, SteinertBasement):
                raise TypeError("SteinertBasement action requires its defining card")
            env = acting_card.env
            acting_card.add_listener(_DuoQueueReactor(action_card, env))
            acting_card.add_listener(_AttackExtraCostModifier(action_card, env))



class _DuoQueueReactor(AVGEEventReactor):
    def __init__(self, owner_card: SteinertBasement, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, SteinertBasement), env, EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if not isinstance(event, PhasePickCard):
            return False
        player = self.env.players[self.env.turn]
        own_chars = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        return len(own_chars) == 2

    async def react(self, event: Event) -> None:
        env = self.env
        player = env.players[env.turn]
        deck = player.card_piles[DeckType.DECK]
        hand = player.card_piles[DeckType.HAND]
        if len(deck) == 0:
            return

        _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, SteinertBasement)
        await env.broadcast(BroadcastIO(
            "Steinert Basement: Duo Queue grants one additional draw this turn.", default_timeout,
        ))
        event.push_event([TransferCard(_id, lambda: deck.get_top(), deck, hand, env)])


class _AttackExtraCostModifier(AVGEEventModifier):
    def __init__(self, owner_card: SteinertBasement, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, SteinertBasement), env, EngineGroup.EXTERNAL_MODIFIERS_1)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if not isinstance(event, PlayCharacterCard):
            return False
        assert isinstance(event.id, AVGEEngineID)
        if callable(event.target_card) or callable(event.action) or callable(event.cost):
            return False
        if event.id.calling_action != ActionTypes.PLAYER_CHOICE:
            return False
        return event.action in (ActionTypes.ATK_1, ActionTypes.ATK_2)

    async def modify(self, event: Event) -> None:
        assert isinstance(event, PlayCharacterCard)
        assert not callable(event.cost)
        event.cost += 1
        await self.env.broadcast(BroadcastIO("Steinert Basement: 15 Minute Walk increased attack cost", default_timeout))
