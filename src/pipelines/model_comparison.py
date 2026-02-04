#!/usr/bin/env python3
"""
Compare 5 different approaches to predicting CBVA beach volleyball set outcomes.

Models:
1. Custom Skill Model (a*max + b*min) - nonlinear team strength with SGD
2. ELO-Based Prediction - standard chess-style ELO ratings
3. Bradley-Terry (Logistic Skill) - logistic regression on latent skills
4. Player Win Rate - empirical win percentages
5. Score Margin Model - average point differentials

Train on all data except Oct/Nov 2025, test on Oct/Nov 2025.

Usage:
    python -m src.pipelines.model_comparison
"""

import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db import get_connection, get_all_sets_with_date
from src.pipelines.calculate_elo import (
    DEFAULT_ELO,
    K_FACTOR,
    calculate_expected,
    update_elo,
    get_team_elo,
)


# --- Data splitting ---

TEST_MONTHS = {10, 11}
TEST_YEAR = 2025


def split_train_test(sets):
    """Split: test = Oct/Nov 2025, train = everything else."""
    train = []
    test = []
    for s in sets:
        if s['tournament_month'] in TEST_MONTHS and s['tournament_year'] == TEST_YEAR:
            test.append(s)
        else:
            train.append(s)
    return train, test


def get_training_players(train_sets):
    """Get set of all player IDs seen in training data."""
    players = set()
    for s in train_sets:
        players.add(s['team1_player1'])
        players.add(s['team1_player2'])
        players.add(s['team2_player1'])
        players.add(s['team2_player2'])
    return players


# --- Evaluation ---

def evaluate_model(name, predict_fn, test_sets, training_players):
    """
    Evaluate a prediction function on test sets.

    Args:
        name: Model name for display
        predict_fn: Function(set_data) -> 1 or 2
        test_sets: Test set data
        training_players: Set of player IDs seen in training

    Returns:
        Dict with accuracy metrics
    """
    correct = 0
    incorrect = 0
    excluded = 0

    for s in test_sets:
        players = {s['team1_player1'], s['team1_player2'],
                   s['team2_player1'], s['team2_player2']}

        if not players.issubset(training_players):
            excluded += 1
            continue

        predicted = predict_fn(s)
        actual = 1 if s['team1_score'] > s['team2_score'] else 2

        if predicted == actual:
            correct += 1
        else:
            incorrect += 1

    n_evaluated = correct + incorrect
    accuracy = correct / n_evaluated if n_evaluated > 0 else 0

    return {
        'name': name,
        'accuracy': accuracy,
        'n_evaluated': n_evaluated,
        'n_excluded': excluded,
        'correct': correct,
        'incorrect': incorrect,
    }


# --- Model 1: Custom Skill Model (a*max + b*min) ---

def train_skill_model(train_sets, n_epochs=50, lr=0.01, lambda_reg=1.0):
    """Train the custom skill model using SGD."""
    players = set()
    for s in train_sets:
        for key in ('team1_player1', 'team1_player2', 'team2_player1', 'team2_player2'):
            players.add(s[key])

    player_list = sorted(players)
    player_to_idx = {pid: idx for idx, pid in enumerate(player_list)}
    n_players = len(player_list)
    n_train = len(train_sets)

    a = 1.0
    b = 1.0
    skills = np.zeros(n_players)

    for epoch in range(n_epochs):
        indices = np.random.permutation(n_train)
        total_loss = 0.0

        for idx in indices:
            s = train_sets[idx]

            t1_p1_idx = player_to_idx[s['team1_player1']]
            t1_p2_idx = player_to_idx[s['team1_player2']]
            t2_p1_idx = player_to_idx[s['team2_player1']]
            t2_p2_idx = player_to_idx[s['team2_player2']]

            s1_p1 = skills[t1_p1_idx]
            s1_p2 = skills[t1_p2_idx]
            s2_p1 = skills[t2_p1_idx]
            s2_p2 = skills[t2_p2_idx]

            t1 = a * max(s1_p1, s1_p2) + b * min(s1_p1, s1_p2)
            t2 = a * max(s2_p1, s2_p2) + b * min(s2_p1, s2_p2)

            predicted_diff = t1 - t2
            actual_diff = s['team1_score'] - s['team2_score']
            error = predicted_diff - actual_diff

            total_loss += error ** 2

            grad_a = 2 * error * (max(s1_p1, s1_p2) - max(s2_p1, s2_p2))
            grad_b = 2 * error * (min(s1_p1, s1_p2) - min(s2_p1, s2_p2))

            if s1_p1 >= s1_p2:
                grad_t1_p1, grad_t1_p2 = a, b
            else:
                grad_t1_p1, grad_t1_p2 = b, a

            if s2_p1 >= s2_p2:
                grad_t2_p1, grad_t2_p2 = a, b
            else:
                grad_t2_p1, grad_t2_p2 = b, a

            skills[t1_p1_idx] -= lr * (2 * error * grad_t1_p1 + 2 * lambda_reg * s1_p1 / n_train)
            skills[t1_p2_idx] -= lr * (2 * error * grad_t1_p2 + 2 * lambda_reg * s1_p2 / n_train)
            skills[t2_p1_idx] -= lr * (2 * error * (-grad_t2_p1) + 2 * lambda_reg * s2_p1 / n_train)
            skills[t2_p2_idx] -= lr * (2 * error * (-grad_t2_p2) + 2 * lambda_reg * s2_p2 / n_train)

            a -= lr * grad_a
            b -= lr * grad_b
            a = max(a, 0.001)
            b = max(b, 0.001)

        rmse = np.sqrt(total_loss / n_train)
        if epoch % 10 == 0 or epoch == n_epochs - 1:
            print(f"    Epoch {epoch+1}/{n_epochs}: RMSE = {rmse:.3f}, a = {a:.4f}, b = {b:.4f}")

    skills_dict = {pid: skills[idx] for pid, idx in player_to_idx.items()}
    return {'a': a, 'b': b, 'skills': skills_dict, 'rmse': rmse}


def predict_skill_model(set_data, model):
    """Predict winner using the custom skill model."""
    a, b, skills = model['a'], model['b'], model['skills']
    s1_p1 = skills.get(set_data['team1_player1'], 0)
    s1_p2 = skills.get(set_data['team1_player2'], 0)
    s2_p1 = skills.get(set_data['team2_player1'], 0)
    s2_p2 = skills.get(set_data['team2_player2'], 0)

    t1 = a * max(s1_p1, s1_p2) + b * min(s1_p1, s1_p2)
    t2 = a * max(s2_p1, s2_p2) + b * min(s2_p1, s2_p2)
    return 1 if t1 >= t2 else 2


# --- Model 2: ELO-Based Prediction ---

def train_elo_model(train_sets):
    """Compute ELO ratings by processing training sets chronologically."""
    elos = defaultdict(lambda: DEFAULT_ELO)

    for s in train_sets:
        team1_players = (s['team1_player1'], s['team1_player2'])
        team2_players = (s['team2_player1'], s['team2_player2'])

        team1_elo = (elos[team1_players[0]] + elos[team1_players[1]]) / 2
        team2_elo = (elos[team2_players[0]] + elos[team2_players[1]]) / 2

        team1_expected = calculate_expected(team1_elo, team2_elo)
        team2_expected = calculate_expected(team2_elo, team1_elo)

        team1_won = s['team1_score'] > s['team2_score']
        team1_actual = 1 if team1_won else 0
        team2_actual = 1 - team1_actual

        for player in team1_players:
            elos[player] = update_elo(elos[player], team1_expected, team1_actual)
        for player in team2_players:
            elos[player] = update_elo(elos[player], team2_expected, team2_actual)

    return {'elos': dict(elos)}


def predict_elo_model(set_data, model):
    """Predict winner using ELO ratings."""
    elos = model['elos']
    t1_elo = (elos.get(set_data['team1_player1'], DEFAULT_ELO) +
              elos.get(set_data['team1_player2'], DEFAULT_ELO)) / 2
    t2_elo = (elos.get(set_data['team2_player1'], DEFAULT_ELO) +
              elos.get(set_data['team2_player2'], DEFAULT_ELO)) / 2
    return 1 if t1_elo >= t2_elo else 2


# --- Model 3: Bradley-Terry (Logistic Skill Model) ---

def train_bradley_terry(train_sets, n_epochs=50, lr=0.01, lambda_reg=1.0):
    """
    Train Bradley-Terry model with SGD.

    P(team1 wins) = sigmoid(team1_strength - team2_strength)
    team_strength = s_i + s_j (additive)
    Minimize cross-entropy loss.
    """
    players = set()
    for s in train_sets:
        for key in ('team1_player1', 'team1_player2', 'team2_player1', 'team2_player2'):
            players.add(s[key])

    player_list = sorted(players)
    player_to_idx = {pid: idx for idx, pid in enumerate(player_list)}
    n_players = len(player_list)
    n_train = len(train_sets)

    skills = np.zeros(n_players)

    for epoch in range(n_epochs):
        indices = np.random.permutation(n_train)
        total_loss = 0.0

        for idx in indices:
            s = train_sets[idx]

            t1_p1_idx = player_to_idx[s['team1_player1']]
            t1_p2_idx = player_to_idx[s['team1_player2']]
            t2_p1_idx = player_to_idx[s['team2_player1']]
            t2_p2_idx = player_to_idx[s['team2_player2']]

            # Team strengths (additive)
            t1_strength = skills[t1_p1_idx] + skills[t1_p2_idx]
            t2_strength = skills[t2_p1_idx] + skills[t2_p2_idx]

            # Sigmoid probability
            diff = t1_strength - t2_strength
            diff = np.clip(diff, -20, 20)  # prevent overflow
            prob_t1 = 1.0 / (1.0 + np.exp(-diff))

            # Actual outcome
            y = 1.0 if s['team1_score'] > s['team2_score'] else 0.0

            # Cross-entropy loss
            eps = 1e-10
            total_loss += -(y * np.log(prob_t1 + eps) + (1 - y) * np.log(1 - prob_t1 + eps))

            # Gradient: d_loss/d_diff = prob_t1 - y
            grad = prob_t1 - y

            # Update skills
            skills[t1_p1_idx] -= lr * (grad + 2 * lambda_reg * skills[t1_p1_idx] / n_train)
            skills[t1_p2_idx] -= lr * (grad + 2 * lambda_reg * skills[t1_p2_idx] / n_train)
            skills[t2_p1_idx] -= lr * (-grad + 2 * lambda_reg * skills[t2_p1_idx] / n_train)
            skills[t2_p2_idx] -= lr * (-grad + 2 * lambda_reg * skills[t2_p2_idx] / n_train)

        avg_loss = total_loss / n_train
        if epoch % 10 == 0 or epoch == n_epochs - 1:
            print(f"    Epoch {epoch+1}/{n_epochs}: avg cross-entropy = {avg_loss:.4f}")

    skills_dict = {pid: skills[idx] for pid, idx in player_to_idx.items()}
    return {'skills': skills_dict, 'avg_loss': avg_loss}


def predict_bradley_terry(set_data, model):
    """Predict winner using Bradley-Terry model."""
    skills = model['skills']
    t1 = skills.get(set_data['team1_player1'], 0) + skills.get(set_data['team1_player2'], 0)
    t2 = skills.get(set_data['team2_player1'], 0) + skills.get(set_data['team2_player2'], 0)
    return 1 if t1 >= t2 else 2


# --- Model 4: Player Win Rate ---

def train_win_rate_model(train_sets):
    """Compute per-player win rates from training data."""
    wins = defaultdict(int)
    total = defaultdict(int)

    for s in train_sets:
        team1_won = s['team1_score'] > s['team2_score']

        for pid in (s['team1_player1'], s['team1_player2']):
            total[pid] += 1
            if team1_won:
                wins[pid] += 1

        for pid in (s['team2_player1'], s['team2_player2']):
            total[pid] += 1
            if not team1_won:
                wins[pid] += 1

    win_rates = {pid: wins[pid] / total[pid] for pid in total}
    return {'win_rates': win_rates}


def predict_win_rate_model(set_data, model):
    """Predict winner using player win rates."""
    wr = model['win_rates']
    t1 = (wr.get(set_data['team1_player1'], 0.5) +
          wr.get(set_data['team1_player2'], 0.5)) / 2
    t2 = (wr.get(set_data['team2_player1'], 0.5) +
          wr.get(set_data['team2_player2'], 0.5)) / 2
    return 1 if t1 >= t2 else 2


# --- Model 5: Score Margin Model ---

def train_score_margin_model(train_sets):
    """Compute per-player average score margins from training data."""
    margins = defaultdict(list)

    for s in train_sets:
        diff = s['team1_score'] - s['team2_score']

        # Team 1 players get +diff, Team 2 players get -diff
        margins[s['team1_player1']].append(diff)
        margins[s['team1_player2']].append(diff)
        margins[s['team2_player1']].append(-diff)
        margins[s['team2_player2']].append(-diff)

    avg_margins = {pid: np.mean(m) for pid, m in margins.items()}
    return {'avg_margins': avg_margins}


def predict_score_margin_model(set_data, model):
    """Predict winner using player score margins."""
    m = model['avg_margins']
    t1 = (m.get(set_data['team1_player1'], 0) +
          m.get(set_data['team1_player2'], 0))
    t2 = (m.get(set_data['team2_player1'], 0) +
          m.get(set_data['team2_player2'], 0))
    return 1 if t1 >= t2 else 2


# --- Main comparison ---

def compare_models():
    """Run all 5 models and compare their performance."""
    print("=" * 60)
    print("Model Comparison: Predicting Oct/Nov 2025 Set Winners")
    print("=" * 60)

    print("\nConnecting to database...")
    conn = get_connection()

    try:
        print("Fetching sets with date info...")
        all_sets = get_all_sets_with_date(conn)
        print(f"  Total sets: {len(all_sets)}")

        print("\nSplitting train/test (test = Oct/Nov 2025)...")
        train_sets, test_sets = split_train_test(all_sets)
        print(f"  Training sets: {len(train_sets)}")
        print(f"  Test sets (Oct/Nov 2025): {len(test_sets)}")

        training_players = get_training_players(train_sets)
        print(f"  Unique players in training: {len(training_players)}")

        results = []

        # Model 1: Custom Skill Model
        print("\n" + "-" * 60)
        print("Model 1: Custom Skill Model (a*max + b*min)")
        print("-" * 60)
        m1 = train_skill_model(train_sets)
        print(f"  a = {m1['a']:.4f}, b = {m1['b']:.4f}, RMSE = {m1['rmse']:.3f}")
        r1 = evaluate_model(
            "Skill Model (a*max+b*min)",
            lambda s: predict_skill_model(s, m1),
            test_sets, training_players
        )
        results.append(r1)

        # Model 2: ELO-Based
        print("\n" + "-" * 60)
        print("Model 2: ELO-Based Prediction")
        print("-" * 60)
        m2 = train_elo_model(train_sets)
        print(f"  Trained on {len(train_sets)} sets, {len(m2['elos'])} players rated")
        r2 = evaluate_model(
            "ELO-Based",
            lambda s: predict_elo_model(s, m2),
            test_sets, training_players
        )
        results.append(r2)

        # Model 3: Bradley-Terry
        print("\n" + "-" * 60)
        print("Model 3: Bradley-Terry (Logistic Skill)")
        print("-" * 60)
        m3 = train_bradley_terry(train_sets)
        r3 = evaluate_model(
            "Bradley-Terry (Logistic)",
            lambda s: predict_bradley_terry(s, m3),
            test_sets, training_players
        )
        results.append(r3)

        # Model 4: Player Win Rate
        print("\n" + "-" * 60)
        print("Model 4: Player Win Rate")
        print("-" * 60)
        m4 = train_win_rate_model(train_sets)
        print(f"  Computed win rates for {len(m4['win_rates'])} players")
        r4 = evaluate_model(
            "Player Win Rate",
            lambda s: predict_win_rate_model(s, m4),
            test_sets, training_players
        )
        results.append(r4)

        # Model 5: Score Margin
        print("\n" + "-" * 60)
        print("Model 5: Score Margin Model")
        print("-" * 60)
        m5 = train_score_margin_model(train_sets)
        print(f"  Computed avg margins for {len(m5['avg_margins'])} players")
        r5 = evaluate_model(
            "Score Margin",
            lambda s: predict_score_margin_model(s, m5),
            test_sets, training_players
        )
        results.append(r5)

        # Print comparison table
        print("\n" + "=" * 60)
        print("RESULTS COMPARISON")
        print("=" * 60)
        print(f"\n  {'Model':<30s} {'Eval':>6s} {'Excl':>6s} {'Correct':>8s} {'Accuracy':>9s}")
        print("  " + "-" * 59)
        for r in sorted(results, key=lambda x: -x['accuracy']):
            print(f"  {r['name']:<30s} {r['n_evaluated']:>6d} {r['n_excluded']:>6d} "
                  f"{r['correct']:>8d} {r['accuracy']:>8.1%}")

        return results

    finally:
        conn.close()


def main():
    """CLI entry point."""
    return compare_models()


if __name__ == "__main__":
    main()
