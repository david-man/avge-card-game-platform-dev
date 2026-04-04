from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class StandardMusescoreFile(AVGEItemCard):
    _TOOL_DISCARD_TARGET_KEY = "standardmusescorefile_tool_discard_target"
    _DECK_NONITEM_PICK_KEY = "standardmusescorefile_deck_nonitem_pick"

    def __init__(self, unique_id):
        super().__init__(unique_id)

    
    
    @staticmethod
    def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
        from card_game.internal_events import InputEvent, TransferCard

        player = card_for.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]
        discard = player.cardholders[Pile.DISCARD]

        tool_targets = [c for c in player.get_cards_in_play() if len(c.tools_attached) > 0]
        if(len(tool_targets) == 0):
            return card_for.generate_response(ResponseType.FAST_FORWARD, {"msg": "No tools to discard for StandardMusescoreFile."})

        def _tool_target_valid(result) -> bool:
            if(len(result) != 1):
                return False
            chosen = result[0]
            return isinstance(chosen, AVGECharacterCard) and chosen in tool_targets

        chosen_tool_target = card_for.env.cache.get(card_for, StandardMusescoreFile._TOOL_DISCARD_TARGET_KEY, None)
        if(chosen_tool_target is None):
            return card_for.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [StandardMusescoreFile._TOOL_DISCARD_TARGET_KEY],
                            InputType.DETERMINISTIC,
                            _tool_target_valid,
                            ActionTypes.NONCHAR,
                            card_for,
                            {
                                "query_label": "standard_musescore_file_tool_discard_target",
                                "targets": tool_targets,
                            },
                        )
                    ]
                },
            )

        packet = []
        if(chosen_tool_target not in tool_targets or len(chosen_tool_target.tools_attached) == 0):
            return card_for.generate_response(ResponseType.SKIP, {"msg": "Selected tool target is no longer valid."})
        tool_to_discard = list(chosen_tool_target.tools_attached)[0]
        packet.append(
            TransferCard(
                tool_to_discard,
                chosen_tool_target.tools_attached,
                discard,
                ActionTypes.NONCHAR,
                card_for,
            )
        )

        non_item_choices = [c for c in deck if not isinstance(c, AVGEItemCard)]
        if(len(non_item_choices) > 0):
            def _deck_pick_valid(result) -> bool:
                if(len(result) != 1):
                    return False
                chosen = result[0]
                return chosen in non_item_choices

            deck_pick = card_for.env.cache.get(card_for, StandardMusescoreFile._DECK_NONITEM_PICK_KEY, None, one_look=True)
            if(deck_pick is None):
                return card_for.generate_response(
                    ResponseType.INTERRUPT,
                    {
                        INTERRUPT_KEY: [
                            InputEvent(
                                player,
                                [StandardMusescoreFile._DECK_NONITEM_PICK_KEY],
                                InputType.DETERMINISTIC,
                                _deck_pick_valid,
                                ActionTypes.NONCHAR,
                                card_for,
                                {
                                    "query_label": "standard_musescore_file_nonitem_pick",
                                    "targets": non_item_choices,
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
                    card_for,
                )
            )

        card_for.propose(packet)

        return card_for.generate_response()
