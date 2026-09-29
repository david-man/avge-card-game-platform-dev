from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, PlayCharacterCard, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery, StringSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class KeiWatanabe(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Rudiments(), ActionTypes.ATK_2: self._DrumKidWorkshop()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _Rudiments(Attack):
        def __init__(self):
            super().__init__(name="Rudiments", description="Deal 10 damage to a chosen opposing character.", action_type=ActionTypes.ATK_1, cost=1)

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            candidates: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            _id = AVGEEngineID(card, self.action_type, KeiWatanabe)
            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Rudiments: 10 damage to one opposing character.",
                1,
                cast(list[AVGECard], candidates),
                cast(list[AVGECard], candidates),
                False,
                False,
            ), _id)
            chosen = picked[0]
            assert isinstance(chosen, AVGECharacterCard)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, chosen, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]))

    class _DrumKidWorkshop(Attack):
        def __init__(self):
            super().__init__(
                name="Drum Kid Workshop",
                description="Donate all of your own energy to a chosen own PERCUSSION character in play, then use one of their attacks.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            candidates: list[AVGECharacterCard] = [
                c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PERCUSSION
            ] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PERCUSSION
            ]
            if not candidates:
                return

            _id = AVGEEngineID(card, self.action_type, KeiWatanabe)
            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Drum Kid Workshop: Choose one of your percussion characters in play whose attack you'd like to use.",
                1,
                cast(list[AVGECard], candidates),
                cast(list[AVGECard], candidates),
                False,
                False,
            ), _id)
            chosen = picked[0]
            assert isinstance(chosen, AVGECharacterCard)

            move_options: dict[str, ActionTypes] = {}
            for action, atk in chosen.actions.items():
                if chosen is card and action == ActionTypes.ATK_2:
                    continue
                move_options[atk.name] = action
            if not move_options:
                return

            names = list(move_options.keys())
            move_choice = await env.report(StringSelectionQuery(
                card.owner, "Choose which attack to use.", 1, names, names, False, False,
            ), _id)
            action_type = move_options[move_choice[0]]

            # Resolve the borrowed definition first, at no additional attack cost.
            # Its child packets must finish before we inspect Kei's remaining energy:
            # copied attacks may spend or otherwise move energy while resolving.
            env.push_packet(Packet(_id, [
                PlayCharacterCard(_id, chosen, action_type, 0, env),
            ]))

            def _transfer_remaining_energy() -> list[Event | Generator]:
                return [
                    AVGEEnergyTransfer(_id, card, chosen, env)
                    for _ in range(len(card.energy_tokens))
                ]

            env.push_packet(Packet(_id, [_transfer_remaining_energy]))
