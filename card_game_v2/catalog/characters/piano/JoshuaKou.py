from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, User
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import StringSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class JoshuaKou(AVGECharacterCard):
    '''Separate Hands (atk_1) is the *inverse* of CocoZeng/HenryWang's Glissando
    cooldown: re-read v1 closely and confirmed it only deals damage when the search
    for "used last turn" *does* find a match (`used_last_turn_idx != -1`), not when it
    doesn't - i.e. it needs momentum from being used the turn before, the opposite
    polarity from what the plan doc's original survey note said. Corrected the
    Section 5 summary to match the actual code.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._last_used_round: int | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._SeparateHands()}), **({ActionTypes.PASSIVE: self._CategoryTheoryPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if (
            deck_from.deck_type == DeckType.HAND
            and deck_to.deck_type == DeckType.BENCH
            and transfer_event.id.calling_action == ActionTypes.PLAYER_CHOICE
        ):
            _id = AVGEEngineID(self, ActionTypes.PASSIVE, JoshuaKou)
            # on_transfer runs before the physical move. A child packet resolves
            # after it, so the draw count sees the hand without Joshua in it.
            self.env.push_packet(Packet(_id, [self._CategoryTheoryResolve(_id, self)]))

    class _CategoryTheoryPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Category Theory",
                description="When played from your hand to your bench, you may draw until you have four cards in hand.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            return

    class _CategoryTheoryResolve(Event):
        def __init__(self, event_id: AVGEEngineID, owner_card: JoshuaKou):
            super().__init__(event_id)
            self.owner_card = owner_card

        async def act(self) -> None:
            env = self.owner_card.env
            player = env.players[self.owner_card.owner]
            hand = player.card_piles[DeckType.HAND]
            deck = player.card_piles[DeckType.DECK]
            if self.owner_card.deck_type != DeckType.BENCH or len(hand) >= 4 or not deck:
                return
            choice = await env.report(StringSelectionQuery(
                self.owner_card.owner,
                "Category Theory: Draw until you have four cards in hand?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), self.id)
            if choice[0] != "Yes":
                return

            draws = min(4 - len(hand), len(deck))
            if draws > 0:
                self.push_event([TransferCard(self.id, lambda: deck.get_top(), deck, hand, env) for _ in range(draws)])

        def rollback(self) -> None:
            return

    class _SeparateHands(Attack):
        def __init__(self):
            super().__init__(
                name="Separate Hands",
                description="Deal 40 damage to the opposing active, but only if this attack was also used on your last turn.",
                action_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            if not isinstance(action_card, JoshuaKou):
                raise TypeError("Separate Hands' definition card must be JoshuaKou")
            env = card.env
            was_used_last_turn = action_card._last_used_round == env.round - 2
            action_card._last_used_round = env.round
            if not was_used_last_turn:
                return

            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, JoshuaKou)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
