from __future__ import annotations
from ..avge_abstracts.AVGECard import *
from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ..avge_abstracts.AVGEPlayer import AVGEPlayer
from collections.abc import Callable
from ..engine.event import Event, Generator, Packet
from ..constants import *
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..avge_abstracts.AVGEDeck import *
from .AVGEIOManager import *


class Broadcast(Event):
    '''An event that broadcasts a list of IO events to everyone. Waits on all futures before continuing'''

    def __init__(self,
                 id: AVGEEngineID,
                 env: AVGEEnvironment,
                 broadcast : BroadcastIO):
        super().__init__(id=id,
                         broadcast=broadcast,
                         env=env)
        self.id: AVGEEngineID = id
        self.broadcast = broadcast
        self.env = env

    async def act(self):
        await self.env.io_manager.broadcast(self.broadcast)

    def rollback(self) -> None:
        return


class AVGECardHPChangeEvent(Event):
    '''An event that causes a card's HP to change'''

    def __init__(self,
                 id: AVGEEngineID,
                 target_card: AVGECharacterCard | Callable[[], AVGECharacterCard],
                 magnitude: int | Callable[[], int],
                 modifier_type: AVGEAttributeModifier | Callable[[], AVGEAttributeModifier],
                 change_type: CardType | Callable[[], CardType],
                 env: AVGEEnvironment):
        super().__init__(id=id,
                         target_card=target_card,
                         magnitude=magnitude,
                         modifier_type=modifier_type,
                         change_type=change_type,
                         env=env)
        self.id: AVGEEngineID = id
        self.magnitude = magnitude
        self.target_card = target_card
        self.change_type = change_type
        self.modifier_type = modifier_type
        self.original_hp: int | None = None
        self.final_change: int | None = None
        self.env = env
        self.is_crit = False

    def modify_magnitude(self, change: int):
        '''Function to help properly the magnitude of the HP change'''
        assert not callable(self.magnitude)
        # please use this function when modifying magnitudes, thanks!
        self.magnitude += change
        self.magnitude = max(0, self.magnitude)

    def current_proposed_hp(self):
        '''Function to help get the HP that this card would be if the event ran right now'''
        assert not callable(self.magnitude)
        assert not callable(self.target_card)
        if (self.modifier_type == AVGEAttributeModifier.ADDITIVE):
            return min(self.target_card.hp + self.magnitude, self.target_card.max_hp)
        elif (self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            return max(0, self.target_card.hp - self.magnitude)
        else:
            return self.magnitude

    async def act(self) -> None:
        '''Defines what the event does'''
        assert not callable(self.target_card)
        self.original_hp = self.target_card.hp
        self.target_card.hp = self.current_proposed_hp()
        self.final_change = self.target_card.hp

    def rollback(self) -> None:
        assert not callable(self.target_card)
        assert self.original_hp is not None
        self.target_card.hp = self.original_hp


class AVGECardMaxHPChangeEvent(Event):
    '''An event that causes a card's MAX HP to change.'''

    def __init__(self,
                 id: AVGEEngineID,
                 target_card: AVGECharacterCard | Callable[[], AVGECharacterCard],
                 magnitude: int | Callable[[], int],
                 modifier_type: AVGEAttributeModifier | Callable[[], AVGEAttributeModifier],
                 change_type: CardType | Callable[[], CardType],
                 env: AVGEEnvironment):
        super().__init__(id=id,
                         target_card=target_card,
                         magnitude=magnitude,
                         modifier_type=modifier_type,
                         change_type=change_type,
                         env=env)
        self.id: AVGEEngineID = id
        self.magnitude = magnitude
        self.target_card = target_card
        self.change_type = change_type
        self.modifier_type = modifier_type
        self.original_hp: int | None = None
        self.original_max_hp: int | None = None
        self.final_hp: int | None = None
        self.final_max_hp: int | None = None
        self.env = env

    def modify_magnitude(self, change: int):
        '''Function to help properly the magnitude of the HP change'''
        assert not callable(self.magnitude)
        # please use this function when modifying magnitudes, thanks!
        self.magnitude += change
        self.magnitude = max(0, self.magnitude)

    def current_proposed_max_hp(self):
        '''Function to help get current MAX HP that this card would be if the event ran right now'''
        assert not callable(self.magnitude)
        assert not callable(self.target_card)
        if (self.modifier_type == AVGEAttributeModifier.ADDITIVE):
            return self.target_card.max_hp + self.magnitude
        elif (self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            return max(0, self.target_card.max_hp - self.magnitude)
        else:
            return self.magnitude

    async def act(self) -> None:
        '''Defines what the event does'''
        assert not callable(self.target_card)
        self.original_hp = self.target_card.hp
        self.original_max_hp = self.target_card.max_hp
        self.target_card.max_hp = self.current_proposed_max_hp()
        self.target_card.hp = min(self.target_card.max_hp, self.target_card.hp)
        self.final_hp = self.target_card.hp
        self.final_max_hp = self.target_card.max_hp

    def rollback(self) -> None:
        assert not callable(self.target_card)
        assert self.original_hp is not None
        assert self.original_max_hp is not None
        self.target_card.max_hp = self.original_max_hp
        self.target_card.hp = self.original_hp


class AVGECardTypeChange(Event):
    '''An event that causes a card's type to change'''

    def __init__(self,
                 id: AVGEEngineID,
                 target: AVGECharacterCard | Callable[[], AVGECharacterCard],
                 new_type: CardType | Callable[[], CardType],
                 env: AVGEEnvironment
                 ):
        super().__init__(id=id, target=target, new_type=new_type, env=env)
        self.id: AVGEEngineID = id
        self.target = target
        self.original_type: CardType | None = None
        self.new_type = new_type
        self.env = env

    async def act(self) -> None:
        '''Defines what the event does'''
        assert not callable(self.target)
        assert not callable(self.new_type)
        self.original_type = self.target.card_type
        self.target.card_type = self.new_type

    def rollback(self) -> None:
        assert not callable(self.target)
        assert self.original_type is not None
        self.target.card_type = self.original_type


class AVGECardStatusChange(Event):
    '''An event that causes a card's status to change'''

    def __init__(self,
                 id: AVGEEngineID,
                 target: AVGECharacterCard | Callable[[], AVGECharacterCard],
                 giver: AVGECard | AVGEPlayer | AVGEEnvironment | Callable[[], AVGECard | AVGEPlayer | AVGEEnvironment],
                 status: StatusEffect | Callable[[], StatusEffect],
                 change: AVGEStatusModifier | Callable[[], AVGEStatusModifier],
                 env: AVGEEnvironment
                 ):
        super().__init__(id=id, target=target, status=status,
                         change=change, env=env, giver=giver)
        self.target = target
        self.status = status
        self.change = change
        self._made_modification = False
        self.id = id
        self.env = env
        self.giver = giver

    @property
    def made_modification(self) -> bool:
        '''Whether act() actually added/removed the status (False for a no-op, e.g.
        adding a status the target already has from this giver).'''
        return self._made_modification

    async def act(self) -> None:
        '''Defines what the event does'''
        assert not callable(self.target)
        assert not callable(self.status)
        assert not callable(self.change)
        assert not callable(self.giver)
        if (self.change == AVGEStatusModifier.ADD and self.giver not in self.target.statuses_attached[self.status]):
            self.target.statuses_attached[self.status].add(self.giver)
            self._made_modification = True
        elif (self.change == AVGEStatusModifier.REMOVE and self.giver in self.target.statuses_attached[self.status]):
            self.target.statuses_attached[self.status].remove(self.giver)
            self._made_modification = True

    def rollback(self) -> None:
        assert not callable(self.target)
        assert not callable(self.status)
        assert not callable(self.change)
        assert not callable(self.giver)
        if (self.change == AVGEStatusModifier.ADD and self._made_modification):
            self.target.statuses_attached[self.status].remove(self.giver)
        elif (self.change == AVGEStatusModifier.REMOVE and self._made_modification):
            self.target.statuses_attached[self.status].add(self.giver)


class AVGEEnergyTransfer(Event):
    '''An event that transfers an arbitrary energy token from one thing to another. Will not do anything if the thing being transferred from has no tokens'''

    def __init__(self,
                 id: AVGEEngineID,
                 token_from: AVGECharacterCard | AVGEEnvironment | Callable[[], AVGECharacterCard | AVGEEnvironment],
                 token_to: AVGECharacterCard | AVGEEnvironment | Callable[[
                 ], AVGECharacterCard | AVGEEnvironment],
                 env: AVGEEnvironment
                 ):
        super().__init__(id=id, token_from=token_from, token_to=token_to, env=env)
        self.id: AVGEEngineID = id
        self.token_from = token_from
        self.token_to = token_to
        self._transferred_token = None
        self.env = env

    @property
    def did_transfer(self) -> bool:
        return self._transferred_token is not None

    async def act(self) -> None:
        '''Defines what the event does'''
        assert not callable(self.token_from)
        assert not callable(self.token_to)
        if (len(self.token_from.energy_tokens) == 0):
            return
        self._transferred_token = self.token_from.energy_tokens.pop(0)
        self.token_to.energy_tokens.append(self._transferred_token)

    def rollback(self) -> None:
        assert not callable(self.token_from)
        assert not callable(self.token_to)
        if (self._transferred_token is not None):
            self.token_to.energy_tokens.remove(self._transferred_token)
            self.token_from.energy_tokens.append(self._transferred_token)


class AVGEPlayerAttributeChange(Event):
    '''An event that changes a player attribute'''

    def __init__(self,
                 id: AVGEEngineID,
                 player: AVGEPlayer | Callable[[], AVGEPlayer],
                 attribute: AVGEPlayerAttribute | Callable[[], AVGEPlayerAttribute],
                 modifier_type: AVGEAttributeModifier | Callable[[], AVGEAttributeModifier],
                 magnitude: int | Callable[[], int],
                 env: AVGEEnvironment
                 ):
        super().__init__(id=id, player=player, attribute=attribute,
                         modifier_type=modifier_type, magnitude=magnitude, env=env)
        self.id: AVGEEngineID
        self.player = player
        self.attribute = attribute
        self.modifier_type = modifier_type
        self.magnitude = magnitude
        self.env = env
        self._original_value = None

    async def act(self) -> None:
        assert not callable(self.player)
        assert not callable(self.magnitude)
        assert not callable(self.attribute)
        self._original_value = self.player.attributes[self.attribute]
        if (self.modifier_type == AVGEAttributeModifier.SET_STATE):
            self.player.attributes[self.attribute] = self.magnitude
        elif (self.modifier_type == AVGEAttributeModifier.ADDITIVE):
            self.player.attributes[self.attribute] += self.magnitude
        elif (self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            self.player.attributes[self.attribute] -= self.magnitude

    def rollback(self) -> None:
        assert self._original_value is not None
        assert not callable(self.player)
        assert not callable(self.attribute)
        self.player.attributes[self.attribute] = self._original_value


class TransferCard(Event):
    '''An event that transfers a card from X to Y'''

    def __init__(self,
                 id: AVGEEngineID,
                 card: AVGECard | Callable[[], AVGECard],
                 deck_from: AVGEDeck | Callable[[], AVGEDeck],
                 deck_to: AVGEDeck | Callable[[], AVGEDeck],
                 env: AVGEEnvironment,
                 cost: int | Callable[[], int] = 0):
        super().__init__(id=id, card=card, deck_from=deck_from, deck_to=deck_to, env=env, cost=cost)
        self.id = id
        self.card = card
        self.deck_from = deck_from
        self.deck_to = deck_to
        self.env = env
        # Only ever meaningful for the ACTIVE_CARD -> BENCH leg of a retreat (see
        # Phase2CardMovement's own construction site below and A2's retreat-cost fix):
        # 0 for every other transfer, which is a no-op everywhere this is read/charged.
        # Kiki's/GOON's/Petteruti's cost effects are plain EXTERNAL_MODIFIERS_1
        # modifiers on this field now, instead of the old regulator-plus-reactor pairs
        # that could never see each other's adjustments (see each of their own files).
        self.cost = cost

    async def _on_character_entry(self, card : AVGECharacterCard):
        _id = AVGEEngineID(card, ActionTypes.PASSIVE, type(card))
        if(ActionTypes.PASSIVE in card.actions):
            events : list[Event | Generator] = [PlayCharacterCard(
                _id, card, ActionTypes.PASSIVE, 0, self.env
            )]
            self.env.push_packet(Packet(_id, events))

    async def _on_character_leaves_play(self, card: AVGECharacterCard):
        '''Resets a character's HP/energy/statuses and moves its tools to discard -
        originally only fired for discard-bound transfers (hence the old name), but
        none of this is actually discard-specific: a character leaving play to HAND or
        DECK (RachaelYuan's E2 Reaction, HappyRuthJara's Leave Rehearsal Early,
        PascalKim's Ominous Chimes) needs the exact same reset, and previously got
        none at all - it kept its damage, energy, and statuses, then re-entered play
        later still carrying them. Attached tools always go to the owner's discard
        regardless of where the character itself is headed - that part was never
        discard-specific to begin with.'''
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        events: list[Event | Generator] = []
        # 1. reset HP
        events.append(AVGECardHPChangeEvent(
            _id,
            card,
            card.max_hp,
            AVGEAttributeModifier.SET_STATE,
            CardType.ALL,
            self.env
        ))
        # 2. remove all energy
        for _ in card.energy_tokens:
            events.append(AVGEEnergyTransfer(
                _id,
                card,
                self.env,
                self.env
            ))
        # 3. remove all effects
        for status in card.statuses_attached:
            for sender in card.statuses_attached[status]:
                events.append(AVGECardStatusChange(
                    _id,
                    card,
                    sender,
                    status,
                    AVGEStatusModifier.REMOVE,
                    self.env
                ))
        # 4. remove all tools
        for tool in card.tools_attached:
            events.append(TransferCard(
                _id,
                tool,
                card.tools_attached,
                self.env.players[card.owner].card_piles[DeckType.DISCARD],
                self.env
            ))
        resp = await self.interrupt(events)
        if (resp == ResponseStatus.REGULATE_FAIL):
            raise Exception(
                "REGULATE_FAIL occured on character card discard for unknown reason")

    async def _on_retreat_cost(self, card: AVGECharacterCard, cost: int):
        '''Charges this transfer's own (already-modifier-resolved, already-validated -
        see AVGETransferValidityCheck) cost directly, mirroring
        _on_character_leaves_play's own energy-removal loop. Replaces the old
        AVGERetreatCostReactor, which read the card's raw, undiscounted retreat_cost
        instead of this event's own cost - see A2's own writeup for why that made
        Kiki's/Petteruti's discounts and GOON's surcharge unable to agree with the
        earlier validity check on what a retreat actually costs.'''
        if cost <= 0:
            return
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        events: list[Event | Generator] = [AVGEEnergyTransfer(
            _id, card, self.env, self.env,
        ) for _ in range(cost)]
        resp = await self.interrupt(events)
        if (resp == ResponseStatus.REGULATE_FAIL):
            raise Exception(
                "REGULATE_FAIL occured on retreat cost charge for unknown reason")

    async def act(self):
        assert not callable(self.card)
        assert not callable(self.deck_to)
        assert not callable(self.deck_from)
        assert not callable(self.cost)

        # Special Case 0: retreat cost. Only ever nonzero for the ACTIVE_CARD -> BENCH
        # leg of a retreat (see Phase2CardMovement's construction site) - runs before
        # the physical transfer below, same as every other special case here.
        if (self.cost > 0 and self.deck_from.deck_type == DeckType.ACTIVE_CARD and self.deck_to.deck_type == DeckType.BENCH and isinstance(self.card, AVGECharacterCard)):
            await self._on_retreat_cost(self.card, self.cost)

        # Special Case 1: Default character-leaves-play handling (HP/energy/status
        # reset, tools to discard). Originally only fired for a discard-bound
        # transfer; broadened to also cover HAND/DECK destinations (see
        # _on_character_leaves_play's own docstring) - a character returning to hand
        # or deck needs the exact same reset a discard already got. This does NOT
        # deal with garbage collection.
        if (self.deck_to.deck_type in [DeckType.DISCARD, DeckType.HAND, DeckType.DECK] and self.deck_from.deck_type in [DeckType.BENCH, DeckType.ACTIVE_CARD] and isinstance(self.card, AVGECharacterCard)):
            await self._on_character_leaves_play(self.card)

        # Special Case 2: Default character passive activation handling
        if (self.deck_from.deck_type not in [DeckType.BENCH, DeckType.ACTIVE_CARD] and self.deck_to.deck_type in [DeckType.BENCH, DeckType.ACTIVE_CARD] and isinstance(self.card, AVGECharacterCard)):
            await self._on_character_entry(self.card)

        # Special Case 3: Tool/Stadium attach handling
        if (self.deck_to.deck_type in [DeckType.OFFHAND, DeckType.STADIUM]):
            assert isinstance(self.card, (AVGEToolCard, AVGEStadiumCard))
            self.push_event(PlayNonCharacterCard(
                self.id,
                self.card,
                self.env
            ))

        # All other cases, including GC
        await self.card.on_transfer(self.deck_from, self.deck_to, self)
        # Assuming everything else succeeded, actualize the transfer
        transfer_card(self.card, self.deck_from, self.deck_to)
        if isinstance(self.deck_to, AVGEToolHolder):
            assert isinstance(self.card, AVGEToolCard)
            self.card.parent_card = self.deck_to.parent_card
        elif isinstance(self.deck_from, AVGEToolHolder):
            assert isinstance(self.card, AVGEToolCard)
            self.card.parent_card = None
        self.card.deck_type = self.deck_to.deck_type

    def rollback(self):
        assert not callable(self.card)
        assert not callable(self.deck_to)
        assert not callable(self.deck_from)
        transfer_card(self.card, self.deck_to, self.deck_from)
        if (isinstance(self.deck_to, AVGEToolHolder)):
            assert isinstance(self.card, AVGEToolCard)
            self.card.parent_card = None
        elif isinstance(self.deck_from, AVGEToolHolder):
            assert isinstance(self.card, AVGEToolCard)
            self.card.parent_card = self.deck_from.parent_card
        self.card.deck_type = self.deck_from.deck_type


class ReorderDeck(Event):
    '''An event that reorders a deck with a new reordering'''

    def __init__(self,
                 id: AVGEEngineID,
                 deck: AVGEDeck | Callable[[], AVGEDeck],
                 reordering: list[AVGECard] | Callable[[], list[AVGECard]],
                 env: AVGEEnvironment):
        super().__init__(id=id, deck=deck, reordering=reordering, env=env)
        self.id = id
        self.deck = deck
        self.reordering = reordering
        self.env = env
        self._old_order = None

    async def act(self):
        assert not callable(self.deck)
        assert not callable(self.reordering)
        assert len(self.reordering) == len(self.deck) and all(
            [r in self.deck.cards_holding for r in self.reordering])
        self._old_order = list(self.deck.cards_holding)
        self.deck.cards_holding = self.reordering

    def rollback(self):
        assert not callable(self.deck)
        assert self._old_order is not None
        self.deck.cards_holding = self._old_order


class PlayCharacterCard(Event):
    def __init__(self,
                 id: AVGEEngineID,
                 target_card: AVGECharacterCard | Callable[[], AVGECharacterCard],
                 action: ActionTypes | Callable[[], ActionTypes],
                 cost: int | Callable[[], int],
                 env: AVGEEnvironment):
        super().__init__(id=id, target_card=target_card, action=action, env=env, cost=cost)
        self.id = id
        self.target_card = target_card
        self.action = action
        self.env = env
        self.cost = cost

    async def act(self):
        assert not callable(self.action)
        assert not callable(self.target_card)
        acting_card = self.target_card if not isinstance(
            self.id.calling_card, AVGECharacterCard) else self.id.calling_card
        action = self.target_card.actions.get(self.action)
        if action is None:
            return
        await action(self.target_card, acting_card)

    def rollback(self):
        return


class PlayNonCharacterCard(Event):
    def __init__(self,
                 id: AVGEEngineID,
                 target_card: AVGENonCharacterCard | Callable[[], AVGENonCharacterCard],
                 env: AVGEEnvironment):
        super().__init__(id=id, target_card=target_card, action=ActionTypes.NONCHAR, env=env)
        self.id = id
        self.target_card = target_card
        self.action = ActionTypes.NONCHAR
        self.env = env

    async def act(self):
        assert not callable(self.target_card)
        acting_card = self.target_card if not isinstance(
            self.id.calling_card, AVGECard) else self.id.calling_card
        action = self.target_card.actions.get(ActionTypes.NONCHAR)
        if action is None:
            return
        await action(self.target_card, acting_card)

    def rollback(self):
        return


class PhasePickCard(Event):
    def __init__(self, id: AVGEEngineID, env: AVGEEnvironment):
        super().__init__(id=id, env=env)
        self.id = id
        self.env = env

    async def act(self):
        player: AVGEPlayer = self.env.get_current_player()
        deck = player.card_piles[DeckType.DECK]
        hand = player.card_piles[DeckType.HAND]

        def draw_top_card() -> list[Event | Generator]:
            if len(deck) == 0:
                return []
            return [TransferCard(
                AVGEEngineID(None, ActionTypes.ENV, None),
                deck.get_top(),
                deck,
                hand,
                self.env)]

        # Queue the draw unconditionally (rather than only when the deck is
        # non-empty) means a player whose deck is already empty at turn start simply
        # skips the draw, then reaches Phase2 through the engine's idle hook.
        # The prompt must wait for this draw and all of its triggered effects.
        self.env.phase = "main"
        self.env.append_packet(Packet(
            AVGEEngineID(None, ActionTypes.ENV, None),
            [draw_top_card]))

    def rollback(self):
        return


class Phase2(Event):
    def __init__(self, id: AVGEEngineID, env: AVGEEnvironment):
        super().__init__(id=id, env=env)
        self.id = id
        self.env = env

    async def act(self):
        self.env.phase = "main"
        io_obj = Phase2IO(self.env.turn)
        res = await self.env.report(io_obj, self.id)
        match res:
            case Phase2PlayCard():
                match res.card:
                    case AVGEItemCard():
                        player = self.env.get_current_player()
                        self.env.push_packet(Packet(
                            AVGEEngineID(
                                None, ActionTypes.PLAYER_CHOICE, None),
                            [
                                PlayNonCharacterCard(
                                    AVGEEngineID(
                                        None, ActionTypes.PLAYER_CHOICE, None),
                                    res.card,
                                    self.env
                                ),
                                TransferCard(
                                    AVGEEngineID(
                                        None, ActionTypes.PLAYER_CHOICE, None),
                                    res.card,
                                    player.card_piles[DeckType.HAND],
                                    player.card_piles[DeckType.DISCARD],
                                    self.env
                                )
                            ]
                        ))
                    case AVGESupporterCard():
                        player = self.env.get_current_player()
                        self.env.push_packet(Packet(
                            AVGEEngineID(
                                None, ActionTypes.PLAYER_CHOICE, None),
                            [
                                PlayNonCharacterCard(
                                    AVGEEngineID(
                                        None, ActionTypes.PLAYER_CHOICE, None),
                                    res.card,
                                    self.env
                                ),
                                AVGEPlayerAttributeChange(
                                    AVGEEngineID(
                                        None, ActionTypes.PLAYER_CHOICE, None),
                                    player,
                                    AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN,
                                    AVGEAttributeModifier.SUBSTRACTIVE,
                                    1,
                                    self.env
                                ),
                                TransferCard(
                                    AVGEEngineID(
                                        None, ActionTypes.PLAYER_CHOICE, None),
                                    res.card,
                                    player.card_piles[DeckType.HAND],
                                    player.card_piles[DeckType.DISCARD],
                                    self.env
                                )
                            ]
                        ))
            case Phase2ActivateAbility():
                self.env.push_packet(Packet(
                    AVGEEngineID(
                        None, ActionTypes.PLAYER_CHOICE, None),
                    [
                        PlayCharacterCard(
                            AVGEEngineID(
                                None, ActionTypes.PLAYER_CHOICE, None),
                            res.card,
                            ActionTypes.ACTIVATE_ABILITY,
                            0,
                            self.env
                        )
                    ]
                ))
            case Phase2CardMovement():
                events: list[Event | Generator] = [
                    TransferCard(
                        AVGEEngineID(
                            None, ActionTypes.PLAYER_CHOICE, None),
                        res.card,
                        res.deck_from,
                        res.deck_to,
                        self.env
                    )
                ]
                if (isinstance(res.card, AVGECharacterCard) and res.deck_from.deck_type == DeckType.BENCH and res.deck_to.deck_type == DeckType.ACTIVE_CARD):
                    # implements the swap
                    outgoing_active = self.env.get_current_player().card_piles[DeckType.ACTIVE_CARD][0]
                    assert isinstance(outgoing_active, AVGECharacterCard)
                    # Resolve retreat cost and its orderable modifiers while
                    # both characters are still in their original slots. An
                    # order prompt on this leg must not expose a halfway swap.
                    events.insert(0, TransferCard(
                        AVGEEngineID(
                            None, ActionTypes.PLAYER_CHOICE, None),
                        outgoing_active,
                        res.deck_to,
                        res.deck_from,
                        self.env,
                        # Base cost, before Kiki's/GOON's/Petteruti's own
                        # EXTERNAL_MODIFIERS_1 modifiers (if any apply) adjust it and
                        # AVGETransferValidityCheck validates the result - see A2.
                        outgoing_active.retreat_cost,
                    ))
                    # AVGETransferValidityCheck only REJECTS once this hits 0 - nothing else in
                    # this case ever decremented it, so a player could otherwise swap as many
                    # times as they liked in one turn.
                    events.append(AVGEPlayerAttributeChange(
                        AVGEEngineID(
                            None, ActionTypes.PLAYER_CHOICE, None),
                        self.env.get_current_player(),
                        AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        1,
                        self.env
                    ))
                self.env.push_packet(Packet(
                    AVGEEngineID(
                        None, ActionTypes.PLAYER_CHOICE, None),
                    events
                ))
            case Phase2EnergyAttach():
                energy_events: list[Event | Generator] = [
                    AVGEEnergyTransfer(
                        AVGEEngineID(
                            None, ActionTypes.PLAYER_CHOICE, None),
                        res.token_from,
                        res.token_to,
                        self.env
                    )
                ]
                if isinstance(res.token_to, AVGECharacterCard):
                    # AVGETokenTransferCheck only REJECTS once this hits 0 - nothing else ever
                    # decremented it, so a player could otherwise attach unlimited energy in one
                    # turn. Matches that check's own gating (token_to being a character) rather
                    # than assuming every Phase2EnergyAttach attaches to one, since token_to can
                    # also be the environment.
                    energy_events.append(AVGEPlayerAttributeChange(
                        AVGEEngineID(
                            None, ActionTypes.PLAYER_CHOICE, None),
                        self.env.get_current_player(),
                        AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        1,
                        self.env
                    ))
                self.env.push_packet(Packet(
                    AVGEEngineID(
                        None, ActionTypes.PLAYER_CHOICE, None),
                    energy_events
                ))
            case Phase2Finish():
                self.env.phase = "attack" if self.env.round > 0 else "turn_end"
                self.env.push_packet(Packet(
                    AVGEEngineID(
                        None, ActionTypes.ENV, None),
                    [
                        AtkPhase(
                            AVGEEngineID(None, ActionTypes.ENV, None),
                            self.env
                        ) if self.env.round > 0 else
                        TurnEnd(
                            AVGEEngineID(None, ActionTypes.ENV, None),
                            self.env
                        )
                    ]
                ))
            case _:
                raise Exception("Bad Phase 2 Event")

    def rollback(self):
        return


class AtkPhase(Event):
    def __init__(self, id: AVGEEngineID, env: AVGEEnvironment):
        super().__init__(id=id, env=env)
        self.id = id
        self.env = env

    async def act(self):
        self.env.phase = "attack"
        # get_player_active() indexes into the active pile directly and raises if it's
        # empty - previously never reached here unless res != SKIP (see below), so a
        # turn with no active card at all (a test-harness-only situation today, but not
        # guaranteed to stay that way - see B4) still worked, just always skipping.
        # Guarding this the same way keeps that tolerance intact now that the active
        # card's own attacks are needed earlier, to build allowed_actions.
        current_active = self.env.get_current_player().card_piles[DeckType.ACTIVE_CARD]
        allowed_actions: list[ActionTypes] = [ActionTypes.SKIP]
        if len(current_active) > 0:
            active_card = current_active[0]
            assert isinstance(active_card, AVGECharacterCard)
            allowed_actions += [
                action_type
                for action_type in (ActionTypes.ATK_1, ActionTypes.ATK_2)
                if (
                    (action := active_card.actions.get(action_type)) is not None
                    and isinstance(action, Attack)
                )
            ]
        res = await (self.env.report(AtkPhaseIO(self.env.turn, allowed_actions), self.id))
        assert (res == ActionTypes.ATK_1 or res ==
                ActionTypes.ATK_2 or res == ActionTypes.SKIP)
        _id = AVGEEngineID(None,
                           ActionTypes.PLAYER_CHOICE,
                           None)

        attacking_turn = self.env.turn

        def _attack_switch() -> list[Event | Generator]:
            # An attack effect may itself advance the turn. Its old continuation
            # must not open an attack prompt for the new player.
            if self.env.phase != "attack" or self.env.turn != attacking_turn:
                return []
            if (self.env.get_current_player().attributes[AVGEPlayerAttribute.ATTACKS_LEFT] != 0):
                return [
                    AtkPhase(AVGEEngineID(
                        None, ActionTypes.ENV, None), self.env)
                ]
            else:
                return [
                    TurnEnd(AVGEEngineID(
                        None, ActionTypes.ENV, None
                    ), self.env)
                ]
        attack_use = AVGEPlayerAttributeChange(
            _id,
            self.env.get_current_player(),
            AVGEPlayerAttribute.ATTACKS_LEFT,
            AVGEAttributeModifier.SUBSTRACTIVE,
            1,
            self.env
        )
        base_packet: list[Event | Generator] = []
        if (res != ActionTypes.SKIP):
            active_card = self.env.get_player_active(self.env.turn)
            action = active_card.actions.get(res)
            if not isinstance(action, Attack):
                return
            base_packet += [
                PlayCharacterCard(
                    _id,
                    active_card,
                    res,
                    action.cost,
                    self.env
                ),
            ]
        # Validate the attack before broadcasting its allowance change. If a
        # cost or card lock rejects it, the packet rolls back without a false
        # "ATTACKS_LEFT -> 0" entry in the player's event log.
        base_packet.append(attack_use)
        self.env.push_packet(Packet(
            _id,
            base_packet))
        self.env.append_packet(Packet(_id, [_attack_switch]))

    def rollback(self):
        return


class TurnEnd(Event):
    def __init__(self, id: AVGEEngineID, env: AVGEEnvironment):
        super().__init__(id=id, env=env)
        self.id = id
        self.env = env
        self._last_turn: User | None = None

    async def act(self):
        self._last_turn = self.env.turn
        self.env.phase = "draw"
        self.env.turn = self.env.turn.next
        _id = AVGEEngineID(None,
                           ActionTypes.ENV,
                           None)
        self.env.push_packet(Packet(
            _id,
            [
                AVGEPlayerAttributeChange(
                    _id,
                    self.env.get_current_player(),
                    AVGEPlayerAttribute.ATTACKS_LEFT,
                    AVGEAttributeModifier.SET_STATE,
                    PER_TURN_ATKS,
                    self.env
                ),
                AVGEPlayerAttributeChange(
                    _id,
                    self.env.get_current_player(),
                    AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN,
                    AVGEAttributeModifier.SET_STATE,
                    PER_TURN_SWAPS,
                    self.env
                ),
                AVGEPlayerAttributeChange(
                    _id,
                    self.env.get_current_player(),
                    AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN,
                    AVGEAttributeModifier.SET_STATE,
                    PER_TURN_SUPPORTER_USE,
                    self.env
                ),
                AVGEPlayerAttributeChange(
                    _id,
                    self.env.get_current_player(),
                    AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN,
                    AVGEAttributeModifier.SET_STATE,
                    PER_TURN_TOKEN_ADD,
                    self.env
                ),
                PhasePickCard(
                    _id,
                    self.env
                )
            ]))
        self.env.round += 1

    def rollback(self):
        raise Exception("A Turn End event should never be rolled back")


class GameEnd(Event):
    def __init__(self, id: AVGEEngineID, winner: User, reason: WinReasons, env: AVGEEnvironment):
        super().__init__(id=id, winner=winner, reason=reason, env=env)
        self.id = id
        self.winner = winner
        self.reason = reason
        self.env = env

    async def act(self):
        self.env.winner = self.winner
        self.env.win_reason = self.reason
        await asyncio.gather(self.env.report(GameEndIO(User.PLAYER_1), AVGEEngineID(None, ActionTypes.ENV, None)), self.env.report(GameEndIO(User.PLAYER_2), AVGEEngineID(None, ActionTypes.ENV, None)))
        self.env.engine.terminate_flag = True

    def rollback(self):
        return
