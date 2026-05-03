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
        assert(isinstance(self.attached_event, AVGEEnergyTransfer))
        target = self.attached_event.target
        projected_amt = len(target.energy)
        if self.attached_event.source != target:
            projected_amt += 1
        
        if projected_amt > 3:
            if(self.attached_event.catalyst_action == ActionTypes.PLAYER_CHOICE):
                return Response(
                    ResponseType.SKIP,
                    Notify(
                        "Get Served prevents opposing characters from receiving more than 3 energy!",
                        [PlayerID.P1, PlayerID.P2],
                        default_timeout,
                    ),
                )
            return Response(
                ResponseType.FAST_FORWARD,
                Notify(
                    "Get Served prevents opposing characters from receiving more than 3 energy!",
                    [PlayerID.P1, PlayerID.P2],
                    default_timeout,
                ),
            )
        return Response(ResponseType.ACCEPT, Data())

class BarronLee(AVGECharacterCard):
    _EMBOUCHURE_KEY = 'barron-lee-embouchure'
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.BRASS, 2, 1)
        self.atk_1_name = 'Embouchure'
        self.has_passive = True

    def passive(self) -> Response:
        # attach postcheck modifier
        self.add_listener(_BarronEnergyCapPostcheck(self))

        def generate_packet():
            packet = []
            assert(self.player is not None)
            opponent = self.player.opponent
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
                                self,
                                None
                            )
                        )

            return packet
        self.propose(AVGEPacket([generate_packet], AVGEEngineID(self, ActionTypes.PASSIVE, BarronLee)))
        return self.generic_response(self, ActionTypes.PASSIVE)

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
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
                    None,
                    card,
                )
            )
            return packet

        # total energy across player's active & bench
        chars = card.player.get_cards_in_play()
        total_energy = sum(len(c.energy) for c in chars)
        energy_tokens = [token for c in chars for token in c.energy]
        packet : PacketType= [generate_packet]
        if total_energy > 0:
            # prompt player for allocation per character; keys per character
            keys = [BarronLee._EMBOUCHURE_KEY+str(i) for i in range(total_energy)]
            vals = [card.env.cache.get(card, key, None, True) for key in keys]
            if vals[0] is None:
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[InputEvent](
                        [
                            InputEvent(
                                card.player,
                                keys,
                                lambda res : True,
                                ActionTypes.ATK_1,
                                card,
                                CardSelectionQuery(
                                    "Embouchure: How do you want to rearrange your energy?",
                                    cast(list[AVGECard], chars),
                                    cast(list[AVGECard], chars),
                                    False,
                                    True,
                                )
                            )
                        ]
                    )
                )
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
                    card,
                    None
                ))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, BarronLee)))
        return self.generic_response(card, ActionTypes.ATK_1)
