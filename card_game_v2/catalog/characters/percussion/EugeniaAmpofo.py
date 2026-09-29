from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, AVGEPlayerAttribute
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class EugeniaAmpofo(AVGECharacterCard):
    '''Fermentation (the active ability)'s "once per turn" gate uses a plain instance
    field, same simplification already established for RachelChen/AntongChen, rather
    than replicating v1's `check_history` search.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._fermentation_last_used_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._StickTrick()}), **({ActionTypes.ACTIVATE_ABILITY: self._Fermentation()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def _first_attached_character_this_turn(self) -> AVGECharacterCard | None:
        index = 0
        while True:
            event, index = self.env.search_history(AVGEEnergyTransfer, None, increment=0, index_to_start=index)
            if event is None:
                return None
            index += 1
            if callable(event.token_from) or callable(event.token_to):
                continue
            if event.id.calling_action != ActionTypes.PLAYER_CHOICE:
                continue
            if event.token_from is not self.env:
                continue
            if not isinstance(event.token_to, AVGECharacterCard):
                continue
            if event.token_to.owner != self.owner:
                continue
            return event.token_to

    class _Fermentation(Ability):
        def __init__(self):
            super().__init__(
                name="Fermentation",
                description="Once per turn, after your normal energy attach, attach 1 more free energy to a different in-play character.",
                action_type=ActionTypes.ACTIVATE_ABILITY,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            card = action_card
            assert isinstance(card, EugeniaAmpofo)
            env = card.env
            # Ownership is verified centrally, server-side, before Phase2ActivateAbility is ever
            # constructed (server/io_adapter.py's _deserialize_phase2).
            if card.deck_type != DeckType.ACTIVE_CARD:
                return False
            player = env.players[card.owner]
            if player.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] != 0:
                return False
            if len(env.energy_tokens) <= 0:
                return False
            if card._fermentation_last_used_round == env.round:
                return False
            first_attached = card._first_attached_character_this_turn()
            if first_attached is None:
                return False
            own_chars: list[AVGECharacterCard] = [
                c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            return any(c is not first_attached for c in own_chars)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, EugeniaAmpofo)
            env = card.env
            player = env.players[card.owner]
            first_attached = card._first_attached_character_this_turn()
            if first_attached is None:
                return
            own_chars: list[AVGECharacterCard] = [
                c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            candidates = [c for c in own_chars if c is not first_attached]
            if not candidates:
                return

            _id = AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, EugeniaAmpofo)
            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Fermentation: Choose another in-play character to attach an extra energy.",
                1,
                cast(list[AVGECard], candidates),
                cast(list[AVGECard], candidates),
                False,
                False,
            ), _id)
            chosen = picked[0]
            assert isinstance(chosen, AVGECharacterCard)
            card._fermentation_last_used_round = env.round

            if len(env.energy_tokens) <= 0:
                return
            env.push_packet(Packet(_id, [AVGEEnergyTransfer(_id, env, chosen, env)]))

    class _StickTrick(Attack):
        '''Byte-identical to HanleiGao/LoangChiang's atk_1, implemented independently.'''

        def __init__(self):
            super().__init__(
                name="Stick Trick",
                description="Deal 20 damage to the opposing active. You may swap with a benched character for free.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, EugeniaAmpofo)

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]

            bench = player.card_piles[DeckType.BENCH]
            active_holder = player.card_piles[DeckType.ACTIVE_CARD]
            bench_candidates = [c for c in bench.cards_holding if isinstance(c, AVGECharacterCard)]
            if bench_candidates:
                picked = await env.report(CardSelectionQuery(
                    card.owner,
                    "Stick Trick: You may swap with a benched character for free.",
                    1,
                    cast(list[AVGECard], bench_candidates),
                    list(bench.cards_holding),
                    True,
                    False,
                ), _id)
                if picked:
                    pick = picked[0]
                    assert isinstance(pick, AVGECharacterCard)
                    events.append(TransferCard(_id, pick, bench, active_holder, env))
                    events.append(TransferCard(_id, card, active_holder, bench, env))

            env.push_packet(Packet(_id, events))
