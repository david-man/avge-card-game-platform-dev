from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Ability, Attack, CardType
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import ActionTypes, AVGEAttributeModifier, EngineGroup
from ....core.AVGEIOManager import CardSelectionQuery
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....engine.event import Event, Packet

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class PhilipYao(AVGECharacterCard):
    _ROTATED_CACHE_KEY = "is_rotated"

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {
            ActionTypes.PASSIVE: self._Rotation(),
            ActionTypes.ATK_1: self._Tossup(),
        }

    def additional_wire_state(self) -> dict[str, bool]:
        return {"is_rotated": bool(self.cache_get(self._ROTATED_CACHE_KEY, False))}

    def _rotation_listeners(self) -> list[PhilipYao._RotationReactor]:
        return [
            listener
            for listener in self.env.engine.listeners
            if isinstance(listener, PhilipYao._RotationReactor)
            and listener.owner_card is self
        ]

    async def on_transfer(
        self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard,
    ) -> None:
        play_zones = {DeckType.ACTIVE_CARD, DeckType.BENCH}
        if deck_from.deck_type in play_zones and deck_to.deck_type not in play_zones:
            for listener in self._rotation_listeners():
                listener.cleanup()
            self.cache_set(self._ROTATED_CACHE_KEY, False)

    class _Rotation(Ability):
        def __init__(self):
            super().__init__(
                name="Rotation!",
                description="After a successful incoming energy transfer, turn this card upside down or upright.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            if not isinstance(action_card, PhilipYao):
                raise TypeError("Rotation's definition card must be PhilipYao")
            active = [
                listener
                for listener in action_card._rotation_listeners()
                if not listener.requires_cleanup
            ]
            if not active:
                action_card.add_listener(
                    PhilipYao._RotationReactor(action_card, action_card.env),
                )

    class _RotationReactor(AVGEEventReactor):
        def __init__(self, owner_card: PhilipYao, env: AVGEEnvironment):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, PhilipYao),
                env,
                EngineGroup.EXTERNAL_REACTORS,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGEEnergyTransfer):
                return False
            if callable(event.token_from) or callable(event.token_to):
                return False
            return event.token_to is self.owner_card and event.token_from is not self.owner_card

        async def react(self, event: Event) -> None:
            if not isinstance(event, AVGEEnergyTransfer):
                return
            # The reactor runs after CORE, so this distinguishes a real transfer from
            # an attempt made while the source had no energy.
            if not event.did_transfer:
                return
            self.owner_card.cache_set(
                PhilipYao._ROTATED_CACHE_KEY,
                not bool(self.owner_card.cache_get(PhilipYao._ROTATED_CACHE_KEY, False)),
            )

    class _Tossup(Attack):
        def __init__(self):
            super().__init__(
                name="Tossup",
                description="Upright: deal 70 damage. Upside down: move any card from your deck or discard to your hand.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            if not isinstance(action_card, PhilipYao):
                raise TypeError("Tossup's definition card must be PhilipYao")
            if not isinstance(acting_card, AVGECharacterCard):
                raise TypeError("Tossup requires a character actor")
            env = acting_card.env
            _id = AVGEEngineID(acting_card, self.action_type, PhilipYao)
            if not bool(action_card.cache_get(PhilipYao._ROTATED_CACHE_KEY, False)):
                target = env.get_player_active(env.get_opponent(acting_card.owner))
                env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                    _id,
                    target,
                    70,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    env,
                )]))
                return

            player = env.players[acting_card.owner]
            deck = player.card_piles[DeckType.DECK]
            discard = player.card_piles[DeckType.DISCARD]
            choices = list(deck.cards_holding) + list(discard.cards_holding)
            if not choices:
                return
            picked = (await env.report(CardSelectionQuery(
                acting_card.owner,
                "Tossup: Choose any card from your deck or discard to put in your hand.",
                1,
                choices,
                choices,
                False,
                False,
            ), _id))[0]
            source = deck if picked in deck.cards_holding else discard
            env.push_packet(Packet(_id, [TransferCard(
                _id, picked, source, player.card_piles[DeckType.HAND], env,
            )]))
