"""Set-based visibility-delta math (spec §7).

Operates on sets of chat IDs, not aggregate counts. The same chat retrieving
multiple gap URLs across multiple platforms is counted once toward the total
delta — that's what the union does. Per-platform deltas are 'if alone'
estimates and will not sum to the total. This is correct, not a bug.
"""
from collections import defaultdict
from urllib.parse import urlparse


PESSIMISTIC_FACTOR = 0.60
OPTIMISTIC_FACTOR = 1.00
MIN_RETRIEVALS_PER_URL = 2


def domain_of(url: str) -> str:
    """Strip scheme + 'www.' to produce a canonical domain."""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return url


def build_chat_brands(url_rows: list[dict]) -> dict[str, set[str]]:
    """Build {chat_id: set(brand_ids)} from /reports/urls rows."""
    chat_brands: dict[str, set[str]] = defaultdict(set)
    for row in url_rows:
        chat_id = (row.get("chat") or {}).get("id", "")
        if not chat_id:
            continue
        for b in row.get("mentioned_brands") or []:
            bid = b.get("id")
            if bid:
                chat_brands[chat_id].add(bid)
    return dict(chat_brands)


def baseline_stats(chat_brands: dict[str, set[str]], own_brand_id: str) -> tuple[int, int, float]:
    """Returns (total_chats, chats_mentioning_brand, visibility_score_pct)."""
    total = len(chat_brands)
    mentioned = sum(1 for brands in chat_brands.values() if own_brand_id in brands)
    score = (mentioned / total * 100) if total else 0.0
    return total, mentioned, round(score, 2)


def group_url_rows_by_domain(url_rows: list[dict]) -> dict[str, list[dict]]:
    """Group URL rows by canonical domain."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in url_rows:
        url = row.get("url", "")
        if not url:
            continue
        grouped[domain_of(url)].append(row)
    return dict(grouped)


def aggregate_url_rows(rows: list[dict]) -> dict:
    """Collapse multiple rows with the same URL into one record:
    { url, retrieval_count, citation_count, chats: set, mentioned_brands_per_chat: dict }
    """
    by_url: dict[str, dict] = {}
    for row in rows:
        url = row.get("url", "")
        if not url:
            continue
        rec = by_url.setdefault(url, {
            "url": url,
            "retrieval_count": 0,
            "citation_count": 0,
            "chats": set(),
            "brands_by_chat": defaultdict(set),
        })
        rec["retrieval_count"] = max(rec["retrieval_count"], int(row.get("retrieval_count", 0)))
        rec["citation_count"] = max(rec["citation_count"], int(row.get("citation_count", 0)))
        chat_id = (row.get("chat") or {}).get("id", "")
        if chat_id:
            rec["chats"].add(chat_id)
            for b in row.get("mentioned_brands") or []:
                bid = b.get("id")
                if bid:
                    rec["brands_by_chat"][chat_id].add(bid)
    return by_url


def contributing_chats_for_url(
    url_chats: set[str],
    brands_by_chat: dict[str, set[str]],
    competitor_ids: set[str],
    own_brand_id: str,
    chat_brands_global: dict[str, set[str]],
) -> set[str]:
    """Chats that:
      - retrieved this URL
      - mentioned at least one competitor in this retrieval
      - do NOT already mention the own brand from any source
    """
    out: set[str] = set()
    for cid in url_chats:
        if own_brand_id in chat_brands_global.get(cid, set()):
            continue
        if brands_by_chat.get(cid, set()) & competitor_ids:
            out.add(cid)
    return out


def contributing_chats_for_platform(
    url_records: list[dict],
    competitor_ids: set[str],
    own_brand_id: str,
    chat_brands_global: dict[str, set[str]],
) -> set[str]:
    """Set union across all gap URLs on the platform."""
    out: set[str] = set()
    for rec in url_records:
        out |= contributing_chats_for_url(
            rec["chats"], rec["brands_by_chat"],
            competitor_ids, own_brand_id, chat_brands_global,
        )
    return out


def compute_per_url_metrics(
    rec: dict,
    competitor_ids: set[str],
    competitor_names: dict[str, str],
    own_brand_id: str,
    chat_brands_global: dict[str, set[str]],
) -> dict:
    """Returns the GapUrl record for one URL record (after aggregate_url_rows)."""
    url_chats = rec["chats"]
    brands_by_chat = rec["brands_by_chat"]
    contributing = contributing_chats_for_url(
        url_chats, brands_by_chat, competitor_ids, own_brand_id, chat_brands_global,
    )
    # Per-competitor mention counts (chats where that competitor was mentioned + URL retrieved)
    comp_mentions: dict[str, set[str]] = defaultdict(set)
    for cid, brands in brands_by_chat.items():
        for bid in brands:
            if bid in competitor_ids:
                comp_mentions[bid].add(cid)
    return {
        "url": rec["url"],
        "retrieval_count": rec["retrieval_count"],
        "citation_count": rec["citation_count"],
        "competitors_present": [
            {"brand_id": bid, "brand_name": competitor_names.get(bid, bid), "mention_chats": len(chats)}
            for bid, chats in sorted(comp_mentions.items(), key=lambda x: -len(x[1]))
        ],
        "contributing_chats": len(contributing),
    }
