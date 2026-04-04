from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGEEnergyTransfer

class _BarronEnergyCapPostcheck(AVGEPostcheck):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_POSTCHECK_1)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGEEnergyTransfer):
            return False
        if not isinstance(event.target, AVGECharacterCard):
            return False
        if event.target.player == self.owner_card.player:
            return False
        return True
    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "BarronLee Energy Cap Postcheck"

    def assess(self, args=None) -> Response:
        from card_game.internal_events import AVGEEnergyTransfer
        # if target target energy attached > 3
        self.attached_event : AVGEEnergyTransfer
        target = self.attached_event.target
        new_amt = len(target.energy)

        if new_amt > 3:
            return self.generate_response(ResponseType.SKIP, {"msg": "Cannot attach more than 3 energy to opposing characters (BarronLee passive)."})
        return self.generate_response()

class BarronLee(AVGECharacterCard):
    _EMBOUCHURE_KEY = 'barron-lee-embouchure'
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.BRASS, 1)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(caller_card, parent_event: AVGEEvent) -> Response:
        # attach postcheck modifier
        caller_card.add_listener(_BarronEnergyCapPostcheck(caller_card))

        def generate_packet():
            packet = []
            opponent = caller_card.player.opponent
            for c in opponent.get_cards_in_play():
                cur = len(c.energy)
                if(cur > 3):
                    for token in c.energy[3:]:
                        packet.append(
                            AVGEEnergyTransfer(
                                token,
                                c,
                                c.player,
                                ActionTypes.PASSIVE,
                                caller_card
                            )
                        )

            return packet
        caller_card.propose(generate_packet)
        return caller_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent
        opponent = card.player.opponent
        # deal 20 damage to opponent active
        packet = []
        packet.append(
            AVGECardHPChange(
                lambda : opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.BRASS,
                ActionTypes.ATK_1,
                card,
            )
        )

        # total energy across player's active & bench
        chars = card.player.get_cards_in_play()
        total_energy = sum(len(c.energy) for c in chars)
        energy_tokens = [token for c in chars for token in c.energy]

        if total_energy <= 0:
            card.propose(packet)
            return card.generate_response()

        # prompt player for allocation per character; keys per character
        keys = [BarronLee._EMBOUCHURE_KEY+str(i) for i in range(len(chars))]
        vals = [card.env.cache.get(card, key, None, True) for key in keys]
        if vals[0] is None:
            # ask player for deterministic integer allocations
            def _valid(result) -> bool:
                if not isinstance(result, list) or len(result) != len(chars):
                    return False
                s = 0
                for v in result:
                    if(int(v) < 0):
                        return False
                    s += int(v)
                return s == total_energy

            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            keys,
                            InputType.DETERMINISTIC,
                            _valid,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "barron_energy_alloc", 
                            "character_cards_in_order": chars},
                        )
                    ]
                },
            )

        # read allocations and set each character's energy accordingly

        for idx, c in enumerate(chars):
            tokens = energy_tokens[:vals[idx]]
            for token in tokens:
                packet.append(AVGEEnergyTransfer(
                    token,
                    token.holder,
                    c,
                    ActionTypes.ATK_1,
                    card
                ))
            energy_tokens = energy_tokens[vals[idx]:]

        if len(packet) > 0:
            card.propose(packet)

        return card.generate_response()
