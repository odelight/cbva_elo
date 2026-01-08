import requests
from bs4 import BeautifulSoup
import re
import sys

def scrape_tournament_team_links(tournament_url, debug=False):
    """
    Scrapes all team links from a CBVA tournament page.
    Extracts links matching the pattern: https://cbva.com/t/<ID>/teams/.*
    
    Args:
        tournament_url: URL of the form "https://cbva.com/t/<ID>"
        debug: If True, prints debugging information
    
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
        
        if debug:
            print(f"Visiting: {teams_url}\n")
        
        # Fetch the teams page
        response = requests.get(teams_url)
        response.raise_for_status()
        
        if debug:
            print(f"✓ Successfully fetched page (status code: {response.status_code})")
            print(f"✓ Page size: {len(response.text)} characters")
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        
        if debug:
            print(f"✓ Found {len(all_links)} total links on the page")
            print(f"✓ Looking for pattern: https://cbva.com/t/{tournament_id}/teams/.*")
            print("\nAll links found:")
            for i, link in enumerate(all_links[:20], 1):  # Show first 20 links
                print(f"  {i}. {link['href']}")
            if len(all_links) > 20:
                print(f"  ... and {len(all_links) - 20} more")
            print()
        
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
                if debug:
                    print(f"  ✓ Match: {href}")
            elif debug and '/teams/' in href:
                if pool_pattern.match(href):
                    print(f"  ✗ Excluded (pool link): {href}")
                else:
                    print(f"  ✗ Near miss: {href}")
        
        if debug:
            print(f"\n✓ Found {len(team_links)} team links (before deduplication)")
        
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
    
    team_links = scrape_tournament_team_links(tournament_url, debug=True)
    
    if team_links:
        print(f"Found {len(team_links)} unique team links:\n")
        for link in team_links:
            print(link)
    else:
        print("No team links found or an error occurred.")