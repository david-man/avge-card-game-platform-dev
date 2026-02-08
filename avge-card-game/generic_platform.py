from __future__ import annotations
from collections import OrderedDict
from random import shuffle
from typing import override, Any

class GenericCard():
    def __init__(self):#type: ignore
        self.cardholder : 'GenericCardholder' = None
        self.game_environment : 'GameEnvironment'= None
        self.player : 'GenericPlayer' = None
        self.ingame_id : Any= None#ingame_id of the card in the game environment
    def register(self, cardholder : 'GenericCardholder', ingame_id : Any):
        #attaches card to card holder with an id
        self.cardholder = cardholder
        self.player = cardholder.player
        self.game_environment = cardholder.player.game_environment
        self.ingame_id = ingame_id
    def check():
        #makes a check to make sure cards are initialized properly. 
        #the base abstract cards already override this
        pass
    def remove_from_cardholder(self):
        #disassociates this from the cardholder, but keeps the id and game environment
        self.cardholder = None
        self.player =None
    def play_card(self, args = []) -> bool:
        #card-specific actions should be encoded in this. returns success
        pass
    def __str__(self):
        pass


class GenericCardholder():
    def __init__(self):
        self.cards_holding : OrderedDict[Any, GenericCard] = OrderedDict([])
        self.ingame_id : Any= None#id of the cardholder in the game environment
        self.player : 'GenericPlayer' = None
        self.game_environment : 'GameEnvironment' = None
    def num_cards(self) -> int:
        return len(self.cards_holding.keys())
    def has_card(self, ingame_id : Any) -> bool:
        #does this cardholder have the card
        return ingame_id in self.cards_holding.keys()
    def get_card(self, ingame_id : Any) -> GenericCard:
        #returns the instance of the card stored at ingame_id
        if(ingame_id in self.cards_holding):
            return self.cards_holding[ingame_id]
        else:
            raise RuntimeError("Tried to get a nonexistent card")
    def get_cards(self) -> list[GenericCard]:
        #gets all the cards
        to_return = []
        for i in self.cards_holding.values():
            to_return.append(i)
        return to_return
    def register_card(self, card : GenericCard, back : bool = True, 
                      card_id : Any = None) -> None:
        #adds a card to the pile. can move it to the front or back. links both tgt
        if(card.ingame_id is None and card_id is None):
            raise("Tried to add a card that hasn't been given an id!")
        if(card.ingame_id is not None and card_id is None):
            card_id = card.ingame_id
        card.register(self, card_id)
        self.cards_holding[card_id] = card
        if(back):
            self.cards_holding.move_to_end(card_id, True)
        else:
            self.cards_holding.move_to_end(card_id, False)
    def remove_card(self, card_id : Any) -> GenericCard:
        #removes the card from the card collection. returns a pointer to the card
        if(card_id in self.cards_holding):
            card = self.cards_holding[card_id]
            card.remove_from_cardholder()
            return self.cards_holding.pop(card_id)
        else:
            raise RuntimeError("Tried to remove a nonexistent card")
    def register(self, player : 'GenericPlayer', ingame_id) -> None:
        #registers the stack to a player
        self.player = player
        self.game_environment = player.game_environment
        self.ingame_id = ingame_id
    def unregister(self):
        #unregisters the stack from the player
        self.player = None
    def reregister_dict(self, new_dict : OrderedDict[Any, GenericCard]):
        #re-registers the dict(usually for preserving content but changing the order)
        if(len(new_dict.keys()) != len(self.cards_holding.keys())):
            raise RuntimeError("Attempted to reregister the ordered dict w/ incorrect set of keys")
        for key in new_dict.keys():
            if(key not in self.cards_holding.keys() or self.cards_holding[key] != new_dict[key]):
                raise RuntimeError("Attempted to reregister the ordered dict w/ incorrect set of keys & values")
        self.cards_holding = new_dict
    def shuffle(self):
        #special reordering where you simply shuffle
        keys = list(self.cards_holding.keys())
        shuffle(keys)
        new_dict : OrderedDict[Any, GenericCard]= {}
        for key in keys:
            new_dict[key] = self.cards_holding[key]
        self.reregister_dict(new_dict)
    def peek(self) -> tuple[Any, GenericCard]:
        #peek @ top id & top card
        return next(iter(self.cards_holding.items()))


class GenericPlayer():
    def __init__(self, npc : bool):
        self.card_holders : dict[Any, GenericCardholder] = {}
        self.ingame_id : Any = None
        self.game_environment : 'GameEnvironment' = None
        self.npc = npc

    def register(self, game_environment : 'GameEnvironment', ingame_id : Any) -> None:
        #registers the player to the environment
        self.game_environment = game_environment
        self.ingame_id = ingame_id

    def get_cardholder(self, ingame_id : Any) -> GenericCard:
        #returns the cardholder stored at the ingame_id
        if(ingame_id in self.card_holders):
            return self.card_holders[ingame_id]
        else:
            raise RuntimeError("Tried to get a nonexistent card")
    def register_cardholder(self, cardholder : GenericCardholder, id : Any):
        #adds a cardholder to the environment. links both to each other
        cardholder.register(self, id)
        self.card_holders[id] = cardholder
    def remove_cardholder(self, id : Any) -> GenericCardholder:
        if(id in self.card_holders):
            cardholder = self.card_holders[id]
            cardholder.unregister()
            del self.card_holders[id]
            return cardholder
        else:
            raise RuntimeError("Tried to remove a nonexistent card")

    def action(self, args : list = []) -> list:
        #override this function to encode player-specific actions
        #returns any list of arguments
        pass

    def validate_action(self, actions : list) -> bool:
        #this function validates whether the action given is allowed
        pass

    def on_entry(self) -> None:
        #any actions that the player will take as their turn ends
        pass

    def on_exit(self) -> None:
        #any actions that the player will take before their turn begins
        pass

class GameEnvironment():
    def __init__(self): # type: ignore
        #fully abstract dicts mapping ingame_ids to their respective objects. 
        # all players, cards, cardholders that can ever participate in the game should be added after env initialization with ingame_ids
        # note: players should be initialized first, followed by cardholders, followed by cards
        self.players : dict[Any, GenericPlayer] = {}

        self.has_turn : dict[Any, bool] = {}#dict mapping ingame ids to whether the player should be given a turn
        self.num_players : int = 0#identifies the number of active participants
        self.cardholder_order : list[Any]= None#identifies the order of players
        self.cardholder_turn : Any = None#identifies the id of the player whose turn it currently is
        self.winner_flag : Any= None#flag that gets set to the id of the winner
    def reset(self):
        #removes all cardholders and prays that Python does adequate garbage collection
        self.__init__()

    def winner_protocol(self):
        #protocol to use after a winner has been decided
        pass
    
    def notify(self, player_id: Any, notif : list = []) -> None:
        #this function notifies a player with some notifs
        #should be overwritten
        pass
    def query(self, player_id : Any, query : list = []) -> list:
        #this function queries a player and returns the arguments given. 
        #should be overriden
        pass

    def get_player(self, player_id : Any):
        if(player_id not in self.players.keys()):
            raise RuntimeError("Tried to access a nonexistent cardholder")
        return self.players[player_id]

    
    def register_new_player(self, empty_player : GenericPlayer, ingame_id : Any,
                            has_turn : bool = True):
        #registers an empty player in the environment with some id
        empty_player.register(self, ingame_id)
        self.players[ingame_id] = empty_player
        self.has_turn[ingame_id] = has_turn
        if(has_turn and not empty_player.npc):
            self.num_players += 1
    def deactivate_player(self, game_id : Any) -> None:
        #deactivates a cardholder, making it no longer get a turn in the overall game loop
        #note: this does NOT affect player ordering. the game will simply skip the player
        if(game_id not in self.players.keys()):
            raise RuntimeError("Tried to deactivate a nonexistent player")
        if(not self.has_turn[game_id]):
            raise RuntimeError("Tried to deactivate a deactivated player")
        self.has_turn[game_id] = False
        self.num_players -= 1
        if(self.num_players == 1):
            #set this to winner
            for player_id in self.players.keys():
                if(self.has_turn[player_id]):
                    self.winner_flag = player_id
                    break
    def activate_player(self, game_id : Any) -> None:
        #reactivates a players, placing it back in the game loop
        if(game_id not in self.players.keys()):
            raise RuntimeError("Tried to activate a nonexistent cardholder")
        if(self.has_turn[game_id]):
            raise RuntimeError("Tried to activate a activated cardholder")
        self.has_turn[game_id] = True
        self.num_players += 1
    def establish_order(self, order : list[Any], init : bool = False):
        #establishes the turn order and sets the turn pointer to the beginning.
        #this should establish a turn order where all non-NPC players are given a slot
        num_players = 0
        for i in self.players.keys():
            if(not self.players[i].npc):
                num_players +=1 
        if(len(order) != num_players):
            raise RuntimeError("Ordering given by establish_order doesn't contain the right number of elements")
        else:
            for i in order:
                if(i not in self.players.keys() or self.players[i].npc):
                    raise RuntimeError("Ordering given by establish_order contains an NPC or is not valid")
            self.cardholder_order = order
            self.cardholder_turn = order[0]

    def next_player(self, current_player : Any) -> Any:
        #gets the id of the next active player in line after the id
        if(self.cardholder_turn is None):
            raise RuntimeError("Tried to get the next player when current turn is undefined")
        elif(self.num_players <= 1):
            raise RuntimeError("Tried to get the next player when there are <=1 players") 
        elif(current_player not in self.players.keys()):
            raise RuntimeError("Tried to find the player after one that doesn't exist")
        index_of_cardholder = self.cardholder_order.index(current_player)
        if(index_of_cardholder == len(self.cardholder_order) - 1):
            next_turn = self.cardholder_order[0]
        else:
            next_turn = self.cardholder_order[index_of_cardholder + 1]
        if(self.has_turn[next_turn]):
            return next_turn
        else:
            return self.next_player(next_turn)
    def next_turn(self):
        #moves the environment to the next player, activating any exit & entry protocols in the process
        if(self.cardholder_turn is None):
            raise RuntimeError("Tried to move to the next turn when current turn is undefined")
        elif(self.num_players < 1):
            raise RuntimeError("Tried to move onto the next person when there's < 1 person left")
        else:
            if(self.has_turn[self.cardholder_turn]):
                self.players[self.cardholder_turn].on_exit()
            if(self.winner_flag is not None):
                self.winner_protocol()
            else:
                next_in_line = self.next_player(self.cardholder_turn)
                self.cardholder_turn = next_in_line
                if(self.has_turn[next_in_line]):
                    self.players[self.cardholder_turn].on_entry()

def transfer_card(card_id : Any, sender : GenericCardholder, receiver : GenericCardholder, back : bool = True):
    #transfers card from 1 -> 2 using its id
    if(card_id in sender.cards_holding.keys()):
        card : GenericCard = sender.remove_card(card_id)
        receiver.register_card(card, back, card_id)
    else:
        raise("Tried to transfer a card from a sender that doesn't have it!")
