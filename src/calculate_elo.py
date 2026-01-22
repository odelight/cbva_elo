#!/usr/bin/env python3
"""
Calculate ELO ratings for CBVA players based on match results.

ELO is updated per-set, not per-match. Each player has an individual rating
that is updated based on set wins/losses with their partner.

Supports both file-based input (for backward compatibility) and database
operations for the full pipeline.
"""

import os
import sys
from collections import defaultdict

# Add parent directory to path for db imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DEFAULT_ELO = 1500
K_FACTOR = 32


def calculate_expected(team_elo, opponent_elo):
    """
    Calculate expected score using ELO formula.

    Returns probability of winning (0 to 1).
    """
    return 1 / (1 + 10 ** ((opponent_elo - team_elo) / 400))


def update_elo(current_elo, expected, actual, k=K_FACTOR):
    """
    Calculate new ELO rating after a result.

    Args:
        current_elo: Current ELO rating
        expected: Expected score (0 to 1)
        actual: Actual result (1 for win, 0 for loss)
        k: K-factor for rating adjustment

    Returns:
        New ELO rating
    """
    return current_elo + k * (actual - expected)


def get_team_elo(elos, player1, player2):
    """Get combined team ELO as average of both players."""
    return (elos[player1] + elos[player2]) / 2


def process_set(elos, team1_players, team2_players, team1_won):
    """
    Update ELO for all 4 players based on set result.

    Args:
        elos: Dict of player_id -> current ELO
        team1_players: Tuple of (player1_id, player2_id) for team 1
        team2_players: Tuple of (player1_id, player2_id) for team 2
        team1_won: True if team 1 won the set
    """
    # Calculate team ELOs before the set
    team1_elo = get_team_elo(elos, team1_players[0], team1_players[1])
    team2_elo = get_team_elo(elos, team2_players[0], team2_players[1])

    # Calculate expected scores
    team1_expected = calculate_expected(team1_elo, team2_elo)
    team2_expected = calculate_expected(team2_elo, team1_elo)

    # Actual results
    team1_actual = 1 if team1_won else 0
    team2_actual = 1 if not team1_won else 0

    # Update each player's ELO
    for player in team1_players:
        elos[player] = update_elo(elos[player], team1_expected, team1_actual)

    for player in team2_players:
        elos[player] = update_elo(elos[player], team2_expected, team2_actual)


def parse_results_file(filepath):
    """
    Parse results file into list of matches.

    Returns list of dicts:
    {
        'team_id': str,
        'players': (player1_id, player2_id),
        'games': [
            {
                'opponent_team_id': str,
                'sets': [(our_score, their_score), ...]
            },
            ...
        ]
    }
    """
    matches = []
    current_team = None

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                if current_team:
                    matches.append(current_team)
                    current_team = None
                continue

            parts = line.split()

            # Check if this is a team header line (team_id player1 player2)
            # vs a game line (opponent_id score1 score2 ...)
            if '-' not in line:
                # Team header line
                if current_team:
                    matches.append(current_team)

                if len(parts) >= 3:
                    current_team = {
                        'team_id': parts[0],
                        'players': (parts[1], parts[2]),
                        'games': []
                    }
                else:
                    current_team = None
            else:
                # Game line with scores
                if current_team and len(parts) >= 2:
                    opponent_id = parts[0]
                    sets = []
                    for score_str in parts[1:]:
                        if '-' in score_str:
                            try:
                                our_score, their_score = score_str.split('-')
                                sets.append((int(our_score), int(their_score)))
                            except ValueError:
                                continue

                    if sets:
                        current_team['games'].append({
                            'opponent_team_id': opponent_id,
                            'sets': sets
                        })

    # Don't forget the last team
    if current_team:
        matches.append(current_team)

    return matches


def build_team_player_map(matches):
    """Build mapping of team_id -> (player1, player2)."""
    team_players = {}
    for match in matches:
        team_players[match['team_id']] = match['players']
    return team_players


def calculate_all_elos(results_file):
    """
    Process all matches and return player ELO ratings.

    Returns dict of player_id -> final ELO rating.
    """
    matches = parse_results_file(results_file)
    team_players = build_team_player_map(matches)

    # Initialize ELOs with default value
    elos = defaultdict(lambda: DEFAULT_ELO)

    # Track processed matches to avoid duplicates
    # Key: frozenset of (team1_id, team2_id) + tuple of set scores
    processed = set()

    for match in matches:
        team1_id = match['team_id']
        team1_players = match['players']

        for game in match['games']:
            team2_id = game['opponent_team_id']

            # Skip if opponent team not found (shouldn't happen with complete data)
            if team2_id not in team_players:
                continue

            team2_players = team_players[team2_id]

            # Create a canonical key to detect duplicates
            # Sort team IDs so (A vs B) and (B vs A) produce same key
            sorted_teams = tuple(sorted([team1_id, team2_id]))

            # Include set scores in key (from perspective of first sorted team)
            if team1_id == sorted_teams[0]:
                score_key = tuple(game['sets'])
            else:
                # Flip scores for canonical ordering
                score_key = tuple((their, our) for our, their in game['sets'])

            match_key = (sorted_teams, score_key)

            if match_key in processed:
                continue
            processed.add(match_key)

            # Process each set
            for our_score, their_score in game['sets']:
                team1_won = our_score > their_score
                process_set(elos, team1_players, team2_players, team1_won)

    return dict(elos)


def calculate_all_elos_from_db(conn):
    """
    Process all sets from database and update player ELO ratings.

    This reads sets from the database in chronological order, calculates
    ELO changes, records them in elo_history, and updates players.current_elo.

    Args:
        conn: Database connection

    Returns:
        Dict of player_id -> (cbva_id, final_elo)
    """
    from db import (
        get_all_sets_for_elo,
        get_all_player_elos,
        insert_elo_history,
        update_player_elo,
    )

    # Get all sets ordered chronologically
    sets = get_all_sets_for_elo(conn)

    if not sets:
        return {}

    # Load current player ELOs from database
    player_data = get_all_player_elos(conn)
    elos = {pid: data[1] for pid, data in player_data.items()}

    # Track processed sets to avoid duplicates (shouldn't happen with DB but be safe)
    processed = set()

    for set_data in sets:
        set_id = set_data['set_id']

        if set_id in processed:
            continue
        processed.add(set_id)

        # Get player IDs for both teams
        team1_players = (set_data['team1_player1'], set_data['team1_player2'])
        team2_players = (set_data['team2_player1'], set_data['team2_player2'])

        # Get current ELOs
        for pid in team1_players + team2_players:
            if pid not in elos:
                elos[pid] = DEFAULT_ELO

        # Record ELO before for history
        elo_before = {pid: elos[pid] for pid in team1_players + team2_players}

        # Determine winner
        team1_won = set_data['team1_score'] > set_data['team2_score']

        # Update ELOs
        process_set(elos, team1_players, team2_players, team1_won)

        # Record ELO changes in history
        for pid in team1_players + team2_players:
            insert_elo_history(conn, pid, elo_before[pid], elos[pid], set_id)

    # Update final ELOs in players table
    for pid, elo in elos.items():
        update_player_elo(conn, pid, elo)

    # Return player_id -> (cbva_id, elo) mapping
    player_data = get_all_player_elos(conn)
    return player_data


def main():
    """CLI entry point - read results file, output ELO rankings."""
    if len(sys.argv) < 2:
        print("Usage: python calculate_elo.py <results_file>", file=sys.stderr)
        print("Example: python calculate_elo.py data/results_20260112_202747.txt", file=sys.stderr)
        sys.exit(1)

    results_file = sys.argv[1]

    try:
        elos = calculate_all_elos(results_file)
    except FileNotFoundError:
        print(f"Error: File not found: {results_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}", file=sys.stderr)
        sys.exit(1)

    # Sort by ELO descending
    ranked = sorted(elos.items(), key=lambda x: x[1], reverse=True)

    print("# CBVA Player ELO Rankings")
    print(f"# Total players: {len(ranked)}")
    print()

    for rank, (player_id, elo) in enumerate(ranked, 1):
        print(f"{rank:4d}. {player_id:30s} {elo:7.1f}")


if __name__ == "__main__":
    main()
