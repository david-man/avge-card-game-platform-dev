from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGEEnergyTransfer

class _BarronEnergyCapPostcheck(AVGEAssessor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, None), group=EngineGroup.EXTERNAL_PRECHECK_1)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGEEnergyTransfer):
            return False
        if not isinstance(event.target, AVGECharacterCard):
            return False
        if event.target.player == self.owner_card.player:
            return False
        return True

    def update_status(self):
        return

    def assess(self, args=None) -> Response:
        from card_game.internal_events import AVGEEnergyTransfer
        # if target target energy attached > 3
        assert(isinstance(self.attached_event, AVGEEnergyTransfer))
        target = self.attached_event.target
        new_amt = len(target.energy)

        if new_amt > 3:
            return self.generate_response(ResponseType.FAST_FORWARD, {MESSAGE_KEY: "Cannot attach more than 3 energy to opposing characters (BarronLee passive)."})
        return self.generate_response()

class BarronLee(AVGECharacterCard):
    _EMBOUCHURE_KEY = 'barron-lee-embouchure'
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.BRASS, 1, 1)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card) -> Response:
        # attach postcheck modifier
        card.add_listener(_BarronEnergyCapPostcheck(card))

        def generate_packet():
            packet = []
            assert(card.player is not None)
            opponent = card.player.opponent
            assert opponent is not None
            for c in opponent.get_cards_in_play():
                cur = len(c.energy)
                assert(isinstance(c.player, AVGEPlayer))
                if(cur > 3):
                    for token in c.energy[3:]:
                        packet.append(
                            AVGEEnergyTransfer(
                                token,
                                c,
                                c.env,
                                ActionTypes.PASSIVE,
                                card
                            )
                        )

            return packet
        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.PASSIVE, BarronLee)))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange
        opponent = card.player.opponent
        # deal 20 damage to opponent active
        def generate_packet():
            packet = []
            packet.append(
                AVGECardHPChange(
                    opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    ActionTypes.ATK_1,
                    card,
                )
            )
            return packet

        # total energy across player's active & bench
        chars = card.player.get_cards_in_play()
        total_energy = sum(len(c.energy) for c in chars)
        energy_tokens = [token for c in chars for token in c.energy]

        if total_energy <= 0:
            card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, BarronLee)))
            return card.generate_response(data={MESSAGE_KEY: "Total energy is none!"})

        # prompt player for allocation per character; keys per character
        keys = [BarronLee._EMBOUCHURE_KEY+str(i) for i in range(total_energy)]
        vals = [card.env.cache.get(card, key, None, True) for key in keys]
        if vals[0] is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            keys,
                            InputType.SELECTION,
                            lambda res : True,
                            ActionTypes.ATK_1,
                            card,
                            {LABEL_FLAG: "barron_lee_energy_alloc", 
                            TARGETS_FLAG: chars,
                            ALLOW_REPEAT: True,
                            DISPLAY_FLAG: chars},
                        )
                    ]
                },
            )

        packet : PacketType= [generate_packet]
        # transfer accordingly
        for i, token_to in enumerate(vals):
            assert isinstance(token_to, AVGECharacterCard)
            cur_holder = energy_tokens[i].holder
            assert cur_holder is not None and not isinstance(cur_holder, AVGEEnvironment)
            packet.append(AVGEEnergyTransfer(
                energy_tokens[i],
                cur_holder,
                token_to,
                ActionTypes.ATK_1,
                card
            ))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, BarronLee)))

        return card.generate_response()
