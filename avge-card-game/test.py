from avge_platform import *
from avge_cards import *

game_env = AVGEEnvironment()
deck_1 = []
deck_2 = []
for _ in range(cards_per_deck):
    deck_1.append(AverageJoe())
    deck_2.append(AverageJoe())

game_env.initialize_player(deck_1, PlayerID.P1)
game_env.initialize_player(deck_2, PlayerID.P2)
game_env.run()