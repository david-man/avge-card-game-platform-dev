#this file is purely for cards 
from avge_platform import *
class AverageJoe(AVGECharacterCard):
    def __init__(self):
        super().__init__()
        self.max_hp = 100
        self.current_hp = 100
        self.has_passive_ability = True
        self.has_move_2 = True
        self.type = Type.STRING
    def __str__(self):
        return f"Jo, {self.current_hp}, {self.ingame_id}"
    @override
    def passive(self):
        def func(card, attacking_type, attack_type, damage):
            self.cleanup_flag = True#tells the game to clean up after this turn
            damage = damage / 2
            return damage
        self.dmg_inject(self, DamageFlow.PRE_DMG, func)
        return True
    @override
    def move_two(self):
        game_env : AVGEEnvironment = self.game_environment
        active_card = game_env.get_active_card(self.cardholder.player.opponent.ingame_id)
        active_card.damage(self.type, 50, ActionTypes.ATK_2)#does 50 dmg
        return True
    @override
    def can_play_move_2(self):
        if(self.energies_attached[Type.ALL] >= 1):
            return True
        return False
    @override
    def can_swap(self):
        if(self.energies_attached[Type.ALL] >= 1):
            return True
        return False
    @override
    def consume_energy_and_swap(self):
        if(self.energies_attached[Type.ALL] >= 1):
            self.energies_attached[Type.ALL] -= 1
            return True
        return False
    @override
    def cleanup(self):
        self.dmg_purify(self, DamageFlow.PRE_DMG)
        return True