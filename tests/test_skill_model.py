"""Tests for the skill-based ranking model."""

import pytest
from src.pipelines.skill_model import (
    compute_team_strength,
    split_train_test,
    build_player_index,
    predict_winner,
)


def test_compute_team_strength_equal_skills():
    """When skills are equal, team strength = (a + b) * skill."""
    result = compute_team_strength(10.0, 10.0, 1.0, 0.5)
    assert result == 15.0  # 1.0 * 10 + 0.5 * 10


def test_compute_team_strength_different_skills():
    """Stronger player weighted by a, weaker by b."""
    result = compute_team_strength(20.0, 10.0, 1.0, 0.5)
    assert result == 25.0  # 1.0 * 20 + 0.5 * 10


def test_compute_team_strength_symmetric():
    """Order of players shouldn't matter."""
    r1 = compute_team_strength(20.0, 10.0, 1.0, 0.5)
    r2 = compute_team_strength(10.0, 20.0, 1.0, 0.5)
    assert r1 == r2


def test_compute_team_strength_both_coefficients_same():
    """When a == b, team strength is just (a+b) * average skill."""
    # t = a * max + b * min = 1.0 * 20 + 1.0 * 10 = 30
    result = compute_team_strength(20.0, 10.0, 1.0, 1.0)
    assert result == 30.0


def test_compute_team_strength_with_c_term():
    """c term adds weight based on skill gap."""
    # t = a * max + b * min + c * abs(s_i - s_j)
    # t = 1.0 * 20 + 0.5 * 10 + 0.25 * |20 - 10| = 20 + 5 + 2.5 = 27.5
    result = compute_team_strength(20.0, 10.0, 1.0, 0.5, 0.25)
    assert result == 27.5


def test_compute_team_strength_c_zero_when_equal():
    """c term contributes nothing when skills are equal."""
    # t = 1.0 * 10 + 0.5 * 10 + 0.5 * |10 - 10| = 10 + 5 + 0 = 15
    result = compute_team_strength(10.0, 10.0, 1.0, 0.5, 0.5)
    assert result == 15.0


def test_split_train_test():
    """October and November go to test set."""
    sets = [
        {'tournament_month': 1},
        {'tournament_month': 5},
        {'tournament_month': 10},
        {'tournament_month': 11},
        {'tournament_month': 12},
    ]
    train, test = split_train_test(sets)
    assert len(train) == 3
    assert len(test) == 2
    assert all(s['tournament_month'] in {10, 11} for s in test)
    assert all(s['tournament_month'] not in {10, 11} for s in train)


def test_split_train_test_empty_test():
    """Handle case where no Oct/Nov data exists."""
    sets = [
        {'tournament_month': 1},
        {'tournament_month': 5},
        {'tournament_month': 9},
    ]
    train, test = split_train_test(sets)
    assert len(train) == 3
    assert len(test) == 0


def test_build_player_index():
    """Player index includes all unique players."""
    sets = [
        {'team1_player1': 1, 'team1_player2': 2,
         'team2_player1': 3, 'team2_player2': 4},
        {'team1_player1': 1, 'team1_player2': 5,
         'team2_player1': 2, 'team2_player2': 3},
    ]
    player_to_idx, idx_to_player = build_player_index(sets)
    assert len(player_to_idx) == 5
    assert set(player_to_idx.keys()) == {1, 2, 3, 4, 5}
    # Check inverse mapping
    for pid, idx in player_to_idx.items():
        assert idx_to_player[idx] == pid


def test_build_player_index_consistent_indices():
    """Player indices should be consistent (sorted by player ID)."""
    sets = [
        {'team1_player1': 100, 'team1_player2': 50,
         'team2_player1': 75, 'team2_player2': 25},
    ]
    player_to_idx, _ = build_player_index(sets)
    # Should be sorted: 25->0, 50->1, 75->2, 100->3
    assert player_to_idx[25] == 0
    assert player_to_idx[50] == 1
    assert player_to_idx[75] == 2
    assert player_to_idx[100] == 3


def test_predict_winner_stronger_team():
    """Higher skill team should be predicted to win."""
    set_data = {
        'team1_player1': 1, 'team1_player2': 2,
        'team2_player1': 3, 'team2_player2': 4,
    }
    # Team 1 has higher skills
    skills = {1: 10.0, 2: 10.0, 3: 5.0, 4: 5.0}
    predicted = predict_winner(set_data, a=1.0, b=0.5, c=0.0, skills=skills)
    assert predicted == 1


def test_predict_winner_weaker_team():
    """Lower skill team should be predicted to lose."""
    set_data = {
        'team1_player1': 1, 'team1_player2': 2,
        'team2_player1': 3, 'team2_player2': 4,
    }
    # Team 2 has higher skills
    skills = {1: 5.0, 2: 5.0, 3: 10.0, 4: 10.0}
    predicted = predict_winner(set_data, a=1.0, b=0.5, c=0.0, skills=skills)
    assert predicted == 2


def test_predict_winner_equal_teams():
    """Equal teams should predict team 1 (tie goes to team 1)."""
    set_data = {
        'team1_player1': 1, 'team1_player2': 2,
        'team2_player1': 3, 'team2_player2': 4,
    }
    skills = {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}
    predicted = predict_winner(set_data, a=1.0, b=0.5, c=0.0, skills=skills)
    assert predicted == 1  # Tie goes to team 1


def test_predict_winner_missing_player_defaults_to_zero():
    """Unknown players should default to skill of 0."""
    set_data = {
        'team1_player1': 1, 'team1_player2': 2,
        'team2_player1': 3, 'team2_player2': 4,
    }
    # Only team 1 players have known skills (positive)
    # Team 2 players will default to 0
    skills = {1: 10.0, 2: 10.0}
    predicted = predict_winner(set_data, a=1.0, b=1.0, c=0.0, skills=skills)
    # Team 1: 1.0*10 + 1.0*10 = 20
    # Team 2: 1.0*0 + 1.0*0 = 0
    assert predicted == 1
