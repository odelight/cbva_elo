from bs4 import BeautifulSoup
import re
import requests
from datetime import date

from . import http_client


def get_tournament_info(tournament_url):
    """
    Fetch tournament info (date and name) from the tournament info page.

    Args:
        tournament_url: URL like https://cbva.com/t/bwQRIBvO

    Returns:
        Dict with 'date' and 'name' keys, values may be None
    """
    result = {'date': None, 'name': None}
    try:
        info_url = tournament_url.rstrip('/') + '/info'
        response = http_client.get(info_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Get date
        date_input = soup.find('input', {'type': 'date'})
        if date_input and date_input.get('value'):
            date_str = date_input['value']  # Format: YYYY-MM-DD
            year, month, day = map(int, date_str.split('-'))
            result['date'] = date(year, month, day)

        # Get name from text input
        name_input = soup.find('input', {'type': 'text'})
        if name_input and name_input.get('value'):
            result['name'] = name_input['value']

        return result
    except Exception as e:
        print(f"Error fetching info for {tournament_url}: {e}")
        return result


def get_tournament_date(tournament_url):
    """
    Fetch the tournament date from the tournament info page.

    Args:
        tournament_url: URL like https://cbva.com/t/bwQRIBvO

    Returns:
        date object or None if not found
    """
    return get_tournament_info(tournament_url)['date']


def _scrape_year_page(url):
    """
    Scrapes tournament links from a single year page.

    Args:
        url: URL like https://cbva.com/t?y=2024

    Returns:
        List of tournament URLs
    """
    try:
        response = http_client.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        all_links = soup.find_all('a', href=True)

        # Pattern to match tournament URLs (not year selector links)
        pattern = re.compile(r'^https://cbva\.com/t/[^?].+')

        matching_links = []
        for link in all_links:
            href = link['href']

            # Handle relative URLs
            if href.startswith('/t/') and '?' not in href:
                href = f"https://cbva.com{href}"

            if pattern.match(href):
                matching_links.append(href)

        return matching_links

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"An error occurred fetching {url}: {e}")
        return []


def scrape_cbva_links(start_year=None, end_year=1997):
    """
    Scrapes all tournament links from cbva.com across multiple years.

    Args:
        start_year: Starting year (default: current year)
        end_year: Ending year (default: 1997)

    Returns:
        List of unique tournament URLs
    """
    if start_year is None:
        start_year = date.today().year

    all_links = []

    for year in range(start_year, end_year - 1, -1):
        url = f"https://cbva.com/t?y={year}"
        print(f"  Scraping {year}...")
        links = _scrape_year_page(url)
        print(f"    Found {len(links)} tournaments")
        all_links.extend(links)

    # Remove duplicates while preserving order
    unique_links = list(dict.fromkeys(all_links))
    return unique_links

if __name__ == "__main__":
    links = scrape_cbva_links()

    print(f"Found {len(links)} unique links:\n")
    for link in links[:5]:  # Show first 5 with dates
        tournament_date = get_tournament_date(link)
        print(f"{tournament_date}  {link}")
    if len(links) > 5:
        print(f"... and {len(links) - 5} more")
