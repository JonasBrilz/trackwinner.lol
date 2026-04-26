"""Prep pipeline orchestrator (spec §4 steps 1–8).

Inputs: ProjectSetup from step1_setup (we already have own_brand + competitors).
Outputs: PreparationPayload — baseline visibility, paid-media gap opportunities,
projected pessimistic + optimistic visibility scores, warnings.
"""
import asyncio
from datetime import date, timedelta
from collections import defaultdict
from ..clients.peec import PeecClient
from ..models import ProjectSetup
from . import classifier, pricing, contact
from . import impact
from .schemas import (
    PreparationPayload, CompanyRef, WindowInfo, Baseline,
    PaidMediaOpportunity, GapUrl, CompetitorPresence, PricingInfo, ContactInfo,
    ProjectedScenario, ProjectedVisibility,
)

WINDOW_DAYS_MAX = 90
MIN_TOTAL_CHATS = 40
MIN_WINDOW_DAYS = 7
MIN_RETRIEVALS_PER_URL = 2
PESSIMISTIC_FACTOR = impact.PESSIMISTIC_FACTOR
OPTIMISTIC_FACTOR = impact.OPTIMISTIC_FACTOR

# Output trimming
TOP_N_OPPORTUNITIES = 3      # only return top 3 by optimistic lift
TOP_N_GAP_URLS_PER_OPP = 2   # only top 2 URLs per opportunity


def _summarize_warnings(raw: list[str], total_paid_domains: int) -> list[str]:
    """Group repetitive per-domain warnings into counts; keep distinct ones as-is."""
    low_conf = [w for w in raw if "classification confidence" in w]
    rfq = [w for w in raw if "pricing unavailable" in w]
    no_gap = [w for w in raw if "no gap URLs" in w]
    below_floor = [w for w in raw if "below retrieval floor" in w]
    distinct = [
        w for w in raw
        if not any(t in w for t in ("classification confidence", "pricing unavailable", "no gap URLs", "below retrieval floor"))
    ]
    summary: list[str] = []
    if low_conf:
        summary.append(f"{len(low_conf)} of {total_paid_domains} paid domains had low classification confidence (<0.8)")
    if rfq:
        summary.append(f"{len(rfq)} domains had no public pricing (RFQ required)")
    if no_gap:
        summary.append(f"{len(no_gap)} domains classified as paid but had no gap URLs in window")
    if below_floor:
        summary.append(f"{len(below_floor)} domains had all URLs below the retrieval floor (<{MIN_RETRIEVALS_PER_URL})")
    summary.extend(distinct)
    return summary


def _category_hint(setup: ProjectSetup) -> str:
    """Heuristic: derive a category hint from competitor names. For Attio this
    becomes 'CRM' (HubSpot, Salesforce, Pipedrive, Zoho are all CRMs). Simple
    hardcoded lookup is fine for the hackathon."""
    names = " ".join(c.name for c in setup.competitors).lower()
    if any(t in names for t in ["hubspot", "salesforce", "pipedrive", "zoho", "monday"]):
        return "CRM software"
    if any(t in names for t in ["mailchimp", "klaviyo", "sendgrid"]):
        return "email marketing"
    if any(t in names for t in ["asana", "monday", "trello", "clickup"]):
        return "project management"
    return "software"


async def run(setup: ProjectSetup) -> PreparationPayload:
    print(f"\n[prep] starting paid-media preparation for {setup.own_brand.name}")
    warnings: list[str] = []

    # Window: try the past 90 days, auto-detect actual range.
    today = date.today()
    end = today.isoformat()
    start = (today - timedelta(days=WINDOW_DAYS_MAX)).isoformat()

    client = PeecClient()
    try:
        # Step 2 + 3: pull all URL rows (with chat_id dim) and the domain inventory in parallel
        print("[prep/step2-3] fetching all URLs (chat_id dim) + domain inventory")
        all_url_rows, domain_rows = await asyncio.gather(
            client.urls_by_chat(setup.project_id, start, end, limit=10000),
            client.domains_inventory(setup.project_id, start, end, limit=200),
        )
    finally:
        await client.close()

    print(f"[prep] got {len(all_url_rows)} URL rows, {len(domain_rows)} domains")

    # Auto-detect actual window
    chat_brands = impact.build_chat_brands(all_url_rows)
    total_chats, mentioned, vis_score = impact.baseline_stats(chat_brands, setup.own_brand.id)
    print(f"[prep/step2] baseline — total_chats={total_chats}, mentioning_brand={mentioned}, vis={vis_score}%")

    # Approximate window from data (we don't have date in URL rows; use requested window for now)
    actual_start, actual_end = start, end
    actual_days = WINDOW_DAYS_MAX

    if actual_days < MIN_WINDOW_DAYS:
        warnings.append(f"short window ({actual_days} days), results are noisy")
    if total_chats < MIN_TOTAL_CHATS:
        warnings.append(f"low chat volume ({total_chats} chats), confidence reduced")
    if vis_score > 90.0:
        warnings.append("high baseline visibility; ceiling effect limits delta")

    # Step 4: classify domains (sort by retrieval_count desc so we focus on impactful domains)
    category_hint = _category_hint(setup)
    print(f"[prep/step4] category_hint='{category_hint}'")
    domain_rows_sorted = sorted(
        [d for d in domain_rows if d.get("domain")],
        key=lambda d: -int(d.get("retrieval_count", 0)),
    )
    domain_inputs = [
        (str(d.get("domain", "")).lower(), d.get("classification"))
        for d in domain_rows_sorted
    ]
    classifications = await classifier.classify_domains(domain_inputs, category_hint)
    paid_domains = [d for d, _ in domain_inputs if classifier.is_paid(classifications.get(d, {}))]
    print(f"[prep/step4] {len(paid_domains)} paid domains: {paid_domains[:5]}{'...' if len(paid_domains) > 5 else ''}")

    if not paid_domains:
        warnings.append("no paid-media surface found in this category")
        return PreparationPayload(
            company=CompanyRef(name=setup.own_brand.name, project_id=setup.project_id, brand_id=setup.own_brand.id),
            window=WindowInfo(start_date=actual_start, end_date=actual_end, days=actual_days),
            baseline=Baseline(total_chats=total_chats, chats_mentioning_brand=mentioned, visibility_score=vis_score),
            paid_media_opportunities=[],
            projected=ProjectedVisibility(
                pessimistic=ProjectedScenario(visibility_score=vis_score, delta=0.0),
                optimistic=ProjectedScenario(visibility_score=vis_score, delta=0.0),
            ),
            warnings=warnings,
        )

    # Step 5: collect rows for paid domains (already in all_url_rows; just filter)
    rows_by_domain: dict[str, list[dict]] = defaultdict(list)
    for row in all_url_rows:
        url = row.get("url", "")
        if not url:
            continue
        d = impact.domain_of(url)
        if d in paid_domains:
            rows_by_domain[d].append(row)
    print(f"[prep/step5] gap-eligible URL rows per domain: {[(d, len(rs)) for d, rs in rows_by_domain.items()][:5]}")

    # Step 6: pricing + contact-email lookup in parallel (cached)
    pricing_map, contact_map = await asyncio.gather(
        pricing.fetch_pricing_for_domains(paid_domains, category_hint),
        contact.find_contacts(paid_domains, category_hint),
    )

    # Step 7: set-based math
    competitor_ids = {c.id for c in setup.competitors}
    competitor_names = {c.id: c.name for c in setup.competitors}

    opportunities: list[PaidMediaOpportunity] = []
    all_contributing: set[str] = set()

    for domain in paid_domains:
        rows = rows_by_domain.get(domain, [])
        if not rows:
            warnings.append(f"{domain}: classified as paid but no gap URLs in window")
            continue

        url_records = impact.aggregate_url_rows(rows)
        # Drop URLs with retrieval_count below floor (noise)
        url_records = [r for r in url_records.values() if len(r["chats"]) >= MIN_RETRIEVALS_PER_URL]
        if not url_records:
            warnings.append(f"{domain}: all URLs below retrieval floor ({MIN_RETRIEVALS_PER_URL})")
            continue

        platform_chats = impact.contributing_chats_for_platform(
            url_records, competitor_ids, setup.own_brand.id, chat_brands,
        )
        all_contributing |= platform_chats
        n = len(platform_chats)

        gap_urls = []
        for rec in url_records:
            metrics = impact.compute_per_url_metrics(
                rec, competitor_ids, competitor_names, setup.own_brand.id, chat_brands,
            )
            if metrics["contributing_chats"] > 0:
                gap_urls.append(GapUrl(
                    url=metrics["url"],
                    retrieval_count=metrics["retrieval_count"],
                    citation_count=metrics["citation_count"],
                    competitors_present=[
                        CompetitorPresence(**cp) for cp in metrics["competitors_present"]
                    ],
                    contributing_chats=metrics["contributing_chats"],
                ))
        if not gap_urls:
            continue

        cls = classifications.get(domain, {})
        price = pricing_map.get(domain, {})
        contact_rec = contact_map.get(domain, {})
        delta_vis_pp_pess = (n * PESSIMISTIC_FACTOR / total_chats * 100) if total_chats else 0.0
        delta_vis_pp_opt = (n * OPTIMISTIC_FACTOR / total_chats * 100) if total_chats else 0.0

        # Trim to top-N gap URLs per opportunity
        trimmed_urls = sorted(gap_urls, key=lambda g: -g.contributing_chats)[:TOP_N_GAP_URLS_PER_OPP]
        opportunities.append(PaidMediaOpportunity(
            domain=domain,
            classification=cls.get("classification", "OTHER"),  # type: ignore[arg-type]
            classification_confidence=round(cls.get("confidence", 0.0), 2),
            pricing=PricingInfo(
                low_usd=price.get("low_usd"),
                high_usd=price.get("high_usd"),
                source=price.get("source", "ESTIMATE"),
                notes=price.get("notes", ""),
            ),
            contact=ContactInfo(
                email=contact_rec.get("email"),
                source_url=contact_rec.get("source_url"),
                notes=contact_rec.get("notes", ""),
            ),
            gap_urls=trimmed_urls,
            contributing_chat_count=n,
            delta_chats_pessimistic=round(n * PESSIMISTIC_FACTOR, 2),
            delta_chats_optimistic=round(n * OPTIMISTIC_FACTOR, 2),
            delta_visibility_pp_pessimistic=round(delta_vis_pp_pess, 2),
            delta_visibility_pp_optimistic=round(delta_vis_pp_opt, 2),
        ))

        if price.get("low_usd") is None and price.get("high_usd") is None:
            warnings.append(f"{domain}: pricing unavailable, RFQ required")
        if cls.get("confidence", 0.0) < 0.8:
            warnings.append(f"{domain}: classification confidence {cls.get('confidence', 0.0):.2f} (low)")

    # Sort by optimistic lift desc (per spec) — but keep ALL for total math, trim later
    opportunities.sort(key=lambda o: -o.delta_chats_optimistic)
    total_opportunities_count = len(opportunities)
    opportunities_top = opportunities[:TOP_N_OPPORTUNITIES]

    # Step 7 totals: set union, NOT sum of per-platform
    total_n = len(all_contributing)
    delta_pess = total_n * PESSIMISTIC_FACTOR
    delta_opt = total_n * OPTIMISTIC_FACTOR

    new_chats_pess = mentioned + delta_pess
    new_chats_opt = mentioned + delta_opt
    vis_pess = (new_chats_pess / total_chats * 100) if total_chats else 0.0
    vis_opt = (new_chats_opt / total_chats * 100) if total_chats else 0.0

    print(f"[prep/step7] |contributing_total|={total_n} (sum across platforms naively={sum(o.contributing_chat_count for o in opportunities)})")
    print(f"[prep/step7] projected — pess={vis_pess:.2f}% (Δ={vis_pess - vis_score:+.2f}pp), opt={vis_opt:.2f}% (Δ={vis_opt - vis_score:+.2f}pp)")

    summarized_warnings = _summarize_warnings(warnings, len(paid_domains))
    if total_opportunities_count > TOP_N_OPPORTUNITIES:
        summarized_warnings.append(
            f"showing top {TOP_N_OPPORTUNITIES} of {total_opportunities_count} paid-media opportunities by optimistic lift"
        )

    return PreparationPayload(
        company=CompanyRef(name=setup.own_brand.name, project_id=setup.project_id, brand_id=setup.own_brand.id),
        window=WindowInfo(start_date=actual_start, end_date=actual_end, days=actual_days),
        baseline=Baseline(total_chats=total_chats, chats_mentioning_brand=mentioned, visibility_score=vis_score),
        paid_media_opportunities=opportunities_top,
        projected=ProjectedVisibility(
            pessimistic=ProjectedScenario(visibility_score=round(vis_pess, 2), delta=round(vis_pess - vis_score, 2)),
            optimistic=ProjectedScenario(visibility_score=round(vis_opt, 2), delta=round(vis_opt - vis_score, 2)),
        ),
        warnings=summarized_warnings,
    )
