from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import ActionTypes, AVGEAttributeModifier
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....engine.event import Event, Generator, Packet
from ....catalog.stadiums.AlumnaeHall import AlumnaeHall
from ....catalog.stadiums.SalomonDECI import SalomonDECI
from ....catalog.stadiums.RileyHall import RileyHall
from ....catalog.stadiums.MainHall import MainHall
from ....catalog.characters.piano.DavidMan import DavidMan
from ....catalog.characters.piano.LukeXu import LukeXu
from ....catalog.characters.woodwinds.EvelynWu import EvelynWu
from ....catalog.characters.percussion.BokaiBi import BokaiBi
from ....catalog.characters.guitar.RobertoGonzales import RobertoGonzales

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEPlayer import AVGEPlayer
    from ....constants import User


_BOOSTED_HALLS = (AlumnaeHall, SalomonDECI, RileyHall, MainHall)
_TARGET_CLASSES = (DavidMan, EvelynWu, BokaiBi, RobertoGonzales, LukeXu)


class JennieWang(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._SmallEnsembleCommittee(), ActionTypes.ATK_2: self._GrandPiano()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _SmallEnsembleCommittee(Attack):
        def __init__(self):
            super().__init__(
                name="Small Ensemble Committee",
                description="Deal 10 damage (max 30) to every opposing in-play character, once per each David Man, Evelyn Wu, Bokai Bi, Roberto Gonzales, or Luke Xu in play on either side.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.action_type, JennieWang)

            def _in_play(player: AVGEPlayer) -> list[AVGECharacterCard]:
                return [
                    c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
                ] + [
                    c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
                ]

            count = sum(1 for c in _in_play(env.players[card.owner]) if isinstance(c, _TARGET_CLASSES))
            count += sum(1 for c in _in_play(opponent) if isinstance(c, _TARGET_CLASSES))
            per_target = min(10 * count, 30)
            if per_target <= 0:
                return

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, per_target, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env)
                for target in _in_play(opponent)
            ]
            if events:
                env.push_packet(Packet(_id, events))

    class _GrandPiano(Attack):
        def __init__(self):
            super().__init__(
                name="Grand Piano",
                description="Deal 60 damage to the opposing active (80 instead if AlumnaeHall, SalomonDECI, RileyHall, or MainHall is active).",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.action_type, JennieWang)

            stadium = env.stadium_cardholder.cards_holding[0] if len(env.stadium_cardholder) > 0 else None
            dmg = 80 if isinstance(stadium, _BOOSTED_HALLS) else 60

            target = env.get_player_active(opponent)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, dmg, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
