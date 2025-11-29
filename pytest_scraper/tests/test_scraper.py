# tests/test_scraper.py
from app.scraper import scrape_example

def test_scraper_basic():
    results = scrape_example()  # no argument now
    print("Scraper results:", results)
    assert isinstance(results, list)
    assert len(results) > 0
