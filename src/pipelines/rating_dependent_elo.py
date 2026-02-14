#!/usr/bin/env python3
"""
Rating-dependent ELO: Calculate ELO using only matches against specific CBVA ratings.

This calculates separate ELO ratings for each player based on their performance
against opponents of different skill levels (AAA, AA, A, B, etc.).

A set counts toward the rating-dependent ELO if AT LEAST ONE opponent has the
target CBVA rating.

Usage:
    python -m src.pipelines.rating_dependent_elo              # Calculate and save all
    python -m src.pipelines.rating_dependent_elo --rating AAA # Just vs AAA
    python -m src.pipelines.rating_dependent_elo --no-save    # Don't save to database
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db import (
    get_connection,
    get_all_sets_with_ratings,
    upsert_rating_dependent_elo,
    clear_rating_dependent_elos,
)

# ELO constants (same as standard ELO)
DEFAULT_ELO = 1500
K_FACTOR = 32

# Valid CBVA ratings in order of skill
RATINGS = ['AAA', 'AA', 'A', 'B', 'Novice', 'Unrated']


def calculate_expected(team_elo, opponent_elo):
    """Calculate expected score using ELO formula."""
    return 1 / (1 + 10 ** ((opponent_elo - team_elo) / 400))


def update_elo(current_elo, expected, actual, k=K_FACTOR):
    """Calculate new ELO rating after a result."""
    return current_elo + k * (actual - expected)


def filter_sets_by_opponent_rating(all_sets, target_rating):
    """
    Filter sets to only include those where at least one opponent has target rating.

    Args:
        all_sets: List of set dicts with player ratings
        target_rating: CBVA rating to filter by (e.g., 'AAA', 'AA', 'A', 'B')

    Returns:
        List of sets where at least one opponent has the target rating
    """
    filtered = []
    for s in all_sets:
        # For team 1, opponents are team 2 players
        # For team 2, opponents are team 1 players
        # A set is included if ANY of the 4 players has the target rating
        # (since each team plays against the other)
        opp_ratings = {
            s['team1_player1_rating'],
            s['team1_player2_rating'],
            s['team2_player1_rating'],
            s['team2_player2_rating'],
        }
        if target_rating in opp_ratings:
            filtered.append(s)
    return filtered


def calculate_rating_dependent_elo(all_sets, target_rating):
    """
    Calculate ELO ratings using only sets against players with target rating.

    Args:
        all_sets: All sets with player ratings
        target_rating: CBVA rating to filter by

    Returns:
        Dict with:
        - 'elos': player_id -> ELO rating
        - 'games_played': player_id -> number of sets played
        - 'target_rating': the rating filtered on
        - 'n_sets': total sets processed
    """
    # Filter sets
    filtered_sets = filter_sets_by_opponent_rating(all_sets, target_rating)

    # Initialize ELOs
    elos = defaultdict(lambda: DEFAULT_ELO)
    games_played = defaultdict(int)

    for s in filtered_sets:
        team1_players = (s['team1_player1'], s['team1_player2'])
        team2_players = (s['team2_player1'], s['team2_player2'])

        # Calculate team ELOs (average)
        team1_elo = (elos[team1_players[0]] + elos[team1_players[1]]) / 2
        team2_elo = (elos[team2_players[0]] + elos[team2_players[1]]) / 2

        # Expected scores
        team1_expected = calculate_expected(team1_elo, team2_elo)
        team2_expected = calculate_expected(team2_elo, team1_elo)

        # Actual results
        team1_won = s['team1_score'] > s['team2_score']
        team1_actual = 1 if team1_won else 0
        team2_actual = 1 - team1_actual

        # Update each player's ELO
        for player in team1_players:
            elos[player] = update_elo(elos[player], team1_expected, team1_actual)
            games_played[player] += 1

        for player in team2_players:
            elos[player] = update_elo(elos[player], team2_expected, team2_actual)
            games_played[player] += 1

    return {
        'elos': dict(elos),
        'games_played': dict(games_played),
        'target_rating': target_rating,
        'n_sets': len(filtered_sets),
    }


def get_player_names(conn):
    """Get mapping of player_id to cbva_id."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, cbva_id FROM players")
        return {row[0]: row[1] for row in cur.fetchall()}


def save_results_to_db(conn, results):
    """
    Save rating-dependent ELO results to the database.

    Args:
        conn: Database connection
        results: Dict of rating -> result dict from calculate_rating_dependent_elo
    """
    total_records = 0

    for rating, result in results.items():
        elos = result['elos']
        games_played = result['games_played']

        for player_id, elo in elos.items():
            games = games_played.get(player_id, 0)
            upsert_rating_dependent_elo(conn, player_id, rating, elo, games)
            total_records += 1

    conn.commit()
    return total_records


def run_rating_dependent_elo(target_rating=None, save_to_db=True):
    """
    Run rating-dependent ELO calculation.

    Args:
        target_rating: Specific rating to calculate for, or None for all ratings
        save_to_db: Whether to save results to the database

    Returns:
        Dict of rating -> result dict
    """
    print("=" * 60)
    print("Rating-Dependent ELO Calculation")
    print("=" * 60)

    print("\nConnecting to database...")
    conn = get_connection()

    try:
        print("Fetching sets with player ratings...")
        all_sets = get_all_sets_with_ratings(conn)
        print(f"  Total sets: {len(all_sets)}")

        player_names = get_player_names(conn)

        ratings_to_process = [target_rating] if target_rating else RATINGS
        results = {}

        # Clear existing data if saving all ratings
        if save_to_db and target_rating is None:
            print("\nClearing existing rating-dependent ELO data...")
            clear_rating_dependent_elos(conn)
            conn.commit()

        for rating in ratings_to_process:
            print(f"\n{'-' * 60}")
            print(f"Calculating ELO vs {rating} players")
            print(f"{'-' * 60}")

            result = calculate_rating_dependent_elo(all_sets, rating)
            results[rating] = result

            print(f"  Sets matching: {result['n_sets']}")
            print(f"  Players with games: {len(result['elos'])}")

            if result['elos']:
                # Show top 10 players with at least 5 games
                qualified = [(pid, elo) for pid, elo in result['elos'].items()
                             if result['games_played'].get(pid, 0) >= 5]
                qualified.sort(key=lambda x: -x[1])

                print(f"\n  Top 10 players (min 5 games vs {rating}):")
                for i, (pid, elo) in enumerate(qualified[:10], 1):
                    name = player_names.get(pid, f"unknown_{pid}")
                    games = result['games_played'][pid]
                    print(f"    {i:2d}. {name:25s} {elo:7.1f} ({games} games)")

        # Save to database
        if save_to_db:
            print("\n" + "=" * 60)
            print("Saving to database...")
            print("=" * 60)
            total_records = save_results_to_db(conn, results)
            print(f"  Saved {total_records} rating-dependent ELO records")

        # Summary comparison
        if len(results) > 1:
            print("\n" + "=" * 60)
            print("SUMMARY: Sets per rating category")
            print("=" * 60)
            for rating in RATINGS:
                if rating in results:
                    n_sets = results[rating]['n_sets']
                    n_players = len(results[rating]['elos'])
                    print(f"  vs {rating:8s}: {n_sets:6d} sets, {n_players:5d} players")

        return results

    finally:
        conn.close()


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='Calculate rating-dependent ELO')
    parser.add_argument('--rating', '-r', choices=RATINGS,
                        help='Specific rating to calculate (default: all)')
    parser.add_argument('--no-save', action='store_true',
                        help="Don't save results to database")
    args = parser.parse_args()

    return run_rating_dependent_elo(args.rating, save_to_db=not args.no_save)


if __name__ == "__main__":
    main()
