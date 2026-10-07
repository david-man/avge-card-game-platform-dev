from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TurnEnd, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class KatieXiang(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._heartbeat: KatieXiang._UndyingHeartbeat | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Rubato()}), **({ActionTypes.PASSIVE: self._UndyingHeartbeatPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _UndyingHeartbeatPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Nausicaa's Undying Heartbeat",
                description="At the end of your turn, if this character is below 50 HP, heal your whole team 20.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, KatieXiang)
            if card._heartbeat is None:
                card._heartbeat = KatieXiang._UndyingHeartbeat(card, card.env)
                card.add_listener(card._heartbeat)

    class _UndyingHeartbeat(AVGEEventReactor):
        def __init__(self, owner_card: KatieXiang, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, KatieXiang), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, TurnEnd):
                return False
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            # TurnEnd.act() flips env.turn before reactors run. The owner's turn
            # just ended when the new turn belongs to the opponent.
            if self.env.turn == self.owner_card.owner:
                return False
            return self.owner_card.hp < 50

        async def react(self, event: Event) -> None:
            owner_card = self.owner_card
            player = self.env.players[owner_card.owner]
            _id = AVGEEngineID(owner_card, ActionTypes.PASSIVE, KatieXiang)
            own_chars = [
                c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, c, 20, AVGEAttributeModifier.ADDITIVE, CardType.ALL, self.env)
                for c in own_chars
            ]
            await self.env.broadcast(BroadcastIO("Nausicaa's Undying Heartbeat: Healed +20", default_timeout))
            event.push_event(events)

    class _Rubato(Attack):
        def __init__(self):
            super().__init__(
                name="Rubato",
                description="Deal 20 damage to the opposing active now, and 30 more at the end of your opponent's next turn.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, KatieXiang)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
            )]))
            # TurnEnd.act() advances the round before reactors run. The opponent's
            # next turn ends two round numbers after this attack.
            env.add_listener(KatieXiang._RubatoDelayed(card, env.round + 2, env))

    class _RubatoDelayed(AVGEEventReactor):
        def __init__(self, attacker: AVGECharacterCard, round_active: int, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.ATK_1, KatieXiang), env, EngineGroup.EXTERNAL_REACTORS)
            self.attacker = attacker
            self.owner = attacker.owner
            self.round_active = round_active

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_active:
                self.cleanup()
                return False
            return isinstance(event, TurnEnd) and self.env.round == self.round_active

        async def react(self, event: Event) -> None:
            self.cleanup()
            opponent = self.env.get_opponent(self.owner)
            target = self.env.get_player_active(opponent)
            # calling_card=self.attacker (not None) so AVGEWeaknessModifier's own
            # isinstance(event.id.calling_card, AVGECharacterCard) check offers the
            # crit coinflip for this delayed hit too, same as the initial 20 damage did.
            _id = AVGEEngineID(self.attacker, ActionTypes.ATK_1, KatieXiang)
            await self.env.broadcast(BroadcastIO("Rubato: 30 damage", default_timeout))
            event.push_event([AVGECardHPChangeEvent(
                _id, target, 30, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, self.env,
            )])
