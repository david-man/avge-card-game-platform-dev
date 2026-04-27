from card_game.server.server_models import MultiplayerTransportState


def test_assign_slot_reconnect_token_takeover_rebinds_active_slot() -> None:
    transport_state = MultiplayerTransportState()

    initial_session = transport_state.assign_slot('sid-old', requested_slot='p2', reconnect_token=None)
    assert initial_session is not None

    initial_session.last_ack = 5
    initial_session.next_seq = 9
    initial_session.environment_initialized = True

    rebound_session = transport_state.assign_slot(
        'sid-new',
        requested_slot='p2',
        reconnect_token=initial_session.reconnect_token,
    )

    assert rebound_session is initial_session
    assert rebound_session.sid == 'sid-new'
    assert rebound_session.slot == 'p2'
    assert rebound_session.connected is True
    assert rebound_session.disconnected_at is None

    # Session sequencing and ack watermark should survive reconnect takeover.
    assert rebound_session.last_ack == 5
    assert rebound_session.next_seq == 9

    assert transport_state.sid_by_slot['p2'] == 'sid-new'
    assert transport_state.session_by_sid.get('sid-old') is None
    assert transport_state.reserved_session_by_slot['p2'] is None
