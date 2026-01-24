import requests
from bs4 import BeautifulSoup
import re
import sys

from . import http_client

def scrape_tournament_team_links(tournament_url):
    """
    Scrapes all team links from a CBVA tournament page.
    Extracts links matching the pattern: https://cbva.com/t/<ID>/teams/.*
    
    Args:
        tournament_url: URL of the form "https://cbva.com/t/<ID>"
    
    Returns:
        List of team URLs
    """
    try:
        # Validate the tournament URL format
        tournament_pattern = re.compile(r'^https://cbva\.com/t/[^/]+$')
        if not tournament_pattern.match(tournament_url):
            print(f"Error: Invalid tournament URL format. Expected https://cbva.com/t/<ID>")
            return []
        
        # Extract the tournament ID
        tournament_id = tournament_url.split('/t/')[-1]
        
        # Append /teams to the URL
        teams_url = f"{tournament_url}/teams"
        
        # Fetch the teams page
        response = http_client.get(teams_url)
        response.raise_for_status()
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        
        # Pattern to match team links for this specific tournament
        team_pattern = re.compile(rf'^https://cbva\.com/t/{re.escape(tournament_id)}/teams/.+')
        # Pattern to exclude pool links
        pool_pattern = re.compile(rf'^https://cbva\.com/t/{re.escape(tournament_id)}/teams/\.\./pools/.+')
        
        # Extract and filter team links
        team_links = []
        for link in all_links:
            href = link['href']
            
            # Handle relative URLs
            if href.startswith(f'/t/{tournament_id}/teams/'):
                href = f"https://cbva.com{href}"
            
            # Check if it matches the team pattern but NOT the pool pattern
            if team_pattern.match(href) and not pool_pattern.match(href):
                team_links.append(href)
        
        # Remove duplicates while preserving order
        unique_team_links = list(dict.fromkeys(team_links))
        
        return unique_team_links
        
    except requests.RequestException as e:
        print(f"Error fetching the page: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

if __name__ == "__main__":
    # Check if URL was provided as command line argument
    if len(sys.argv) > 1:
        tournament_url = sys.argv[1]
    else:
        # Prompt for URL if not provided
        tournament_url = input("Enter CBVA tournament URL (e.g., https://cbva.com/t/12345): ").strip()
    
    if not tournament_url:
        print("Error: No URL provided")
        sys.exit(1)
    
    team_links = scrape_tournament_team_links(tournament_url)
    
    if team_links:
        for link in team_links:
            print(link)
    else:
        print("No team links found or an error occurred.", file=sys.stderr)