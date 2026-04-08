from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class StandardMusescoreFile(AVGEItemCard):
    _TOOL_DISCARD_TARGET_KEY = "standardmusescorefile_tool_discard_target"
    _DECK_NONITEM_PICK_KEY = "standardmusescorefile_deck_nonitem_pick"

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
            return card.generate_response(ResponseType.FAST_FORWARD, {MESSAGE_KEY: "No tools to discard for StandardMusescoreFile."})

        chosen_tool_target = card.env.cache.get(card, StandardMusescoreFile._TOOL_DISCARD_TARGET_KEY, None)
        if(chosen_tool_target is None):
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [StandardMusescoreFile._TOOL_DISCARD_TARGET_KEY],
                            InputType.DETERMINISTIC,
                            lambda res : True,
                            ActionTypes.NONCHAR,
                            card,
                            {
                                "query_label": "standard_musescore_file_tool_discard_target",
                                "targets": tool_targets,
                                "display": player.get_cards_in_play()
                            },
                        )
                    ]
                },
            )

        packet : PacketType = []
        assert(isinstance(chosen_tool_target, AVGECharacterCard))
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

        non_item_choices = [c for c in deck if not isinstance(c, AVGEItemCard)]
        missing = object()
        deck_pick = card.env.cache.get(card, StandardMusescoreFile._DECK_NONITEM_PICK_KEY, missing, one_look=True)
        if(deck_pick is missing):
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [StandardMusescoreFile._DECK_NONITEM_PICK_KEY],
                            InputType.SELECTION,
                            lambda res: True,
                            ActionTypes.NONCHAR,
                            card,
                            {
                                "query_label": "standard_musescore_file_nonitem_pick",
                                "targets": non_item_choices,
                                "display": list(deck),
                                "allow_none": True
                            },
                        )
                    ]
                },
            )
        if deck_pick is not None:
            packet.append(
                TransferCard(
                    deck_pick,
                    deck,
                    hand,
                    ActionTypes.NONCHAR,
                    card,
                )
            )

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, StandardMusescoreFile)))

        return card.generate_response()
