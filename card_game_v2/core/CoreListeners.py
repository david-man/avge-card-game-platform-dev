from ..avge_abstracts.AVGEEventListener import *
from ..avge_abstracts.AVGECard import *
from .EventCatalog import *
from ..constants import ResponseStatus
from ..engine.event import Event


class AVGETokenTransferCheck(AVGEEventRegulator):
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, AVGEEnergyTransfer)

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, AVGEEnergyTransfer)
        assert not callable(event.token_from)
        if (len(event.token_from.energy_tokens) == 0):
            return ResponseStatus.REGULATE_FAIL
        if (event.id.action_type == ActionTypes.PLAYER_CHOICE):
            if (isinstance(event.token_to, AVGECharacterCard)):
                if (self.env.players[event.token_to.owner].attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] == 0):
                    return ResponseStatus.REGULATE_FAIL
        return ResponseStatus.REGULATE_PASS


class AVGEHPChangeCheck(AVGEEventRegulator):
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, AVGECardHPChangeEvent)

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, AVGECardHPChangeEvent)
        assert not callable(event.target_card)
        if (event.target_card.deck_type not in [DeckType.BENCH, DeckType.ACTIVE_CARD] and event.id.action_type != ActionTypes.ENV):
            return ResponseStatus.REGULATE_IGNORE
        return ResponseStatus.REGULATE_PASS


class AVGEHPChangeReactor(AVGEEventReactor):
    def match(self, event: Event) -> bool:
        return isinstance(event, AVGECardHPChangeEvent)

    async def react(self, event: Event):
        assert isinstance(event, AVGECardHPChangeEvent)
        assert not callable(event.target_card)
        if (event.target_card.hp <= 0 and event.id.action_type != ActionTypes.ENV):
            player = self.env.players[event.target_card.owner]
            opponent = self.env.get_opponent(event.target_card.owner)
            ko_increment = AVGEPlayerAttributeChange(
                AVGEEngineID(self.env, ActionTypes.ENV, None),
                opponent,
                AVGEPlayerAttribute.KO_COUNT,
                AVGEAttributeModifier.ADDITIVE,
                1,
                self.env
            )
            transfer_card_out = TransferCard(
                AVGEEngineID(self.env, ActionTypes.ENV, None),
                event.target_card,
                player.card_piles[DeckType.DISCARD],
                player.card_piles[event.target_card.deck_type],
                self.env
            )

            if (opponent.attributes[AVGEPlayerAttribute.KO_COUNT] < KOS_TO_WIN - 1):
                # if the opponent still has a chance
                if (event.target_card.deck_type == DeckType.ACTIVE_CARD):
                    if (len(player.card_piles[DeckType.BENCH]) == 0):
                        event.push_event([ko_increment, GameEnd(
                            AVGEEngineID(self.env, ActionTypes.ENV, None),
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
                        ))
                        new_card = resp[0]
                        assert isinstance(new_card, AVGECharacterCard)
                        transfer_card_in = TransferCard(
                            AVGEEngineID(self.env, ActionTypes.ENV, None),
                            event.target_card,
                            player.card_piles[new_card.deck_type],
                            player.card_piles[DeckType.ACTIVE_CARD],
                            self.env
                        )
                        event.push_event([
                            ko_increment,
                            transfer_card_in,
                            transfer_card_out
                        ])
                else:
                    event.push_event([
                        ko_increment,
                        transfer_card_out
                    ])
            else:
                event.push_event([
                    ko_increment
                ])


class AVGEWeaknessModifier(AVGEEventModifier):
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, AVGECardHPChangeEvent)

    async def modify(self, event: Event):
        assert isinstance(event, AVGECardHPChangeEvent)
        assert not callable(event.target_card)
        assert not callable(event.magnitude)
        if (type_weaknesses[event.target_card.card_type] == event.change_type and isinstance(event.id.caller, AVGECharacterCard) and event.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            res = await self.env.report(CoinflipData(event.id.caller.owner,
                                                     "Critical! Flip a coin and get heads to double the damage!"))
            if (res == 1):
                event.modify_magnitude(event.magnitude)
                event.is_crit = True


class AVGEPlayerAttributeChangeReactor(AVGEEventReactor):
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, AVGEPlayerAttributeChange)

    async def react(self, event: Event):
        assert isinstance(event, AVGEPlayerAttributeChange)
        assert not callable(event.player)
        if (event.attribute == AVGEPlayerAttribute.KO_COUNT):
            if (event.player.attributes[AVGEPlayerAttribute.KO_COUNT] == 3):
                event.push_event(
                    GameEnd(
                        AVGEEngineID(self.env, ActionTypes.ENV, None),
                        event.player.id,
                        WinReasons.ALL_KOS,
                        self.env
                    )
                )
                return ResponseStatus.REACTOR_SKIP


class AVGETransferValidityCheck(AVGEEventRegulator):
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, TransferCard) and event.id.action_type == ActionTypes.PLAYER_CHOICE

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, TransferCard)
        assert not callable(event.deck_from)
        assert not callable(event.card)
        assert not callable(event.deck_to)
        if (event.deck_from.deck_type == DeckType.HAND and event.deck_to.deck_type == DeckType.DECK and len(event.deck_to) == MAX_BENCH_SIZE):
            return ResponseStatus.REGULATE_FAIL
        elif (event.deck_from.deck_type == DeckType.BENCH and event.deck_to.deck_type == DeckType.ACTIVE_CARD and self.env.players[event.card.owner].attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] == 0):
            return ResponseStatus.REGULATE_FAIL
        elif (isinstance(event.card, AVGECharacterCard) and event.deck_from.deck_type == DeckType.BENCH and event.deck_to.deck_type == DeckType.ACTIVE_CARD and len(self.env.get_player_active(event.card.owner).energy_tokens) < event.card.retreat_cost):
            return ResponseStatus.REGULATE_FAIL
        else:
            return ResponseStatus.REGULATE_PASS


class AVGERetreatCostReactor(AVGEEventReactor):
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, TransferCard) and \
            not callable(event.deck_from) and \
                not callable(event.deck_to) and \
                    event.id.action_type == ActionTypes.PLAYER_CHOICE and \
                        isinstance(event.card, AVGECharacterCard) and \
                            event.deck_to.deck_type == DeckType.BENCH and \
                                event.deck_from.deck_type == DeckType.ACTIVE_CARD

    async def react(self, event: Event):
        assert isinstance(event, TransferCard)
        assert isinstance(event.card, AVGECharacterCard)
        event.push_event([AVGEEnergyTransfer(
            AVGEEngineID(self.env, ActionTypes.ENV, None),
            event.card,
            self.env,
            self.env
        ) for _ in range(event.card.retreat_cost)])


class AVGEPlayCharacterCardValidityCheck(AVGEEventRegulator):
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, PlayCharacterCard)

    async def respond(self, event: Event) -> ResponseStatus:
        assert(isinstance(event, PlayCharacterCard))
        assert not callable(event.target_card)
        assert not callable(event.cost)
        if(event.cost > len(event.target_card.energy_tokens)):
            return ResponseStatus.REGULATE_FAIL
        match event.action:
            case ActionTypes.ATK_1:
                if(event.target_card.attacks.get(ActionTypes.ATK_1) is None):
                    return ResponseStatus.REGULATE_FAIL
            case ActionTypes.ATK_2:
                if(event.target_card.attacks.get(ActionTypes.ATK_2) is None):
                    return ResponseStatus.REGULATE_FAIL
            case ActionTypes.PASSIVE:
                if(event.target_card.abilities.get(ActionTypes.PASSIVE) is None):
                    return ResponseStatus.REGULATE_FAIL
            case ActionTypes.ACTIVATE_ABILITY:
                if(event.target_card.abilities.get(ActionTypes.ACTIVATE_ABILITY, None) is None
                   or not event.target_card.abilities[ActionTypes.ACTIVATE_ABILITY].can_play(event.target_card)):
                    return ResponseStatus.REGULATE_FAIL
            case _:
                raise Exception("No clue how you got here...")
        return ResponseStatus.REGULATE_PASS
        


class AVGEPlayNonCharacterCardValidityCheck(AVGEEventRegulator):
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        return isinstance(event, PlayNonCharacterCard) and isinstance(event.target_card, AVGESupporterCard) and event.id.action_type == ActionTypes.PLAYER_CHOICE

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, PlayNonCharacterCard) and isinstance(event.target_card, AVGESupporterCard)
        if(self.env.players[event.target_card.owner].attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] == 0):
            return ResponseStatus.REGULATE_FAIL
        return ResponseStatus.REGULATE_PASS
