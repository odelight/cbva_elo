import sys
sys.path.insert(0, '.')

from src.pipelines.scrape_tournaments import scrape_cbva_links
from src.pipelines.tournament_to_teams import scrape_tournament_team_links
from src.pipelines.teams_page_to_scores import scrape_team_page


def get_team_url():
    """Get a real team URL from the site for testing."""
    tournaments = scrape_cbva_links()
    assert len(tournaments) > 0, "Need at least one tournament to test"

    team_links = scrape_tournament_team_links(tournaments[0])
    assert len(team_links) > 0, "Need at least one team to test"

    return team_links[0]


def test_scrape_team_page_returns_tuple():
    """Test that scraping returns a tuple of (team_id, player_ids, games)."""
    team_url = get_team_url()
    result = scrape_team_page(team_url)

    assert isinstance(result, tuple)
    assert len(result) == 3


def test_scrape_team_page_returns_team_id():
    """Test that team_id is extracted correctly."""
    team_url = get_team_url()
    team_id, player_ids, games = scrape_team_page(team_url)

    assert team_id is not None
    assert isinstance(team_id, str)
    assert len(team_id) > 0


def test_scrape_team_page_returns_player_ids():
    """Test that player_ids is a list."""
    team_url = get_team_url()
    team_id, player_ids, games = scrape_team_page(team_url)

    assert isinstance(player_ids, list)


def test_scrape_team_page_returns_games_list():
    """Test that games is a list."""
    team_url = get_team_url()
    team_id, player_ids, games = scrape_team_page(team_url)

    assert isinstance(games, list)


def test_games_contain_opponent_team_id():
    """Test that each game has an opponent_team_id."""
    team_url = get_team_url()
    team_id, player_ids, games = scrape_team_page(team_url)

    for game in games:
        assert 'opponent_team_id' in game
        assert isinstance(game['opponent_team_id'], str)
        assert len(game['opponent_team_id']) > 0


def test_games_contain_sets():
    """Test that each game has a sets list with score tuples."""
    team_url = get_team_url()
    team_id, player_ids, games = scrape_team_page(team_url)

    for game in games:
        assert 'sets' in game
        assert isinstance(game['sets'], list)
        assert len(game['sets']) > 0  # At least one set per game


def test_set_scores_are_integer_tuples():
    """Test that each set score is a tuple of two non-negative integers."""
    team_url = get_team_url()
    team_id, player_ids, games = scrape_team_page(team_url)

    for game in games:
        for set_score in game['sets']:
            assert isinstance(set_score, tuple)
            assert len(set_score) == 2
            assert isinstance(set_score[0], int)
            assert isinstance(set_score[1], int)
            assert set_score[0] >= 0
            assert set_score[1] >= 0


def test_scrape_team_page_invalid_url():
    """Test that invalid URLs return None and empty lists."""
    result = scrape_team_page("https://cbva.com/invalid")
    assert result == (None, [], [])
