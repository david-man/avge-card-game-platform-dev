#example file that shows how the environment can be used to make a game work. 
from enum import StrEnum, auto
from typing import override
from game import GenericCard, GenericCardholder, GameEnvironment
from random import shuffle
class Color(StrEnum):
    RED = auto()
    YELLOW = auto()
    BLUE = auto()
    GREEN = auto()
    NONE = auto()
    
class Type(StrEnum):
    REVERSE = auto()
    ONE = auto()
    TWO = auto()
    THREE = auto()
    FOUR = auto()
    FIVE = auto()
    SIX = auto()
    SEVEN = auto()
    EIGHT = auto()
    NINE = auto()
    SKIP = auto()
    PLUS2 = auto()
    PLUS4 = auto()
    WILDCARD = auto()

class UnoCard(GenericCard):
    def __init__(self, type : Type, color : Color):
        super().__init__()
        self.type = type
        self.color = color
    def __str__(self):
        return f"Color: {self.color}, Type: {self.type}"
class Deck(GenericCardholder):
    def __init__(self):
        super().__init__(npc = True)
    #don't need to write in any actions
class UnoPlayer(GenericCardholder):
    def __init__(self):
        super().__init__(npc = False)
    @override
    def get_actions(self):
        parent_env : UnoEnvironment = self.game_environment
        available_actions = ["ff"]
        if(parent_env.get_cardholder(-1).num_cards() > 0):
            available_actions.append("pick_deck")
        next_card : UnoCard = parent_env.top_of_pile
        if(next_card is None):
            raise RuntimeError("Trying to get action before full init process")
        for card_id in self.cards_holding.keys():
            card : UnoCard = self.cards_holding[card_id]
            if(card.type == Type.WILDCARD or card.type == Type.PLUS4):
                for color in [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW]:
                    available_actions.append(f"colorswap_{card.type}_{color}_{card_id}")
            elif(card.type == next_card.type or card.color == next_card.color):
                available_actions.append(f"play_{card.type}_{card.color}_{card_id}")
                
        return available_actions
    @override 
    def action(self, action : str) -> bool:
        parent_env : UnoEnvironment = self.game_environment
        if(action == 'ff'):
            parent_env.deactivate_cardholder(self.game_id)
            return True
        elif(action == 'pick_deck'):
            deck = parent_env.get_cardholder(-1)
            if(deck.num_cards() == 0):
                return False
            else:
                top_card_id = deck.peek()[0]
                parent_env.transfer_card(-1, self.game_id, top_card_id)
                return True
        elif(action[:10] == 'colorswap_'):
            str_split = action.split("_")
            color_requested = str_split[2]
            card_id_requested = int(str_split[3])
            if(card_id_requested not in self.cards_holding.keys()):
                return False
            elif(color_requested not in [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW]):
                return False
            else:
                card : UnoCard = self.cards_holding[card_id_requested]
                if(card.type != Type.WILDCARD and card.type != Type.PLUS4):
                    return False
                else:
                    card.color = color_requested
                    parent_env.get_cardholder(-1).add_card(parent_env.top_of_pile)#places old top of pile at the back
                    
                    parent_env.top_of_pile = card#places this card at the top of the pile

                    parent_env.discard_card(self.game_id, card_id_requested)#discards this card from the user's pile
                    
                    
                    if(card.type == Type.PLUS4):
                        deck = parent_env.get_cardholder(-1)
                        next_player = parent_env.next_player(self.game_id)
                        for _ in range(min(deck.num_cards(), 4)):
                            top_card_id = deck.peek()[0]
                            parent_env.transfer_card(-1, next_player, top_card_id)
                        
                    if(len(self.cards_holding.keys()) == 0):#check for win
                        parent_env.winner_flag = self.game_id
                    return True
        elif(action[:5] == 'play_'):
            str_split = action.split("_")
            card_id_requested = int(str_split[3])
            if(card_id_requested not in self.cards_holding.keys()):
                return False
            else:
                card : UnoCard = self.cards_holding[card_id_requested]
                top_card : UnoCard = parent_env.top_of_pile
                if(card.type == top_card.type or card.color == top_card.color):
                    if(card.type == Type.REVERSE):
                        parent_env.cardholder_order = list(reversed(parent_env.cardholder_order))
                        parent_env.cardholder_turn = parent_env.cardholder_order.index(self.game_id)
                    elif(card.type == Type.SKIP):
                        parent_env.cardholder_turn = parent_env.next_player(self.game_id)
                    elif(card.type == Type.PLUS2):
                        deck = parent_env.get_cardholder(-1)
                        next_player = parent_env.next_player(self.game_id)
                        for _ in range(min(deck.num_cards(), 2)):
                            top_card_id = deck.peek()[0]
                            parent_env.transfer_card(-1, next_player, top_card_id)
                    parent_env.get_cardholder(-1).add_card(parent_env.top_of_pile)#places old top of pile at the back
                
                    parent_env.top_of_pile = card#places this card at the top of the pile

                    parent_env.discard_card(self.game_id, card_id_requested)#discards this card from the user's pile
                    if(len(self.cards_holding.keys()) == 0):#check for win
                        parent_env.winner_flag = self.game_id
                    return True
        else:
            return False
                    
class UnoEnvironment(GameEnvironment):
    def __init__(self, num_players = 4):
        super().__init__()
        self.num_players = num_players

        #register cardholders and register cards under Deck cardholder
        deck_of_cards = []
        for color in [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW]:
            for type in [Type.ONE, Type.TWO, Type.THREE, Type.FOUR, Type.FIVE, Type.SIX, Type.SEVEN, 
                         Type.EIGHT, Type.NINE, Type.REVERSE, Type.SKIP, Type.PLUS2]:
                for _ in range(2):
                    deck_of_cards.append(UnoCard(type, color))
        for _ in range(4):
            deck_of_cards.append(UnoCard(Type.WILDCARD, Color.NONE))
            deck_of_cards.append(UnoCard(Type.PLUS4, Color.NONE))
        shuffle(deck_of_cards)
        deck = Deck()
        self.add_cardholder(-1, deck, deck_of_cards)
        for i in range(num_players):
            player = UnoPlayer()
            self.add_cardholder(i, player, [])
        
        #put something on the top
        top_idx, top_of_deck = self.get_cardholder(-1).peek()
        self.top_of_pile = top_of_deck
        self.discard_card(-1, top_idx)

        #hand out 3 cards to each player
        for i in range(self.num_players):
            for _ in range(3):
                top_idx, _ = self.get_cardholder(-1).peek()
                self.transfer_card(-1, i, top_idx)

        #establish the order randomly
        order = list(range(num_players))
        shuffle(order)
        self.establish_order(order)
    def reset_deck(self):
        for i in self.card_holders.keys():#transfer all cards back to the deck
            for card_id in self.card_holders[i].cards_holding.keys():
                self.transfer_card(i, -1, card_id)
        if(self.top_of_pile is not None):
            self.get_cardholder(-1).add_card(self.top_of_pile)
            self.top_of_pile = None
        #shuffle
        self.get_cardholder(-1).shuffle()
        #put a card on the top of the pile and discard it from the deck
        top_idx, top_of_deck = self.get_cardholder(-1).peek()
        self.top_of_pile = top_of_deck
        self.discard_card(-1, top_idx)

        #reset the winner flag
        self.winner_flag = None


if __name__ == '__main__':
    env = UnoEnvironment()
    while(env.winner_flag is None):
        print(f"Player|| {env.cardholder_turn}")
        print(f"Top of deck|| {str(env.top_of_pile)}")
        print(f"Cards left in pile|| {env.get_cardholder(-1).num_cards()}")
        old_deck = [str(i) for i in env.get_cardholder(env.cardholder_turn).get_cards()]
        print(f"Current hand|| {old_deck}")
        print(f"Available actions|| {env.card_holders[env.cardholder_turn].get_actions()}")
        valid_input = False
        while(not valid_input):
            input_str = input("Enter action: ")
            valid_input = env.card_holders[env.cardholder_turn].action(input_str)
        new_deck = [str(i) for i in env.get_cardholder(env.cardholder_turn).get_cards()]
        print(f"New deck|| {new_deck}")
        env.next_turn()
        if(env.active_participants == 1):
            for k in env.participants.keys():
                if(env.participants[k]):
                    env.winner_flag = k
        print("\n\n")
    print(f"Winner: {env.winner_flag}")