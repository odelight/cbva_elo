# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python web scraping pipeline for extracting Colorado Beach Volleyball Association (CBVA) tournament data from cbva.com. The extracted data is stored in a PostgreSQL database and used for ELO rating calculations.

## Running Scripts

### Full Pipeline

Run the entire pipeline end-to-end, storing results in the PostgreSQL database:

```bash
python -m src.pipelines.run_pipeline
```

This scrapes all tournaments, teams, matches, and sets, then calculates ELO ratings for all players.

### Individual Stages

Scripts can also be run individually in the `src/pipelines/` directory:

```bash
# Stage 1: Get all tournament URLs
python -m src.pipelines.scrape_tournaments

# Stage 2: Get team URLs for a tournament
python -m src.pipelines.tournament_to_teams <tournament-url>
python -m src.pipelines.tournament_to_teams https://cbva.com/t/12345

# Stage 3: Get team data with player IDs and game scores
python -m src.pipelines.teams_page_to_scores <team-url>
python -m src.pipelines.teams_page_to_scores https://cbva.com/t/12345/teams/67890

# Stage 4: Calculate ELO from results file (standalone)
python -m src.pipelines.calculate_elo <results-file>
```

Scripts accept URLs as command-line arguments or prompt interactively if not provided.

### Web Service

Run the Flask web service:

```bash
python -m src.services.web
```

Then open http://localhost:5000 in your browser.

## Database Setup

### Prerequisites

Install PostgreSQL:
```bash
brew install postgresql@16
brew services start postgresql@16
```

### Create Database

```bash
createdb cbva_elo
psql -d cbva_elo -f db/schema.sql
```

### Configuration

Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

Default configuration works for local development with no password.

### Database Schema

- `players` - Player IDs and current ELO ratings
- `tournaments` - Tournament metadata
- `teams` - Team compositions (pairs of players per tournament)
- `matches` - Matches between teams
- `sets` - Individual set scores
- `elo_history` - ELO rating changes over time

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `psycopg2-binary` - PostgreSQL database driver
- `flask` - Web framework

Install dependencies: `pip install requests beautifulsoup4 psycopg2-binary pytest flask`

## Testing

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run a single test file
python -m pytest tests/test_scrape_tournaments.py
```

Tests are integration tests that run against live cbva.com.

## Architecture

Four-stage data pipeline:

```
cbva.com/t → scrape_tournaments.py → tournament URLs → DB: tournaments
                    ↓
tournament URL → tournament_to_teams.py → team URLs → DB: players, teams
                    ↓
team URL → teams_page_to_scores.py → game results → DB: matches, sets
                    ↓
DB data → calculate_elo.py → ELO ratings → DB: elo_history, players.current_elo
```

### URL Patterns

- Tournament list: `https://cbva.com/t`
- Tournament page: `https://cbva.com/t/<tournament-id>`
- Team page: `https://cbva.com/t/<tournament-id>/teams/<team-id>`
- Player page: `https://cbva.com/p/<player-id>`

### Output Formats

`teams_page_to_scores.py` outputs:
```
<team-id> <player1-id> <player2-id>
<opponent-team-id> <set1-our>-<set1-their> <set2-our>-<set2-their> ...
...
```

Example output:
```
gs0cxnVR troyfitzgerald ayrtongarciajurado
c3BatH1k 13-21 10-21
5SmBMlDh 21-16 21-19
```

The function returns `(team_id, player_ids, games)` where each game is a dict:
```python
{
    'opponent_team_id': str,
    'sets': [(our_score, their_score), ...]  # e.g., [(21, 19), (18, 21)]
}
```

## Querying the Database

```bash
# Connect to database
psql -d cbva_elo

# View top players by ELO
SELECT cbva_id, current_elo FROM players ORDER BY current_elo DESC LIMIT 20;

# Count records
SELECT
    (SELECT COUNT(*) FROM players) as players,
    (SELECT COUNT(*) FROM tournaments) as tournaments,
    (SELECT COUNT(*) FROM teams) as teams,
    (SELECT COUNT(*) FROM matches) as matches,
    (SELECT COUNT(*) FROM sets) as sets;
```
