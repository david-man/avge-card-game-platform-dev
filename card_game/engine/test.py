from . import engine
from . import event
from . import event_listener
from .engine_constants import *
from ..constants import *
#engine test cases

number = 10
class OverrideFlag(Flag):
    FLAG_1 = 10
    FLAG_2 = 12
class InternalAsessor(event_listener.AssessorEventListener):
    def __init__(self):
        super().__init__(EngineGroup.INTERNAL_1,
                         [OverrideFlag.FLAG_1],
                         internal = True)
        self.overrides = 0
    def package(self):
        return "InternalAssessor"
    def assess(self, args):
        self.overrides+=1
        if(self.overrides == 3):
            return self.generate_response(ResponseType.SKIP, data = {'hello': 'world'})
        else:
            return self.generate_response()
    def make_announcement(self):
        return True
    def is_valid(self):
        return (self.overrides <= 2)

k = InternalAsessor()
class TestEvent(event.Event):
    def __init__(self):
        super().__init__([OverrideFlag.FLAG_1])
    def package(self):
        return "TestEvent"
    def generate_internal_listeners(self):
        return
    def make_announcement(self):
        return True
    def core(self, args):
        global number
        number += 20
        return self.generate_core_response(data = {"announcement": 'core'})
    def invert_core(self, args):
        global number
        number -= 20
class TestEvent2(event.Event):
    def __init__(self):
        super().__init__([OverrideFlag.FLAG_1])
    def package(self):
        return "TestEvent"
    def generate_internal_listeners(self):
        return
    def make_announcement(self):
        return True
    def core(self, args):
        global number
        number *= 20
        return self.generate_core_response(data = {"announcement": 'core'})
    def invert_core(self, args):
        global number
        number /= 20
        
eng = engine.Engine()
test_event = TestEvent()
test_event_2 = TestEvent2()
eng.add_external_listener(k)
eng._propose([test_event, test_event_2])
while(True):
    response = eng.forward()
    if(response.announce):
        print(response.source.package())
    if(response.response_type == ResponseType.NO_MORE_EVENTS):
        break
print(number)
for i in eng.external_listeners:
    print(i.overrides)
   