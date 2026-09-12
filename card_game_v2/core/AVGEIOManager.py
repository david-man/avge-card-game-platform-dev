from __future__ import annotations
from typing import TYPE_CHECKING, Any, Literal, cast
from ..engine.engine_io import *
from ..engine.engine import *
from ..constants import *
from ..avge_abstracts.AVGECard import AVGECard
if TYPE_CHECKING:
    from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ..avge_abstracts.AVGECard import *
    from ..avge_abstracts.AVGEDeck import AVGEDeck
    from ..avge_abstracts.AVGEPlayer import AVGEPlayer

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
class BroadcastIO(IOType[None]):
    message: str
    timeout: int | None


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


# Per-event update IO types (server -> client, broadcast via env.broadcast() from the engine's
# on_event_committed/on_packet_failed hooks - see engine/engine.py and engine/event.py). One
# dataclass per player-visible Event subclass in core/EventCatalog.py, mirroring that event's own
# constructor fields plus whatever it computes at runtime (e.g. original_hp, final_change).

@dataclass
class HPChangeUpdate(IOType[None]):
    '''Mirrors AVGECardHPChangeEvent.'''
    target_card: AVGECharacterCard
    magnitude: int
    modifier_type: AVGEAttributeModifier
    change_type: CardType
    original_hp: int
    final_change: int
    is_crit: bool


@dataclass
class MaxHPChangeUpdate(IOType[None]):
    '''Mirrors AVGECardMaxHPChangeEvent.'''
    target_card: AVGECharacterCard
    magnitude: int
    modifier_type: AVGEAttributeModifier
    change_type: CardType
    original_hp: int
    original_max_hp: int
    final_hp: int
    final_max_hp: int


@dataclass
class CardTypeChangeUpdate(IOType[None]):
    '''Mirrors AVGECardTypeChange.'''
    target: AVGECharacterCard
    original_type: CardType
    new_type: CardType


@dataclass
class StatusChangeUpdate(IOType[None]):
    '''Mirrors AVGECardStatusChange.'''
    target: AVGECharacterCard
    giver: AVGECard | AVGEPlayer | AVGEEnvironment
    status: StatusEffect
    change: AVGEStatusModifier
    made_modification: bool


@dataclass
class EnergyTransferUpdate(IOType[None]):
    '''Mirrors AVGEEnergyTransfer. No `transferred` flag - whether a token actually moved is
    tracked on a private attribute of the source event (`_transferred_token`), and reaching into
    it from here would violate encapsulation across the core/engine boundary; the no-op case
    (token_from had zero energy) is rare and self-corrects on the next full snapshot resync.'''
    token_from: AVGECharacterCard | AVGEEnvironment
    token_to: AVGECharacterCard | AVGEEnvironment


@dataclass
class PlayerAttributeUpdate(IOType[None]):
    '''Mirrors AVGEPlayerAttributeChange.'''
    player: AVGEPlayer
    attribute: AVGEPlayerAttribute
    modifier_type: AVGEAttributeModifier
    magnitude: int
    new_value: int


@dataclass
class CardMovedUpdate(IOType[None]):
    '''Mirrors TransferCard.'''
    card: AVGECard
    deck_from: AVGEDeck
    deck_to: AVGEDeck


@dataclass
class DeckReorderedUpdate(IOType[None]):
    '''Mirrors ReorderDeck.'''
    deck: AVGEDeck
    new_order: list[AVGECard]


@dataclass
class CharacterActionUpdate(IOType[None]):
    '''Mirrors PlayCharacterCard.'''
    target_card: AVGECharacterCard
    action: ActionTypes
    cost: int
    calling_card: AVGECharacterCard | None


@dataclass
class NonCharacterPlayUpdate(IOType[None]):
    '''Mirrors PlayNonCharacterCard.'''
    target_card: AVGEToolCard | AVGESupporterCard | AVGEItemCard | AVGEStadiumCard
    action: ActionTypes


@dataclass
class TurnEndUpdate(IOType[None]):
    '''Mirrors TurnEnd.'''
    new_turn: User
    new_round: int


@dataclass
class PhaseChangedUpdate(IOType[None]):
    '''Mirrors PhasePickCard / Phase2 / AtkPhase.'''
    phase: Literal["draw", "main", "attack"]


@dataclass
class ActionRejectedUpdate(IOType[None]):
    '''No single source event - sent from the engine's on_packet_failed hook whenever any packet
    is REGULATE_FAILed. `reason` is whatever the failing regulator left on
    Packet.rejection_reason (None if it didn't set one - not every regulator explains itself
    yet). The server attaches a fresh state snapshot to this message at send time (after
    rollback has already run), so the client can both learn why its optimistic update was
    reverted and resync to the corrected state in one message.'''
    rejected_for: User
    reason: str | None = None


# IO Manager

class AVGEIO(IOManager):
    def __init__(self):
        super().__init__()
        self.env: AVGEEnvironment | None = None

    def register_to_environment(self, env: AVGEEnvironment):
        self.env = env

    def resolve_users[T](self, io: IOType[T]) -> User:
        assert self.env is not None
        if isinstance(io, IOListenerReorderIO):
            reorder_io = cast(IOListenerReorderIO[Any], io)
            assert isinstance(reorder_io.io_obj, UserIOType)
            return reorder_io.io_obj.user_for
        if isinstance(io, ListenerReorderIO):
            return self.env.turn
        raise Exception("All non-base IO types should be built off the UserIOType")

    async def send[T](self, user: User, io: IOType[T]):
        """Send a packet to the appropriate user. Returns the user it sent to"""
        pass

    async def retry[T](self, user: User, io: IOType[T], error: IOException):
        """Retry a packet to the appropriate user."""
        pass

    def deserialize[T](self, io: IOType[T], data: dict[str, Any]) -> T:
        """Convert frontend data into T based on a pending IO. Raises an exception on incorrect data"""
        raise Exception("AVGE IO Manager not implemented yet, sorry!")
