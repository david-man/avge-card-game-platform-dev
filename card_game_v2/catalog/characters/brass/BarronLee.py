from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventRegulator
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import ActionTypes, EngineGroup, ResponseStatus, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer
from ....core.AVGEIOManager import CardSelectionQuery, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEDeck import AVGEDeck
    from ....constants import User
    from ....core.EventCatalog import TransferCard


class BarronLee(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._energy_cap_listener: BarronLee._EnergyCapRegulator | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.BRASS

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Embouchure()}), **({ActionTypes.PASSIVE: self._GetServed()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        # Entering play is handled globally by TransferCard's own passive-trigger special case.
        entering_play = deck_to.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
        was_in_play = deck_from.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
        if was_in_play and not entering_play and self._energy_cap_listener is not None:
            self._energy_cap_listener.cleanup()
            self._energy_cap_listener = None

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    class _EnergyCapRegulator(AVGEEventRegulator):
        '''Prevents opposing characters from holding more than 3 energy at once.'''

        def __init__(self, owner_card: BarronLee):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, None),
                owner_card.env,
                EngineGroup.EXTERNAL_PRECHECK_1,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGEEnergyTransfer):
                return False
            if not isinstance(event.token_to, AVGECharacterCard):
                return False
            if event.token_to.owner == self.owner_card.owner:
                return False
            return True

        async def respond(self, event: Event) -> ResponseStatus:
            assert isinstance(event, AVGEEnergyTransfer)
            assert isinstance(event.token_to, AVGECharacterCard)
            assert not callable(event.token_from)
            projected_amt = len(event.token_to.energy_tokens)
            if event.token_from is not event.token_to:
                projected_amt += 1

            if projected_amt > 3:
                await self.env.broadcast(BroadcastIO(
                    "Get Served prevents opposing characters from receiving more than 3 energy!",
                    default_timeout,
                ))
                if event.id.calling_action == ActionTypes.PLAYER_CHOICE:
                    return ResponseStatus.REGULATE_FAIL
                return ResponseStatus.REGULATE_IGNORE
            return ResponseStatus.REGULATE_PASS

    # ------------------------------------------------------------------
    # Abilities
    # ------------------------------------------------------------------

    class _GetServed(Ability):
        def __init__(self):
            super().__init__(
                name="Get Served",
                description="Opposing characters cannot hold more than 3 energy at a time. When this character is first played, remove any excess energy already attached to each opposing character.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, BarronLee)
            env = card.env
            if card._energy_cap_listener is None:
                card._energy_cap_listener = BarronLee._EnergyCapRegulator(card)
                card.add_listener(card._energy_cap_listener)

            # Strip any energy the opponent's characters already hold above the 3 token cap.
            opponent = env.get_opponent(card.owner)
            opposing_chars: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            _id = AVGEEngineID(card, ActionTypes.PASSIVE, BarronLee)
            events: list[Event | Generator] = []
            for c in opposing_chars:
                for _ in range(max(0, len(c.energy_tokens) - 3)):
                    events.append(AVGEEnergyTransfer(_id, c, env, env))

            if events:
                env.push_packet(Packet(_id, events))

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _Embouchure(Attack):
        def __init__(self):
            super().__init__(
                name="Embouchure",
                description="Deal 20 damage to the opposing active character. Then, rearrange all energy currently on your characters however you like.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, BarronLee)

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    env,
                )
            ]

            player = env.players[card.owner]
            own_chars: list[AVGECharacterCard] = [env.get_player_active(player)] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            sources = [c for c in own_chars for _ in c.energy_tokens]

            if sources:
                # destinations are paired with `sources` by position, so spell that order out.
                source_names = ", ".join(str(c) for c in sources)
                destinations = await env.report(CardSelectionQuery(
                    card.owner,
                    f"Embouchure: Choose where each energy goes, in this order (currently on: {source_names}).",
                    len(sources),
                    cast(list[AVGECard], own_chars),
                    cast(list[AVGECard], own_chars),
                    False,
                    True,
                ), _id)
                for source, dest in zip(sources, destinations):
                    assert isinstance(dest, AVGECharacterCard)
                    events.append(AVGEEnergyTransfer(_id, source, dest, env))

            env.push_packet(Packet(_id, events))
