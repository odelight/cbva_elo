"""Scrape player information from CBVA player pages."""

import requests
import re
import json
import codecs
import sys

from . import http_client


def extract_json_data(html_content):
    """
    Extract embedded JSON data from CBVA page HTML.

    The site uses client-side rendering with JSON embedded in a script tag
    in the pattern: let val = "...escaped JSON...";
    """
    pattern = r'let val = "(.+?)";'
    match = re.search(pattern, html_content)

    if not match:
        return None

    json_string = match.group(1)

    # Convert Rust-style unicode escapes \u{XX} to standard \uXXXX format
    def convert_rust_unicode(m):
        hex_val = m.group(1)
        return f'\\u{hex_val.zfill(4)}'

    json_string = re.sub(r'\\u\{([0-9a-fA-F]+)\}', convert_rust_unicode, json_string)
    json_string = codecs.decode(json_string, 'unicode_escape')

    try:
        data = json.loads(json_string)
        if isinstance(data, dict) and 'Ok' in data:
            return data['Ok']
        return data
    except json.JSONDecodeError:
        return None


def scrape_player_rating(cbva_id):
    """
    Scrape a player's CBVA rating from their profile page.

    Args:
        cbva_id: Player's CBVA identifier (e.g., "abudulad")

    Returns:
        Rating string (e.g., "AAA", "AA", "A", "B") or None if not found
    """
    url = f"https://cbva.com/p/{cbva_id}"

    try:
        response = http_client.get(url)
        response.raise_for_status()

        data = extract_json_data(response.text)
        if data and isinstance(data, dict):
            rating = data.get('rating')
            if rating:
                return rating

        return None

    except requests.RequestException as e:
        print(f"Error fetching player {cbva_id}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error parsing player {cbva_id}: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cbva_id = sys.argv[1]
    else:
        cbva_id = input("Enter CBVA player ID: ").strip()

    if not cbva_id:
        print("Error: No player ID provided", file=sys.stderr)
        sys.exit(1)

    rating = scrape_player_rating(cbva_id)
    if rating:
        print(f"{cbva_id}: {rating}")
    else:
        print(f"{cbva_id}: No rating found")
