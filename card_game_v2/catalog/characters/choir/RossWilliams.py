from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventRegulator
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import ActionTypes, EngineGroup, ResponseStatus, AVGEAttributeModifier, AVGEPlayerAttribute, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import (
    AVGECardHPChangeEvent, AVGEPlayerAttributeChange, PlayCharacterCard, AtkPhase, TurnEnd, TransferCard,
)
from ....core.AVGEIOManager import CardSelectionQuery, StringSelectionQuery, BroadcastIO, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEDeck import AVGEDeck
    from ....constants import User


class RossWilliams(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._hijack_regulator: RossWilliams._AttackHijack | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.CHOIR

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._RossAttack()}), **({ActionTypes.PASSIVE: self._IAmBecomeRoss()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        # Entering play is handled globally by TransferCard's own passive-trigger special case.
        entering_play = deck_to.deck_type in (
            DeckType.ACTIVE_CARD, DeckType.BENCH)
        was_in_play = deck_from.deck_type in (
            DeckType.ACTIVE_CARD, DeckType.BENCH)
        if was_in_play and not entering_play and self._hijack_regulator is not None:
            self._hijack_regulator.cleanup()
            self._hijack_regulator = None

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    class _AttackHijack(AVGEEventRegulator):
        '''While Ross Williams is benched, offers to replace whichever character is about to
        attack with Ross's own attack instead, for free, as long as that character has at
        least 2 energy. Works regardless of which player owns the acting character or this
        particular Ross.'''

        def __init__(self, owner_card: RossWilliams):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, RossWilliams),
                owner_card.env,
                EngineGroup.EXTERNAL_MODIFIERS_2,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AtkPhase):
                return False
            if self.owner_card.deck_type != DeckType.BENCH:
                return False
            active = self.env.get_player_active(self.env.turn)
            return len(active.energy_tokens) >= 2

        async def respond(self, event: Event) -> ResponseStatus:
            current_player = self.env.get_current_player()
            active = self.env.get_player_active(self.env.turn)

            # Ross's own attack implementation runs (target_card=Ross), but the actual
            # attacker is whoever was about to act (id.calling_card=active) - mirrors
            # PlayCharacterCard.act()'s acting_card resolution. cost=0 so this never
            # checks/spends anyone's energy, matching the original's energy_requirement=0.
            _id = AVGEEngineID(active, ActionTypes.PASSIVE, RossWilliams)
            choice = await self.env.report(StringSelectionQuery(
                current_player.id,
                f"I Am Become Ross: Use {self.owner_card.owner.name}'s Ross's attack?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                return ResponseStatus.REGULATE_PASS
            events: list[Event | Generator] = [
                PlayCharacterCard(_id, self.owner_card,
                                  ActionTypes.ATK_1, 0, self.env),
                AVGEPlayerAttributeChange(
                    _id,
                    current_player,
                    AVGEPlayerAttribute.ATTACKS_LEFT,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    1,
                    self.env,
                ),
            ]

            def _attack_switch() -> list[Event | Generator]:
                if current_player.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] != 0:
                    return [AtkPhase(AVGEEngineID(None, ActionTypes.ENV, None), self.env)]
                else:
                    return [TurnEnd(AVGEEngineID(None, ActionTypes.ENV, None), self.env)]
            events.append(_attack_switch)

            self.env.push_packet(Packet(_id, events))
            await self.env.broadcast(BroadcastIO(
                f"{active} used Ross's attack!",
                default_timeout,
            ))
            # Skip AtkPhase's own core (the normal attack-choice prompt) entirely - our
            # substitute packet above replaces it, including re-driving the turn onward.
            return ResponseStatus.REGULATE_IGNORE

    # ------------------------------------------------------------------
    # Abilities
    # ------------------------------------------------------------------

    class _IAmBecomeRoss(Ability):
        def __init__(self):
            super().__init__(
                name="I Am Become Ross",
                description="While Ross Williams is benched, the player about to attack may use his attack instead, for free.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, RossWilliams)
            if card._hijack_regulator is None:
                card._hijack_regulator = RossWilliams._AttackHijack(card)
                card.add_listener(card._hijack_regulator)

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _RossAttack(Attack):
        def __init__(self):
            super().__init__(
                name="Ross Attack!",
                description="If your bench has a Ross Williams, retrieve a card from your discard. Otherwise, if the opponent's bench has one, deal 20 damage to a character of your choice.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)

            player_has = any(isinstance(c, RossWilliams)
                             for c in player.card_piles[DeckType.BENCH])
            opp_has = any(isinstance(c, RossWilliams)
                          for c in opponent.card_piles[DeckType.BENCH])

            _id = AVGEEngineID(card, self.action_type, RossWilliams)

            if player_has and opp_has:
                await env.report(Notification(
                    card.owner, "Ross Attack, but it did nothing...", default_timeout,
                ), _id)
                return

            if player_has:
                discard = player.card_piles[DeckType.DISCARD]
                hand = player.card_piles[DeckType.HAND]
                if len(discard) == 0:
                    await env.report(Notification(
                        card.owner, "Ross Attack, but there were no cards in discard.", default_timeout,
                    ), _id)
                    return
                discard_cards = [c for c in discard]
                choice = await env.report(CardSelectionQuery(
                    card.owner,
                    "Ross Attack!: Choose a card from discard to put in your hand",
                    1,
                    discard_cards,
                    discard_cards,
                    False,
                    False,
                ), _id)
                env.push_packet(
                    Packet(_id, [TransferCard(_id, choice[0], discard, hand, env)]))
                await env.broadcast(BroadcastIO("Ross Attack!", default_timeout))
                return

            if opp_has:
                targets: list[AVGECharacterCard] = [
                    c for pile in (DeckType.ACTIVE_CARD, DeckType.BENCH) for c in opponent.card_piles[pile]
                    if isinstance(c, AVGECharacterCard)
                ]
                choice = await env.report(CardSelectionQuery(
                    card.owner,
                    "Ross Attack!: Choose a card to attack",
                    1,
                    cast(list[AVGECard], targets),
                    cast(list[AVGECard], targets),
                    False,
                    False,
                ), _id)
                target = choice[0]
                assert isinstance(target, AVGECharacterCard)
                env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                    _id,
                    target,
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.CHOIR,
                    env,
                )]))
                await env.broadcast(BroadcastIO("Ross Attack!", default_timeout))
                return

            await env.report(Notification(
                card.owner, "Ross Attack, but it did nothing...", default_timeout,
            ), _id)
