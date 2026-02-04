#!/usr/bin/env python3
"""
Custom skill-based ranking model for CBVA beach volleyball.

Model: t(i,j) = a * max(s_i, s_j) + b * min(s_i, s_j) + c * abs(s_i - s_j)

Where:
- s_i = hidden skill value for player i
- a = coefficient for stronger player's contribution
- b = coefficient for weaker player's contribution
- c = coefficient for skill gap between partners
- t(i,j) = team strength for players i and j

Uses regression to minimize prediction error on set score differences
and estimate a, b, c, and all player skill values.

Usage:
    python -m src.pipelines.skill_model
"""

import os
import sys
import numpy as np
from scipy.optimize import minimize

# Add project root to path for db imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db import get_connection, get_all_sets_with_month


# Train/Test split months
TEST_MONTHS = {10, 11}  # October, November


def split_train_test(sets):
    """
    Split sets by month: Oct/Nov for test, rest for training.

    Args:
        sets: List of set dicts with 'tournament_month' key

    Returns:
        Tuple of (train_sets, test_sets)
    """
    train = [s for s in sets if s['tournament_month'] not in TEST_MONTHS]
    test = [s for s in sets if s['tournament_month'] in TEST_MONTHS]
    return train, test


def build_player_index(sets):
    """
    Build player ID to index mapping from sets.

    Args:
        sets: List of set dicts with player ID keys

    Returns:
        Tuple of (player_to_idx, idx_to_player) dicts
    """
    players = set()
    for s in sets:
        players.add(s['team1_player1'])
        players.add(s['team1_player2'])
        players.add(s['team2_player1'])
        players.add(s['team2_player2'])

    player_list = sorted(players)
    player_to_idx = {pid: idx for idx, pid in enumerate(player_list)}
    idx_to_player = {idx: pid for pid, idx in player_to_idx.items()}
    return player_to_idx, idx_to_player


def compute_team_strength(s_i, s_j, a, b, c=0.0):
    """
    Compute team strength using the model formula.

    t(i,j) = a * max(s_i, s_j) + b * min(s_i, s_j) + c * abs(s_i - s_j)

    Args:
        s_i: Skill of player i
        s_j: Skill of player j
        a: Coefficient for stronger player
        b: Coefficient for weaker player
        c: Coefficient for skill gap (abs difference)

    Returns:
        Team strength value
    """
    return a * max(s_i, s_j) + b * min(s_i, s_j) + c * abs(s_i - s_j)


def objective_function(params, train_sets, player_to_idx, n_players, lambda_reg=0.0):
    """
    Compute sum of squared errors with L2 regularization for optimization.

    Args:
        params: Array of [a, b, s_0, s_1, ..., s_{n-1}]
        train_sets: Training data
        player_to_idx: Player ID to parameter index mapping
        n_players: Number of unique players
        lambda_reg: L2 regularization strength (penalty on skill magnitudes)

    Returns:
        Sum of squared errors + L2 penalty on skills
    """
    a = params[0]
    b = params[1]
    skills = params[2:]

    total_error = 0.0

    for s in train_sets:
        # Get player skills
        s1_p1 = skills[player_to_idx[s['team1_player1']]]
        s1_p2 = skills[player_to_idx[s['team1_player2']]]
        s2_p1 = skills[player_to_idx[s['team2_player1']]]
        s2_p2 = skills[player_to_idx[s['team2_player2']]]

        # Compute team strengths
        t1 = compute_team_strength(s1_p1, s1_p2, a, b)
        t2 = compute_team_strength(s2_p1, s2_p2, a, b)

        # Predicted vs actual score difference
        predicted_diff = t1 - t2
        actual_diff = s['team1_score'] - s['team2_score']

        total_error += (predicted_diff - actual_diff) ** 2

    # L2 regularization penalty on skills
    if lambda_reg > 0:
        total_error += lambda_reg * np.sum(skills ** 2)

    return total_error


def fit_model_sgd(train_sets, player_to_idx, lambda_reg=1.0, n_epochs=50, lr=0.01):
    """
    Fit the skill model using Stochastic Gradient Descent with L2 regularization.

    Model: t(i,j) = a * max(s_i, s_j) + b * min(s_i, s_j) + c * abs(s_i - s_j)

    Args:
        train_sets: Training set data
        player_to_idx: Player ID to index mapping
        lambda_reg: L2 regularization strength (default 1.0)
        n_epochs: Number of passes through training data
        lr: Learning rate

    Returns:
        Dict with 'a', 'b', 'c', 'skills', 'train_rmse', 'lambda_reg', 'n_epochs'
    """
    n_players = len(player_to_idx)
    n_train = len(train_sets)

    # Initialize parameters
    a = 1.0
    b = 1.0
    c = 0.0  # Start c at 0 (no skill gap effect initially)
    skills = np.zeros(n_players)

    print(f"  Starting SGD with {n_players} players, {n_train} samples...")
    print(f"  Initial a={a}, b={b}, c={c}, lambda={lambda_reg}, lr={lr}, epochs={n_epochs}")

    # SGD training
    for epoch in range(n_epochs):
        # Shuffle training data each epoch
        indices = np.random.permutation(n_train)

        total_loss = 0.0

        for idx in indices:
            s = train_sets[idx]

            # Get player indices
            t1_p1_idx = player_to_idx[s['team1_player1']]
            t1_p2_idx = player_to_idx[s['team1_player2']]
            t2_p1_idx = player_to_idx[s['team2_player1']]
            t2_p2_idx = player_to_idx[s['team2_player2']]

            # Get current skills
            s1_p1 = skills[t1_p1_idx]
            s1_p2 = skills[t1_p2_idx]
            s2_p1 = skills[t2_p1_idx]
            s2_p2 = skills[t2_p2_idx]

            # Compute team strengths with c term
            t1 = a * max(s1_p1, s1_p2) + b * min(s1_p1, s1_p2) + c * abs(s1_p1 - s1_p2)
            t2 = a * max(s2_p1, s2_p2) + b * min(s2_p1, s2_p2) + c * abs(s2_p1 - s2_p2)

            # Compute error
            predicted_diff = t1 - t2
            actual_diff = s['team1_score'] - s['team2_score']
            error = predicted_diff - actual_diff

            total_loss += error ** 2

            # Compute gradients
            # Gradient w.r.t. a: 2 * error * (max(team1) - max(team2))
            grad_a = 2 * error * (max(s1_p1, s1_p2) - max(s2_p1, s2_p2))
            # Gradient w.r.t. b: 2 * error * (min(team1) - min(team2))
            grad_b = 2 * error * (min(s1_p1, s1_p2) - min(s2_p1, s2_p2))
            # Gradient w.r.t. c: 2 * error * (|team1_gap| - |team2_gap|)
            grad_c = 2 * error * (abs(s1_p1 - s1_p2) - abs(s2_p1 - s2_p2))

            # Gradient w.r.t. skills
            # For max/min terms: derivative is a if player is max, b if player is min
            # For abs term: derivative is c * sign(s_i - s_j) for player i

            # Team 1 player 1
            if s1_p1 >= s1_p2:
                grad_t1_p1 = a + c  # max contributor + positive side of abs
            else:
                grad_t1_p1 = b - c  # min contributor + negative side of abs

            # Team 1 player 2
            if s1_p2 >= s1_p1:
                grad_t1_p2 = a + c
            else:
                grad_t1_p2 = b - c

            # Team 2 player 1
            if s2_p1 >= s2_p2:
                grad_t2_p1 = a + c
            else:
                grad_t2_p1 = b - c

            # Team 2 player 2
            if s2_p2 >= s2_p1:
                grad_t2_p2 = a + c
            else:
                grad_t2_p2 = b - c

            # Full gradients for skills (team1 contributes +, team2 contributes -)
            grad_s1_p1 = 2 * error * grad_t1_p1
            grad_s1_p2 = 2 * error * grad_t1_p2
            grad_s2_p1 = 2 * error * (-grad_t2_p1)
            grad_s2_p2 = 2 * error * (-grad_t2_p2)

            # Add L2 regularization gradients
            grad_s1_p1 += 2 * lambda_reg * s1_p1 / n_train
            grad_s1_p2 += 2 * lambda_reg * s1_p2 / n_train
            grad_s2_p1 += 2 * lambda_reg * s2_p1 / n_train
            grad_s2_p2 += 2 * lambda_reg * s2_p2 / n_train

            # Update parameters
            a -= lr * grad_a
            b -= lr * grad_b
            c -= lr * grad_c
            skills[t1_p1_idx] -= lr * grad_s1_p1
            skills[t1_p2_idx] -= lr * grad_s1_p2
            skills[t2_p1_idx] -= lr * grad_s2_p1
            skills[t2_p2_idx] -= lr * grad_s2_p2

            # Enforce a, b > 0 (c can be any value)
            a = max(a, 0.001)
            b = max(b, 0.001)

        # Compute RMSE at end of epoch
        rmse = np.sqrt(total_loss / n_train)
        if epoch % 10 == 0 or epoch == n_epochs - 1:
            print(f"    Epoch {epoch+1}/{n_epochs}: RMSE = {rmse:.3f}, a = {a:.4f}, b = {b:.4f}, c = {c:.4f}")

    # Build skills dict
    skills_dict = {}
    for pid, idx in player_to_idx.items():
        skills_dict[pid] = skills[idx]

    return {
        'a': a,
        'b': b,
        'c': c,
        'skills': skills_dict,
        'train_rmse': rmse,
        'lambda_reg': lambda_reg,
        'n_epochs': n_epochs
    }


def fit_model(train_sets, player_to_idx, lambda_reg=1.0):
    """Wrapper that calls SGD-based fitting."""
    return fit_model_sgd(train_sets, player_to_idx, lambda_reg=lambda_reg, n_epochs=50, lr=0.01)


def predict_winner(set_data, a, b, c, skills):
    """
    Predict which team wins a set.

    Args:
        set_data: Dict with player ID keys
        a: Stronger player coefficient
        b: Weaker player coefficient
        c: Skill gap coefficient
        skills: Dict of player_id -> skill value

    Returns:
        1 if team1 predicted to win, 2 if team2
    """
    s1_p1 = skills.get(set_data['team1_player1'], 0)
    s1_p2 = skills.get(set_data['team1_player2'], 0)
    s2_p1 = skills.get(set_data['team2_player1'], 0)
    s2_p2 = skills.get(set_data['team2_player2'], 0)

    t1 = compute_team_strength(s1_p1, s1_p2, a, b, c)
    t2 = compute_team_strength(s2_p1, s2_p2, a, b, c)

    return 1 if t1 >= t2 else 2


def validate_model(test_sets, a, b, c, skills, training_players):
    """
    Evaluate model on test sets.

    Args:
        test_sets: Test set data
        a: Stronger player coefficient
        b: Weaker player coefficient
        c: Skill gap coefficient
        skills: Dict of player_id -> skill value
        training_players: Set of player IDs seen in training

    Returns:
        Dict with validation metrics
    """
    correct = 0
    incorrect = 0
    excluded = 0
    predictions = []

    for s in test_sets:
        players = {s['team1_player1'], s['team1_player2'],
                   s['team2_player1'], s['team2_player2']}

        # Skip if any player not in training data
        if not players.issubset(training_players):
            excluded += 1
            continue

        predicted = predict_winner(s, a, b, c, skills)
        actual = 1 if s['team1_score'] > s['team2_score'] else 2

        is_correct = (predicted == actual)
        if is_correct:
            correct += 1
        else:
            incorrect += 1

        predictions.append({
            'set_id': s['set_id'],
            'predicted': predicted,
            'actual': actual,
            'correct': is_correct
        })

    n_evaluated = correct + incorrect
    accuracy = correct / n_evaluated if n_evaluated > 0 else 0

    return {
        'accuracy': accuracy,
        'n_sets': len(test_sets),
        'n_evaluated': n_evaluated,
        'n_excluded': excluded,
        'correct': correct,
        'incorrect': incorrect,
        'predictions': predictions
    }


def get_player_rankings(skills, conn):
    """
    Get player rankings sorted by skill.

    Args:
        skills: Dict of player_id -> skill value
        conn: Database connection

    Returns:
        List of (cbva_id, skill_value) tuples sorted by skill descending
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id, cbva_id FROM players")
        player_names = {row[0]: row[1] for row in cur.fetchall()}

    rankings = []
    for pid, skill in sorted(skills.items(), key=lambda x: -x[1]):
        cbva_id = player_names.get(pid, f"unknown_{pid}")
        rankings.append((cbva_id, skill))

    return rankings


def run_skill_model():
    """
    Run the complete skill model pipeline.

    Returns:
        Dict with model, validation, and rankings
    """
    print("=" * 60)
    print("CBVA Skill-Based Ranking Model")
    print("=" * 60)

    print("\nConnecting to database...")
    conn = get_connection()

    try:
        print("Fetching sets with tournament dates...")
        all_sets = get_all_sets_with_month(conn)
        print(f"  Total sets: {len(all_sets)}")

        print("\nSplitting train/test (Oct/Nov for test)...")
        train_sets, test_sets = split_train_test(all_sets)
        print(f"  Training sets: {len(train_sets)}")
        print(f"  Test sets: {len(test_sets)}")

        print("\nBuilding player index from training data...")
        player_to_idx, idx_to_player = build_player_index(train_sets)
        training_players = set(player_to_idx.keys())
        print(f"  Unique players in training: {len(player_to_idx)}")

        print("\nFitting model with SGD and L2 regularization...")
        model = fit_model(train_sets, player_to_idx, lambda_reg=1.0)
        print(f"\n  Final results:")
        print(f"  Lambda (L2 reg): {model['lambda_reg']}")
        print(f"  a = {model['a']:.4f} (stronger player weight)")
        print(f"  b = {model['b']:.4f} (weaker player weight)")
        print(f"  c = {model['c']:.4f} (skill gap weight)")
        print(f"  Training RMSE: {model['train_rmse']:.2f} points")

        print("\nValidating on test data...")
        validation = validate_model(
            test_sets, model['a'], model['b'], model['c'], model['skills'], training_players
        )
        print(f"  Sets evaluated: {validation['n_evaluated']}")
        print(f"  Sets excluded (unseen players): {validation['n_excluded']}")
        print(f"  Correct predictions: {validation['correct']}")
        print(f"  Incorrect predictions: {validation['incorrect']}")
        print(f"  Accuracy: {validation['accuracy']:.1%}")

        print("\n" + "=" * 60)
        print("Top 20 Players by Skill")
        print("=" * 60)
        rankings = get_player_rankings(model['skills'], conn)
        for rank, (cbva_id, skill) in enumerate(rankings[:20], 1):
            print(f"  {rank:2d}. {cbva_id:30s} {skill:+8.2f}")

        print("\n" + "=" * 60)
        print("Bottom 20 Players by Skill")
        print("=" * 60)
        for rank, (cbva_id, skill) in enumerate(rankings[-20:], len(rankings) - 19):
            print(f"  {rank:3d}. {cbva_id:30s} {skill:+8.2f}")

        return {
            'model': model,
            'validation': validation,
            'rankings': rankings
        }

    finally:
        conn.close()


def main():
    """CLI entry point."""
    results = run_skill_model()
    return results


if __name__ == "__main__":
    main()
