from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, AVGECard, Attack, Ability, CardType
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import ActionTypes, AVGEAttributeModifier
from ....core.EventCatalog import AVGECardHPChangeEvent, ReorderDeck, TransferCard
from ....core.AVGEIOManager import RevealCards
from ....engine.event import Event, Generator, Packet
from ....catalog.stadiums.AlumnaeHall import AlumnaeHall
from ....catalog.stadiums.SalomonDECI import SalomonDECI
from ....catalog.stadiums.RileyHall import RileyHall
from ....catalog.stadiums.MainHall import MainHall

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


_BOOSTED_HALLS = (AlumnaeHall, SalomonDECI, RileyHall, MainHall)


class MichaelTu(AVGECharacterCard):
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._SynchroSummon(), ActionTypes.ATK_2: self._ElectricCello()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _SynchroSummon(Attack):
        def __init__(self):
            super().__init__(
                name="Synchro Summon",
                description="Reveal cards from the top of your deck until a character is found (or the deck runs out). If that character isn't STRING-typed, take it to hand and deal 30 damage to the opposing active. Then shuffle your deck.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            player = env.players[card.owner]
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.action_type, MichaelTu)

            revealed: list[AVGECard] = []
            first_char: AVGECharacterCard | None = None
            for c in deck.cards_holding:
                revealed.append(c)
                if isinstance(c, AVGECharacterCard):
                    first_char = c
                    break

            await env.broadcast(RevealCards(card.owner, revealed))

            events: list[Event | Generator] = []
            if first_char is not None and first_char.card_type != CardType.STRING:
                events.append(TransferCard(_id, first_char, deck, hand, env))
                events.append(AVGECardHPChangeEvent(
                    _id, env.get_player_active(opponent), 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
                ))

            def gen() -> list[Event | Generator]:
                if len(deck.cards_holding) <= 1:
                    return []
                return [ReorderDeck(_id, deck, lambda: random.sample(deck.cards_holding, len(deck.cards_holding)), env)]

            events.append(gen)
            env.push_packet(Packet(_id, events))

    class _ElectricCello(Attack):
        def __init__(self):
            super().__init__(
                name="Electric Cello",
                description="Deal 60 damage to the opposing active (80 instead if AlumnaeHall, SalomonDECI, RileyHall, or MainHall is active).",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.action_type, MichaelTu)

            stadium = env.stadium_cardholder.cards_holding[0] if len(env.stadium_cardholder) > 0 else None
            dmg = 80 if isinstance(stadium, _BOOSTED_HALLS) else 60

            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, dmg, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))
