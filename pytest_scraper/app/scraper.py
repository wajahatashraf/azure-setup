import requests
from bs4 import BeautifulSoup


def scrape_example():
    """Fetches the HTML content of example.com"""
    url = "https://example.com"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        print("Request failed:", e)
        return ""

    return response.text


# Example usage
if __name__ == "__main__":
    data = scrape_example()
    print("Scraper results:", data)
