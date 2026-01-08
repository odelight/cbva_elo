# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python web scraping pipeline for extracting Colorado Beach Volleyball Association (CBVA) tournament data from cbva.com. The extracted data is intended for ELO rating calculations.

## Running Scripts

All scripts are standalone CLI tools with no build system:

```bash
# Stage 1: Get all tournament URLs
python scrape_tournaments.py

# Stage 2: Get team URLs for a tournament
python tournament_to_teams.py <tournament-url>
python tournament_to_teams.py https://cbva.com/t/12345

# Stage 3: Get team data with player IDs and game scores
python teams_page_to_scores.py <team-url>
python teams_page_to_scores.py https://cbva.com/t/12345/teams/67890
```

Scripts accept URLs as command-line arguments or prompt interactively if not provided.

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing

No requirements.txt exists; install dependencies manually: `pip install requests beautifulsoup4 pytest`

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

Three-stage data pipeline:

```
cbva.com/t → scrape_tournaments.py → tournament URLs
                    ↓
tournament URL → tournament_to_teams.py → team URLs
                    ↓
team URL → teams_page_to_scores.py → team_id, player_ids, game results
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
<opponent-team-id> <score1> <score2>
...
```