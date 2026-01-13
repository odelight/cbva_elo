import sys
sys.path.insert(0, '.')

from src.calculate_elo import (
    calculate_expected,
    update_elo,
    get_team_elo,
    process_set,
    parse_results_file,
    calculate_all_elos,
    DEFAULT_ELO,
    K_FACTOR,
)
import tempfile
import os


def test_calculate_expected_equal_elos():
    """Equal ELOs should give 0.5 expected score."""
    expected = calculate_expected(1500, 1500)
    assert abs(expected - 0.5) < 0.001


def test_calculate_expected_higher_elo_favored():
    """Higher rated team should have >0.5 expected score."""
    expected = calculate_expected(1600, 1400)
    assert expected > 0.5
    assert expected < 1.0


def test_calculate_expected_lower_elo_underdog():
    """Lower rated team should have <0.5 expected score."""
    expected = calculate_expected(1400, 1600)
    assert expected < 0.5
    assert expected > 0.0


def test_calculate_expected_symmetry():
    """Expected scores should sum to 1."""
    e1 = calculate_expected(1600, 1400)
    e2 = calculate_expected(1400, 1600)
    assert abs(e1 + e2 - 1.0) < 0.001


def test_update_elo_win_increases():
    """Winning should increase ELO."""
    new_elo = update_elo(1500, 0.5, 1)
    assert new_elo > 1500


def test_update_elo_loss_decreases():
    """Losing should decrease ELO."""
    new_elo = update_elo(1500, 0.5, 0)
    assert new_elo < 1500


def test_update_elo_expected_win():
    """Winning when expected gives small gain."""
    # When favored (expected=0.75), winning gives small increase
    new_elo = update_elo(1500, 0.75, 1)
    gain = new_elo - 1500
    assert 0 < gain < K_FACTOR / 2


def test_update_elo_upset_win():
    """Winning as underdog gives large gain."""
    # When underdog (expected=0.25), winning gives large increase
    new_elo = update_elo(1500, 0.25, 1)
    gain = new_elo - 1500
    assert gain > K_FACTOR / 2


def test_get_team_elo_average():
    """Team ELO should be average of both players."""
    elos = {'player1': 1600, 'player2': 1400}
    team_elo = get_team_elo(elos, 'player1', 'player2')
    assert team_elo == 1500


def test_process_set_winner_gains():
    """Winners should gain ELO after a set."""
    elos = {
        'winner1': DEFAULT_ELO,
        'winner2': DEFAULT_ELO,
        'loser1': DEFAULT_ELO,
        'loser2': DEFAULT_ELO,
    }
    process_set(elos, ('winner1', 'winner2'), ('loser1', 'loser2'), team1_won=True)

    assert elos['winner1'] > DEFAULT_ELO
    assert elos['winner2'] > DEFAULT_ELO
    assert elos['loser1'] < DEFAULT_ELO
    assert elos['loser2'] < DEFAULT_ELO


def test_process_set_zero_sum():
    """Total ELO change should be zero (what winners gain, losers lose)."""
    elos = {
        'winner1': DEFAULT_ELO,
        'winner2': DEFAULT_ELO,
        'loser1': DEFAULT_ELO,
        'loser2': DEFAULT_ELO,
    }
    initial_total = sum(elos.values())
    process_set(elos, ('winner1', 'winner2'), ('loser1', 'loser2'), team1_won=True)
    final_total = sum(elos.values())

    # Should be approximately equal (within floating point tolerance)
    assert abs(initial_total - final_total) < 0.001


def test_parse_results_file():
    """Test parsing a results file."""
    content = """team1 player1 player2
opponent1 21-19 21-15

team2 player3 player4
team1 19-21 15-21
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        f.flush()
        filepath = f.name

    try:
        matches = parse_results_file(filepath)

        assert len(matches) == 2

        assert matches[0]['team_id'] == 'team1'
        assert matches[0]['players'] == ('player1', 'player2')
        assert len(matches[0]['games']) == 1
        assert matches[0]['games'][0]['opponent_team_id'] == 'opponent1'
        assert matches[0]['games'][0]['sets'] == [(21, 19), (21, 15)]

        assert matches[1]['team_id'] == 'team2'
        assert matches[1]['players'] == ('player3', 'player4')
    finally:
        os.unlink(filepath)


def test_calculate_all_elos_basic():
    """Test full ELO calculation with simple data."""
    content = """teamA playerA1 playerA2
teamB 21-10 21-10

teamB playerB1 playerB2
teamA 10-21 10-21
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        f.flush()
        filepath = f.name

    try:
        elos = calculate_all_elos(filepath)

        # All players should be present
        assert 'playerA1' in elos
        assert 'playerA2' in elos
        assert 'playerB1' in elos
        assert 'playerB2' in elos

        # Team A won both sets, should have higher ELO
        assert elos['playerA1'] > DEFAULT_ELO
        assert elos['playerA2'] > DEFAULT_ELO
        assert elos['playerB1'] < DEFAULT_ELO
        assert elos['playerB2'] < DEFAULT_ELO
    finally:
        os.unlink(filepath)


def test_calculate_all_elos_deduplication():
    """Test that duplicate matches are not double-counted."""
    # Same match from both perspectives
    content = """teamA playerA1 playerA2
teamB 21-10 21-10

teamB playerB1 playerB2
teamA 10-21 10-21
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        f.flush()
        filepath = f.name

    try:
        elos = calculate_all_elos(filepath)

        # With deduplication, the match should only be processed once
        # If processed twice, ELO changes would be larger
        # Winner gains ~16 per set (for equal opponents), ~32 for 2 sets
        # Without dedup it would be ~64
        gain = elos['playerA1'] - DEFAULT_ELO
        assert 20 < gain < 50  # Roughly 32 expected for 2 set wins
    finally:
        os.unlink(filepath)
