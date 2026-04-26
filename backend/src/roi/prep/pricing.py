"""Per-domain placement pricing via Tavily.

Short search query (Tavily caps at 400 chars) + Python-side regex extraction.
Cached 7 days. Many results will be (None, None) — that's fine, the UI surfaces
those as 'RFQ required'.
"""
import asyncio
import pathlib
import re
from datetime import date
from tavily import AsyncTavilyClient
from ..config import TAVILY_API_KEY
from . import _cache

_CACHE_FILE = pathlib.Path(__file__).parent.parent / ".pricing_cache.json"
_CACHE_TTL_DAYS = 7
_SEM = asyncio.Semaphore(5)
def _client(): return AsyncTavilyClient(api_key=TAVILY_API_KEY)

_PRICE_LO_USD = 100
_PRICE_HI_USD = 500_000


def _parse_dollar_amount(num_str: str, suffix: str | None) -> int | None:
    try:
        n = float(num_str.replace(",", ""))
        if suffix:
            s = suffix.upper()
            if s == "K":
                n *= 1_000
            elif s == "M":
                n *= 1_000_000
        n = int(n)
        if _PRICE_LO_USD <= n <= _PRICE_HI_USD:
            return n
    except ValueError:
        pass
    return None


def _extract_prices(text: str) -> tuple[int | None, int | None]:
    """Find dollar amounts that look like vendor placement pricing.
    Returns (low, high). If only one found, both are equal."""
    if not text:
        return None, None
    found: list[int] = []
    # $1,000-$5,000 range
    for m in re.finditer(
        r"\$\s*(\d[\d,]*(?:\.\d+)?)\s*([KkMm])?\s*(?:-|to|–|—)\s*\$?\s*(\d[\d,]*(?:\.\d+)?)\s*([KkMm])?",
        text,
    ):
        lo = _parse_dollar_amount(m.group(1), m.group(2))
        hi = _parse_dollar_amount(m.group(3), m.group(4))
        if lo and hi:
            return min(lo, hi), max(lo, hi)
    # Single $X
    for m in re.finditer(r"\$\s*(\d[\d,]*(?:\.\d+)?)\s*([KkMm])?", text):
        n = _parse_dollar_amount(m.group(1), m.group(2))
        if n:
            found.append(n)
    if not found:
        return None, None
    if len(found) == 1:
        return found[0], found[0]
    return min(found), max(found)


async def _tavily_price(domain: str, category_hint: str) -> dict:
    query = f"{domain} sponsored placement pricing cost rate card vendor program {category_hint}"[:380]
    async with _SEM:
        try:
            result = await _client().search(
                query, max_results=4, search_depth="basic", include_answer=True,
            )
            answer = result.get("answer", "") or ""
            results = result.get("results", []) or []
            sources = [r.get("url", "") for r in results if r.get("url")]
            blob = answer + "\n" + "\n".join((r.get("content", "") or "") for r in results)
            low, high = _extract_prices(blob)
            if low or high:
                return {
                    "low_usd": low,
                    "high_usd": high,
                    "source": sources[0] if sources else "ESTIMATE",
                    "notes": (answer[:300] if answer else "Found in search results"),
                }
        except Exception as e:
            print(f"[pricing] Tavily failed for {domain}: {type(e).__name__}: {e}")
    return {
        "low_usd": None,
        "high_usd": None,
        "source": "ESTIMATE",
        "notes": "pricing unavailable; RFQ required",
    }


async def fetch_pricing_for_domains(domains: list[str], category_hint: str) -> dict[str, dict]:
    """Batched: read cache once, fetch missing in parallel, write cache once."""
    cache = _cache.load(_CACHE_FILE)
    fresh: dict[str, dict] = {}
    pending: list[str] = []
    for d in domains:
        key = f"{d}::{category_hint}"
        cached = cache.get(key)
        if cached and _cache.is_fresh(cached.get("date", ""), _CACHE_TTL_DAYS):
            fresh[d] = {k: cached[k] for k in ("low_usd", "high_usd", "source", "notes")}
        else:
            pending.append(d)
    print(f"[pricing] cache hits {len(fresh)}, fetching {len(pending)} (sem=5, cache=7d)")
    if pending:
        results = await asyncio.gather(*[_tavily_price(d, category_hint) for d in pending])
        today_iso = date.today().isoformat()
        for d, r in zip(pending, results):
            fresh[d] = r
            cache[f"{d}::{category_hint}"] = {**r, "date": today_iso}
        _cache.save(_CACHE_FILE, cache)
    return fresh
