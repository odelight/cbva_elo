#!/usr/bin/env python3
"""
Run the full CBVA scraping pipeline end-to-end.

Stages:
1. Scrape all tournament URLs from cbva.com/t
2. For each tournament, scrape all team URLs
3. For each team, scrape player IDs and game results
4. Calculate ELO ratings for all players

Outputs are saved to text files in the data/ directory.
"""

import os
import sys
from datetime import datetime

from scrape_tournaments import scrape_cbva_links
from tournament_to_teams import scrape_tournament_team_links
from teams_page_to_scores import scrape_team_page
from calculate_elo import calculate_all_elos


def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def run_pipeline():
    """Run the full scraping pipeline."""
    data_dir = ensure_data_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Stage 1: Get all tournament URLs
    print("Stage 1: Scraping tournament URLs...")
    tournaments = scrape_cbva_links()
    print(f"  Found {len(tournaments)} tournaments")

    tournaments_file = os.path.join(data_dir, f'tournaments_{timestamp}.txt')
    with open(tournaments_file, 'w') as f:
        for url in tournaments:
            f.write(f"{url}\n")
    print(f"  Saved to {tournaments_file}")

    # Stage 2: Get team URLs for each tournament
    print("\nStage 2: Scraping team URLs...")
    all_team_urls = []
    teams_file = os.path.join(data_dir, f'teams_{timestamp}.txt')

    with open(teams_file, 'w') as f:
        for i, tournament_url in enumerate(tournaments):
            print(f"  [{i+1}/{len(tournaments)}] {tournament_url}")
            team_urls = scrape_tournament_team_links(tournament_url)
            print(f"    Found {len(team_urls)} teams")

            for url in team_urls:
                f.write(f"{url}\n")
                all_team_urls.append(url)

    print(f"  Total teams: {len(all_team_urls)}")
    print(f"  Saved to {teams_file}")

    # Stage 3: Get player IDs and game results for each team
    print("\nStage 3: Scraping team data and game results...")
    results_file = os.path.join(data_dir, f'results_{timestamp}.txt')

    with open(results_file, 'w') as f:
        for i, team_url in enumerate(all_team_urls):
            print(f"  [{i+1}/{len(all_team_urls)}] {team_url}")
            team_id, player_ids, games = scrape_team_page(team_url)

            if team_id:
                # Write team header
                f.write(f"{team_id} {' '.join(player_ids)}\n")

                # Write game results
                for game in games:
                    set_scores = ' '.join(f"{s[0]}-{s[1]}" for s in game['sets'])
                    f.write(f"{game['opponent_team_id']} {set_scores}\n")

                # Blank line between teams
                f.write("\n")

    print(f"  Saved to {results_file}")

    # Stage 4: Calculate ELO ratings
    print("\nStage 4: Calculating ELO ratings...")
    elos = calculate_all_elos(results_file)
    print(f"  Calculated ratings for {len(elos)} players")

    elo_file = os.path.join(data_dir, f'elo_{timestamp}.txt')
    ranked = sorted(elos.items(), key=lambda x: x[1], reverse=True)

    with open(elo_file, 'w') as f:
        f.write("# CBVA Player ELO Rankings\n")
        f.write(f"# Total players: {len(ranked)}\n\n")
        for rank, (player_id, elo) in enumerate(ranked, 1):
            f.write(f"{rank:4d}. {player_id:30s} {elo:7.1f}\n")

    print(f"  Saved to {elo_file}")

    print("\nPipeline complete!")
    print(f"  Tournaments: {tournaments_file}")
    print(f"  Teams: {teams_file}")
    print(f"  Results: {results_file}")
    print(f"  ELO Rankings: {elo_file}")


if __name__ == "__main__":
    run_pipeline()