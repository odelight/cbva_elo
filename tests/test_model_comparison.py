"""Tests for the model comparison module."""

from src.pipelines.model_comparison import (
    split_train_test,
    get_training_players,
    evaluate_model,
    train_win_rate_model,
    predict_win_rate_model,
    train_score_margin_model,
    predict_score_margin_model,
    predict_skill_model,
    predict_elo_model,
    predict_bradley_terry,
)


def _make_set(t1p1, t1p2, t2p1, t2p2, t1_score, t2_score, month=5, year=2025):
    return {
        'set_id': 1,
        'team1_player1': t1p1, 'team1_player2': t1p2,
        'team2_player1': t2p1, 'team2_player2': t2p2,
        'team1_score': t1_score, 'team2_score': t2_score,
        'tournament_month': month, 'tournament_year': year,
    }


def test_split_train_test_oct_nov_2025():
    """Only Oct/Nov 2025 goes to test set."""
    sets = [
        _make_set(1, 2, 3, 4, 21, 19, month=10, year=2025),
        _make_set(1, 2, 3, 4, 21, 19, month=11, year=2025),
        _make_set(1, 2, 3, 4, 21, 19, month=10, year=2024),  # wrong year
        _make_set(1, 2, 3, 4, 21, 19, month=5, year=2025),   # wrong month
        _make_set(1, 2, 3, 4, 21, 19, month=12, year=2025),
    ]
    train, test = split_train_test(sets)
    assert len(test) == 2
    assert len(train) == 3
    assert all(s['tournament_month'] in {10, 11} and s['tournament_year'] == 2025 for s in test)


def test_get_training_players():
    """Training players includes all unique player IDs from training data."""
    sets = [
        _make_set(1, 2, 3, 4, 21, 19),
        _make_set(1, 5, 3, 6, 21, 19),
    ]
    players = get_training_players(sets)
    assert players == {1, 2, 3, 4, 5, 6}


def test_evaluate_model_excludes_unseen():
    """Sets with unseen players are excluded from evaluation."""
    test_sets = [
        _make_set(1, 2, 3, 4, 21, 19),
        _make_set(1, 2, 99, 4, 21, 19),  # player 99 unseen
    ]
    training_players = {1, 2, 3, 4}

    result = evaluate_model("test", lambda s: 1, test_sets, training_players)
    assert result['n_evaluated'] == 1
    assert result['n_excluded'] == 1


def test_win_rate_model():
    """Win rate model predicts based on player win percentages."""
    train = [
        _make_set(1, 2, 3, 4, 21, 19),  # team 1 wins
        _make_set(1, 2, 3, 4, 21, 15),  # team 1 wins
        _make_set(1, 2, 3, 4, 15, 21),  # team 2 wins
    ]
    model = train_win_rate_model(train)
    # Player 1: 2 wins, 1 loss = 0.667
    # Player 3: 1 win, 2 losses = 0.333
    assert abs(model['win_rates'][1] - 2/3) < 1e-6
    assert abs(model['win_rates'][3] - 1/3) < 1e-6

    # Team 1 (players 1,2) should beat team 2 (players 3,4)
    test_set = _make_set(1, 2, 3, 4, 0, 0)
    assert predict_win_rate_model(test_set, model) == 1


def test_score_margin_model():
    """Score margin model predicts based on average point differentials."""
    train = [
        _make_set(1, 2, 3, 4, 21, 10),  # diff = +11 for t1, -11 for t2
        _make_set(1, 2, 3, 4, 21, 15),  # diff = +6 for t1, -6 for t2
    ]
    model = train_score_margin_model(train)
    # Player 1 avg margin: (11 + 6) / 2 = 8.5
    assert abs(model['avg_margins'][1] - 8.5) < 1e-6
    # Player 3 avg margin: (-11 + -6) / 2 = -8.5
    assert abs(model['avg_margins'][3] - (-8.5)) < 1e-6

    test_set = _make_set(1, 2, 3, 4, 0, 0)
    assert predict_score_margin_model(test_set, model) == 1


def test_predict_skill_model():
    """Skill model predicts based on a*max + b*min."""
    model = {'a': 1.0, 'b': 0.5, 'skills': {1: 10, 2: 8, 3: 5, 4: 5}}
    # t1 = 1.0*10 + 0.5*8 = 14, t2 = 1.0*5 + 0.5*5 = 7.5
    test_set = _make_set(1, 2, 3, 4, 0, 0)
    assert predict_skill_model(test_set, model) == 1


def test_predict_elo_model():
    """ELO model predicts based on average team ELO."""
    model = {'elos': {1: 1600, 2: 1600, 3: 1400, 4: 1400}}
    test_set = _make_set(1, 2, 3, 4, 0, 0)
    assert predict_elo_model(test_set, model) == 1


def test_predict_bradley_terry():
    """Bradley-Terry model predicts based on additive skills."""
    model = {'skills': {1: 2.0, 2: 1.5, 3: -1.0, 4: -0.5}}
    # t1 = 2.0 + 1.5 = 3.5, t2 = -1.0 + -0.5 = -1.5
    test_set = _make_set(1, 2, 3, 4, 0, 0)
    assert predict_bradley_terry(test_set, model) == 1
