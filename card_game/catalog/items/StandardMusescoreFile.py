from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard

class StandardMusescoreFile(AVGEItemCard):
    _TOOL_DISCARD_TARGET_KEY = 'standardmusescorefile_tool_discard_target'
    _DECK_NONITEM_PICK_KEY = 'standardmusescorefile_deck_nonitem_pick'

    def __init__(self, unique_id):
        super().__init__(unique_id)

    def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:

        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]
        discard = player.cardholders[Pile.DISCARD]

        tool_targets = [c for c in player.get_cards_in_play() if isinstance(c, AVGECharacterCard) and len(c.tools_attached) > 0]

        missing = object()
        source_probe = card.env.cache.get(card, StandardMusescoreFile._TOOL_DISCARD_TARGET_KEY, missing, False)
        if source_probe is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                    InputEvent(
                        player,
                        [StandardMusescoreFile._TOOL_DISCARD_TARGET_KEY],
                        lambda res: True,
                        ActionTypes.NONCHAR,
                        card,
                        CardSelectionQuery(
                            'Standard Musescore File: Choose a character with a tool to discard (or None).',
                            tool_targets,
                            player.get_cards_in_play(),
                            True,
                            False,
                        )
                    )
                ]),
            )

        if source_probe is None:
            card.env.cache.get(card, StandardMusescoreFile._TOOL_DISCARD_TARGET_KEY, None, True)
            return self.generic_response(card)

        if not isinstance(source_probe, AVGECharacterCard) or source_probe not in tool_targets:
            raise Exception('StandardMusescoreFile: Invalid tool source selection')

        tool_to_discard = list(source_probe.tools_attached)[0]
        packet: PacketType = [
            TransferCard(
                tool_to_discard,
                tool_to_discard.cardholder,
                discard,
                ActionTypes.NONCHAR,
                card,
                None,
            )
        ]

        non_item_choices = [c for c in deck if not isinstance(c, AVGEItemCard)]
        deck_pick_probe = card.env.cache.get(card, StandardMusescoreFile._DECK_NONITEM_PICK_KEY, missing, False)
        if deck_pick_probe is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                    InputEvent(
                        player,
                        [StandardMusescoreFile._DECK_NONITEM_PICK_KEY],
                        lambda res: True,
                        ActionTypes.NONCHAR,
                        card,
                        CardSelectionQuery(
                            'Standard Musescore File: Choose a non-item card from your deck to put into your hand (or None).',
                            non_item_choices,
                            list(deck),
                            True,
                            False,
                        )
                    )
                ]),
            )

        if deck_pick_probe is not None:
            if not isinstance(deck_pick_probe, AVGECard) or deck_pick_probe not in non_item_choices:
                raise Exception('StandardMusescoreFile: Invalid deck non-item selection')
            packet.append(
                TransferCard(
                    deck_pick_probe,
                    deck,
                    hand,
                    ActionTypes.NONCHAR,
                    card,
                    None,
                )
            )

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, StandardMusescoreFile)))

        return self.generic_response(card)
