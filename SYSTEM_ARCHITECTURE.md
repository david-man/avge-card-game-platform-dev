# Card Game Platform - System Architecture Overview

## 1. Event System: Creation, Queuing, and Processing

### 1.1 Event Lifecycle Overview

Events flow through a **17-group processing pipeline**, ensuring proper ordering of validation, modification, execution, and reaction:

```
INTERNAL_1 → PRECHECK_1 → MODIFIERS_1 → PRECHECK_2 → INTERNAL_2 → PRECHECK_3 → MODIFIERS_2 
→ PRECHECK_4 → INTERNAL_3 → CORE (Execute) → INTERNAL_4 → POSTCHECK_1 → REACTORS → POSTCHECK_2 → INTERNAL_5
```

### 1.2 Event Queuing (`engine.py`)

Events are queued in **packets** (collections of related events):

```python
# From engine.py
class Engine():
    def __init__(self):
        self._queue: EngineQueue[event.Packet] = EngineQueue()
        self.event_running: event.Event = None
        self.packet_running: event.Packet = event.Packet([], self)
        
    def _propose(self, new_event: Event | list[Event] | Callable, priority: int = 0):
        """Proposes events to the queue"""
        packet_assembler = event.Packet(new_event, self)
        self._queue.propose(packet_assembler, priority)
```

**Key Points:**
- Events can be **deferred callables** (resolved at runtime)
- **Packet** manages event batches
- **Priority** controls execution order
- Queue can be **OPEN** (normal), **BUFFERED** (during CORE execution), or **CLOSED**

### 1.3 Event Processing Flow

Each event moves through groups sequentially:

```python
# From event.py - Event.forward() method
def forward(self, constraints: list[constrainer.Constraint], args: Data = {}) -> Response:
    if self.group_on == EngineGroup.CORE:
        # Execute the core game logic
        response = self.core_wrapper(args)
        if response.response_type == ResponseType.CORE:
            self.group_on = self.group_on.succ()  # Move to next group
        return response
    else:
        # For other groups, process listeners
        # 1. Apply constraints to listeners in current group
        # 2. Handle ordering if needed (for MODIFIERS and REACTORS)
        # 3. Pop next listener and call appropriate method (modify, react, assess, etc)
        # 4. Handle response types (ACCEPT, INTERRUPT, REQUIRES_QUERY, SKIP)
```

### 1.4 Event Transactions and Rollback

The system supports **atomic transactions** with rollback:

```python
# From engine.py
def forward(self, args: Data = {}) -> Response:
    # ... event processing ...
    
    if response.response_type == ResponseType.SKIP:
        # Rollback entire packet on failure
        for c in self._constraints:
            if c not in self._constraints_backup:
                c.invalidate()
        self._constraints = self._constraints_backup
        
        # Invert all changes in LIFO order
        while len(self.event_stack) > 0:
            e = self.event_stack.pop()  # FILO
            if e.core_ran:
                e.invert_core(e.core_args)
        
        self.packet_running = event.Packet([], self)
        self.event_running = None
```

---

## 2. Base Event Structure

### 2.1 Event Base Class (`event.py`)

```python
class Event():
    def __init__(self, **kwargs):
        # Lazy evaluation support
        self._kwargs = kwargs
        self._ready = False
        
        # Listener groups for the 17-group pipeline
        self.event_listener_groups: dict[EngineGroup, list[AbstractEventListener]] = {
            group: [] for group in EngineGroup
        }
        
        # Track which groups have been constrained/ordered
        self.groups_constrained: dict[EngineGroup, bool] = {}
        self.groups_ordered: dict[EngineGroup, bool] = {}
        
        self.core_ran: bool = False
        self.core_args: Data = None

    def generate_internal_listeners(self):
        """Override to attach internal listeners specific to this event type"""
        raise NotImplementedError()
    
    def core(self, args: Data = {}) -> Response:
        """The core game logic that actually changes state"""
        raise NotImplementedError()
    
    def invert_core(self, args: Data = {}) -> None:
        """Undo changes made by core() - enables rollback"""
        raise NotImplementedError()
```

### 2.2 AVGE Events (`AVGEEvent.py`)

All game events inherit from `AVGEEvent`, which adds context:

```python
class AVGEEvent(Event):
    def __init__(self, catalyst_action: ActionTypes, caller_card: Card, **kwargs):
        super().__init__(catalyst_action=catalyst_action, caller_card=caller_card, **kwargs)
        self.catalyst_action = catalyst_action  # What action caused this (ATK_1, PASSIVE, etc)
        self.caller_card = caller_card          # Who initiated this
        self.temp_cache = {}                    # Event-scoped cache
```

---

## 3. Card Structure

### 3.1 Base Card (`abstract/card.py`)

```python
class Card():
    def __init__(self, unique_id: str):
        self.unique_id = unique_id
        self.player: player.Player = None
        self.cardholder: cardholder.Cardholder = None  # Pile location
        self.env: environment.Environment = None
        
        # Cards own listeners and constraints
        self.owned_listeners: list[AbstractEventListener] = []
        self.owned_constraints: list[Constraint] = []

    def add_listener(self, listener: AbstractEventListener):
        """Cards use this to register passive effects"""
        self.env.add_listener(listener)
        self.owned_listeners.append(listener)

    def add_constrainer(self, constrainer: Constraint):
        """Cards use this to restrict actions"""
        self.env.add_constrainer(constrainer)
        self.owned_constraints.append(constrainer)

    def deactivate_card(self):
        """Called when card leaves play - invalidates owned listeners/constraints"""
        for listener in self.owned_listeners:
            listener.invalidate()
        for constrainer in self.owned_constraints:
            constrainer.invalidate()
```

### 3.2 Character Card (`avge_abstracts/AVGECards.py`)

```python
class AVGECharacterCard(AVGECard):
    def __init__(self, unique_id: str):
        super().__init__(unique_id)
        self.tools_attached: AVGEToolCardholder = AVGEToolCardholder(self)
        self.statuses_attached: dict[StatusEffect, int] = {}
        
        self.attributes: dict[AVGECardAttribute, int | CardType] = {
            AVGECardAttribute.TYPE: None,           # Element
            AVGECardAttribute.HP: None,             # Current health
            AVGECardAttribute.MAXHP: None,          # Max health
            AVGECardAttribute.MV_1_COST: None,      # Energy cost for attack 1
            AVGECardAttribute.MV_2_COST: None,      # Energy cost for attack 2
            AVGECardAttribute.SWITCH_COST: None,    # Energy to switch out
            AVGECardAttribute.ENERGY_ATTACHED: 0    # Energy on card
        }
        
        self.has_atk_1: bool = False
        self.has_atk_2: bool = False
        self.has_passive: bool = False  # Ability on entry to Active pile
        self.has_active: bool = False   # Ability activatable once per turn

    def play_card(self, parent_event: AVGEEvent, card: AVGECharacterCard, 
                  args: Data = {}) -> Response:
        """Routes to appropriate ability based on action type"""
        if args['type'] == ActionTypes.ATK_1:
            return self.atk_1(card, parent_event, args)
        elif args['type'] == ActionTypes.ATK_2:
            return self.atk_2(card, parent_event, args)
        elif args['type'] == ActionTypes.ACTIVATE_ABILITY:
            return self.active(card, parent_event, args)
        elif args['type'] == ActionTypes.PASSIVE:
            return self.passive(parent_event, args)

    @staticmethod
    def atk_1(card: 'AVGECharacterCard', parent_event: AVGEEvent, 
              args: Data = {}) -> Response:
        raise NotImplementedError()

    def passive(self, parent_event: AVGEEvent, args: Data = {}) -> Response:
        """Called when card enters Active pile"""
        raise NotImplementedError()
```

---

## 4. Example Card Implementations

### 4.1 Simple Attack: WestonPoe

```python
class WestonPoe(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.attributes = {
            AVGECardAttribute.TYPE: CardType.WOODWIND,
            AVGECardAttribute.HP: 110,
            AVGECardAttribute.MAXHP: 110,
            AVGECardAttribute.MV_1_COST: 2,
            AVGECardAttribute.MV_2_COST: 0,
            AVGECardAttribute.SWITCH_COST: 2,
            AVGECardAttribute.ENERGY_ATTACHED: 0,
        }
        self.has_atk_1 = True
        self.has_passive = True

    def passive(self, parent_event: AVGEEvent, args={}) -> Response:
        """Passive: reflects damage >= 60 back to attacker"""
        owner_card = self

        class _DamageReflector(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=(owner_card, ActionTypes.PASSIVE),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )

            def event_match(self, event):
                # Only match damage events to owner
                if not isinstance(event, AVGECardAttributeChange):
                    return False
                if event.target_card != owner_card:
                    return False
                if event.attribute != AVGECardAttribute.HP:
                    return False
                if event.change_amount >= 0:  # Only matches damage
                    return False
                # Only from opponent's attacks
                if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
                    return False
                if event.caller_card.player != owner_card.player.opponent:
                    return False
                # Only reflect big damage
                return abs(int(event.change_amount)) >= 60

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                if owner_card.env is None:
                    self.invalidate()

            def react(self, args={}):
                event = self.attached_event
                reflected_damage = abs(int(event.change_amount))
                # Propose damage back to attacker
                self.propose(
                    AVGECardAttributeChange(
                        event.caller_card,
                        AVGECardAttribute.HP,
                        -reflected_damage,
                        AVGEAttributeModifier.ADDITIVE,
                        ActionTypes.PASSIVE,
                        owner_card,
                        owner_card.attributes[AVGECardAttribute.TYPE],
                    )
                )
                return self.generate_response()

        self.add_listener(_DamageReflector())
        return self.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent, args={}) -> Response:
        """ATK 1: Deal 50 damage to opponent, take 10 recoil"""
        from card_game.internal_events import AVGECardAttributeChange

        target_card = card.player.opponent.get_active_card()
        # Create event packet with multiple events
        packet = [
            AVGECardAttributeChange(
                target_card,
                AVGECardAttribute.HP,
                -50,  # Deal 50 damage
                AVGEAttributeModifier.ADDITIVE,
                ActionTypes.ATK_1,
                card,
                card.attributes[AVGECardAttribute.TYPE],
            ),
            AVGECardAttributeChange(
                card,
                AVGECardAttribute.HP,
                -10,  # Take 10 recoil
                AVGEAttributeModifier.ADDITIVE,
                ActionTypes.ATK_1,
                card,
                card.attributes[AVGECardAttribute.TYPE],
            ),
        ]
        card.propose(packet)
        return card.generate_response()
```

### 4.2 Complex Attack with Randomness: FelixChen

```python
class FelixChen(AVGECharacterCard):
    _COIN_KEY_0 = "felixchen_coin_0"
    _COIN_KEY_1 = "felixchen_coin_1"

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent, args: Data = {}) -> Response:
        """ATK 1: Flip two coins. HH=50 dmg to all bench, TT=100 dmg to all bench, HT/TH=0 dmg"""
        from card_game.internal_events import InputEvent, AVGECardAttributeChange

        owner_card = card
        env = owner_card.env
        opponent = owner_card.player.opponent
        bench = opponent.cardholders[Pile.BENCH]

        # Check if coin results are cached
        roll0 = env.cache.get(owner_card, FelixChen._COIN_KEY_0, None, one_look=True)
        roll1 = env.cache.get(owner_card, FelixChen._COIN_KEY_1, None, one_look=True)

        if roll0 is None or roll1 is None:
            # First call: request player input
            def _coin_valid(result) -> bool:
                if len(result) != 2:
                    return False
                for v in result:
                    try:
                        iv = int(v)
                    except (TypeError, ValueError):
                        return False
                    if iv not in [0, 1]:
                        return False
                return True

            # INTERRUPT: Pause ability, request input, resume when provided
            return owner_card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            owner_card.player,
                            [FelixChen._COIN_KEY_0, FelixChen._COIN_KEY_1],
                            InputType.COIN,
                            _coin_valid,
                            ActionTypes.ATK_1,
                            owner_card,
                            {"query_type": "card_query", "prompt": "Flip two coins..."},
                        )
                    ]
                },
            )

        # Second call: use cached coin flips
        try:
            c0 = int(roll0)
            c1 = int(roll1)
        except Exception:
            env.cache.delete(owner_card, FelixChen._COIN_KEY_0)
            env.cache.delete(owner_card, FelixChen._COIN_KEY_1)
            return owner_card.generate_response()

        # Determine damage based on coin flips
        if c0 == 1 and c1 == 1:
            dmg = 50  # HH
        elif c0 == 0 and c1 == 0:
            dmg = 100  # TT
        else:
            dmg = 0  # HT or TH

        # Create damage events for each bench card
        packet = []
        if dmg > 0:
            for target in list(bench):
                packet.append(
                    AVGECardAttributeChange(
                        target,
                        AVGECardAttribute.HP,
                        -dmg,
                        AVGEAttributeModifier.ADDITIVE,
                        ActionTypes.ATK_1,
                        owner_card,
                        owner_card.attributes.get(AVGECardAttribute.TYPE),
                    )
                )

        if len(packet) > 0:
            owner_card.propose(packet)

        # Clean up cache
        env.cache.delete(owner_card, FelixChen._COIN_KEY_0)
        env.cache.delete(owner_card, FelixChen._COIN_KEY_1)
        
        return owner_card.generate_response()
```

### 4.3 State Tracking: DesmondRoper

```python
class DesmondRoper(AVGECharacterCard):
    _PLAYED_ROUND_KEY = "desmond_played_round"

    def passive(self, parent_event: AVGEEvent, args: Data = {}) -> Response:
        """Passive: Track when this card was played to Active"""
        owner_card = self

        class _DesmondPlayTracker(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=(owner_card, ActionTypes.PASSIVE),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )

            def event_match(self, event):
                # Match: "this card transferred to Active pile"
                from card_game.internal_events import TransferCard
                if not isinstance(event, TransferCard):
                    return False
                if event.card != owner_card:
                    return False
                return event.pile_to.pile_type == Pile.ACTIVE

            def react(self, args={}):
                # Cache the round when played
                env = owner_card.env
                env.cache.set(owner_card, DesmondRoper._PLAYED_ROUND_KEY, env.round)
                return self.generate_response()

        owner_card.add_listener(_DesmondPlayTracker())
        return owner_card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent, args: Data = {}) -> Response:
        """ATK 2: Deal 40 damage, or 100 if played this round"""
        env = card.env
        
        played_round = env.cache.get(card, DesmondRoper._PLAYED_ROUND_KEY, None)
        damage = 100 if played_round == env.round else 40

        target = card.player.opponent.get_active_card()
        card.propose(
            AVGECardAttributeChange(
                target,
                AVGECardAttribute.HP,
                -damage,
                AVGEAttributeModifier.ADDITIVE,
                ActionTypes.ATK_2,
                card,
                card.attributes.get(AVGECardAttribute.TYPE),
            )
        )
        return card.generate_response()
```

---

## 5. Event Listeners: Registration and Response

### 5.1 Listener Types and Groups

The system has **four listener types**, each responding at different pipeline stages:

```python
# From event_listener.py

class ModifierEventListener(AbstractEventListener[T]):
    """Runs in EXTERNAL_MODIFIERS groups - modifies event parameters before core"""
    def modify(self, args: Data = {}) -> Response:
        raise NotImplementedError()

class ReactorEventListener(AbstractEventListener[T]):
    """Runs in EXTERNAL_REACTORS group - AFTER core, can propose new events"""
    def react(self, args: Data = {}) -> Response:
        raise NotImplementedError()
    
    def propose(self, e: Event | list[Event], priority: int = 0):
        self.engine._propose(e, priority)

class AssessorEventListener(AbstractEventListener[T]):
    """Runs in PRECHECK groups - validates event before modification"""
    def assess(self, args: Data = {}) -> Response:
        raise NotImplementedError()

class PostCheckEventListener(AbstractEventListener[T]):
    """Runs in POSTCHECK groups - final checks after core"""
    def assess(self, args: Data = {}) -> Response:
        raise NotImplementedError()
```

### 5.2 Listener Registration and Matching

```python
class AbstractEventListener(Generic[T]):
    def __init__(self, identifier: T, group: EngineGroup, 
                 internal: bool = False, requires_runtime_info: bool = True):
        self.engine: engine.Engine = None
        self.attached_event: event.Event = None
        self.group = group
        self.internal = internal
        self.identifier = identifier  # Unique ID for this listener
        self._invalidated: bool = False
        self.requires_runtime_info: bool = requires_runtime_info

    def event_match(self, event: event.Event) -> bool:
        """Called when event enters engine - decide if this listener should attach"""
        raise NotImplementedError()

    def event_effect(self) -> bool:
        """Called at runtime - decide if listener should actually execute"""
        if not self.requires_runtime_info:
            return True
        raise NotImplementedError()

    def update_status(self):
        """Periodically called - listener can invalidate itself here"""
        raise NotImplementedError()

    def invalidate(self):
        """Mark listener as inactive - it will be removed from engine"""
        self._invalidated = True

    def on_packet_completion(self):
        """Called after packet successfully completes - useful for one-use abilities"""
        return
```

### 5.3 Example: Modifier Listener (FelixChen Damage Reducer)

```python
class _FelixDamageReducer(AVGEModifier):
    """Modifier that reduces damage by 10 if all types are different"""
    
    def __init__(self):
        super().__init__(
            identifier=(owner_card, ActionTypes.PASSIVE),
            group=EngineGroup.EXTERNAL_MODIFIERS_2  # Runs before core
        )

    def event_match(self, event):
        """Does this damage event match our criteria?"""
        from card_game.internal_events import AVGECardAttributeChange

        if not isinstance(event, AVGECardAttributeChange):
            return False
        if event.attribute_modifier_type != AVGEAttributeModifier.ADDITIVE:
            return False
        if event.change_amount >= 0:  # Only damage, not healing
            return False
        # Only reduce damage to owner's characters
        if event.target_card.player != owner_card.player:
            return False
        return True

    def event_effect(self) -> bool:
        """Should we actually reduce this damage?"""
        player = owner_card.player
        cards_in_play = list(player.cardholders[Pile.BENCH])
        if player.cardholders[Pile.ACTIVE]:
            cards_in_play.append(player.cardholders[Pile.ACTIVE].peek())
        
        # Check: all character cards have different types
        char_cards = [c for c in cards_in_play if isinstance(c, AVGECharacterCard)]
        types = [c.attributes.get(AVGECardAttribute.TYPE) for c in char_cards]
        return len(types) == len(set(types))

    def update_status(self):
        """Invalidate when card is not in play"""
        if owner_card.cardholder is None or owner_card.cardholder.pile_type == Pile.DISCARD:
            self.invalidate()

    def modify(self, args={}):
        """Modify the event data"""
        event = self.attached_event
        try:
            amt = int(event.change_amount)
        except Exception:
            return self.generate_response()
        
        # Reduce damage by 10
        incoming = abs(amt)
        if incoming <= 10:
            event.change_amount = 0  # Negate small damage
        else:
            event.change_amount = event.change_amount + 10  # Reduce damage
        
        return self.generate_response()
```

### 5.4 Example: Reactor Listener (WestonPoe Damage Reflector)

```python
class _DamageReflector(AVGEReactor):
    """Reactor that reflects large damage back to attacker"""
    
    def __init__(self):
        super().__init__(
            identifier=(owner_card, ActionTypes.PASSIVE),
            group=EngineGroup.EXTERNAL_REACTORS  # Runs AFTER core
        )

    def event_match(self, event):
        # ... (criteria check) ...
        return abs(int(event.change_amount)) >= 60

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if owner_card.env is None:
            self.invalidate()

    def react(self, args={}):
        """React to the event - can propose new events"""
        event = self.attached_event
        reflected_damage = abs(int(event.change_amount))
        
        # Propose counter-damage (this gets queued normally)
        self.propose(
            AVGECardAttributeChange(
                event.caller_card,           # Damage goes to attacker
                AVGECardAttribute.HP,
                -reflected_damage,
                AVGEAttributeModifier.ADDITIVE,
                ActionTypes.PASSIVE,
                owner_card,
                owner_card.attributes[AVGECardAttribute.TYPE],
            )
        )
        return self.generate_response()
```

---

## 6. Constrainers: Validation and Action Restrictions

### 6.1 Constraint Base Class (`constrainer.py`)

```python
class Constraint(Generic[T]):
    def __init__(self, identifier: T):
        self.identifier = identifier
        self._invalidated: bool = False

    def match(self, obj: AbstractEventListener | Constraint) -> bool:
        """
        Does this constraint apply to this listener/constraint?
        
        Constraints form a hierarchy:
        - A general constraint matches (and covers) specific constraints
        - Remove general constraint if specific constraint is added first
        """
        raise NotImplementedError()

    def update_status(self):
        """Check if constraint is still valid - call invalidate() if not"""
        raise NotImplementedError()

    def invalidate(self):
        """Mark constraint as no longer active"""
        self._invalidated = True
```

### 6.2 Constraint Hierarchy Management

```python
# From engine.py
def add_constraint(self, constraint: 'constrainer.Constraint'):
    # Check if new constraint is covered by existing constraints
    for c in self._constraints:
        if c.match(constraint):
            return  # Constraint is subsumed, don't add it
    
    # Add the new constraint
    self._constraints.append(constraint)

    # Check if new constraint covers existing constraints
    deactivated_constrainers = []
    for c in self._constraints[:-1]:
        if constraint.match(c):  # New constraint is more general
            deactivated_constrainers.append(c)
            c.invalidate()
    
    # Remove covered constraints
    self._constraints = [c for c in self._constraints if c not in deactivated_constrainers]
```

### 6.3 Constraints Applied During Event Processing

```python
# From event.py - during listener processing
def forward(self, constraints: list[constrainer.Constraint], args: Data = {}):
    if len(self.event_listener_groups[self.group_on]) >= 1:
        # Apply constraints to listeners in current group
        for listener in self.event_listener_groups[self.group_on]:
            for constraint in constraints:
                if constraint._should_attach(listener):
                    # Constraint blocks this listener
                    listener.detach_from_event()
                    self.event_listener_groups[self.group_on].remove(listener)
                    return Response(self, ResponseType.ACCEPT, 
                                    data={'constrainer_announced': constraint.package()}, 
                                    announce=constraint.make_announcement())
```

### 6.4 Example: Attack Energy Constraint

While not shown in the files, here's how a constraint would work:

```python
class CannotAttackConstraint(AVGEConstraint):
    """Prevents attacks for some number of turns"""
    
    def __init__(self, target_card: AVGECharacterCard, turns_remaining: int):
        super().__init__(identifier=target_card)
        self.target_card = target_card
        self.turns_remaining = turns_remaining

    def match(self, obj: AbstractEventListener | Constraint) -> bool:
        """This constraint applies to all attack modifiers for this card"""
        if isinstance(obj, Constraint):
            # Match to general constraints
            return isinstance(obj, CannotAttackConstraint)
        else:
            # Match to listeners
            listener = obj
            # Block if listener is attack-related for this card
            if not hasattr(listener, 'identifier'):
                return False
            card, listener_type = listener.identifier
            return (card == self.target_card and 
                    listener_type in [ActionTypes.ATK_1, ActionTypes.ATK_2])

    def update_status(self):
        """Decrement turns and invalidate when expired"""
        self.turns_remaining -= 1
        if self.turns_remaining <= 0:
            self.invalidate()

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return f"{self.target_card} cannot attack ({self.turns_remaining} turns)"
```

---

## 7. Complete Flow: Multi-Stage Ability Example

### 7.1 Example Ability: "Heal for 20 HP, then remove 1 energy"

This demonstrates the complete flow from ability triggering to listener modifications:

```python
class CustomCharacter(AVGECharacterCard):
    @staticmethod
    def active(card: AVGECharacterCard, parent_event: AVGEEvent, 
               args: Data = {}) -> Response:
        """
        Multi-stage ability:
        1. Heal self for 20 HP
        2. Remove 1 energy from self
        """
        owner_card = card
        
        # Create packet with two sequential events
        packet = [
            # Stage 1: Healing (ADDITIVE change of +20)
            AVGECardAttributeChange(
                owner_card,
                AVGECardAttribute.HP,
                20,  # Positive = healing
                AVGEAttributeModifier.ADDITIVE,
                ActionTypes.ACTIVATE_ABILITY,
                owner_card,
                owner_card.attributes[AVGECardAttribute.TYPE],
            ),
            # Stage 2: Energy removal (ADDITIVE change of -1)
            AVGECardAttributeChange(
                owner_card,
                AVGECardAttribute.ENERGY_ATTACHED,
                -1,  # Negative = removal
                AVGEAttributeModifier.ADDITIVE,
                ActionTypes.ACTIVATE_ABILITY,
                owner_card,
                owner_card.attributes[AVGECardAttribute.TYPE],
            ),
        ]
        
        owner_card.propose(packet)
        return owner_card.generate_response()
```

### 7.2 Detailed Step-by-Step Flow

**Initial State:**
- Active Character: CustomCharacter (90 HP, 3 energy)
- Action: Activate Ability

**Step 1: PlayCharacterCard Event Created**
```
PlayCharacterCard(
    card=CustomCharacter,
    card_action=ActionTypes.ACTIVATE_ABILITY,
    catalyst_action=ActionTypes.PLAYER_CHOICE,
    caller_card=CustomCharacter
)
```

**Step 2: Event Enters Processing Pipeline**
- Group INTERNAL_1: Assessment listeners check validity
- Groups EXTERNAL_PRECHECK_1-4: Early validation
- Group EXTERNAL_MODIFIERS_2-2: Modifiers adjust parameters
- Group CORE: `core()` calls `CustomCharacter.active()`
  - **Result:** Proposes packet of 2 AVGECardAttributeChange events

**Step 3: First AVGECardAttributeChange (Heal) Processed**

Pipeline groups:
```
INTERNAL_1: AVGECardAttributeChangeAssessment
  - Check action is valid (ENERGY_ADD_REMAINING, etc)
  
EXTERNAL_MODIFIERS_2-2: Enemy modifiers attached
  - e.g., FelixDamageReducer (not affected by healing)
  
INTERNAL_3: AVGECardAttributeChangeModifier (INTERNAL)
  - Clamps HP to MAXHP if needed
  - Old HP: 90, Change: +20
  - New HP would be: 110, but MAXHP is 110
  - Change adjusted to: +20 (no change needed)

CORE: Execute healing
  - card.attributes[HP] = 90 + 20 = 110
  - Stores old value (90) for potential rollback

EXTERNAL_REACTORS: Reactor listeners
  - WestonPoe's DamageReflector doesn't match (no damage)
  - DesmondRoper's PlayTracker doesn't match (not a transfer)
  
INTERNAL_4+: Post-checks pass
```

**Step 4: Second AVGECardAttributeChange (Energy Removal) Processed**

```
INTERNAL_1: Assessment
  - Validates energy removal
  
EXTERNAL_MODIFIERS: Any damage/energy modifiers
  
INTERNAL_3: Clamping modifier
  - Current energy: 3, Change: -1
  - New energy: 2 (valid, stays positive)
  
CORE: Execute removal
  - card.attributes[ENERGY_ATTACHED] = 3 - 1 = 2
  
EXTERNAL_REACTORS: Any reactions
  - Could have "energy removed" listeners here
```

**Step 5: Packet Completion**
- Both events ran successfully
- All constraints remain valid
- All listeners probed for status
- Packet marked as FINISHED

**Final State:**
- Active Character: CustomCharacter (110 HP, 2 energy)
- Both stages completed atomically

### 7.3 Rollback Scenario: What if Energy Removal Failed?

If an energy removal listener returned `SKIP`:

```
Step 1: First event ran successfully
  - HP is now 110

Step 2: Second event encounters constraint/failure
  - Returns SKIP response

Step 3: Engine initiates rollback
  - Second event's core_ran = False (never executed)
  - First event's core_ran = True
  - Calls first_event.invert_core()
    - card.attributes[HP] = 90 (restored)
  
Step 4: Entire packet rolled back
  - HP: 110 → 90
  - Energy: stays unchanged (second event never ran)
  - Game returns to pre-ability state
```

---

## 8. Event Response Types and Control Flow

### 8.1 Response Types

```python
class ResponseType(StrEnum):
    # Normal flow
    ACCEPT = 'ACCEPT'                # Proceed normally
    CORE = 'CORE'                    # Core completed successfully
    FINISHED = 'FINISHED'            # Event complete, move to next event
    FINISHED_PACKET = 'FINISHED_PACKET'  # All events in packet complete
    
    # Control flow
    REQUIRES_QUERY = 'REQUIRES_QUERY'    # Waiting for user input
    INTERRUPT = 'INTERRUPT'             # Stop current event, process others first
    FAST_FORWARD = 'FF'                 # Skip to end of event
    
    # Error/Stop
    SKIP = 'SKIP'                       # Rollback entire packet
    GAME_END = 'GAME_END'               # Game over
    NO_MORE_EVENTS = 'NO_MORE_EVENTS'   # Queue empty
    
    # Navigation
    NEXT_EVENT = 'NEXT_EVENT'
    NEXT_PACKET = 'NEXT_PACKET'
```

### 8.2 Example: INTERRUPT Flow (FelixChen Coin Flip)

```
Initial call to atk_1:
  ├─ Coin results not cached
  └─ Return INTERRUPT with InputEvent

Engine receives INTERRUPT:
  ├─ Backs up current state
  ├─ Insert InputEvent into packet front
  ├─ Resume packet processing with InputEvent

InputEvent processes (gets user input):
  ├─ User flips coins: [1, 0]  (Heads, Tails)
  ├─ Caches results
  └─ Returns FINISHED

Engine processes next event in packet:
  ├─ Resume atk_1 (same instance)
  ├─ Coin results now in cache
  ├─ Proceed with damage calculation
  └─ Return FINISHED
```

---

## 9. Internal Event Architecture

### 9.1 AVGECardAttributeChange Event

This is the most common event - handles all card stat changes:

```python
class AVGECardAttributeChange(AVGEEvent):
    def __init__(self, target_card, attribute, change_amount, 
                 attribute_modifier_type, catalyst_action, caller_card, 
                 change_type):
        super().__init__(catalyst_action=catalyst_action, caller_card=caller_card, ...)
        self.target_card = target_card
        self.attribute = attribute
        self.change_amount = change_amount
        self.attribute_modifier_type = attribute_modifier_type
        self.old_amt = None

    def generate_internal_listeners(self):
        """Attach standardized listeners for all attribute changes"""
        self.attach_listener(AVGECardAttributeChangeAssessment())
        self.attach_listener(AVGECardAttributeChangeModifier())
        self.attach_listener(AVGECardAttributeChangeReactor())
        self.attach_listener(AVGECardAttributeChangePostCheck())

    def core(self, args: Data = {}) -> Response:
        """Execute the change"""
        self.old_amt = self.target_card.attributes[self.attribute]
        if self.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE:
            self.target_card.attributes[self.attribute] += self.change_amount
        else:
            self.target_card.attributes[self.attribute] = self.change_amount
        return self.generate_core_response()

    def invert_core(self, args: Data = {}) -> None:
        """Restore old value on rollback"""
        self.target_card.attributes[self.attribute] = self.old_amt
```

### 9.2 TransferCard Event

Moves cards between piles (deck, hand, active, bench, discard):

```python
class TransferCard(AVGEEvent):
    def __init__(self, card, pile_from, pile_to, catalyst_action, caller_card, new_idx):
        super().__init__(card=card, pile_from=pile_from, pile_to=pile_to, ...)
        self.card = card
        self.pile_to = pile_to
        self.pile_from = pile_from
        self.new_idx = new_idx
        self.old_idx = pile_from.get_posn(self.card)

    def core(self, args: Data = {}) -> Response:
        # Handle tool attachment
        if isinstance(self.card, AVGEToolCard):
            self.card.card_attached = (
                self.pile_to.parent_card if isinstance(self.pile_to, AVGEToolCardholder) 
                else None
            )
        # Transfer card
        self.card.env.transfer_card(self.card, self.pile_from, self.pile_to, self.new_idx)
        return self.generate_core_response()

    def invert_core(self, args: Data = {}) -> None:
        # Reverse transfer
        if isinstance(self.card, AVGEToolCard) and isinstance(self.pile_from, AVGEToolCardholder):
            self.card.card_attached = self._previous_card
        self.card.env.transfer_card(self.card, self.pile_to, self.pile_from, self.old_idx)
```

---

## 10. Summary: Complete Request Flow

### Attack Resolution (WestonPoe ATK 1)

```
USER ACTION: "Play ATK 1"
    ↓
PlayCharacterCard(
    card=WestonPoe,
    card_action=ActionTypes.ATK_1,
    catalyst_action=ActionTypes.PLAYER_CHOICE,
    caller_card=WestonPoe
)
    ↓ (through pipeline groups)
    ↓
CORE: Calls WestonPoe.atk_1()
    ↓
Proposes packet:
  [
    AVGECardAttributeChange(target=opponent, HP: -50, ATK_1),
    AVGECardAttributeChange(target=self, HP: -10, ATK_1)
  ]
    ↓ (packet queued)
    ↓
ENGINE PROCESSES FIRST EVENT: damage to opponent
    ├─ INTERNAL_1: Assessment passes
    ├─ EXTERNAL_MODIFIERS_2: Opponent's FelixDamageReducer
    │   └─ Checks: Is it damage? (-50) Is it to opponent's character? Yes
    │   └─ event_effect(): Different types? (checking...)
    │   └─ modify(): change_amount = -50 + 10 = -40 (reduced to 40 damage)
    ├─ INTERNAL_3: Clamping modifier
    │   └─ 80 - 40 = 40 HP (valid)
    ├─ CORE: opponent.attributes[HP] = 80 - 40 = 40
    ├─ EXTERNAL_REACTORS: WestonPoe's passive doesn't match (damage is TO opponent)
    └─ Event complete: 40 damage dealt (reduced from 50)
    ↓
ENGINE PROCESSES SECOND EVENT: 10 recoil damage to self
    ├─ INTERNAL_1: Assessment passes
    ├─ EXTERNAL_MODIFIERS: Check mods on WestonPoe
    │   └─ No damage reducers for self-damage
    ├─ CORE: WestonPoe.attributes[HP] = 110 - 10 = 100
    ├─ EXTERNAL_REACTORS: Check reactions
    │   └─ WestonPoe's DamageReflector checks: Is damage >= 60? No (10 < 60)
    │   └─ No reaction
    └─ Event complete
    ↓
PACKET COMPLETE
    ├─ All listeners called on_packet_completion()
    ├─ Constraints remain valid
    └─ Turn continues to next phase

FINAL STATE:
  WestonPoe: 110 → 100 HP
  Opponent Character: 80 → 40 HP
```

---

## Architecture Strengths

1. **Atomic Transactions**: Entire packet rollback on any error - no partial state mutations
2. **Listener Flexibility**: Listeners can run in any group, modifying or reacting at appropriate times
3. **Constraint Hierarchy**: Constraints automatically manage their own supersession
4. **Lazy Evaluation**: Events can defer computation to runtime with callables
5. **Event Interruption**: Abilities can pause for user input without losing state
6. **Extensibility**: New event types just implement `core()` and `generate_internal_listeners()`

