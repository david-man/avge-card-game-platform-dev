from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEItemCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, PlayNonCharacterCard
from ....core.AVGEIOManager import CardSelectionQuery, RevealCards

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class JuliaCeccarelli(AVGECharacterCard):
    '''The KO-chain-reaction reactor in Ricochet's atk_2 is byte-identical to
    SophiaYWang's atk_2, implemented independently here.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Photograph(), ActionTypes.ATK_2: self._Ricochet()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Photograph(Attack):
        def __init__(self):
            super().__init__(
                name="Photograph",
                description="Reveal the opponent's hand. You may choose one of their item cards to play as this attack.",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            opp_hand = opponent.card_piles[DeckType.HAND]
            items = [c for c in opp_hand.cards_holding if isinstance(c, AVGEItemCard)]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), JuliaCeccarelli)

            await env.report(RevealCards(card.owner, list(opp_hand.cards_holding)), _id)
            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Photograph: Choose an item to copy as this attack (or None).",
                1,
                cast(list[AVGECard], items),
                opp_hand.cards_holding,
                True,
                False,
            ), _id)

            if not picked:
                return
            chosen = picked[0]
            if isinstance(chosen, AVGEItemCard) and chosen in opp_hand.cards_holding:
                env.push_packet(Packet(_id, [PlayNonCharacterCard(_id, chosen, ActionTypes.ATK_1, env)]))

    class _Ricochet(Attack):
        def __init__(self):
            super().__init__(
                name="Ricochet",
                description="Deal 50 damage to the opposing active. Each knockout dealt this way splashes 30 damage to every remaining opposing bench character, recursively.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), JuliaCeccarelli)

            assert isinstance(card, JuliaCeccarelli)
            card.add_listener(JuliaCeccarelli._KnockoutChainReactor(card, env, 1))
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))

    class _KnockoutChainReactor(AVGEEventReactor):
        '''Lives only for the duration of one Ricochet resolution chain: starts armed
        for exactly 1 pending hit (the initial 50-damage strike), decrements on every
        subsequent qualifying hit, and re-arms itself by the number of new splash hits
        whenever one of those hits is a knockout - so a KO chain can cascade through
        the whole opposing bench. Self-removes once no pending hits remain.'''

        def __init__(self, owner_card: JuliaCeccarelli, env: AVGEEnvironment, pending_hits: int):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.ATK_2, JuliaCeccarelli), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card
            self.pending_hits = pending_hits

        def match(self, event: Event) -> bool:
            if self.pending_hits <= 0:
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.target_card):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_card is not self.owner_card:
                return False
            if event.id.calling_action != ActionTypes.ATK_2:
                return False
            return event.target_card.owner == self.env.get_opponent(self.owner_card.owner).id

        async def react(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            assert not callable(event.target_card)
            owner = self.owner_card
            env = self.env
            _id = AVGEEngineID(owner, ActionTypes.ATK_2, JuliaCeccarelli)

            self.pending_hits -= 1
            knocked_out = event.target_card

            # Use the snapshot taken at CORE-time (`final_change`), not the live
            # `.hp` - by the time this EXTERNAL_REACTORS-group reactor runs, the
            # engine's own INTERNAL_3 discard-and-replace flow has already discarded
            # a KO'd character and reset its HP back to max as part of cleanup.
            if event.final_change == 0:
                opponent = env.get_opponent(owner.owner)
                targets = [
                    t for t in opponent.card_piles[DeckType.BENCH]
                    if isinstance(t, AVGECharacterCard) and t.hp > 0 and t is not knocked_out
                ]
                if targets:
                    self.pending_hits += len(targets)
                    event.push_event([AVGECardHPChangeEvent(
                        _id, t, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
                    ) for t in targets])

            if self.pending_hits <= 0:
                self.cleanup()
