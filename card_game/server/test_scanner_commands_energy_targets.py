from __future__ import annotations

from card_game.server.scanner_commands import normalize_scanner_command


def test_mv_energy_legacy_p1_energy_normalizes_to_shared_energy() -> None:
    action, normalized = normalize_scanner_command('mv-energy ENERGY-1 p1-energy')

    assert action == 'mv-energy'
    assert normalized == 'mv-energy ENERGY-1 shared-energy'


def test_mv_energy_legacy_p2_energy_normalizes_to_shared_energy() -> None:
    action, normalized = normalize_scanner_command('mv-energy ENERGY-1 p2-energy')

    assert action == 'mv-energy'
    assert normalized == 'mv-energy ENERGY-1 shared-energy'


def test_mv_energy_accepts_shared_energy_target() -> None:
    action, normalized = normalize_scanner_command('mv-energy ENERGY-1 shared-energy')

    assert action == 'mv-energy'
    assert normalized == 'mv-energy ENERGY-1 shared-energy'
