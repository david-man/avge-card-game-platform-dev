from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class CorruptedMusescoreFile(AVGEItemCard):
    _TOOL_DISCARD_TARGET_KEY = "corruptedmusescorefile_tool_discard_target"
    _DECK_ITEM_PICK_KEY = "corruptedmusescorefile_deck_item_pick"

    def __init__(self, unique_id):
        super().__init__(unique_id)
    @staticmethod
    def play_card(card) -> Response:
        from card_game.internal_events import InputEvent, TransferCard

        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]
        discard = player.cardholders[Pile.DISCARD]

        tool_targets = [c for c in player.get_cards_in_play() if len(c.tools_attached) > 0]
        if(len(tool_targets) == 0):
            return card.generate_response(data={MESSAGE_KEY: "No cards with tools!"})
        packet : PacketType = []
        chosen_tool_target = card.env.cache.get(card, CorruptedMusescoreFile._TOOL_DISCARD_TARGET_KEY, None)
        if(chosen_tool_target is None):
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [CorruptedMusescoreFile._TOOL_DISCARD_TARGET_KEY],
                            InputType.SELECTION,
                            lambda res : True,
                            ActionTypes.NONCHAR,
                            card,
                            {
                                LABEL_FLAG: "corrupted_musescore_file_tool_discard_target",
                                TARGETS_FLAG: tool_targets,
                                DISPLAY_FLAG: player.get_cards_in_play()
                            },
                        )
                    ]
                },
            )
        assert isinstance(chosen_tool_target, AVGECharacterCard)
        tool_to_discard = list(chosen_tool_target.tools_attached)[0]
        packet.append(
            TransferCard(
                tool_to_discard,
                chosen_tool_target.tools_attached,
                discard,
                ActionTypes.NONCHAR,
                card,
            )
        )

        item_choices = [c for c in deck if isinstance(c, AVGEItemCard)]
        missing = object()
        deck_pick = card.env.cache.get(card, CorruptedMusescoreFile._DECK_ITEM_PICK_KEY, missing, one_look=True)
        if(deck_pick is missing):
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [CorruptedMusescoreFile._DECK_ITEM_PICK_KEY],
                            InputType.SELECTION,
                            lambda res : True,
                            ActionTypes.NONCHAR,
                            card,
                            {
                                LABEL_FLAG: "corrupted_musescore_file_item_pick",
                                TARGETS_FLAG: item_choices,
                                DISPLAY_FLAG: list(deck),
                                ALLOW_NONE: True
                            },
                        )
                    ]
                },
            )
        if(deck_pick is not None):
            packet.append(
                TransferCard(
                    deck_pick,
                    deck,
                    hand,
                    ActionTypes.NONCHAR,
                    card,
                )
            )
        if(len(packet)>0):
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, CorruptedMusescoreFile)))
        card.env.cache.delete(card, CorruptedMusescoreFile._TOOL_DISCARD_TARGET_KEY)

        return card.generate_response()
