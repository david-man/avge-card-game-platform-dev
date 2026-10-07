from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Ability, Attack, CardType
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import ActionTypes, AVGEAttributeModifier, EngineGroup
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard, TurnEnd
from ....engine.event import Event, Packet

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class JadenOuyang(AVGECharacterCard):
    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {
            ActionTypes.ATK_1: self._Balls(),
            ActionTypes.ATK_2: self._Ricochet(),
        }

    async def on_transfer(
        self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard,
    ) -> None:
        return

    class _Balls(Attack):
        def __init__(self):
            super().__init__(
                name="Balls",
                description="Give one energy to each of your in-play characters that currently has exactly one energy.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            if not isinstance(acting_card, AVGECharacterCard):
                raise TypeError("Balls requires a character actor")
            env = acting_card.env
            player = env.players[acting_card.owner]
            # Eligibility is intentionally snapshotted before any transfer resolves.
            targets = [
                card
                for pile in (DeckType.ACTIVE_CARD, DeckType.BENCH)
                for card in player.card_piles[pile]
                if isinstance(card, AVGECharacterCard) and len(card.energy_tokens) == 1
            ]
            _id = AVGEEngineID(acting_card, self.action_type, JadenOuyang)
            if targets:
                env.push_packet(Packet(_id, [
                    AVGEEnergyTransfer(_id, env, target, env) for target in targets
                ]))

    class _Ricochet(Attack):
        def __init__(self):
            super().__init__(
                name="Ricochet",
                description="Deal 50 damage to the opposing active. Each knockout dealt this way recursively deals 30 damage to every remaining opposing bench character.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            if not isinstance(acting_card, AVGECharacterCard):
                raise TypeError("Ricochet requires a character actor")
            env = acting_card.env
            target = env.get_player_active(env.get_opponent(acting_card.owner))
            _id = AVGEEngineID(acting_card, self.action_type, JadenOuyang)
            acting_card.add_listener(JadenOuyang._KnockoutChainReactor(acting_card, env, 1))
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))

    class _KnockoutChainReactor(AVGEEventReactor):
        def __init__(
            self, owner_card: AVGECharacterCard, env: AVGEEnvironment, pending_hits: int,
        ):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.ATK_2, JadenOuyang),
                env,
                EngineGroup.EXTERNAL_REACTORS,
            )
            self.owner_card = owner_card
            self.pending_hits = pending_hits
            self.started_round = env.round

        def match(self, event: Event) -> bool:
            if isinstance(event, TurnEnd) or self.env.round != self.started_round:
                self.cleanup()
                return False
            if self.pending_hits <= 0 or not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.target_card):
                return False
            return (
                event.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE
                and event.id.calling_card is self.owner_card
                and event.id.calling_action == ActionTypes.ATK_2
                and event.target_card.owner
                == self.env.get_opponent(self.owner_card.owner).id
            )

        async def react(self, event: Event) -> None:
            if not isinstance(event, AVGECardHPChangeEvent) or callable(event.target_card):
                return
            self.pending_hits -= 1
            knocked_out = event.target_card
            if event.final_change == 0:
                opponent = self.env.get_opponent(self.owner_card.owner)
                targets = [
                    target
                    for target in opponent.card_piles[DeckType.BENCH]
                    if isinstance(target, AVGECharacterCard)
                    and target.hp > 0
                    and target is not knocked_out
                ]
                if targets:
                    self.pending_hits += len(targets)
                    _id = AVGEEngineID(
                        self.owner_card, ActionTypes.ATK_2, JadenOuyang,
                    )
                    event.push_event([AVGECardHPChangeEvent(
                        _id,
                        target,
                        30,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        self.env,
                    ) for target in targets])
            if self.pending_hits <= 0:
                self.cleanup()
