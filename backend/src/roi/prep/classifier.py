"""Per-domain paid-media classification.

Strategy: a hardcoded whitelist of well-known paid-media platforms (G2, Capterra,
Forbes Advisor, Gartner, etc.) gives high-confidence labels instantly — these
override Peec's domain classification (G2 is "UGC" to Peec, but it's also
DIRECT_PAID for our purposes). For domains not on the whitelist, fall back to
keyword matching on Tavily search results (Tavily's 400-char query cap means
we can't ask for structured JSON output).

Cache writes are batched at the end of `classify_domains` to avoid the
read-modify-write race condition that loses entries during parallel classification.
"""
import asyncio
import pathlib
from datetime import date
from tavily import AsyncTavilyClient
from ..config import TAVILY_API_KEY
from . import _cache

_CACHE_FILE = pathlib.Path(__file__).parent.parent / ".classifier_cache.json"
_CACHE_TTL_DAYS = 30
_MIN_CONFIDENCE = 0.6
_SEM = asyncio.Semaphore(5)
def _client(): return AsyncTavilyClient(api_key=TAVILY_API_KEY)

# Classify the top N domains by retrieval count, plus any whitelisted domains
# regardless of their rank.
MAX_DOMAINS_TO_CLASSIFY = 60

# Well-known paid-media platforms in B2B SaaS — these labels beat Peec's
# generic "UGC"/"EDITORIAL" classification. confidence intentionally high.
_PAID_WHITELIST: dict[str, tuple[str, float]] = {
    "g2.com":               ("DIRECT_PAID",   0.95),
    "capterra.com":         ("DIRECT_PAID",   0.95),
    "getapp.com":           ("DIRECT_PAID",   0.95),
    "softwareadvice.com":   ("DIRECT_PAID",   0.95),
    "business.com":         ("DIRECT_PAID",   0.95),
    "trustradius.com":      ("DIRECT_PAID",   0.90),
    "techradar.com":        ("DIRECT_PAID",   0.85),  # TechRadar Pro accepts sponsored
    "pcmag.com":            ("DIRECT_PAID",   0.85),
    "forbes.com":           ("AFFILIATE_PAID", 0.90),  # Forbes Advisor
    "nerdwallet.com":       ("AFFILIATE_PAID", 0.90),
    "thebalance.com":       ("AFFILIATE_PAID", 0.85),
    "investopedia.com":     ("AFFILIATE_PAID", 0.80),
    "gartner.com":          ("ANALYST_PAID",   0.95),
    "forrester.com":        ("ANALYST_PAID",   0.90),
    "idc.com":              ("ANALYST_PAID",   0.85),
    "crozdesk.com":         ("DIRECT_PAID",    0.85),
    "saashub.com":          ("DIRECT_PAID",    0.80),
    "slashdot.org":         ("DIRECT_PAID",    0.75),
    "sourceforge.net":      ("DIRECT_PAID",    0.75),
}

_PAID_LABELS = {"DIRECT_PAID", "AFFILIATE_PAID", "ANALYST_PAID"}

# Known UGC / social / forum platforms — never classify as paid even if Tavily
# search results mention "affiliate program" (creators do affiliate, the platform
# itself doesn't sell vendor placement).
_UGC_WHITELIST: set[str] = {
    "youtube.com", "reddit.com", "linkedin.com", "medium.com",
    "facebook.com", "twitter.com", "x.com", "tiktok.com",
    "instagram.com", "stackoverflow.com", "quora.com",
    "discord.com", "github.com", "stackexchange.com",
    "producthunt.com",  # has paid features but predominantly UGC
}

# Keyword classification (used when whitelist + Peec shortcut don't match)
_DIRECT_PAID_KW = [
    "sponsored listing", "sponsored placement", "sponsored content",
    "vendor profile", "premium listing", "pay to be listed",
    "boost ranking", "pay for placement", "advertising rate card",
    "promoted listing", "paid placement", "vendor program",
]
_AFFILIATE_KW = [
    "affiliate program", "affiliate marketing", "affiliate partner",
    "commission per", "referral fee", "earn a commission",
    "commission-based", "affiliate disclosure",
]
_ANALYST_KW = [
    "magic quadrant", "analyst access", "gartner peer", "forrester wave",
    "research report subscription", "analyst inquiry",
]
_EDITORIAL_KW = [
    "editorial team", "newsroom", "press release", "journalist",
    "editorial standards", "editorial guidelines",
]
_UGC_KW = [
    "user-generated", "community-driven", "forum thread", "user reviews",
    "user submitted", "discussion thread",
]


def _normalize(domain: str) -> str:
    d = domain.lower().strip()
    return d[4:] if d.startswith("www.") else d


def _whitelist_match(domain: str) -> dict | None:
    d = _normalize(domain)
    hit = _PAID_WHITELIST.get(d)
    if hit is None:
        return None
    label, conf = hit
    return {
        "classification": label,
        "reasoning": f"whitelisted as {label} (well-known paid-media platform)",
        "confidence": conf,
    }


def _peec_first_pass(peec_classification: str | None) -> str | None:
    """Map Peec's domain.classification when it's safe.
    Only used as a NEGATIVE signal (skip Tavily if we're sure it's not paid).
    Note: UGC is NOT used here because G2/Capterra are tagged UGC by Peec
    but are also DIRECT_PAID for our purposes — the whitelist handles those.
    """
    if not peec_classification:
        return None
    p = peec_classification.upper()
    if p in {"NEWS", "BLOG"}:
        return "EDITORIAL_NO_BUY"
    return None


def _classify_text(text: str) -> tuple[str, float]:
    t = text.lower()
    if any(kw in t for kw in _DIRECT_PAID_KW):
        return "DIRECT_PAID", 0.75
    if any(kw in t for kw in _AFFILIATE_KW):
        return "AFFILIATE_PAID", 0.75
    if any(kw in t for kw in _ANALYST_KW):
        return "ANALYST_PAID", 0.75
    if any(kw in t for kw in _UGC_KW):
        return "UGC", 0.65
    if any(kw in t for kw in _EDITORIAL_KW):
        return "EDITORIAL_NO_BUY", 0.65
    return "OTHER", 0.30


async def _tavily_classify(domain: str, category_hint: str) -> dict:
    query = f"{domain} sponsored content advertising paid placement {category_hint}"[:380]
    async with _SEM:
        try:
            result = await _client().search(
                query, max_results=3, search_depth="basic", include_answer=True,
            )
            answer = result.get("answer", "") or ""
            results = result.get("results", []) or []
            blob = answer + "\n" + "\n".join((r.get("content", "") or "") for r in results)
            label, confidence = _classify_text(blob)
            reasoning = answer[:200] if answer else (results[0].get("content", "")[:200] if results else "")
            return {
                "classification": label,
                "reasoning": reasoning,
                "confidence": confidence,
            }
        except Exception as e:
            print(f"[classifier] Tavily failed for {domain}: {type(e).__name__}: {e}")
    return {"classification": "OTHER", "reasoning": "classification unavailable", "confidence": 0.0}


async def _classify_one(domain: str, category_hint: str, peec_classification: str | None) -> dict:
    """Pure: classify one domain. Reads no cache, writes no cache.
    Order: paid whitelist → UGC whitelist → Peec negative shortcut → Tavily."""
    if _normalize(domain) in _UGC_WHITELIST:
        return {
            "classification": "UGC",
            "reasoning": "whitelisted as UGC (social/forum platform)",
            "confidence": 0.95,
        }
    hit = _whitelist_match(domain)
    if hit:
        return hit
    fast = _peec_first_pass(peec_classification)
    if fast:
        return {
            "classification": fast,
            "reasoning": f"Peec classified domain as {peec_classification}.",
            "confidence": 0.85,
        }
    return await _tavily_classify(domain, category_hint)


async def classify_domains(
    domains: list[tuple[str, str | None]],     # [(domain, peec_classification), ...]
    category_hint: str,
    max_domains: int = MAX_DOMAINS_TO_CLASSIFY,
) -> dict[str, dict]:
    """Classify the top `max_domains` plus all whitelisted domains in the inventory.
    Single batched cache write at the end (avoids race condition)."""
    cache = _cache.load(_CACHE_FILE)

    # Top-N by input order (caller already sorted by retrieval count desc), PLUS
    # whitelist domains that appear in the inventory but past rank N.
    head = domains[:max_domains]
    head_set = {d for d, _ in head}
    tail_whitelist = [
        (d, p) for d, p in domains[max_domains:]
        if _normalize(d) in _PAID_WHITELIST and d not in head_set
    ]
    to_classify = head + tail_whitelist
    if tail_whitelist:
        print(f"[classifier] adding {len(tail_whitelist)} whitelisted domains past rank {max_domains}: {[d for d, _ in tail_whitelist]}")
    skipped = max(0, len(domains) - max_domains - len(tail_whitelist))
    if skipped:
        print(f"[classifier] pre-filter: classifying {len(to_classify)} of {len(domains)} domains (skipping {skipped} long-tail)")

    # Split into cache-hits and need-classification
    fresh_results: dict[str, dict] = {}
    pending: list[tuple[str, str | None]] = []
    for d, p in to_classify:
        key = f"{d}::{category_hint}"
        cached = cache.get(key)
        if cached and _cache.is_fresh(cached.get("date", ""), _CACHE_TTL_DAYS):
            fresh_results[d] = {k: cached[k] for k in ("classification", "reasoning", "confidence")}
        else:
            pending.append((d, p))

    print(f"[classifier] cache hits {len(fresh_results)}, classifying {len(pending)} (sem=5)")

    # Run classification in parallel; write cache once at the end
    if pending:
        results = await asyncio.gather(*[
            _classify_one(d, category_hint, p) for d, p in pending
        ])
        today_iso = date.today().isoformat()
        for (d, _), r in zip(pending, results):
            fresh_results[d] = r
            cache[f"{d}::{category_hint}"] = {**r, "date": today_iso}
        _cache.save(_CACHE_FILE, cache)

    paid_count = sum(
        1 for r in fresh_results.values()
        if r["classification"] in _PAID_LABELS and r["confidence"] >= _MIN_CONFIDENCE
    )
    print(f"[classifier] {paid_count}/{len(fresh_results)} classified as paid (conf ≥ {_MIN_CONFIDENCE})")
    return fresh_results


def is_paid(result: dict) -> bool:
    return (
        result.get("classification") in _PAID_LABELS
        and result.get("confidence", 0.0) >= _MIN_CONFIDENCE
    )
