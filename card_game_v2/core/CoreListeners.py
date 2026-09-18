from ..avge_abstracts.AVGEEventListener import *
from ..avge_abstracts.AVGECard import *
from .EventCatalog import *
from ..constants import ResponseStatus
from ..engine.event import Event


def _reject(event: Event, reason: str) -> ResponseStatus:
    '''Regulator helper: records a human-readable reason on the packet - relayed to clients
    alongside the state resync once REGULATE_FAIL propagates up to on_packet_failed, see
    Packet.rejection_reason in engine/event.py - and returns REGULATE_FAIL.'''
    assert event._parent_packet is not None  # type: ignore
    event._parent_packet.rejection_reason = reason  # type: ignore
    return ResponseStatus.REGULATE_FAIL


class AVGETokenTransferCheck(AVGEEventRegulator):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_1)
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, AVGEEnergyTransfer)

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, AVGEEnergyTransfer)
        assert not callable(event.token_from)
        if (len(event.token_from.energy_tokens) == 0):
            return _reject(event, "No energy left on that card to move.")
        if (event.id.calling_action == ActionTypes.PLAYER_CHOICE):
            if (isinstance(event.token_to, AVGECharacterCard)):
                if (self.env.players[event.token_to.owner].attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] == 0):
                    return _reject(event, "You've already attached energy this turn.")
        return ResponseStatus.REGULATE_PASS


class AVGEHPChangeCheck(AVGEEventRegulator):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_1)
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, AVGECardHPChangeEvent)

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, AVGECardHPChangeEvent)
        assert not callable(event.target_card)
        if (event.target_card.deck_type not in [DeckType.BENCH, DeckType.ACTIVE_CARD] and event.id.calling_action != ActionTypes.ENV):
            return ResponseStatus.REGULATE_IGNORE
        return ResponseStatus.REGULATE_PASS


class AVGEHPChangeReactor(AVGEEventReactor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_3)
    def match(self, event: Event) -> bool:
        return isinstance(event, AVGECardHPChangeEvent)

    async def react(self, event: Event):
        assert isinstance(event, AVGECardHPChangeEvent)
        assert not callable(event.target_card)
        if (event.target_card.hp <= 0 and event.id.calling_action != ActionTypes.ENV):
            player = self.env.players[event.target_card.owner]
            opponent = self.env.get_opponent(event.target_card.owner)
            ko_increment = AVGEPlayerAttributeChange(
                AVGEEngineID(None, ActionTypes.ENV, None),
                opponent,
                AVGEPlayerAttribute.KO_COUNT,
                AVGEAttributeModifier.ADDITIVE,
                1,
                self.env
            )
            transfer_card_out = TransferCard(
                AVGEEngineID(None, ActionTypes.ENV, None),
                event.target_card,
                player.card_piles[event.target_card.deck_type],
                player.card_piles[DeckType.DISCARD],
                self.env
            )

            # ko_increment is pushed LAST in every branch below, after the discard/replacement -
            # it's the one event whose own reactor (AVGEPlayerAttributeChangeReactor, below) can
            # push GameEnd, and GameEnd sets engine.terminate_flag, which aborts whatever's still
            # queued in this same packet (engine/event.py's _run_queue loop checks it before
            # popping the next event). GameEnd's own push_event() also runs ahead of anything
            # already queued (push_event always inserts right after the currently-executing
            # event), so an event queued AFTER ko_increment can be abandoned entirely once
            # GameEnd commits - discarding the KO'd character has to happen before the increment
            # that might end the game, not after, or the discard silently never happens.
            if (opponent.attributes[AVGEPlayerAttribute.KO_COUNT] < KOS_TO_WIN - 1):
                # if the opponent still has a chance
                if (event.target_card.deck_type == DeckType.ACTIVE_CARD):
                    if (len(player.card_piles[DeckType.BENCH]) == 0):
                        # This is an instant loss regardless of KO_COUNT (no bench to replace
                        # with) - was never discarding the KO'd character here either, the same
                        # gap as the "winning KO" branch below, just reached a different way.
                        event.push_event([transfer_card_out, ko_increment, GameEnd(
                            AVGEEngineID(None, ActionTypes.ENV, None),
                            opponent.id,
                            WinReasons.KO_NO_DECK,
                            self.env
                        )])
                        return ResponseStatus.REACTOR_SKIP
                    else:
                        resp = await self.env.report(CardSelectionQuery(
                            player.id,
                            "Choose a benched character to switch the KO'd character with: ",
                            1,
                            [card for card in player.card_piles[DeckType.BENCH]],
                            [card for card in player.card_piles[DeckType.BENCH]],
                            False,
                            False
                        ), AVGEEngineID(None, ActionTypes.ENV, None))
                        new_card = resp[0]
                        assert isinstance(new_card, AVGECharacterCard)
                        transfer_card_in = TransferCard(
                            AVGEEngineID(None, ActionTypes.ENV, None),
                            new_card,
                            player.card_piles[new_card.deck_type],
                            player.card_piles[DeckType.ACTIVE_CARD],
                            self.env
                        )
                        event.push_event([
                            transfer_card_out,
                            transfer_card_in,
                            ko_increment
                        ])
                else:
                    event.push_event([
                        transfer_card_out,
                        ko_increment
                    ])
            else:
                # The winning KO - every other branch above also pushes transfer_card_out to
                # actually discard the KO'd character; this one was missing it entirely, leaving
                # a permanently un-discarded 0-HP "zombie" character in play (masked today only
                # because GameEnd fires immediately once KO_COUNT reaches KOS_TO_WIN, ending the
                # game right after - but that doesn't retroactively undo the missing discard).
                event.push_event([
                    transfer_card_out,
                    ko_increment
                ])


class AVGEWeaknessModifier(AVGEEventModifier):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_1)
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, AVGECardHPChangeEvent)

    async def modify(self, event: Event):
        assert isinstance(event, AVGECardHPChangeEvent)
        assert not callable(event.target_card)
        assert not callable(event.magnitude)
        if (type_weaknesses[event.target_card.card_type] == event.change_type and isinstance(event.id.calling_card, AVGECharacterCard) and event.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            res = await self.env.report(CoinflipData(event.id.calling_card.owner,"Critical! Flip a coin and get heads to double the damage!"), AVGEEngineID(None, ActionTypes.ENV, None))
            if (res == 1):
                event.modify_magnitude(event.magnitude)
                event.is_crit = True


class AVGEPlayerAttributeChangeReactor(AVGEEventReactor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_3)
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, AVGEPlayerAttributeChange)

    async def react(self, event: Event):
        assert isinstance(event, AVGEPlayerAttributeChange)
        assert not callable(event.player)
        if (event.attribute == AVGEPlayerAttribute.KO_COUNT):
            # Was hardcoded to `== 3` - harmless only because KOS_TO_WIN currently also equals 3.
            # AVGEHPChangeReactor's own win-condition check (above) already correctly derives from
            # KOS_TO_WIN; the moment that tunable constant changes, this hardcoded check would
            # stop matching it, and GameEnd would never fire.
            if (event.player.attributes[AVGEPlayerAttribute.KO_COUNT] == KOS_TO_WIN):
                event.push_event(
                    GameEnd(
                        AVGEEngineID(None, ActionTypes.ENV, None),
                        event.player.id,
                        WinReasons.ALL_KOS,
                        self.env
                    )
                )
                return ResponseStatus.REACTOR_SKIP


class AVGETransferValidityCheck(AVGEEventRegulator):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_1)
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, TransferCard) and event.id.calling_action == ActionTypes.PLAYER_CHOICE

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, TransferCard)
        assert not callable(event.deck_from)
        assert not callable(event.card)
        assert not callable(event.deck_to)
        # Was comparing deck_to against DeckType.DECK (the draw pile) instead of DeckType.BENCH -
        # HAND -> DECK never happens in real play, so the bench-size cap was completely
        # unenforced; a client could bench unlimited characters via the real HAND -> BENCH path.
        # Only a character card may ever land on the bench or active slot - server/io_adapter.py's
        # Phase2 deserializer already rejects this for a direct client request, but this is the
        # authoritative engine-level guard for every PLAYER_CHOICE transfer path (this regulator's
        # own match() above), not just that one. Load-bearing: AVGEHPChangeReactor's active-KO
        # bench-replacement flow below asserts the incoming card is a character - letting a
        # non-character through here would turn a KO into an engine crash instead of a clean
        # rejection.
        if (
            event.deck_to.deck_type in (DeckType.BENCH, DeckType.ACTIVE_CARD)
            and not isinstance(event.card, AVGECharacterCard)
        ):
            return _reject(event, "Only character cards can go on the bench or in the active slot.")
        # Symmetric guard for the other two typed destinations - without this, a mismatched
        # card/destination pairing (however it got constructed - not just a raw client request,
        # any future card effect building its own TransferCard) would reach
        # TransferCard.act()'s isinstance assert instead of a clean rejection, crashing the engine
        # and ending the match with reason="server_error" for both players.
        elif event.deck_to.deck_type == DeckType.STADIUM and not isinstance(event.card, AVGEStadiumCard):
            return _reject(event, "Only stadium cards can go in the stadium slot.")
        elif event.deck_to.deck_type == DeckType.OFFHAND and not isinstance(event.card, AVGEToolCard):
            return _reject(event, "Only tool cards can be attached as offhand items.")
        elif (event.deck_from.deck_type == DeckType.HAND and event.deck_to.deck_type == DeckType.BENCH and len(event.deck_to) >= MAX_BENCH_SIZE):
            return _reject(event, "Your bench is already full.")
        elif (event.deck_from.deck_type == DeckType.BENCH and event.deck_to.deck_type == DeckType.ACTIVE_CARD and self.env.players[event.card.owner].attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] == 0):
            return _reject(event, "You've already swapped your active character this turn.")
        # retreat_cost belongs to the card actually leaving the active slot (the current active
        # card), never the incoming bench card in event.card - AVGERetreatCostReactor (below)
        # charges the outgoing card's own cost, so this check must match that.
        elif (isinstance(event.card, AVGECharacterCard) and event.deck_from.deck_type == DeckType.BENCH and event.deck_to.deck_type == DeckType.ACTIVE_CARD and len((active := self.env.get_player_active(event.card.owner)).energy_tokens) < active.retreat_cost):
            return _reject(event, "Your active character doesn't have enough energy attached to retreat.")
        # No server-side cap existed at all before this - the frontend's own noExistingTool guard
        # (useGestureLegality.ts) was the only thing preventing a second tool attach, which a raw
        # client request could always bypass.
        elif (event.deck_to.deck_type == DeckType.OFFHAND and len(event.deck_to) > 0):
            return _reject(event, "That character already has a tool attached.")
        else:
            return ResponseStatus.REGULATE_PASS


class AVGERetreatCostReactor(AVGEEventReactor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_3)
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, TransferCard) and \
            not callable(event.deck_from) and \
                not callable(event.deck_to) and \
                    event.id.calling_action == ActionTypes.PLAYER_CHOICE and \
                        isinstance(event.card, AVGECharacterCard) and \
                            event.deck_to.deck_type == DeckType.BENCH and \
                                event.deck_from.deck_type == DeckType.ACTIVE_CARD

    async def react(self, event: Event):
        assert isinstance(event, TransferCard)
        assert isinstance(event.card, AVGECharacterCard)
        event.push_event([AVGEEnergyTransfer(
            AVGEEngineID(None, ActionTypes.ENV, None),
            event.card,
            self.env,
            self.env
        ) for _ in range(event.card.retreat_cost)])


class AVGEStadiumReplaceReactor(AVGEEventReactor):
    '''Playing a new stadium replaces whichever one is already in play, discarding the outgoing
    one to its own owner's discard pile - the same thing BAIEmail's bespoke effect
    (catalog/items/BAIEmail.py) already does by hand, generalized here so every stadium-playing
    card gets it for free instead of every card having to reimplement it, and so a stadium can
    never simply stack with the previous one.

    EngineGroup.CORE (7) runs before INTERNAL_3 (8) - by the time this reactor fires, the
    triggering TransferCard's own act() has already appended the new stadium to
    stadium_cardholder, so "was one already there" means len() > 1 here, not > 0, and the card to
    discard is index 0 (the original occupant), not whichever one is newest.'''
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_3)

    def match(self, event: Event) -> bool:
        return isinstance(event, TransferCard) and \
            not callable(event.deck_to) and \
                event.id.calling_action == ActionTypes.PLAYER_CHOICE and \
                    event.deck_to.deck_type == DeckType.STADIUM and \
                        len(self.env.stadium_cardholder) > 1

    async def react(self, event: Event):
        outgoing = self.env.stadium_cardholder.cards_holding[0]
        assert isinstance(outgoing, AVGEStadiumCard)
        discard_owner = self.env.players[outgoing.owner]
        event.push_event([TransferCard(
            AVGEEngineID(None, ActionTypes.ENV, None),
            outgoing,
            self.env.stadium_cardholder,
            discard_owner.card_piles[DeckType.DISCARD],
            self.env,
        )])


class AVGEPlayCharacterCardValidityCheck(AVGEEventRegulator):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_1)
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, PlayCharacterCard)

    async def respond(self, event: Event) -> ResponseStatus:
        assert(isinstance(event, PlayCharacterCard))
        assert not callable(event.target_card)
        assert not callable(event.cost)
        if(event.cost > len(event.target_card.energy_tokens)):
            return _reject(event, "Not enough energy attached to use that.")
        match event.action:
            case ActionTypes.ATK_1:
                if(event.target_card.attacks.get(ActionTypes.ATK_1) is None):
                    return _reject(event, "That character doesn't have this attack.")
            case ActionTypes.ATK_2:
                if(event.target_card.attacks.get(ActionTypes.ATK_2) is None):
                    return _reject(event, "That character doesn't have this attack.")
            case ActionTypes.PASSIVE:
                if(event.target_card.abilities.get(ActionTypes.PASSIVE) is None):
                    return _reject(event, "That character doesn't have this ability.")
            case ActionTypes.ACTIVATE_ABILITY:
                if(event.target_card.abilities.get(ActionTypes.ACTIVATE_ABILITY, None) is None
                   or not event.target_card.abilities[ActionTypes.ACTIVATE_ABILITY].can_play(event.target_card)):
                    return _reject(event, "That ability can't be used right now.")
            case _:
                raise Exception("No clue how you got here...")
        return ResponseStatus.REGULATE_PASS
        


class AVGEPlayNonCharacterCardValidityCheck(AVGEEventRegulator):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_1)
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, PlayNonCharacterCard) and isinstance(event.target_card, AVGESupporterCard) and event.id.calling_action == ActionTypes.PLAYER_CHOICE

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, PlayNonCharacterCard) and isinstance(event.target_card, AVGESupporterCard)
        if(self.env.players[event.target_card.owner].attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] == 0):
            return _reject(event, "You've already played a supporter card this turn.")
        return ResponseStatus.REGULATE_PASS
