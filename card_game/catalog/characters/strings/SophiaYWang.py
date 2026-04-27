from __future__ import annotations

from random import randint

from card_game.avge_abstracts import *
from card_game.catalog.items.AVGEBirb import AVGEBirb
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard


class _SophiaAtk2KnockoutReactor(AVGEReactor):
    _PENDING_HITS_KEY = 'sophiaywang_ricochet_pending_hits'

    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_2, SophiaYWang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card
        self.owner_card.env.cache.set(self.owner_card, _SophiaAtk2KnockoutReactor._PENDING_HITS_KEY, 1)

    def _get_pending_hits(self) -> int:
        pending = self.owner_card.env.cache.get(self.owner_card, _SophiaAtk2KnockoutReactor._PENDING_HITS_KEY, 0)
        if isinstance(pending, int):
            return pending
        return 0

    def _set_pending_hits(self, value: int):
        self.owner_card.env.cache.set(self.owner_card, _SophiaAtk2KnockoutReactor._PENDING_HITS_KEY, value)

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.caller != self.owner_card:
            return False
        if event.catalyst_action != ActionTypes.ATK_2:
            return False
        if not isinstance(event.target_card, AVGECharacterCard):
            return False
        if event.target_card.player != self.owner_card.player.opponent:
            return False
        return self._get_pending_hits() > 0

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self._get_pending_hits() <= 0:
            self.owner_card.env.cache.delete(self.owner_card, _SophiaAtk2KnockoutReactor._PENDING_HITS_KEY)
            self.invalidate()

    def react(self, args=None):
        if args is None:
            args = {}
        assert isinstance(self.attached_event, AVGECardHPChange)
        assert isinstance(self.attached_event.final_change, int)
        owner = self.owner_card
        self._set_pending_hits(self._get_pending_hits() - 1)

        if self.attached_event.final_change == 0:
            knocked_out = self.attached_event.target_card

            def splash_remaining() -> PacketType:
                packet: PacketType = []
                targets = [
                    target
                    for target in owner.player.opponent.cardholders[Pile.BENCH]
                    if isinstance(target, AVGECharacterCard) and target.hp > 0 and target != knocked_out
                ]
                for target in targets:
                    packet.append(
                        AVGECardHPChange(
                            target,
                            30,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.STRING,
                            ActionTypes.ATK_2,
                            None,
                            owner,
                        )
                    )
                self._set_pending_hits(self._get_pending_hits() + len(packet))
                return packet

            self.propose(AVGEPacket([splash_remaining], AVGEEngineID(owner, ActionTypes.ATK_2, SophiaYWang)))
            return Response(ResponseType.ACCEPT, Notify('Ricochet: Knockout confirmed, 30 damage to each remaining opposing character.', all_players, default_timeout))

        return Response(ResponseType.ACCEPT, Notify('Ricochet: Damage resolved with no knockout, no splash damage applied.', all_players, default_timeout))


class SophiaYWang(AVGECharacterCard):
    _GACHA_DRAW_CHOICE_KEY = 'sophiaywang_gacha_draw_choice'
    _GACHA_DRAWN_CARDS_KEY = 'sophiaywang_gacha_cards_drawn'

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.STRING, 2, 1, 3)
        self.atk_1_name = 'Gacha Gaming'
        self.atk_2_name = 'Ricochet'

    def _cleanup_gacha_cache(self, card: AVGECharacterCard):
        card.env.cache.delete(card, SophiaYWang._GACHA_DRAWN_CARDS_KEY)

    def _draw_choice_interrupt(self, card: AVGECharacterCard) -> Response:
        return Response(
            ResponseType.INTERRUPT,
            Interrupt[AVGEEvent]([
                    InputEvent(
                        card.player,
                        [SophiaYWang._GACHA_DRAW_CHOICE_KEY],
                        lambda r: True,
                        ActionTypes.ATK_1,
                        card,
                        StrSelectionQuery(
                            'Gacha Gaming: Draw a card and take 20 fixed damage? (You cannot self-KO.)',
                            ['Yes', 'No'],
                            ['Yes', 'No'],
                            False,
                            False,
                        )
                    )
                ]),
        )

    def _shuffle_drawn_cards_back(self, card: AVGECharacterCard, drawn_cards: list[AVGECard]):
        deck = card.player.cardholders[Pile.DECK]
        packet: PacketType = []
        for drawn in drawn_cards:
            holder = drawn.cardholder
            if holder is None or holder == deck:
                continue

            def put_back(c=drawn) -> PacketType:
                c_holder = c.cardholder
                if c_holder is None or c_holder == deck:
                    return []
                return [
                    TransferCard(
                        c,
                        c_holder,
                        deck,
                        ActionTypes.ATK_1,
                        card,
                        None,
                        randint(0, len(deck)),
                    )
                ]

            packet.append(put_back)

        if len(packet) > 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang)))

    def atk_1(self, card: AVGECharacterCard) -> Response:
        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]

        drawn_cards_cached = card.env.cache.get(card, SophiaYWang._GACHA_DRAWN_CARDS_KEY, [], False)
        drawn_cards: list[AVGECard] = []
        if isinstance(drawn_cards_cached, list):
            drawn_cards = [c for c in drawn_cards_cached if isinstance(c, AVGECard)]

        if len(deck) == 0 or card.hp <= 20:
            self._shuffle_drawn_cards_back(card, drawn_cards)
            self._cleanup_gacha_cache(card)
            return self.generic_response(card, ActionTypes.ATK_1)

        choice = card.env.cache.get(card, SophiaYWang._GACHA_DRAW_CHOICE_KEY, None, True)
        if choice is None:
            return self._draw_choice_interrupt(card)

        if not choice == 'Yes':
            self._shuffle_drawn_cards_back(card, drawn_cards)
            self._cleanup_gacha_cache(card)
            return self.generic_response(card, ActionTypes.ATK_1)

        next_card = deck.peek()
        packet: PacketType = [
            TransferCard(next_card, deck, hand, ActionTypes.ATK_1, card, None)
        ]

        if isinstance(next_card, AVGEBirb):
            self._cleanup_gacha_cache(card)
            packet.append(
                AVGECardHPChange(
                    card,
                    card.max_hp,
                    AVGEAttributeModifier.SET_STATE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang)))
            return self.generic_response(card, ActionTypes.ATK_1)

        new_drawn_cards = drawn_cards + [next_card]
        card.env.cache.set(card, SophiaYWang._GACHA_DRAWN_CARDS_KEY, new_drawn_cards)

        new_hp = max(1, card.hp - 20)
        follow_up: list[AVGEEvent] = [
            TransferCard(next_card, deck, hand, ActionTypes.ATK_1, card, None),
            AVGECardHPChange(
                card,
                new_hp,
                AVGEAttributeModifier.SET_STATE,
                CardType.STRING,
                ActionTypes.ATK_1,
                None,
                card,
            ),
        ]

        return Response(ResponseType.INTERRUPT, Interrupt[AVGEEvent](follow_up))

    def atk_2(self, card: AVGECharacterCard) -> Response:
        card.add_listener(_SophiaAtk2KnockoutReactor(card))

        def atk() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([atk], AVGEEngineID(card, ActionTypes.ATK_2, SophiaYWang)))
        return self.generic_response(card, ActionTypes.ATK_2)
