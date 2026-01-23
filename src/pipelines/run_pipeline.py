#!/usr/bin/env python3
"""
Run the full CBVA scraping pipeline end-to-end.

Stages:
1. Scrape all tournament URLs from cbva.com/t
2. For each tournament, scrape all team URLs
3. For each team, scrape player IDs and game results
4. Calculate ELO ratings for all players

Data is stored in the PostgreSQL database.
"""

import argparse
import os
import re
import sys

# Add project root to path for db imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .scrape_tournaments import scrape_cbva_links, get_tournament_date
from .tournament_to_teams import scrape_tournament_team_links
from .teams_page_to_scores import scrape_team_page
from .calculate_elo import calculate_all_elos_from_db

from db import (
    get_connection,
    get_or_create_player,
    get_or_create_tournament,
    get_or_create_team,
    get_team_by_cbva_id,
    insert_match,
    insert_set,
)


def extract_tournament_id(url):
    """Extract tournament ID from URL like https://cbva.com/t/19Xt68go"""
    match = re.search(r'/t/([^/]+)', url)
    return match.group(1) if match else None


def extract_team_id(url):
    """Extract team ID from URL like https://cbva.com/t/19Xt68go/teams/gs0cxnVR"""
    match = re.search(r'/teams/([^/]+)', url)
    return match.group(1) if match else None


def run_pipeline(limit=None):
    """Run the full scraping pipeline.

    Args:
        limit: Maximum number of tournaments to process (None for all)
    """
    print("Connecting to database...")
    conn = get_connection()

    try:
        # Stage 1: Get all tournament URLs
        print("\nStage 1: Scraping tournament URLs...")
        tournaments = scrape_cbva_links()
        print(f"  Found {len(tournaments)} tournaments")

        if limit is not None:
            tournaments = tournaments[:limit]
            print(f"  Limiting to first {len(tournaments)} tournaments")

        tournament_db_ids = {}  # url -> db_id
        for i, url in enumerate(tournaments):
            cbva_id = extract_tournament_id(url)
            if cbva_id:
                tournament_date = get_tournament_date(url)
                print(f"  [{i+1}/{len(tournaments)}] {cbva_id} ({tournament_date})")
                db_id = get_or_create_tournament(conn, cbva_id, url, tournament_date=tournament_date)
                tournament_db_ids[url] = db_id
        conn.commit()
        print(f"  Inserted/updated {len(tournament_db_ids)} tournaments in database")

        # Stage 2: Get team URLs for each tournament
        print("\nStage 2: Scraping team URLs...")
        all_team_urls = []
        team_tournament_map = {}  # team_url -> tournament_url

        for i, tournament_url in enumerate(tournaments):
            print(f"  [{i+1}/{len(tournaments)}] {tournament_url}")
            team_urls = scrape_tournament_team_links(tournament_url)
            print(f"    Found {len(team_urls)} teams")

            for url in team_urls:
                all_team_urls.append(url)
                team_tournament_map[url] = tournament_url

        print(f"  Total teams: {len(all_team_urls)}")

        # Stage 3: Get player IDs and game results for each team
        print("\nStage 3: Scraping team data and game results...")

        # Track teams we've processed for match insertion
        team_db_ids = {}  # (tournament_db_id, cbva_team_id) -> team_db_id

        for i, team_url in enumerate(all_team_urls):
            print(f"  [{i+1}/{len(all_team_urls)}] {team_url}")
            team_id, player_ids, games = scrape_team_page(team_url)

            if not team_id or len(player_ids) < 2:
                print(f"    Skipping (incomplete data)")
                continue

            tournament_url = team_tournament_map[team_url]
            tournament_db_id = tournament_db_ids.get(tournament_url)
            if not tournament_db_id:
                continue

            # Create players
            player1_db_id = get_or_create_player(conn, player_ids[0])
            player2_db_id = get_or_create_player(conn, player_ids[1])

            # Create team
            team_db_id = get_or_create_team(
                conn, team_id, tournament_db_id, player1_db_id, player2_db_id
            )
            team_db_ids[(tournament_db_id, team_id)] = team_db_id

            # Insert matches and sets
            for game in games:
                opponent_team_id = game['opponent_team_id']
                opponent_key = (tournament_db_id, opponent_team_id)

                # Get opponent's database ID (if they've been processed)
                opponent_db_id = team_db_ids.get(opponent_key)

                if not opponent_db_id:
                    # Opponent not yet in our map - try to look them up
                    opponent_info = get_team_by_cbva_id(conn, opponent_team_id, tournament_db_id)
                    if opponent_info:
                        opponent_db_id = opponent_info[0]
                        team_db_ids[opponent_key] = opponent_db_id

                if not opponent_db_id:
                    # Opponent not in database yet, skip this match for now
                    # It will be inserted when we process the opponent's team page
                    continue

                # Insert match (will be skipped if already exists due to UNIQUE constraint)
                match_type = game.get('match_type')
                match_name = game.get('match_name')
                match_db_id = insert_match(conn, tournament_db_id, team_db_id, opponent_db_id,
                                          match_type=match_type, match_name=match_name)

                if match_db_id:
                    # New match - insert sets
                    # Determine score order based on which team is team1 in the match
                    # Matches are stored with smaller team_id first
                    is_team1 = team_db_id < opponent_db_id

                    for set_num, (our_score, their_score) in enumerate(game['sets'], 1):
                        if is_team1:
                            team1_score, team2_score = our_score, their_score
                        else:
                            team1_score, team2_score = their_score, our_score
                        insert_set(conn, match_db_id, set_num, team1_score, team2_score)
                else:
                    # Match already exists - sets were inserted when opponent was processed
                    pass

            # Commit after each team to avoid losing too much progress on error
            conn.commit()

        print(f"  Processed {len(all_team_urls)} teams")

        # Stage 4: Calculate ELO ratings
        print("\nStage 4: Calculating ELO ratings...")
        elos = calculate_all_elos_from_db(conn)
        conn.commit()
        print(f"  Calculated ratings for {len(elos)} players")

        # Print top 20 players
        print("\nTop 20 Players by ELO:")
        ranked = sorted(elos.items(), key=lambda x: x[1][1], reverse=True)[:20]
        for rank, (_, (cbva_id, elo)) in enumerate(ranked, 1):
            print(f"  {rank:2d}. {cbva_id:30s} {elo:7.1f}")

        print("\nPipeline complete!")
        print(f"  Use 'psql -d cbva_elo' to query the database")

    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full CBVA scraping pipeline")
    parser.add_argument(
        "-n",
        type=int,
        metavar="NUM_TOURNAMENTS",
        help="Limit to first N tournaments (useful for testing)",
    )
    args = parser.parse_args()
    run_pipeline(limit=args.n)
