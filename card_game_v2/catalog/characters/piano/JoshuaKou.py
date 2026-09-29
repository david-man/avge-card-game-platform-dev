from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, PhasePickCard, TransferCard
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
        self._category_theory: JoshuaKou._CategoryTheory | None = None

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
        return

    class _CategoryTheoryPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Category Theory",
                description="At the start of your turn, if you have fewer than 4 cards in hand, may draw up to 4.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, JoshuaKou)
            if card._category_theory is None:
                card._category_theory = JoshuaKou._CategoryTheory(card, card.env)
                card.add_listener(card._category_theory)

    class _CategoryTheory(AVGEEventReactor):
        def __init__(self, owner_card: JoshuaKou, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, JoshuaKou), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, PhasePickCard):
                return False
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            if self.env.turn != self.owner_card.owner:
                return False
            player = self.env.players[self.owner_card.owner]
            if len(player.card_piles[DeckType.HAND]) >= 4:
                return False
            return len(player.card_piles[DeckType.DECK]) > 0

        async def react(self, event: Event) -> None:
            player = self.env.players[self.owner_card.owner]
            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, JoshuaKou)
            choice = await self.env.report(StringSelectionQuery(
                self.owner_card.owner,
                "Category Theory: Draw until you have four cards in hand?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                return

            hand = player.card_piles[DeckType.HAND]
            deck = player.card_piles[DeckType.DECK]
            draws = min(4 - len(hand), len(deck))
            if draws <= 0:
                return
            event.push_event([TransferCard(_id, lambda: deck.get_top(), deck, hand, self.env) for _ in range(draws)])

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
