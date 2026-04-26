from .step6_position import position_weight
from ..models import MarketEstimate, ActionRateEstimate


def annual_global_ai_queries(
    search_volume: int,
    chats_30d: int,
    market: MarketEstimate,
) -> tuple[float, str]:
    """Returns (annual_global_ai_queries_for_this_prompt, source_label).

    Primary path: search_volume × 12 × ai_query_share
    Fallback:     chats_30d × 12 × peec_to_global_multiplier
    """
    if search_volume > 0:
        return search_volume * 12 * market.ai_query_share, "search_volume"
    return chats_30d * 12 * market.peec_to_global_multiplier, "chat_fallback"


def compute_current_revenue(
    search_volume: int,
    chats_30d: int,
    your_visibility: float,
    your_position: float | None,
    market: MarketEstimate,
    action: ActionRateEstimate,
    visit_to_lead: float,
    lead_to_customer: float,
    acv_eur: float,
) -> tuple[float, float, str]:
    """Returns (annual_mentions, annual_revenue_eur, source_label)."""
    annual_queries, source = annual_global_ai_queries(search_volume, chats_30d, market)
    annual_mentions = annual_queries * your_visibility
    effective_action_rate = action.base_rate * position_weight(your_position)
    annual_actions = annual_mentions * effective_action_rate
    annual_revenue = annual_actions * visit_to_lead * lead_to_customer * acv_eur
    return annual_mentions, annual_revenue, source
