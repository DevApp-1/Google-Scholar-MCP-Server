"""Google Scholar MCP server.

Run locally (stdio, for Claude Desktop / Claude Code):
    python google_scholar_server.py

Run as a remote server (for a claude.ai custom connector):
    python google_scholar_server.py --transport streamable-http
    # endpoint: http://HOST:PORT/mcp   (or /mcp/<MCP_SECRET> if MCP_SECRET is set)

Environment variables: HOST (default 0.0.0.0), PORT (default 8000),
MCP_SECRET (hide the endpoint behind a secret path), PROXY_URL (route
Scholar requests through a proxy to avoid CAPTCHA blocks).
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from scholarly import ProxyGenerator, scholarly

from google_scholar_web_search import advanced_google_scholar_search, google_scholar_search

# Log to stderr: stdout is reserved for the MCP protocol when using stdio.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stderr
)

_secret = os.environ.get("MCP_SECRET", "").strip("/")

mcp = FastMCP(
    "google_scholar",
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "8000")),
    streamable_http_path=f"/mcp/{_secret}" if _secret else "/mcp",
    stateless_http=True,  # no sticky sessions needed when hosted
    json_response=True,
)

if os.environ.get("PROXY_URL"):
    _pg = ProxyGenerator()
    if _pg.SingleProxy(http=os.environ["PROXY_URL"], https=os.environ["PROXY_URL"]):
        scholarly.use_proxy(_pg)

MAX_RESULTS = 10  # one Google Scholar results page


def _clamp(n: int) -> int:
    return max(1, min(int(n), MAX_RESULTS))


@mcp.tool()
async def search_google_scholar_key_words(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for articles on Google Scholar using key words.

    Args:
        query: Search query string
        num_results: Number of results to return (1-10, default: 5)

    Returns:
        List of dictionaries containing article information
    """
    logging.info("Searching Google Scholar: query=%r num_results=%s", query, num_results)
    try:
        return await asyncio.to_thread(google_scholar_search, query, _clamp(num_results))
    except Exception as e:
        logging.exception("keyword search failed")
        return [{"error": f"An error occurred while searching Google Scholar: {e}"}]


@mcp.tool()
async def search_google_scholar_advanced(
    query: str,
    author: Optional[str] = None,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search for articles on Google Scholar using advanced filters.

    Args:
        query: General search query
        author: Author name to filter by
        year_start: Only include articles published in or after this year
        year_end: Only include articles published in or before this year
        num_results: Number of results to return (1-10, default: 5)

    Returns:
        List of dictionaries containing article information
    """
    logging.info(
        "Advanced search: query=%r author=%r years=%s-%s", query, author, year_start, year_end
    )
    year_range = (year_start, year_end) if (year_start or year_end) else None
    try:
        return await asyncio.to_thread(
            advanced_google_scholar_search, query, author, year_range, _clamp(num_results)
        )
    except Exception as e:
        logging.exception("advanced search failed")
        return [{"error": f"An error occurred while performing advanced search on Google Scholar: {e}"}]


@mcp.tool()
async def get_author_info(author_name: str) -> Dict[str, Any]:
    """
    Get detailed information about an author from Google Scholar.

    Args:
        author_name: Name of the author to search for

    Returns:
        Dictionary containing author information
    """
    logging.info("Retrieving author information for: %s", author_name)

    def lookup():
        author = next(scholarly.search_author(author_name), None)
        if author is None:
            return None
        return scholarly.fill(author, sections=["basics", "indices", "publications"])

    try:
        filled_author = await asyncio.to_thread(lookup)
        if filled_author is None:
            return {"error": f"No Google Scholar profile found for {author_name!r}"}

        pubs = sorted(
            filled_author.get("publications", []),
            key=lambda p: p.get("num_citations", 0),
            reverse=True,
        )
        return {
            "name": filled_author.get("name", "N/A"),
            "affiliation": filled_author.get("affiliation", "N/A"),
            "interests": filled_author.get("interests", []),
            "citedby": filled_author.get("citedby", 0),
            "h_index": filled_author.get("hindex"),
            "i10_index": filled_author.get("i10index"),
            "scholar_id": filled_author.get("scholar_id"),
            "publications": [
                {
                    "title": pub.get("bib", {}).get("title", "N/A"),
                    "year": pub.get("bib", {}).get("pub_year", "N/A"),
                    "citations": pub.get("num_citations", 0),
                }
                for pub in pubs[:5]  # top 5 most-cited publications
            ],
        }
    except Exception as e:
        logging.exception("author lookup failed")
        return {"error": f"An error occurred while retrieving author information: {e}"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Scholar MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="stdio for local clients; streamable-http to host as a remote connector",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)
