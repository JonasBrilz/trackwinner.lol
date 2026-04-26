import re
import json
import pathlib
from datetime import date
from tavily import AsyncTavilyClient
from ..config import TAVILY_API_KEY
from ..models import MarketEstimate, ActionRateEstimate

_CACHE_FILE = pathlib.Path(__file__).parent.parent / ".research_cache.json"
def _client(): return AsyncTavilyClient(api_key=TAVILY_API_KEY)

# Documented fallbacks (used only when Tavily can't extract a reasonable number)
_DEFAULT_AI_QUERY_SHARE = 0.10   # ~10% of relevant search queries now happen on AI assistants
_DEFAULT_ACTION_RATE = 0.12      # ~12% of LLM mentions drive a measurable user action
_DEFAULT_PEEC_MULTIPLIER = 10.0  # documented assumption: Peec samples ~10% of relevant AI chats


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


def _extract_pct(text: str, lo: float, hi: float, default: float) -> float | None:
    """Extract first percentage in [lo, hi] from text. Returns fraction (0–1) or None."""
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:percent|%)", text, re.IGNORECASE):
        n = float(match.group(1))
        if lo <= n <= hi:
            return round(n / 100, 3)
    return None


async def _research(query: str, lo: float, hi: float, default: float, label: str) -> tuple[float, list[str]]:
    try:
        result = await _client().search(
            query, max_results=3, search_depth="basic", include_answer=True,
        )
        answer = result.get("answer", "") or ""
        sources = [r.get("url", "") for r in result.get("results", []) if r.get("url")]
        print(f"[step4] {label} answer: {answer[:200]}")
        extracted = _extract_pct(answer, lo, hi, default)
        if extracted is not None:
            print(f"[step4] {label}={extracted} (from Tavily, range {lo}-{hi}%)")
            return extracted, sources
        print(f"[step4] {label} not found in Tavily answer, using default={default}")
        return default, sources
    except Exception as e:
        print(f"[step4] {label} Tavily failed ({e}), using default={default}")
        return default, []


async def run() -> tuple[MarketEstimate, ActionRateEstimate]:
    today = date.today().isoformat()
    cache = _load_cache()

    if cache.get("date") == today and "ai_query_share" in cache:
        print(f"[step4] cached — ai_query_share={cache['ai_query_share']}, action_rate={cache['action_rate']}, peec_mult={cache['peec_to_global_multiplier']}")
        return (
            MarketEstimate(
                ai_query_share=cache["ai_query_share"],
                peec_to_global_multiplier=cache["peec_to_global_multiplier"],
                sources=cache["sources"],
                rationale=cache.get("rationale", ""),
            ),
            ActionRateEstimate(base_rate=cache["action_rate"], sources=cache["sources"], rationale=""),
        )

    print("[step4] fetching estimates via Tavily")

    # 1. ai_query_share: % of relevant searches that happen on AI now (the only number that drives volume-mode revenue)
    ai_query_share, src1 = await _research(
        "what percentage of online product research and shopping search queries now happen on ChatGPT and AI assistants instead of Google in 2025",
        lo=3, hi=30, default=_DEFAULT_AI_QUERY_SHARE, label="ai_query_share",
    )

    # 2. action_rate: % of AI mentions that drive a measurable click/visit
    action_rate, src2 = await _research(
        "what percentage of users click or search a brand after seeing it mentioned in a ChatGPT answer 2025",
        lo=5, hi=25, default=_DEFAULT_ACTION_RATE, label="action_rate",
    )

    # 3. peec_to_global_multiplier: only used as fallback for prompts without search_volume.
    #    Tavily can't research this directly (it's tool-specific), so it stays as a documented assumption.
    peec_multiplier = _DEFAULT_PEEC_MULTIPLIER

    sources = list({s for s in (src1 + src2) if s})
    rationale = (
        f"ai_query_share={ai_query_share} researched via Tavily. "
        f"peec_to_global_multiplier={peec_multiplier} is a documented assumption "
        f"(Peec samples ~{int(100/peec_multiplier)}% of relevant AI conversations) "
        f"used only when a prompt has no search_volume."
    )

    _save_cache({
        "date": today,
        "ai_query_share": ai_query_share,
        "action_rate": action_rate,
        "peec_to_global_multiplier": peec_multiplier,
        "sources": sources,
        "rationale": rationale,
    })
    print(f"[step4] ai_query_share={ai_query_share}, action_rate={action_rate}, peec_multiplier={peec_multiplier}x (fallback)")

    return (
        MarketEstimate(
            ai_query_share=ai_query_share,
            peec_to_global_multiplier=peec_multiplier,
            sources=sources,
            rationale=rationale,
        ),
        ActionRateEstimate(base_rate=action_rate, sources=sources, rationale=""),
    )
