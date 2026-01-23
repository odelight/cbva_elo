import re
import sys
sys.path.insert(0, '.')

from src.pipelines.scrape_tournaments import scrape_cbva_links
from src.pipelines.tournament_to_teams import scrape_tournament_team_links


def test_scrape_tournament_team_links_returns_list():
    """Test that scraping returns a list."""
    # Get a real tournament URL from the site
    tournaments = scrape_cbva_links()
    assert len(tournaments) > 0, "Need at least one tournament to test"

    tournament_url = tournaments[0]
    team_links = scrape_tournament_team_links(tournament_url)
    assert isinstance(team_links, list)


def test_scrape_tournament_team_links_returns_team_urls():
    """Test that returned URLs match the expected team URL pattern."""
    tournaments = scrape_cbva_links()
    assert len(tournaments) > 0, "Need at least one tournament to test"

    tournament_url = tournaments[0]
    tournament_id = tournament_url.split('/t/')[-1]

    team_links = scrape_tournament_team_links(tournament_url)

    pattern = re.compile(rf'^https://cbva\.com/t/{re.escape(tournament_id)}/teams/.+')
    for link in team_links:
        assert pattern.match(link), f"Link does not match pattern: {link}"


def test_scrape_tournament_team_links_no_duplicates():
    """Test that there are no duplicate URLs."""
    tournaments = scrape_cbva_links()
    assert len(tournaments) > 0, "Need at least one tournament to test"

    tournament_url = tournaments[0]
    team_links = scrape_tournament_team_links(tournament_url)
    assert len(team_links) == len(set(team_links)), "Found duplicate links"


def test_scrape_tournament_team_links_invalid_url():
    """Test that invalid URLs return empty list."""
    result = scrape_tournament_team_links("https://cbva.com/invalid")
    assert result == []
