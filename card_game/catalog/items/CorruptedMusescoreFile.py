from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


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
            return card.generate_response(ResponseType.FAST_FORWARD, {"msg": "No tools to discard for CorruptedMusescoreFile."})

        def _tool_target_valid(result) -> bool:
            if(len(result) != 1):
                return False
            chosen = result[0]
            return isinstance(chosen, AVGECharacterCard) and chosen in tool_targets

        chosen_tool_target = card.env.cache.get(card, CorruptedMusescoreFile._TOOL_DISCARD_TARGET_KEY, None)
        if(chosen_tool_target is None):
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [CorruptedMusescoreFile._TOOL_DISCARD_TARGET_KEY],
                            InputType.DETERMINISTIC,
                            _tool_target_valid,
                            ActionTypes.NONCHAR,
                            card,
                            {
                                "query_label": "corrupted_musescore_file_tool_discard_target",
                                "targets": tool_targets,
                            },
                        )
                    ]
                },
            )

        packet = []
        if(chosen_tool_target not in tool_targets or len(chosen_tool_target.tools_attached) == 0):
            return card.generate_response(ResponseType.SKIP, {"msg": "Selected tool target is no longer valid."})
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
        if(len(item_choices) > 0):
            def _deck_pick_valid(result) -> bool:
                if(len(result) != 1):
                    return False
                chosen = result[0]
                return chosen in item_choices

            deck_pick = card.env.cache.get(card, CorruptedMusescoreFile._DECK_ITEM_PICK_KEY, None, one_look=True)
            if(deck_pick is None):
                return card.generate_response(
                    ResponseType.INTERRUPT,
                    {
                        INTERRUPT_KEY: [
                            InputEvent(
                                player,
                                [CorruptedMusescoreFile._DECK_ITEM_PICK_KEY],
                                InputType.DETERMINISTIC,
                                _deck_pick_valid,
                                ActionTypes.NONCHAR,
                                card,
                                {
                                    "query_label": "corrupted_musescore_file_item_pick",
                                    "targets": item_choices,
                                },
                            )
                        ]
                    },
                )
            packet.append(
                TransferCard(
                    deck_pick,
                    deck,
                    hand,
                    ActionTypes.NONCHAR,
                    card,
                )
            )

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, CorruptedMusescoreFile)))

        return card.generate_response()
