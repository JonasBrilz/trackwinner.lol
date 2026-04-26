from pydantic import BaseModel
from typing import Optional, Literal
from dataclasses import dataclass, field
from .prep.schemas import PreparationPayload, AcvInfo


class UserInputs(BaseModel):
    peec_project_id: str
    visit_to_lead_rate: float
    lead_to_customer_rate: float
    acv_eur: Optional[float] = None  # if None, researched via Tavily
    visibility_increase_pp: float = 5.0  # percentage points to increase visibility by


class Brand(BaseModel):
    id: str
    name: str
    is_own: bool = False


class Prompt(BaseModel):
    id: str
    message: str
    search_volume: int = 0  # monthly search volume from Peec
    tags: list[str] = []
    topics: list[str] = []
    location: Optional[str] = None


class BrandsReportRow(BaseModel):
    prompt_id: str
    model_id: str
    brand_id: str
    visibility: float
    position: Optional[float] = None
    sentiment: Optional[float] = None


class PromptVolume(BaseModel):
    prompt_id: str
    chats_last_30_days: int


class MarketEstimate(BaseModel):
    ai_query_share: float  # fraction of relevant search queries that happen on AI assistants (Tavily-researched)
    peec_to_global_multiplier: float  # fallback only: chats_30d × this ≈ global AI conversations
    sources: list[str]
    rationale: str


class ActionRateEstimate(BaseModel):
    base_rate: float
    sources: list[str]
    rationale: str


class PromptRevenue(BaseModel):
    prompt_id: str
    prompt_message: str
    volume_source: Literal["search_volume", "tavily_research", "chat_fallback"]
    search_volume: int  # monthly search volume used (0 if chat_fallback)
    volume_source_urls: list[str] = []  # citation URLs when volume_source=tavily_research
    your_visibility: float
    your_position: Optional[float]
    top_competitor_visibility: float
    top_competitor_name: str
    annual_mentions: float
    current_annual_revenue_eur: float
    target_visibility: float
    target_position: float
    target_annual_revenue_eur: float
    revenue_lift_eur: float
    ai_summary: str = "this will be the ai summary"  # populated later by Pioneer (Fastino)


class ScenarioOutcome(BaseModel):
    """Per-scenario lift result for a single prompt."""
    target_visibility: float
    target_position: float
    target_annual_revenue_eur: float
    revenue_lift_eur: float


class PromptRevenueDual(BaseModel):
    """Per-prompt revenue with both scenarios baked in. Used at the top level
    of EnhancedFinalReport so Pioneer gets a single payload with full context."""
    prompt_id: str
    prompt_message: str
    volume_source: Literal["search_volume", "tavily_research", "chat_fallback"]
    search_volume: int
    volume_source_urls: list[str] = []
    your_visibility: float
    your_position: Optional[float]
    top_competitor_visibility: float
    top_competitor_name: str
    annual_mentions: float
    current_annual_revenue_eur: float
    pessimistic: ScenarioOutcome
    optimistic: ScenarioOutcome
    ai_summary: str = "this will be the ai summary"


class CompetitorStanding(BaseModel):
    competitor_name: str
    prompts_won_against_you: int  # competitor's visibility > yours on this many prompts
    competitor_avg_visibility: float
    your_avg_visibility: float


class ActionRecommendation(BaseModel):
    prompt_id: str
    prompt_message: str
    revenue_lift_eur: float
    action_type: Literal[
        "pr_placement", "comparison_page", "schema_enhancement",
        "page_refresh", "ugc_engagement"
    ]
    rationale: str
    evidence_signals: list[str]
    suggested_targets: list[str]


class ScenarioBracket(BaseModel):
    """Side-by-side summary of two scenarios for the dual-scenario report."""
    pessimistic_visibility_increase_pp: float
    optimistic_visibility_increase_pp: float
    pessimistic_total_revenue_lift_eur: float
    optimistic_total_revenue_lift_eur: float
    pessimistic_customer_equivalents: float
    optimistic_customer_equivalents: float


class FinalReport(BaseModel):
    total_current_annual_revenue_eur: float
    total_potential_annual_revenue_eur: float
    total_revenue_lift_eur: float

    # Headline stats
    total_prompts: int
    untapped_prompt_count: int        # prompts where own visibility = 0
    prompts_using_real_volume: int    # search_volume from Peec or Tavily
    prompts_using_chat_fallback: int  # chats × peec_multiplier path
    overall_your_visibility: float    # simple avg across prompts
    leader_name: str
    leader_visibility: float
    visibility_gap_pp: float          # (leader - you) × 100, in percentage points
    top3_lift_share_pct: float        # top 3 prompts' share of total lift, 0–100
    customer_equivalents: float       # total_lift / acv_eur

    competitive_landscape: list[CompetitorStanding]  # sorted desc by wins-against-you
    market_estimate: MarketEstimate
    action_rate_estimate: ActionRateEstimate
    visit_to_lead_rate: float
    lead_to_customer_rate: float
    prompt_revenues: list[PromptRevenue]
    top_actions: list[ActionRecommendation]
    executive_summary: str = ""


class EnhancedFinalReport(BaseModel):
    """Combined output of /roi/full-analysis. Contains:
      - one top-level executive_summary covering both scenarios (Gemini)
      - the prep-pipeline payload (paid-media gap data, baseline, projected vis)
      - two FinalReport objects: lift computed with pessimistic + optimistic deltas
        (their executive_summary fields are intentionally empty — see the umbrella one above)
      - a top-level scenario bracket for quick comparison
      - the ACV used (researched via Tavily if not user-provided)
    """
    company_name: str
    executive_summary: str = ""
    acv: AcvInfo
    bracket: ScenarioBracket
    prompt_revenues: list[PromptRevenueDual]   # merged top 10 with both scenarios + one Pioneer summary
    pessimistic: FinalReport                   # full report; .prompt_revenues emptied (use top-level instead)
    optimistic: FinalReport                    # full report; .prompt_revenues emptied (use top-level instead)
    prep: PreparationPayload


@dataclass
class BrandsReportSummary:
    your_visibility: float
    your_position: Optional[float]
    top_competitor_visibility: float
    top_competitor_id: str
    top_competitor_name: str


@dataclass
class ProjectSetup:
    project_id: str
    own_brand: Brand
    competitors: list[Brand]
    all_brands: list[Brand]
    prompts: list[Prompt]
