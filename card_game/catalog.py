from __future__ import annotations
from card_game.avge_abstracts.AVGECards import AVGECharacterCard
from card_game.constants import AVGECardAttribute, AVGEAttributeModifier, ActionTypes, ResponseType, Type, RNGType, Response
from card_game.engine.event_listener import ModifierEventListener, ReactorEventListener

class daniel(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.attributes = {
            AVGECardAttribute.TYPE: Type.WOODWIND,
            AVGECardAttribute.HP: 120,
            AVGECardAttribute.MV_1_COST: 0,
            AVGECardAttribute.MV_2_COST: 0,
            AVGECardAttribute.SWITCH_COST: 2,
            AVGECardAttribute.ENERGY_ATTACHED: 0,
        }
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

        self.RNG_type[ActionTypes.ATK_1] = RNGType.D6
    def atk_1(card, args=None) -> Response:
        from card_game.internal_events import AVGECardAttributeChange
        if(RNGType.D6 not in card.data_cache):
            print("NO RNG RECEIVED. DOING NOTHING")
            return card.generate_response()
        target_card = card.player.opponent.get_active_card()
        dmg_amount = 10 * int(card.data_cache[RNGType.D6])
        card.env.propose(AVGECardAttributeChange(
            target_card,
            AVGECardAttribute.HP,
            -dmg_amount,
            AVGEAttributeModifier.ADDITIVE,
            ActionTypes.ATK_1,
            card,
            Type.WOODWIND
        ))
        return card.generate_response()

    def passive(card, args=None) -> bool:
        owner_card = card
        class _RedirectDamageModifier(ModifierEventListener):
            def __init__(self):
                from card_game.constants import AVGEFlag
                super().__init__(flags=[AVGEFlag.CARD_ATTR_CHANGE])
                from card_game.internal_events import AVGECardAttributeChange
                def constraint(slf : ReactorEventListener, event : AVGECardAttributeChange):
                    return event.target_card.player == owner_card.player
                self.add_external_validity_constraint(constraint)
            def is_valid(self) -> bool:
                return True
            def make_announcement(self) -> bool:
                return True
            def package(self):
                return "Daniel Modifier"
            def modify(self, args = None):
                from card_game.internal_events import AVGECardAttributeChange
                if(args is None):
                    args = {}
                event: AVGECardAttributeChange = self.attached_event
                if(
                    event.attribute != AVGECardAttribute.HP
                    or event.attribute_modifier_type != AVGEAttributeModifier.ADDITIVE
                    or event.change_amount >= 0
                    or event.target_card == owner_card
                    or event.target_card.player != owner_card.player
                ):
                    return self.generate_response()
                damage = abs(event.change_amount)
                owner_hp = owner_card.attributes[AVGECardAttribute.HP]
                max_redirect = min(30, damage, owner_hp - 1)
                raw_amt = args.get("redirect_damage")
                if(raw_amt is None or int(raw_amt) > max_redirect):
                    return self.generate_response(
                        ResponseType.REQUIRES_QUERY,
                        {
                            "query_type": "redirect_damage",
                            "max_redirect": max_redirect
                        },
                    )
                raw_amt = int(raw_amt)
                if(raw_amt == 0):
                    return self.generate_response()
                else:
                    owner_card.data_cache["redirect_dmg"] = raw_amt
                event.change_amount = -(damage - raw_amt)
                return self.generate_response()
        class _RedirectDamageReactor(ReactorEventListener):
            def __init__(self):
                from card_game.constants import AVGEFlag
                super().__init__(flags=[AVGEFlag.CARD_ATTR_CHANGE])

                from card_game.internal_events import AVGECardAttributeChange
                
                def constraint(slf : ReactorEventListener, event : AVGECardAttributeChange):
                    return event.target_card.player == owner_card.player
                self.add_external_validity_constraint(constraint)
            def is_valid(self) -> bool:
                return True
            def make_announcement(self) -> bool:
                return True
            def package(self):
                return "Daniel Reactor"
            def react(self, args=None):
                from card_game.internal_events import AVGECardAttributeChange
                event: AVGECardAttributeChange = self.attached_event
                if("redirect_dmg" not in owner_card.data_cache):
                    return self.generate_response()
                else:
                    self.propose(
                        AVGECardAttributeChange(
                            owner_card,
                            AVGECardAttribute.HP,
                            -owner_card.data_cache['redirect_dmg'],
                            AVGEAttributeModifier.ADDITIVE,
                            ActionTypes.PASSIVE,
                            owner_card,
                            owner_card.attributes[AVGECardAttribute.TYPE],
                        )
                    )
                    del owner_card.data_cache['redirect_dmg']
                return self.generate_response()
        card.add_external_listener(_RedirectDamageModifier())
        card.add_external_listener(_RedirectDamageReactor())
        return card.generate_response()

