from __future__ import annotations
from typing import TYPE_CHECKING, Any
from ..engine.engine_io import *
from ..engine.engine import *
from ..constants import *
from ..avge_abstracts.AVGECard import AVGECard
if TYPE_CHECKING:
    from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ..avge_abstracts.AVGECard import *
    from ..avge_abstracts.AVGEDeck import AVGEDeck

# Complex Phase return objects


@dataclass
class Phase2Finish:
    '''Applicable for: moving to attack phase'''
    pass


@dataclass
class Phase2EnergyAttach:
    '''Applicable for: adding an energy'''
    token_from: AVGECharacterCard | AVGEEnvironment
    token_to: AVGECharacterCard | AVGEEnvironment


@dataclass
class Phase2CardMovement:
    '''Applicable for: adding a tool, retreating a card, and playing a stadium'''
    card: AVGECharacterCard | AVGEToolCard | AVGEStadiumCard
    deck_from: AVGEDeck
    deck_to: AVGEDeck


@dataclass
class Phase2ActivateAbility:
    '''Applicable for: activating abilities'''
    card: AVGECharacterCard


@dataclass
class Phase2PlayCard:
    '''Applicable for: playing an item card, playing a supporter card'''
    card: AVGEItemCard | AVGESupporterCard


# IO Types
@dataclass
class Phase2IO(UserIOType[Phase2EnergyAttach | Phase2CardMovement | Phase2ActivateAbility | Phase2PlayCard | Phase2Finish]):
    pass


@dataclass
class AtkPhaseIO(UserIOType[ActionTypes]):
    pass

@dataclass
class GameEndIO(UserIOType[None]):
    pass

@dataclass
class Notification(UserIOType[None]):
    message: str
    timeout: int | None


@dataclass
class EndOfTurn(UserIOType[None]):
    pass


@dataclass
class RevealCards(UserIOType[None]):
    cards_to_reveal: list[AVGECard]


@dataclass
class ShowBoxedStrings(UserIOType[None]):
    strings_to_show: list[str]


@dataclass
class CardSelectionQuery(UserIOType[list[AVGECard]]):
    header_msg: str
    num_selections : int
    allowed_selections: list[AVGECard]
    displayed_cards: list[AVGECard]
    allows_none: bool
    allows_repeat: bool


@dataclass
class StringSelectionQuery(UserIOType[list[str]]):
    header_msg: str
    num_selections : int
    allowed_selections: list[str]
    displayed_cards: list[str]
    allows_none: bool
    allows_repeat: bool


@dataclass
class IntInput(UserIOType[int]):
    header_msg: str
    min_num: int  # inclusive
    max_num: int  # inclusive


@dataclass
class D6Input(UserIOType[int]):
    header_msg: str


@dataclass
class CoinflipData(UserIOType[int]):  # heads = 1, tails = 0
    header_msg: str


# IO Manager

class AVGEIO(IOManager):
    def __init__(self):
        self.env: AVGEEnvironment | None = None

    def register_to_environment(self, env: AVGEEnvironment):
        self.env = env

    def resolve_users[T](self, io: IOType[T]) -> User:
        assert isinstance(io, ListenerReorderIO)
        assert self.env is not None
        return self.env.turn

    async def send[T](self, user: User, io: IOType[T]):
        """Send a packet to the appropriate user. Returns the user it sent to"""
        pass

    async def retry[T](self, user: User, io: IOType[T], error: IOException):
        """Retry a packet to the appropriate user."""
        pass

    def deserialize[T](self, io: IOType[T], data: dict[str, Any]) -> T:
        """Convert frontend data into T based on a pending IO. Raises an exception on incorrect data"""
        raise Exception("AVGE IO Manager not implemented yet, sorry!")
