from . import engine
from . import event
from . import event_listener
from .engine_constants import *
from ..constants import *
#infinite loop test case

class OverrideFlag(Flag):
    FLAG_1 = 10
    FLAG_2 = 12
class InternalAsessor(event_listener.AssessorEventListener):
    def __init__(self):
        super().__init__(EngineGroup.INTERNAL_1,
                         [OverrideFlag.FLAG_1],
                         internal = True)
    def assess(self, args):
        print("here")
        return self.generate_response(ResponseType.SKIP, data = {'hello': 'world'})
    def make_announcement(self):
        return False
    
class TestEvent(event.Event):
    def __init__(self):
        super().__init__([OverrideFlag.FLAG_1])
    def generate_internal_listeners(self):
        self.attach_listener(InternalAsessor())
    def make_announcement(self):
        return True
    def core(self, args):
        return self.generate_response(data = {"announcement": 'core'})
        
eng = engine.Engine()
test_event = TestEvent()
test_event_2 = TestEvent()

eng._inject_event(test_event)
while(True):
    response = eng.forward()
    if(response.announce):
        print(response.data)
    if(response.response_type == ResponseType.NO_MORE_EVENTS):
        break