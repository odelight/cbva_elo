import requests
from bs4 import BeautifulSoup
import re
import sys

def scrape_team_page(team_url):
    """
    Scrapes team and game information from a CBVA team page.

    Args:
        team_url: URL of the form "https://cbva.com/t/<tournament-id>/teams/<team-id>"

    Returns:
        Tuple of (team_id, player_ids, games)
    """
    try:
        # Validate the team URL format
        team_pattern = re.compile(r'^https://cbva\.com/t/([^/]+)/teams/([^/]+)$')
        match = team_pattern.match(team_url)

        if not match:
            print(f"Error: Invalid team URL format. Expected https://cbva.com/t/<tournament-id>/teams/<team-id>", file=sys.stderr)
            return None, [], []

        tournament_id = match.group(1)
        team_id = match.group(2)

        # Fetch the page
        response = requests.get(team_url)
        response.raise_for_status()

        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the first two player links
        all_links = soup.find_all('a', href=True)
        player_pattern = re.compile(r'^https://cbva\.com/p/([^/]+)$')

        player_ids = []
        for link in all_links:
            href = link['href']

            # Handle relative URLs
            if href.startswith('/p/'):
                href = f"https://cbva.com{href}"

            # Check if it's a player link
            player_match = player_pattern.match(href)
            if player_match:
                player_ids.append(player_match.group(1))
                if len(player_ids) == 2:
                    break

        # Find game elements and extract opponent team IDs and scores
        games = []

        # Find all tables containing game information
        tables = soup.find_all('table')

        opponent_team_pattern = re.compile(rf'^/t/{re.escape(tournament_id)}/teams/([^/]+)')

        for table in tables:
            # Find all rows in the table
            rows = table.find_all('tr')

            if len(rows) < 2:
                continue

            # Look for team links in the first row (team names)
            team_row = rows[0]
            team_cells = team_row.find_all('td')

            if len(team_cells) != 2:
                continue

            # Find team links in both cells
            team1_links = team_cells[0].find_all('a', href=opponent_team_pattern)
            team2_links = team_cells[1].find_all('a', href=opponent_team_pattern)

            # Extract team IDs
            team1_id = None
            team2_id = None

            for link in team1_links:
                match = opponent_team_pattern.search(link['href'])
                if match:
                    team1_id = match.group(1)
                    break

            for link in team2_links:
                match = opponent_team_pattern.search(link['href'])
                if match:
                    team2_id = match.group(1)
                    break

            # Look for scores in the second row
            if len(rows) >= 2:
                score_row = rows[1]
                score_cells = score_row.find_all('td')

                if len(score_cells) == 2:
                    score1_text = score_cells[0].get_text(strip=True)
                    score2_text = score_cells[1].get_text(strip=True)

                    # Try to parse as integers
                    try:
                        score1 = int(score1_text)
                        score2 = int(score2_text)

                        # Determine which team is the opponent
                        if team1_id == team_id and team2_id and team2_id != team_id:
                            games.append({
                                'opponent_team_id': team2_id,
                                'score1': score1,
                                'score2': score2
                            })
                        elif team2_id == team_id and team1_id and team1_id != team_id:
                            games.append({
                                'opponent_team_id': team1_id,
                                'score1': score2,
                                'score2': score1
                            })
                    except ValueError:
                        # Skip if scores aren't valid integers
                        pass

        return team_id, player_ids, games

    except requests.RequestException as e:
        print(f"Error fetching the page: {e}", file=sys.stderr)
        return None, [], []
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        return None, [], []

if __name__ == "__main__":
    # Check if URL was provided as command line argument
    if len(sys.argv) > 1:
        team_url = sys.argv[1]
    else:
        # Prompt for URL if not provided
        team_url = input("Enter CBVA team URL: ").strip()

    if not team_url:
        print("Error: No URL provided", file=sys.stderr)
        sys.exit(1)

    team_id, player_ids, games = scrape_team_page(team_url)

    if team_id:
        # Output team ID and player IDs
        print(f"{team_id} {' '.join(player_ids)}")

        # Output games
        for game in games:
            print(f"{game['opponent_team_id']} {game['score1']} {game['score2']}")
    else:
        print("Failed to scrape team page.", file=sys.stderr)
