from __future__ import annotations
from collections import OrderedDict
from random import shuffle
from typing import override


class GenericCard():
    def __init__(self):#type: ignore
        self.owner : 'GenericCardholder' = None
        self.game_environment : 'GameEnvironment'= None
        self.uuid : int= None#uuid of the card in the card holder's hand. only matters to the player
    def attach_to_holder(self, owner : 'GenericCardholder', uuid : int):
        #attaches card to card holder with an id
        self.owner = owner
        self.game_environment = owner.game_environment
        self.uuid = uuid
    def remove_from_player(self):
        self.owner = None
        self.game_environment = None
        self.uuid = None
    def play_card(self, args = []) -> None:
        #card-specific actions should be encoded in this
        pass
    def __str__(self):
        pass
class GenericCardholder():
    def __init__(self, npc : bool):
        self.cards_holding : OrderedDict[int, GenericCard] = OrderedDict([])
        self.ingame_id = None#id of the cardholder in the environment
        self.id_counter = 0#counter to start giving ids to cards
        self.npc = npc#whether or not this cardholder is a player or nonplayer (dealer, poker river, etc.)
        self.game_environment : GameEnvironment = None
    def num_cards(self) -> int:
        return len(self.cards_holding.keys())
    def get_card(self, uuid : int) -> int:
        #returns the instance of the card stored at uuid
        if(uuid in self.cards_holding):
            return self.cards_holding[uuid]
        else:
            raise RuntimeError("Tried to get a nonexistent card")
    def get_cards(self) -> list[GenericCard]:
        to_return = []
        for i in self.cards_holding.values():
            to_return.append(i)
        return to_return
    def add_card(self, card : GenericCard, back : bool = True) -> int:
        #adds the card to the player's pile. can move it to the front or back
        card_id = self.id_counter
        card.attach_to_holder(self, card_id)
        self.cards_holding[card_id] = card
        self.id_counter += 1
        if(back):
            self.cards_holding.move_to_end(card_id, True)
        else:
            self.cards_holding.move_to_end(card_id, False)
        return card_id#returns the id that was given to the card
    def remove_card(self, card_id : int) -> GenericCard:
        #removes the card from the player's hand. returns a pointer to the card
        if(card_id in self.cards_holding):
            card = self.cards_holding[card_id]
            card.remove_from_player()
            del self.cards_holding[card_id]
            return card
        else:
            raise RuntimeError("Tried to remove a nonexistent card")
    def register(self, game_environment : 'GameEnvironment', ingame_id : int) -> None:
        #registers the player to a game environment
        self.game_environment = game_environment
        self.ingame_id = ingame_id
    def reregister_dict(self, new_dict : OrderedDict[int, GenericCard]):
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
        new_dict : OrderedDict[int, GenericCard]= {}
        for key in keys:
            new_dict[key] = self.cards_holding[key]
        self.reregister_dict(new_dict)
    def peek(self) -> tuple[int, GenericCard]:
        #peek @ top id & top card
        return next(iter(self.cards_holding.items()))

    def action(self, args : list = []) -> bool:
        #override this function to encode player-specific ations
        pass

    def get_actions(self) -> list:
        #this function gets the list of actions that can be made. actions can be of any type
        pass

    def on_entry(self) -> None:
        #any actions that the player will take as their turn ends
        pass

    def on_exit(self) -> None:
        #any actions that the player will take before their turn begins
        pass

class GameEnvironment():
    def __init__(self): # type: ignore
        #fully abstract dict mapping ids to ANYTHING that holds cards
        self.card_holders : dict[int, GenericCardholder] = {}
        self.has_turn : dict[int, bool] = {}#dict mapping ingame ids to whether the participant should be given a turn that they can act
        self.num_active_participants : int = 0#identifies the number of active participants
        self.cardholder_order = None#identifies the order of players
        self.cardholder_turn = None#identifies the id of the player whose turn it currently is
        self.winner_flag = None#flag that gets set to the id of the winner
    def reset(self):
        #removes all cardholders and prays that Python does adequate garbage collection
        self.__init__()
    def get_cardholder(self, cardholder_id : int):
        if(cardholder_id not in self.card_holders.keys()):
            raise RuntimeError("Tried to access a nonexistent cardholder")
        return self.card_holders[cardholder_id]
    def add_cardholder(self, ingame_id : int, 
                       empty_cardholder : GenericCardholder,
                       cards_to_give : list[GenericCard] = [],
                       has_turn : bool = True) -> None:
        #adds 1 untied cardholder(one w/out environment yet) with a list of cards to give
        if(ingame_id in self.card_holders.keys()):
            raise RuntimeError("Tried to create a cardholder w/ an ingame id that already exists")
        
        self.card_holders[ingame_id] = empty_cardholder
        empty_cardholder.register(self, ingame_id)
        for card in cards_to_give:
            self.card_holders[ingame_id].add_card(card)
        
        self.has_turn[ingame_id] = has_turn
        if(has_turn and not empty_cardholder.npc):#if it has a turn and isn't an NPC
            self.num_active_participants += 1
    def deactivate_cardholder(self, game_id : int) -> None:
        #deactivates a cardholder, making it no longer get a turn in the overall game loop
        #note: this does NOT affect player ordering. the game will simply skip the player
        if(game_id not in self.card_holders.keys()):
            raise RuntimeError("Tried to deactivate a nonexistent cardholder")
        if(not self.has_turn[game_id]):
            raise RuntimeError("Tried to deactivate a deactivated cardholder")
        self.has_turn[game_id] = False
        self.num_active_participants -= 1
    def activate_cardholder(self, game_id : int) -> None:
        #reactivates a cardholder, placing it back in the game loop
        if(game_id not in self.card_holders.keys()):
            raise RuntimeError("Tried to activate a nonexistent cardholder")
        if(self.has_turn[game_id]):
            raise RuntimeError("Tried to activate a activated cardholder")
        self.has_turn[game_id] = True
        self.num_active_participants += 1
        
    def transfer_card(self, holder_1 : int, holder_2 : int, card_id : int, back : bool = True) -> None:
        #transfers a card of id "card_id" from player id_1 -> player id_2
        if(holder_1 not in self.card_holders or holder_2 not in self.card_holders):
            raise RuntimeError("Tried to transfer a cardholder between 2 players where 1+ don't exist")
        else:
            owner = self.card_holders[holder_1]
            card = owner.get_card(card_id)
            owner.remove_card(card_id)
            receiver = self.card_holders[holder_2]
            card_id = receiver.add_card(card, back = back)
    def discard_card(self, holder : int, card_id : int) -> None:
        #discards the card from the holder's pile
        if(holder not in self.card_holders):
            raise RuntimeError("Tried to discard a card from a nonexistent holder")
        else:
            owner = self.card_holders[holder]
            owner.remove_card(card_id)
    def establish_order(self, order : list[int]):
        #establishes the turn order and sets the turn pointer to the beginning.
        #this should establish a turn order where all non-NPC players are given a slot
        num_players = 0
        for i in self.card_holders.keys():
            if(not self.card_holders[i].npc):
                num_players +=1 
        if(len(order) != num_players):
            raise RuntimeError("Ordering given by establish_order doesn't contain the right number of elements")
        else:
            for i in order:
                if(i not in self.card_holders.keys() or self.card_holders[i].npc):
                    raise RuntimeError("Ordering given by establish_order contains an NPC or is not valid")
            self.cardholder_order = order
            self.cardholder_turn = order[0]

    def next_player(self, current_player : int):
        #gets the next active player in line after the id
        if(self.cardholder_turn is None):
            raise RuntimeError("Tried to get the next player when current turn is undefined")
        elif(self.winner_flag is not None or self.num_active_participants <= 1):
            raise RuntimeError("Tried to get the next player when there are no more turns in game") 
        elif(current_player not in self.card_holders.keys()):
            raise RuntimeError("Tried to find the player after one that doesn't exist")
        if(self.winner_flag):
            raise RuntimeError("Tried to get the next player when a winner has been announced")
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
        elif(self.winner_flag is not None or self.num_active_participants <= 1):
            raise RuntimeError("Tried to move onto the next person when there's only 1 person left or a winner has been announced")
        else:
            if(self.has_turn[self.cardholder_turn]):
                self.card_holders[self.cardholder_turn].on_exit()
            next_in_line = self.next_player(self.cardholder_turn)
            self.cardholder_turn = next_in_line
            if(self.has_turn[next_in_line]):
                self.card_holders[self.cardholder_turn].on_entry()
