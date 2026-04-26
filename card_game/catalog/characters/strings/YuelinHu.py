from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.catalog.items.AVGEBirb import AVGEBirb
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard


class _YuelinBirbDrawReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, YuelinHu), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, TransferCard):
            return False
        if not isinstance(event.card, AVGEBirb):
            return False
        if event.pile_from.pile_type != Pile.DECK:
            return False
        if event.pile_to.pile_type != Pile.HAND:
            return False
        if event.pile_to.player != self.owner_card.player:
            return False
        if self.owner_card.cardholder is None:
            return False
        return self.owner_card.cardholder.pile_type in [Pile.ACTIVE, Pile.BENCH]

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        if args is None:
            args = {}

        owner = self.owner_card
        player = owner.player
        hand = player.cardholders[Pile.HAND]
        discard = player.cardholders[Pile.DISCARD]

        yn = owner.env.cache.get(owner, YuelinHu._DISCARD_DECISION_KEY, None, True)
        if yn is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            player,
                            [YuelinHu._DISCARD_DECISION_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            StrSelectionQuery(
                                'Musical Cat Summoned!: Discard the drawn AVGE Birb to deal 40 damage?',
                                ['Yes', 'No'],
                                ['Yes', 'No'],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if yn != 'Yes':
            return Response(ResponseType.ACCEPT, Notify('Musical Cat Summoned!: You kept AVGE Birb in hand.', all_players, default_timeout))

        assert isinstance(self.attached_event, TransferCard)
        birb = self.attached_event.card

        def discard_and_damage() -> PacketType:
            packet: PacketType = [
                TransferCard(
                    birb,
                    hand,
                    discard,
                    ActionTypes.PASSIVE,
                    owner,
                    None,
                )
            ]
            active = player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.PASSIVE,
                        None,
                        owner,
                    )
                )
            return packet

        owner.propose(AVGEPacket([discard_and_damage], AVGEEngineID(owner, ActionTypes.PASSIVE, YuelinHu)))
        return Response(ResponseType.ACCEPT, Notify('Musical Cat Summoned!: Discarded AVGE Birb to deal 40 damage.', all_players, default_timeout))


class YuelinHu(AVGECharacterCard):
    _DISCARD_DECISION_KEY = 'yuelinhu_discard_decision'
    _COIN_KEY_0 = 'yuelinhu_coin_0'
    _COIN_KEY_1 = 'yuelinhu_coin_1'
    _COIN_KEY_2 = 'yuelinhu_coin_2'

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 3)
        self.atk_1_name = 'Triple Stop'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_YuelinBirbDrawReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        r0 = card.env.cache.get(card, YuelinHu._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, YuelinHu._COIN_KEY_1, None, True)
        r2 = card.env.cache.get(card, YuelinHu._COIN_KEY_2, None, True)
        if r0 is None or r1 is None or r2 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [YuelinHu._COIN_KEY_0, YuelinHu._COIN_KEY_1, YuelinHu._COIN_KEY_2],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CoinflipData('Triple Stop: Flip 3 coins.')
                        )
                    ]),
            )

        heads = int(r0) + int(r1) + int(r2)
        packet: PacketType = []

        for _ in range(max(0, heads)):
            def hit_active() -> PacketType:
                active = card.player.opponent.get_active_card()
                p: PacketType = []
                if isinstance(active, AVGECharacterCard):
                    p.append(
                        AVGECardHPChange(
                            active,
                            40,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.STRING,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
                return p

            packet.append(hit_active)

        if len(packet) > 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, YuelinHu)))

        return self.generic_response(card, ActionTypes.ATK_1)
