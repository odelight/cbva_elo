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


def scrape_cbva_links(url="https://cbva.com/t"):
    """
    Scrapes all links from the given URL that match the pattern https://cbva.com/t/.*
    """
    try:
        # Fetch the page
        response = http_client.get(url)
        response.raise_for_status()
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        
        # Pattern to match https://cbva.com/t/.*
        pattern = re.compile(r'^https://cbva\.com/t/.+')
        
        # Extract and filter links
        matching_links = []
        for link in all_links:
            href = link['href']
            
            # Handle relative URLs
            if href.startswith('/t/') and not href == '/t':
                href = f"https://cbva.com{href}"
            
            # Check if it matches the pattern
            if pattern.match(href):
                matching_links.append(href)
        
        # Remove duplicates while preserving order
        unique_links = list(dict.fromkeys(matching_links))
        
        return unique_links
        
    except requests.RequestException as e:
        print(f"Error fetching the page: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

if __name__ == "__main__":
    links = scrape_cbva_links()

    print(f"Found {len(links)} unique links:\n")
    for link in links[:5]:  # Show first 5 with dates
        tournament_date = get_tournament_date(link)
        print(f"{tournament_date}  {link}")
    if len(links) > 5:
        print(f"... and {len(links) - 5} more")
