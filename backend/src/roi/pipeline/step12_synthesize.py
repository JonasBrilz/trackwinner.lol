from ..models import (
    MarketEstimate, ActionRateEstimate, PromptRevenue,
    ActionRecommendation, FinalReport, BrandsReportSummary,
    CompetitorStanding, ProjectSetup,
)


async def _safe_executive_summary(facts: dict) -> str:
    """Belt-and-suspenders wrapper: lazy-imports the Gemini client and catches
    everything (including ImportError). The pipeline never blocks on this."""
    try:
        from ..clients import gemini
        return await gemini.synthesize_summary(facts)
    except Exception as e:
        print(f"[step12] executive_summary unavailable ({type(e).__name__}: {e})")
        return ""


def _competitive_landscape(
    setup: ProjectSetup,
    summaries: dict[str, BrandsReportSummary],
    brand_vis: dict[tuple[str, str], float],
) -> list[CompetitorStanding]:
    own_id = setup.own_brand.id
    standings: list[CompetitorStanding] = []

    for comp in setup.competitors:
        wins = 0
        comp_vis_sum = 0.0
        own_vis_sum = 0.0
        n = 0
        for prompt_id in summaries:
            comp_vis = brand_vis.get((prompt_id, comp.id), 0.0)
            own_vis = brand_vis.get((prompt_id, own_id), 0.0)
            if comp_vis > own_vis:
                wins += 1
            comp_vis_sum += comp_vis
            own_vis_sum += own_vis
            n += 1
        if n == 0:
            continue
        standings.append(CompetitorStanding(
            competitor_name=comp.name,
            prompts_won_against_you=wins,
            competitor_avg_visibility=round(comp_vis_sum / n, 4),
            your_avg_visibility=round(own_vis_sum / n, 4),
        ))

    standings.sort(key=lambda s: -s.prompts_won_against_you)
    return standings


async def run(
    prompt_revenues: list[PromptRevenue],
    actions: list[ActionRecommendation],
    market: MarketEstimate,
    action_rate: ActionRateEstimate,
    visit_to_lead: float,
    lead_to_customer: float,
    setup: ProjectSetup,
    summaries: dict[str, BrandsReportSummary],
    brand_vis: dict[tuple[str, str], float],
    acv_eur: float,
) -> FinalReport:
    total_current = sum(p.current_annual_revenue_eur for p in prompt_revenues)
    total_target = sum(p.target_annual_revenue_eur for p in prompt_revenues)
    total_lift = sum(p.revenue_lift_eur for p in prompt_revenues)
    sorted_by_lift = sorted(prompt_revenues, key=lambda p: -p.revenue_lift_eur)
    top_10 = sorted_by_lift[:10]

    # Volume-source mix
    real_volume = sum(1 for p in prompt_revenues if p.volume_source in ("search_volume", "tavily_research"))
    chat_fb = sum(1 for p in prompt_revenues if p.volume_source == "chat_fallback")

    # Untapped: prompts where own visibility is exactly 0 (we never appear)
    untapped = sum(1 for s in summaries.values() if s.your_visibility == 0.0)

    # Overall visibility — simple avg
    if summaries:
        overall_vis = sum(s.your_visibility for s in summaries.values()) / len(summaries)
    else:
        overall_vis = 0.0

    # Leader: competitor with highest avg visibility across all prompts
    own_id = setup.own_brand.id
    leader_name = setup.own_brand.name
    leader_vis = overall_vis
    for comp in setup.competitors:
        per_prompt = [brand_vis.get((pid, comp.id), 0.0) for pid in summaries]
        if not per_prompt:
            continue
        avg = sum(per_prompt) / len(per_prompt)
        if avg > leader_vis:
            leader_vis = avg
            leader_name = comp.name

    visibility_gap_pp = round((leader_vis - overall_vis) * 100, 2)

    # Top-3 share of total lift
    top3_lift = sum(p.revenue_lift_eur for p in sorted_by_lift[:3])
    top3_share = round((top3_lift / total_lift) * 100, 1) if total_lift > 0 else 0.0

    customer_eq = round(total_lift / acv_eur, 2) if acv_eur > 0 else 0.0

    landscape = _competitive_landscape(setup, summaries, brand_vis)

    print(f"[step12] assembled report — current=€{total_current:,.0f}, lift=€{total_lift:,.0f}")
    print(f"[step12] {untapped}/{len(summaries)} prompts untapped, leader={leader_name} ({leader_vis:.1%} vs you {overall_vis:.1%})")
    print(f"[step12] top3 share={top3_share}%, customer_eq={customer_eq}")

    summary_facts = {
        "company": setup.own_brand.name,
        "total_revenue_lift_eur": int(total_lift),
        "customer_equivalents_per_year": customer_eq,
        "current_visibility_pct": round(overall_vis * 100, 1),
        "leader_name": leader_name,
        "leader_visibility_pct": round(leader_vis * 100, 1),
        "visibility_gap_pp": visibility_gap_pp,
        "prompts_total": len(summaries),
        "prompts_untapped": untapped,
        "top3_lift_share_pct": top3_share,
        "top_competitors_beating_you": [
            {"name": c.competitor_name, "prompts_won": c.prompts_won_against_you}
            for c in landscape[:3]
        ],
    }
    summary = await _safe_executive_summary(summary_facts)
    if summary:
        print(f"[step12] executive_summary: {summary[:140]}{'...' if len(summary) > 140 else ''}")
    else:
        print("[step12] executive_summary: (empty — Gemini unavailable, report unaffected)")

    return FinalReport(
        total_current_annual_revenue_eur=total_current,
        total_potential_annual_revenue_eur=total_target,
        total_revenue_lift_eur=total_lift,
        total_prompts=len(summaries),
        untapped_prompt_count=untapped,
        prompts_using_real_volume=real_volume,
        prompts_using_chat_fallback=chat_fb,
        overall_your_visibility=round(overall_vis, 4),
        leader_name=leader_name,
        leader_visibility=round(leader_vis, 4),
        visibility_gap_pp=visibility_gap_pp,
        top3_lift_share_pct=top3_share,
        customer_equivalents=customer_eq,
        competitive_landscape=landscape,
        market_estimate=market,
        action_rate_estimate=action_rate,
        visit_to_lead_rate=visit_to_lead,
        lead_to_customer_rate=lead_to_customer,
        prompt_revenues=top_10,
        top_actions=actions,
        executive_summary=summary,
    )
