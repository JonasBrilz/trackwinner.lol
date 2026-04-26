"""ACV (annual contract value / average revenue per customer) research via Tavily.

Used when the user doesn't pass acv_eur. Searches for published figures about
the company's pricing, ARR, ARPU, or average ACV. Falls back to a B2B-SaaS
industry default if no number found.

USD numbers are kept as-is (close enough to EUR for hackathon estimates).
Cached per company for 30 days.
"""
import asyncio
import pathlib
import re
from datetime import date
from tavily import AsyncTavilyClient
from ..config import TAVILY_API_KEY
from . import _cache

_CACHE_FILE = pathlib.Path(__file__).parent.parent / ".acv_cache.json"
_CACHE_TTL_DAYS = 30
_SEM = asyncio.Semaphore(3)
def _client(): return AsyncTavilyClient(api_key=TAVILY_API_KEY)

_DEFAULT_ACV_EUR = 7500.0  # B2B SaaS blended-customer fallback
_LO = 200       # minimum plausible ACV
_HI = 500_000   # maximum plausible ACV (single-customer enterprise)


def _parse_amount(num_str: str, suffix: str | None) -> float | None:
    try:
        n = float(num_str.replace(",", ""))
        if suffix:
            s = suffix.upper()
            if s == "K":
                n *= 1_000
            elif s == "M":
                n *= 1_000_000
        if _LO <= n <= _HI:
            return float(n)
    except ValueError:
        pass
    return None


def _extract_acv(text: str) -> float | None:
    """Look for amounts associated with ACV/ARR-per-customer/revenue-per-customer language."""
    if not text:
        return None
    # Patterns where the dollar amount is near an ACV-meaningful keyword
    patterns = [
        r"(?:ACV|annual contract value|average\s+(?:revenue|contract|ACV)|revenue\s+per\s+customer|ARPU)[^.\n$]*?\$\s*(\d[\d,]*(?:\.\d+)?)\s*([KkMm])?",
        r"\$\s*(\d[\d,]*(?:\.\d+)?)\s*([KkMm])?\s+(?:ACV|annual contract value|per customer|per account|ARPU)",
        # Generic per-customer pricing
        r"(?:customers?\s+pay|each\s+customer|per\s+seat|per\s+user)[^.\n$]*?\$\s*(\d[\d,]*(?:\.\d+)?)\s*([KkMm])?",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            n = _parse_amount(m.group(1), m.group(2))
            if n is not None:
                return n
    return None


async def _research(company_name: str) -> dict:
    """Returns {value_eur, source, notes}."""
    query = f'"{company_name}" average revenue per customer ACV ARR pricing'[:380]
    async with _SEM:
        try:
            result = await _client().search(
                query, max_results=4, search_depth="basic", include_answer=True,
            )
            answer = result.get("answer", "") or ""
            results = result.get("results", []) or []
            blob = answer + "\n" + "\n".join((r.get("content", "") or "") for r in results)
            value = _extract_acv(blob)
            if value is not None:
                source = results[0].get("url", "Tavily research") if results else "Tavily research"
                return {
                    "value_eur": round(value, 0),
                    "source": source,
                    "notes": (answer[:240] if answer else "Found in search snippets")[:240],
                }
        except Exception as e:
            print(f"[acv] Tavily failed for {company_name}: {type(e).__name__}: {e}")
    return {
        "value_eur": _DEFAULT_ACV_EUR,
        "source": "DEFAULT",
        "notes": f"No published ACV found; using B2B-SaaS blended default (€{_DEFAULT_ACV_EUR:,.0f})",
    }


async def get_acv(company_name: str, user_acv_eur: float | None) -> dict:
    """Returns {value_eur, source, notes}.
    If user provided an ACV, return that with source='user-provided'.
    Otherwise look up cache, then Tavily, then default."""
    if user_acv_eur is not None and user_acv_eur > 0:
        return {
            "value_eur": float(user_acv_eur),
            "source": "user-provided",
            "notes": "supplied via API parameter",
        }

    cache = _cache.load(_CACHE_FILE)
    key = company_name.lower().strip()
    cached = cache.get(key)
    if cached and _cache.is_fresh(cached.get("date", ""), _CACHE_TTL_DAYS):
        return {k: cached[k] for k in ("value_eur", "source", "notes")}

    print(f"[acv] researching ACV for '{company_name}' via Tavily")
    result = await _research(company_name)
    cache[key] = {**result, "date": date.today().isoformat()}
    _cache.save(_CACHE_FILE, cache)
    print(f"[acv] {company_name}: €{result['value_eur']:,.0f} (source={result['source'][:60]})")
    return result
