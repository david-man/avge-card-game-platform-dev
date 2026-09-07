from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, TurnEnd
from ....core.AVGEIOManager import CardSelectionQuery
from ....catalog.tools.AVGEShowcaseSticker import AVGEShowcaseSticker
from ....catalog.tools.AVGETShirt import AVGETShirt
from ....catalog.tools.MaidOutfit import MaidOutfit

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class GraceZhao(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._royalties_reactor: GraceZhao._Royalties | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.GUITAR

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._FeedbackLoop()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._RoyaltiesPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _RoyaltiesPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Royalties",
                description="Whenever your turn ends, if any opposing character carries a Showcase Sticker, AVGE T-Shirt, or Maid Outfit, deal 10 damage to a chosen one of them.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, GraceZhao)
            if card._royalties_reactor is None:
                card._royalties_reactor = GraceZhao._Royalties(card, card.env)
                card.add_listener(card._royalties_reactor)

    class _Royalties(AVGEEventReactor):
        def __init__(self, owner_card: GraceZhao, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, GraceZhao), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def _candidates(self) -> list[AVGECharacterCard]:
            opponent = self.env.get_opponent(self.owner_card.owner)
            opposing_chars: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            return [
                c for c in opposing_chars
                if any(isinstance(t, (AVGEShowcaseSticker, AVGETShirt, MaidOutfit)) for t in c.tools_attached.cards_holding)
            ]

        def match(self, event: Event) -> bool:
            if not isinstance(event, TurnEnd):
                return False
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            # TurnEnd.act() (CORE) already flips env.turn to the next player before any
            # EXTERNAL_REACTORS group runs - unlike v1, where this listener type
            # apparently evaluates pre-flip. So "my own turn just ended" has to be read
            # as "env.turn is now the opponent's", not "env.turn is still mine".
            if self.env.turn != self.env.get_opponent(self.owner_card.owner).id:
                return False
            return len(self._candidates()) > 0

        async def react(self, event: Event) -> None:
            candidates = self._candidates()
            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, GraceZhao)
            picked = await self.env.report(CardSelectionQuery(
                self.owner_card.owner,
                "Royalties: Deal 10 damage to an opposing card carrying Showcase Sticker/AVGE T-Shirt/Maid Outfit.",
                1,
                cast(list[AVGECard], candidates),
                cast(list[AVGECard], candidates),
                True,
                False,
            ), _id)
            if not picked:
                return
            target = picked[0]
            assert isinstance(target, AVGECharacterCard)
            event.push_event([AVGECardHPChangeEvent(
                _id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, self.env,
            )])

    class _FeedbackLoop(Attack):
        def __init__(self):
            super().__init__(
                name="Feedback Loop",
                description="Deal 50 damage to the opposing active. Also deal 10 damage to each of your own benched GUITAR characters.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), GraceZhao)

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]
            for c in player.card_piles[DeckType.BENCH]:
                if isinstance(c, AVGECharacterCard) and c.card_type == CardType.GUITAR:
                    events.append(AVGECardHPChangeEvent(
                        _id, c, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
                    ))
            env.push_packet(Packet(_id, events))
