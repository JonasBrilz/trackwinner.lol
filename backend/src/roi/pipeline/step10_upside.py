from .step6_position import position_weight
from .step9_revenue import compute_current_revenue, annual_global_ai_queries
from ..models import (
    Prompt, BrandsReportSummary, MarketEstimate, ActionRateEstimate, PromptRevenue
)

UNTAPPED_FLOOR = 0.005


def build_prompt_revenue(
    prompt: Prompt,
    summary: BrandsReportSummary,
    chats_30d: int,
    search_volume: int,
    volume_source_urls: list[str],
    volume_from_tavily: bool,
    market: MarketEstimate,
    action: ActionRateEstimate,
    visit_to_lead: float,
    lead_to_customer: float,
    acv_eur: float,
    visibility_increase_pp: float = 5.0,
) -> PromptRevenue:
    effective_vis = max(summary.your_visibility, UNTAPPED_FLOOR)

    annual_mentions, current_rev, formula_source = compute_current_revenue(
        search_volume, chats_30d, effective_vis, summary.your_position,
        market, action, visit_to_lead, lead_to_customer, acv_eur,
    )

    target_visibility = min(effective_vis + visibility_increase_pp / 100, 1.0)
    target_position = max((summary.your_position or 5) - 2, 1)

    annual_queries, _ = annual_global_ai_queries(search_volume, chats_30d, market)
    annual_mentions_target = annual_queries * target_visibility
    target_actions = annual_mentions_target * action.base_rate * position_weight(target_position)
    target_rev = target_actions * visit_to_lead * lead_to_customer * acv_eur

    if formula_source == "search_volume":
        report_source = "tavily_research" if volume_from_tavily else "search_volume"
    else:
        report_source = "chat_fallback"

    return PromptRevenue(
        prompt_id=prompt.id,
        prompt_message=prompt.message,
        volume_source=report_source,  # type: ignore[arg-type]
        search_volume=search_volume if formula_source == "search_volume" else 0,
        volume_source_urls=volume_source_urls if volume_from_tavily else [],
        your_visibility=summary.your_visibility,
        your_position=summary.your_position,
        top_competitor_visibility=summary.top_competitor_visibility,
        top_competitor_name=summary.top_competitor_name,
        annual_mentions=annual_mentions,
        current_annual_revenue_eur=current_rev,
        target_visibility=target_visibility,
        target_position=float(target_position),
        target_annual_revenue_eur=target_rev,
        revenue_lift_eur=max(0.0, target_rev - current_rev),
    )
