"""Find an advertising/partnerships contact email per paid-media domain.

Tavily search with a short query, parse emails from the answer + result snippets.
Prefer emails on the same domain (contact@guideflow.com) over generic ones (info@gmail.com).
Cached 30 days per (domain, category_hint) — emails don't change often.
"""
import asyncio
import pathlib
import re
from datetime import date
from tavily import AsyncTavilyClient
from ..config import TAVILY_API_KEY
from . import _cache

_CACHE_FILE = pathlib.Path(__file__).parent.parent / ".contact_cache.json"
_CACHE_TTL_DAYS = 30
_SEM = asyncio.Semaphore(5)
def _client(): return AsyncTavilyClient(api_key=TAVILY_API_KEY)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Emails ranked by likelihood of being the right contact for ad/sponsorship inquiries
_PREFERRED_LOCAL_PARTS = [
    "partnerships", "sponsorship", "sponsorships", "advertising",
    "ads", "media", "sales", "bd", "business",
    "press", "marketing", "hello", "info", "contact",
]


def _root_domain(domain: str) -> str:
    d = domain.lower().strip()
    return d[4:] if d.startswith("www.") else d


def _rank_email(email: str, root: str) -> int:
    """Lower is better. We prefer same-domain + role-based locals."""
    e = email.lower()
    same_domain = e.endswith("@" + root) or e.endswith("." + root)
    local = e.split("@", 1)[0]

    domain_score = 0 if same_domain else 50
    try:
        local_score = _PREFERRED_LOCAL_PARTS.index(local)
    except ValueError:
        local_score = 30  # any same-domain email beats any non-same-domain
    return domain_score + local_score


def _pick_email(blob: str, root: str) -> str | None:
    candidates = list(set(_EMAIL_RE.findall(blob)))
    # Skip obvious junk: example.com, no-reply@, image.png@*, etc.
    candidates = [
        e for e in candidates
        if not any(bad in e.lower() for bad in ["@example.", "noreply", "no-reply", ".png@", ".jpg@", "@sentry."])
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda e: _rank_email(e, root))
    return candidates[0]


async def _tavily_find(domain: str, category_hint: str) -> dict:
    root = _root_domain(domain)
    query = f"{root} advertising sponsorship partnerships contact email {category_hint}"[:380]
    async with _SEM:
        try:
            result = await _client().search(
                query, max_results=5, search_depth="basic", include_answer=True,
            )
            answer = result.get("answer", "") or ""
            results = result.get("results", []) or []
            blob = answer + "\n" + "\n".join((r.get("content", "") or "") for r in results)
            email = _pick_email(blob, root)

            source_url = None
            if email and results:
                for r in results:
                    if email in (r.get("content", "") or ""):
                        source_url = r.get("url")
                        break
                if source_url is None:
                    source_url = results[0].get("url")

            return {
                "email": email,
                "source_url": source_url,
                "notes": (answer[:200] if answer else "")[:200],
            }
        except Exception as e:
            print(f"[contact] Tavily failed for {domain}: {type(e).__name__}: {e}")
    return {"email": None, "source_url": None, "notes": "lookup failed"}


async def find_contacts(domains: list[str], category_hint: str) -> dict[str, dict]:
    """Batched: read cache, fetch missing in parallel, write cache once.
    Always returns suggested_emails fallback so callers never have an empty list."""
    cache = _cache.load(_CACHE_FILE)
    fresh: dict[str, dict] = {}
    pending: list[str] = []
    for d in domains:
        key = f"{d}::{category_hint}"
        cached = cache.get(key)
        if cached and _cache.is_fresh(cached.get("date", ""), _CACHE_TTL_DAYS):
            fresh[d] = {
                "email": cached.get("email"),
                "source_url": cached.get("source_url"),
                "notes": cached.get("notes", ""),
            }
        else:
            pending.append(d)
    print(f"[contact] cache hits {len(fresh)}, fetching {len(pending)} (sem=5, cache=30d)")
    if pending:
        results = await asyncio.gather(*[_tavily_find(d, category_hint) for d in pending])
        today_iso = date.today().isoformat()
        for d, r in zip(pending, results):
            fresh[d] = r
            cache[f"{d}::{category_hint}"] = {**r, "date": today_iso}
        _cache.save(_CACHE_FILE, cache)
    found = sum(1 for r in fresh.values() if r.get("email"))
    print(f"[contact] found explicit emails for {found}/{len(domains)} domains")
    return fresh
