import asyncio
from tavily import AsyncTavilyClient
from ..config import TAVILY_API_KEY

def _client(): return AsyncTavilyClient(api_key=TAVILY_API_KEY)

_search_counter = {"count": 0}
MONTHLY_QUOTA = 1000


async def search(query: str, max_results: int = 5) -> list[dict]:
    _search_counter["count"] += 1
    result = await _client().search(query, max_results=max_results, search_depth="advanced")
    return result.get("results", [])


async def search_many(queries: list[str], max_results: int = 5) -> list[list[dict]]:
    return await asyncio.gather(*[search(q, max_results) for q in queries])


def remaining_quota() -> int:
    return max(0, MONTHLY_QUOTA - _search_counter["count"])


def searches_used() -> int:
    return _search_counter["count"]
