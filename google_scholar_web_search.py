import logging
import os

import requests
from bs4 import BeautifulSoup

# NOTE: never print() in this module. When the MCP server runs over stdio,
# stdout carries the JSON-RPC protocol and any stray output corrupts it.
log = logging.getLogger(__name__)

SCHOLAR_URL = "https://scholar.google.com/scholar"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 20


class ScholarBlockedError(RuntimeError):
    """Google Scholar refused the request (CAPTCHA / rate limit)."""


def _proxies():
    """Optional proxy (e.g. http://user:pass@host:port) to avoid Scholar blocks."""
    url = os.environ.get("PROXY_URL")
    return {"http": url, "https": url} if url else None


def _fetch_and_parse(params, num_results):
    response = requests.get(
        SCHOLAR_URL, params=params, headers=HEADERS, proxies=_proxies(), timeout=TIMEOUT
    )
    text = response.text
    if response.status_code in (403, 429) or "gs_captcha" in text or "unusual traffic" in text:
        raise ScholarBlockedError(
            "Google Scholar blocked the request (CAPTCHA / rate limit). "
            "Try again later or set PROXY_URL on the server."
        )
    response.raise_for_status()

    soup = BeautifulSoup(text, "html.parser")
    results = []
    for item in soup.find_all("div", class_="gs_ri"):
        if len(results) >= num_results:
            break

        title_tag = item.find("h3", class_="gs_rt")
        title = title_tag.get_text(strip=True) if title_tag else "No title available"

        link_tag = title_tag.find("a") if title_tag else None
        link = link_tag["href"] if link_tag and link_tag.has_attr("href") else "No link available"

        authors_tag = item.find("div", class_="gs_a")
        authors = authors_tag.get_text(strip=True) if authors_tag else "No authors available"

        abstract_tag = item.find("div", class_="gs_rs")
        abstract = abstract_tag.get_text(strip=True) if abstract_tag else "No abstract available"

        results.append({"Title": title, "Authors": authors, "Abstract": abstract, "URL": link})

    log.info("Google Scholar returned %d results", len(results))
    return results


# 普通关键词搜索函数
def google_scholar_search(query, num_results=5):
    """
    Search Google Scholar using a simple keyword query.

    Parameters:
    query (str): The search query (e.g., paper title or author).
    num_results (int): The number of results to retrieve (max 10 per page).

    Returns:
    list: A list of dictionaries containing search results.
    """
    return _fetch_and_parse({"q": query}, num_results)


# 高级搜索函数
def advanced_google_scholar_search(query, author=None, year_range=None, num_results=5):
    """
    Search Google Scholar using advanced filters (author, year range).

    Parameters:
    query (str): The search query (e.g., paper title or topic).
    author (str): Author name to filter results (default None).
    year_range (tuple): (start_year, end_year); either may be None (default None).
    num_results (int): The number of results to retrieve (max 10 per page).

    Returns:
    list: A list of dictionaries containing search results.
    """
    params = {"q": query}
    if author:
        params["as_sauthors"] = author
    if year_range:
        start_year, end_year = year_range
        if start_year:
            params["as_ylo"] = start_year
        if end_year:
            params["as_yhi"] = end_year
    return _fetch_and_parse(params, num_results)


# Example usage:
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for r in google_scholar_search("machine learning", num_results=5):
        print(f"\nTitle: {r['Title']}\nAuthors: {r['Authors']}\nURL: {r['URL']}")
    for r in advanced_google_scholar_search(
        "machine learning", author="Ian Goodfellow", year_range=(2010, 2021), num_results=5
    ):
        print(f"\nTitle: {r['Title']}\nAuthors: {r['Authors']}\nURL: {r['URL']}")
