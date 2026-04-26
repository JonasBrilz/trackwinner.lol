"""Per-prompt search volume lookup via Tavily.

Peec doesn't expose Google search volume per prompt. This step asks Tavily to find
a published monthly search-volume number for each prompt and surfaces the source URLs
so the calculation is auditable. Cached per-prompt for 7 days.
"""
import asyncio
import json
import pathlib
import re
from datetime import date
from tavily import AsyncTavilyClient
from ..config import TAVILY_API_KEY
from ..models import Prompt

_CACHE_FILE = pathlib.Path(__file__).parent.parent / ".volume_cache.json"
def _client(): return AsyncTavilyClient(api_key=TAVILY_API_KEY)
_SEM = asyncio.Semaphore(5)  # cap concurrent Tavily calls

_VOLUME_LO = 50
_VOLUME_HI = 5_000_000
_CACHE_TTL_DAYS = 7


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE_FILE.read_text())
    except Exception:
        return {}


def _save_cache(data: dict):
    try:
        _CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _is_fresh(cached_date: str) -> bool:
    try:
        return (date.today() - date.fromisoformat(cached_date)).days < _CACHE_TTL_DAYS
    except Exception:
        return False


def _parse_number(num_str: str, suffix: str | None) -> int | None:
    try:
        n = float(num_str.replace(",", ""))
        if suffix:
            s = suffix.upper()
            if s == "K":
                n *= 1_000
            elif s == "M":
                n *= 1_000_000
        n = int(n)
        if _VOLUME_LO <= n <= _VOLUME_HI:
            return n
    except ValueError:
        pass
    return None


def _extract_volume(text: str) -> int | None:
    """Find a plausible monthly search-volume number in text. Looks for numbers
    that appear near volume-related keywords."""
    if not text:
        return None
    # Numbers like "12,000", "1.2K", "12k", "1.2M", "12000"
    num_re = r"(\d[\d,]*(?:\.\d+)?)\s*([KkMm])?"
    # Patterns ordered by specificity
    patterns = [
        rf"{num_re}\s*(?:monthly\s+searches?|per\s+month|/mo|/month|searches?\s*(?:per|/)\s*month)",
        rf"(?:monthly\s+(?:search\s+)?volume|search\s+volume|monthly\s+queries|monthly\s+traffic)(?:\s+(?:of|is|:|=|approximately|around|about))?[\s:]+{num_re}",
        rf"{num_re}\s*(?:monthly\s+search(?:es)?|monthly\s+queries|monthly\s+visits)",
        rf"(?:volume|searches?|queries|traffic)\s*(?:of|:|=)?\s*{num_re}\s*(?:per\s+month|monthly|/mo)",
    ]
    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            n = _parse_number(match.group(1), match.group(2))
            if n is not None:
                return n
    return None


async def _research_one(prompt_message: str) -> tuple[int, list[str]]:
    async with _SEM:
        try:
            result = await _client().search(
                f'"{prompt_message}" monthly search volume keyword data',
                max_results=5, search_depth="advanced", include_answer=True,
            )
            answer = result.get("answer", "") or ""
            results = result.get("results", []) or []
            sources = [r.get("url", "") for r in results if r.get("url")]

            # Scan answer first, then each result's content snippet
            volume = _extract_volume(answer)
            if volume is None:
                for r in results:
                    content = r.get("content", "") or ""
                    volume = _extract_volume(content)
                    if volume is not None:
                        break
            return volume or 0, sources
        except Exception as e:
            print(f"[step1.5] Tavily failed for '{prompt_message[:40]}': {e}")
            return 0, []


async def run(prompts: list[Prompt]) -> dict[str, tuple[int, list[str]]]:
    """Returns {prompt_id: (search_volume, source_urls)}.

    Skips prompts that already have search_volume from Peec. Uses cached results
    when fresh; otherwise hits Tavily in parallel (sem=5).
    """
    cache = _load_cache()
    results: dict[str, tuple[int, list[str]]] = {}
    to_research: list[Prompt] = []

    for p in prompts:
        if p.search_volume > 0:
            results[p.id] = (p.search_volume, [])
            continue
        cached = cache.get(p.id)
        if cached and _is_fresh(cached.get("date", "")):
            results[p.id] = (cached["volume"], cached.get("sources", []))
            continue
        to_research.append(p)

    if not to_research:
        cached_count = sum(1 for v, _ in results.values() if v > 0)
        print(f"[step1.5] all prompts cached/from-Peec — {cached_count}/{len(prompts)} have volume")
        return results

    print(f"[step1.5] researching volume for {len(to_research)} prompts via Tavily (sem=5)")
    fetched = await asyncio.gather(*[_research_one(p.message) for p in to_research])

    today_iso = date.today().isoformat()
    for p, (volume, sources) in zip(to_research, fetched):
        results[p.id] = (volume, sources)
        cache[p.id] = {
            "date": today_iso,
            "volume": volume,
            "sources": sources,
            "message": p.message[:120],
        }

    _save_cache(cache)

    found = sum(1 for vol, _ in fetched if vol > 0)
    print(f"[step1.5] Tavily found volume for {found}/{len(to_research)} prompts")
    if found:
        sample = [(p.message[:40], v) for p, (v, _) in zip(to_research, fetched) if v > 0][:3]
        print(f"[step1.5] sample volumes: {sample}")
    return results
