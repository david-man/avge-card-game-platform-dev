from flask import request, Flask
import queue
class GameHost():
    def __init__(self, app : Flask):
        self.app = app   
        self.player_1 = "david"
        self.player_2 = "rob"
        self.input_queues = {string : queue.Queue() for string in [self.player_1, self.player_2]}
    