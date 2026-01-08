import sys
sys.path.insert(0, '.')

from scrape_tournaments import scrape_cbva_links
from tournament_to_teams import scrape_tournament_team_links
from teams_page_to_scores import scrape_team_page


def test_scrape_team_page_returns_tuple():
    """Test that scraping returns a tuple of (team_id, player_ids, games)."""
    # Get a real team URL from the site
    tournaments = scrape_cbva_links()
    assert len(tournaments) > 0, "Need at least one tournament to test"

    team_links = scrape_tournament_team_links(tournaments[0])
    assert len(team_links) > 0, "Need at least one team to test"

    team_url = team_links[0]
    result = scrape_team_page(team_url)

    assert isinstance(result, tuple)
    assert len(result) == 3


def test_scrape_team_page_returns_team_id():
    """Test that team_id is extracted correctly."""
    tournaments = scrape_cbva_links()
    assert len(tournaments) > 0, "Need at least one tournament to test"

    team_links = scrape_tournament_team_links(tournaments[0])
    assert len(team_links) > 0, "Need at least one team to test"

    team_url = team_links[0]
    team_id, player_ids, games = scrape_team_page(team_url)

    assert team_id is not None
    assert isinstance(team_id, str)
    assert len(team_id) > 0


def test_scrape_team_page_returns_player_ids():
    """Test that player_ids is a list."""
    tournaments = scrape_cbva_links()
    assert len(tournaments) > 0, "Need at least one tournament to test"

    team_links = scrape_tournament_team_links(tournaments[0])
    assert len(team_links) > 0, "Need at least one team to test"

    team_url = team_links[0]
    team_id, player_ids, games = scrape_team_page(team_url)

    assert isinstance(player_ids, list)


def test_scrape_team_page_returns_games_list():
    """Test that games is a list."""
    tournaments = scrape_cbva_links()
    assert len(tournaments) > 0, "Need at least one tournament to test"

    team_links = scrape_tournament_team_links(tournaments[0])
    assert len(team_links) > 0, "Need at least one team to test"

    team_url = team_links[0]
    team_id, player_ids, games = scrape_team_page(team_url)

    assert isinstance(games, list)


def test_scrape_team_page_invalid_url():
    """Test that invalid URLs return None and empty lists."""
    result = scrape_team_page("https://cbva.com/invalid")
    assert result == (None, [], [])
