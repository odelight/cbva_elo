import requests
from bs4 import BeautifulSoup
import re
import sys
import json


def extract_json_data(html_content):
    """
    Extract embedded JSON data from CBVA page HTML.

    The site uses client-side rendering with JSON embedded in a script tag
    in the pattern: let val = "...escaped JSON...";
    """
    # Find the JSON data embedded in the script
    pattern = r'let val = "(.+?)";'
    match = re.search(pattern, html_content)

    if not match:
        return None

    json_string = match.group(1)
    # Unescape the JSON string (handles \" and \\ escapes)
    json_string = json_string.encode().decode('unicode_escape')

    try:
        data = json.loads(json_string)
        # Data is wrapped in {"Ok": {...}} structure
        if isinstance(data, dict) and 'Ok' in data:
            return data['Ok']
        return data
    except json.JSONDecodeError:
        return None


def extract_matches_from_data(data, team_id):
    """
    Extract all matches involving the given team from tournament data.

    Returns list of dicts with opponent_team_id and sets (list of score tuples).
    """
    games = []

    # Collect matches from playoffs and pool play
    match_sources = []
    if 'playoffs' in data and data['playoffs']:
        match_sources.extend(data['playoffs'])
    # Pool play matches are nested inside pools[].series
    if 'pools' in data and data['pools']:
        for pool in data['pools']:
            if 'series' in pool and pool['series']:
                match_sources.extend(pool['series'])

    for match in match_sources:
        team_a = match.get('team_a_url')
        team_b = match.get('team_b_url')
        match_games = match.get('games', [])

        # Check if this match involves our team
        if team_a == team_id:
            opponent_id = team_b
            is_team_a = True
        elif team_b == team_id:
            opponent_id = team_a
            is_team_a = False
        else:
            continue

        if not opponent_id:
            continue

        # Extract individual set scores
        sets = []
        for game in match_games:
            scores = game.get('scores')
            if scores and len(scores) == 2:
                if is_team_a:
                    # Our score is first (team_a)
                    sets.append((scores[0], scores[1]))
                else:
                    # Our score is second (team_b), so flip
                    sets.append((scores[1], scores[0]))

        if sets:  # Only add if we have score data
            games.append({
                'opponent_team_id': opponent_id,
                'sets': sets
            })

    return games


def scrape_team_page(team_url):
    """
    Scrapes team and game information from a CBVA team page.

    Args:
        team_url: URL of the form "https://cbva.com/t/<tournament-id>/teams/<team-id>"

    Returns:
        Tuple of (team_id, player_ids, games)
        where games is a list of dicts with 'opponent_team_id' and 'sets' keys.
        Each set is a tuple of (our_score, their_score).
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

        html_content = response.text

        # Parse the HTML for player links
        soup = BeautifulSoup(html_content, 'html.parser')

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

        # Extract JSON data and parse matches
        games = []
        json_data = extract_json_data(html_content)
        if json_data:
            games = extract_matches_from_data(json_data, team_id)

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

        # Output games with individual set scores
        for game in games:
            set_scores = ' '.join(f"{s[0]}-{s[1]}" for s in game['sets'])
            print(f"{game['opponent_team_id']} {set_scores}")
    else:
        print("Failed to scrape team page.", file=sys.stderr)
