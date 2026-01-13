import requests
from bs4 import BeautifulSoup
import re

def scrape_cbva_links(url="https://cbva.com/t"):
    """
    Scrapes all links from the given URL that match the pattern https://cbva.com/t/.*
    """
    try:
        # Fetch the page
        response = requests.get(url)
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
    for link in links:
        print(link)
