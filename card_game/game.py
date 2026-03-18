from .avge_abstracts.AVGECardholder import *
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEEnvironment import *
from .avge_abstracts.AVGEEvent import *
from .avge_abstracts.AVGEPlayer import *
from .internal_events import *
import unittest

class BasicCharacterCard(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.attributes : dict[AVGECardAttribute, Type | float] = {
            AVGECardAttribute.TYPE: Type.BRASS,
            AVGECardAttribute.HP: 100,
            AVGECardAttribute.MV_1_COST: 0,
            AVGECardAttribute.MV_2_COST: 1,
            AVGECardAttribute.SWITCH_COST: 1,
            AVGECardAttribute.ENERGY_ATTACHED: 0
        }
        self.has_atk_1 : bool = True
        self.has_atk_2 : bool = True
        self.has_passive : bool = False#any ability that activates when the card gets put in play
        self.has_active : bool = False#any ability that can be activated whenever
    def atk_1(self):
        return True
    def atk_2(self):
        return True


class TestBasicCharacterCard(unittest.TestCase):
    def setUp(self):
        self.card = BasicCharacterCard("basic_1")

    def test_default_attributes(self):
        self.assertEqual(self.card.attributes[AVGECardAttribute.TYPE], Type.BRASS)
        self.assertEqual(self.card.attributes[AVGECardAttribute.HP], 100)
        self.assertEqual(self.card.attributes[AVGECardAttribute.MV_1_COST], 0)
        self.assertEqual(self.card.attributes[AVGECardAttribute.MV_2_COST], 1)
        self.assertEqual(self.card.attributes[AVGECardAttribute.SWITCH_COST], 1)
        self.assertEqual(self.card.attributes[AVGECardAttribute.ENERGY_ATTACHED], 0)

    def test_basic_attack_flags(self):
        self.assertTrue(self.card.has_atk_1)
        self.assertTrue(self.card.has_atk_2)
        self.assertFalse(self.card.has_passive)
        self.assertFalse(self.card.has_active)

    def test_attacks_return_true(self):
        self.assertTrue(self.card.atk_1())
        self.assertTrue(self.card.atk_2())


if __name__ == "__main__":
    unittest.main()
    
    