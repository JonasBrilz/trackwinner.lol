from datetime import date, timedelta
from collections import defaultdict
from ..clients.peec import PeecClient
from ..models import ProjectSetup, PromptRevenue, ActionRecommendation

_UGC_DOMAINS = {"reddit.com", "quora.com", "stackoverflow.com", "trustpilot.com", "g2.com"}


def _thirty_days_ago() -> tuple[str, str]:
    today = date.today()
    return (today - timedelta(days=30)).isoformat(), today.isoformat()


def _classify_action(
    prompt_id: str,
    own_brand_id: str,
    domain_rows: list[dict],
    url_rows: list[dict],
) -> tuple[str, list[str], list[str]]:
    """Returns (action_type, evidence_signals, suggested_targets)."""

    prompt_domains = [r for r in domain_rows if str(r.get("prompt_id", "")) == prompt_id]
    prompt_urls = [r for r in url_rows if str(r.get("prompt_id", "")) == prompt_id]

    # 1. PR placement
    editorial_targets = []
    for d in prompt_domains:
        dtype = str(d.get("type", d.get("domain_type", ""))).upper()
        usage_rate = float(d.get("usage_rate", 0.0))
        brands_cited = d.get("brands_cited", [])
        domain = str(d.get("domain", ""))
        if dtype in ("EDITORIAL", "REFERENCE") and usage_rate > 0.1:
            own_cited = any(str(b) == own_brand_id for b in brands_cited)
            if not own_cited and brands_cited:
                editorial_targets.append(domain)
    if len(editorial_targets) >= 2:
        return (
            "pr_placement",
            [f"Competitor cited on {d} (usage_rate > 10%)" for d in editorial_targets[:3]],
            editorial_targets[:5],
        )

    # 2. Comparison / Listicle page
    competitor_comparison_urls = []
    own_has_comparison = False
    for u in prompt_urls:
        cls = str(u.get("classification", u.get("url_type", ""))).upper()
        brand_id = str(u.get("brand_id", ""))
        url = str(u.get("url", ""))
        if cls in ("COMPARISON", "LISTICLE"):
            if brand_id == own_brand_id:
                own_has_comparison = True
            else:
                competitor_comparison_urls.append(url)
    if competitor_comparison_urls and not own_has_comparison:
        return (
            "comparison_page",
            [f"Competitor has comparison/listicle page cited: {u}" for u in competitor_comparison_urls[:2]],
            ["Create a new comparison or alternatives page targeting this prompt intent"],
        )

    # 3. Schema enhancement — own URLs cited but visibility still low
    own_cited_urls = [
        u for u in prompt_urls
        if str(u.get("brand_id", "")) == own_brand_id
        or str(u.get("classification", "")).upper() == "OWN"
    ]
    if own_cited_urls:
        urls = [str(u.get("url", "")) for u in own_cited_urls]
        return (
            "schema_enhancement",
            [f"Your URL cited but visibility low: {u}" for u in urls[:2]],
            urls[:3],
        )

    # 4. Page refresh — own URLs with declining usage
    declining = [
        u for u in own_cited_urls
        if float(u.get("usage_count_trend", u.get("trend", 0))) < 0
    ]
    if declining:
        urls = [str(u.get("url", "")) for u in declining]
        return (
            "page_refresh",
            [f"Declining citation count on {u}" for u in urls[:2]],
            urls[:3],
        )

    # 5. UGC engagement — fallback
    ugc_targets = []
    for d in prompt_domains:
        domain = str(d.get("domain", ""))
        usage_rate = float(d.get("usage_rate", 0.0))
        base = domain.removeprefix("www.")
        if any(ugc in base for ugc in _UGC_DOMAINS) and usage_rate > 0.05:
            ugc_targets.append(domain)

    if ugc_targets:
        return (
            "ugc_engagement",
            [f"UGC domain with high citation rate: {d}" for d in ugc_targets[:2]],
            ugc_targets[:3],
        )

    return (
        "ugc_engagement",
        ["No strong editorial or URL signal found — community presence recommended"],
        ["Reddit communities relevant to this prompt topic"],
    )


async def run(
    setup: ProjectSetup,
    top_10: list[PromptRevenue],
) -> list[ActionRecommendation]:
    start, end = _thirty_days_ago()
    client = PeecClient()
    try:
        domain_rows = await client.domains_report(setup.project_id, start, end)
        url_rows = await client.urls_report(setup.project_id, start, end)
    finally:
        await client.close()

    recommendations: list[ActionRecommendation] = []
    for pr in top_10:
        action_type, signals, targets = _classify_action(
            pr.prompt_id, setup.own_brand.id, domain_rows, url_rows
        )
        recommendations.append(ActionRecommendation(
            prompt_id=pr.prompt_id,
            prompt_message=pr.prompt_message,
            revenue_lift_eur=pr.revenue_lift_eur,
            action_type=action_type,
            rationale="",  # filled in by step12 Gemini synthesis
            evidence_signals=signals,
            suggested_targets=targets,
        ))

    return recommendations
