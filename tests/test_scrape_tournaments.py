import re
import sys
sys.path.insert(0, '.')

from src.scrape_tournaments import scrape_cbva_links


def test_scrape_cbva_links_returns_list():
    """Test that scraping returns a list of URLs."""
    links = scrape_cbva_links()
    assert isinstance(links, list)


def test_scrape_cbva_links_returns_tournament_urls():
    """Test that returned URLs match the expected pattern."""
    links = scrape_cbva_links()
    assert len(links) > 0, "Expected at least one tournament link"

    pattern = re.compile(r'^https://cbva\.com/t/.+')
    for link in links:
        assert pattern.match(link), f"Link does not match pattern: {link}"


def test_scrape_cbva_links_no_duplicates():
    """Test that there are no duplicate URLs."""
    links = scrape_cbva_links()
    assert len(links) == len(set(links)), "Found duplicate links"
