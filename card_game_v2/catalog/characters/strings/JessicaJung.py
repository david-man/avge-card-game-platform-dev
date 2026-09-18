from __future__ import annotations

import random
from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType, AVGESupporterCard
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, ReorderDeck, TransferCard
from ....core.AVGEIOManager import CoinflipData, CardSelectionQuery, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class JessicaJung(AVGECharacterCard):
    '''Cleric Spell's once-per-turn gate uses a plain instance field, same
    simplification established elsewhere.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._cleric_spell_last_used_round: int | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Vibrato()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.ACTIVATE_ABILITY: self._ClericSpell()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _ClericSpell(Ability):
        def __init__(self):
            super().__init__(
                name="Cleric Spell",
                description="Once per turn, flip a coin; on heads, may shuffle a supporter from your discard into your deck.",
                ability_type=ActionTypes.ACTIVATE_ABILITY,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            assert isinstance(card, JessicaJung)
            # Ownership is verified centrally, server-side, before Phase2ActivateAbility is ever
            # constructed (server/io_adapter.py's _deserialize_phase2).
            return card._cleric_spell_last_used_round != card.env.round

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, JessicaJung)
            env = card.env
            player = env.players[card.owner]
            card._cleric_spell_last_used_round = env.round

            _id = AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, JessicaJung)
            heads = await env.report(CoinflipData(card.owner, "Cleric Spell: Flip a coin."), _id)
            if heads != 1:
                await env.report(Notification(
                    card.owner,
                    "Jessica Jung used Cleric Spell, but she didn't roll a heads...", default_timeout,
                ), _id)
                return

            discard = player.card_piles[DeckType.DISCARD]
            supporter_cards = [c for c in discard.cards_holding if isinstance(c, AVGESupporterCard)]
            if not supporter_cards:
                await env.report(Notification(
                    card.owner,
                    "Jessica Jung used Cleric Spell, but there are no supporter cards in the discard pile...",
                    default_timeout,
                ), _id)
                return

            picked = await env.report(CardSelectionQuery(
                card.owner,
                "Cleric Spell: Choose a supporter in your discard to shuffle into your deck.",
                1,
                cast(list[AVGECard], supporter_cards),
                cast(list[AVGECard], supporter_cards),
                False,
                False,
            ), _id)
            chosen = picked[0]
            assert isinstance(chosen, AVGESupporterCard)

            deck = player.card_piles[DeckType.DECK]

            def _shuffled_order(deck: AVGEDeck = deck):
                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                return gen

            events: list[Event | Generator] = [
                TransferCard(_id, chosen, discard, deck, env),
                ReorderDeck(_id, deck, _shuffled_order(), env),
            ]
            env.push_packet(Packet(_id, events))

    class _Vibrato(Attack):
        def __init__(self):
            super().__init__(name="Vibrato", description="Deal 40 damage to the opposing active.", atk_type=ActionTypes.ATK_1, cost=2)

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), JessicaJung)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))
