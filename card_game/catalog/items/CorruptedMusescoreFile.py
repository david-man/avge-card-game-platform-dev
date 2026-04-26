from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard

class CorruptedMusescoreFile(AVGEItemCard):
    _TOOL_SOURCE_KEY = 'corruptedmusescorefile_tool_source'
    _TOOL_PICK_KEY = 'corruptedmusescorefile_tool_pick'
    _DECK_ITEM_PICK_KEY = 'corruptedmusescorefile_deck_item_pick'

    def __init__(self, unique_id):
        super().__init__(unique_id)

    def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:

        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]
        discard = player.cardholders[Pile.DISCARD]

        tool_targets = [c for c in player.get_cards_in_play() if isinstance(c, AVGECharacterCard) and len(c.tools_attached) > 0]

        missing = object()
        source_probe = card.env.cache.get(card, CorruptedMusescoreFile._TOOL_SOURCE_KEY, missing, False)
        if source_probe is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            player,
                            [CorruptedMusescoreFile._TOOL_SOURCE_KEY],
                            lambda res: True,
                            ActionTypes.NONCHAR,
                            card,
                            CardSelectionQuery(
                                'Corrupted Musescore File: Choose one of your characters with a tool attached.',
                                tool_targets,
                                player.get_cards_in_play(),
                                True,
                                False,
                            )
                        )
                    ]),
            )

        if source_probe is None:
            card.env.cache.get(card, CorruptedMusescoreFile._TOOL_SOURCE_KEY, None, True)
            return self.generic_response(card)

        if not isinstance(source_probe, AVGECharacterCard) or source_probe not in tool_targets:
            raise Exception('CorruptedMusescoreFile: Invalid tool source selection')

        tool_choice = list(source_probe.tools_attached)[0]

        item_choices = [c for c in deck if isinstance(c, AVGEItemCard)]
        if len(item_choices) > 0:
            deck_pick_probe = card.env.cache.get(card, CorruptedMusescoreFile._DECK_ITEM_PICK_KEY, missing, False)
            if deck_pick_probe is missing:
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[AVGEEvent]([
                            InputEvent(
                                player,
                                [CorruptedMusescoreFile._DECK_ITEM_PICK_KEY],
                                lambda res: True,
                                ActionTypes.NONCHAR,
                                card,
                                CardSelectionQuery(
                                    'Corrupted Musescore File: Choose an item from your deck to put into your hand.',
                                    item_choices,
                                    list(deck),
                                    False,
                                    False,
                                )
                            )
                        ]),
                )
        chosen_item = card.env.cache.get(card, CorruptedMusescoreFile._DECK_ITEM_PICK_KEY, None, True) if len(item_choices) > 0 else None

        packet: PacketType = [
            TransferCard(
                tool_choice,
                tool_choice.cardholder,
                discard,
                ActionTypes.NONCHAR,
                card,
                None,
            )
        ]

        if len(item_choices) > 0:
            if not isinstance(chosen_item, AVGEItemCard) or chosen_item not in deck:
                raise Exception('CorruptedMusescoreFile: Deck item selection no longer valid')
            packet.append(
                TransferCard(
                    chosen_item,
                    deck,
                    hand,
                    ActionTypes.NONCHAR,
                    card,
                    None,
                )
            )

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, CorruptedMusescoreFile)))
        return self.generic_response(card)
