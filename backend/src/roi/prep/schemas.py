from typing import Optional, Literal
from pydantic import BaseModel


Classification = Literal[
    "DIRECT_PAID", "AFFILIATE_PAID", "ANALYST_PAID",
    "EDITORIAL_NO_BUY", "UGC", "OTHER",
]


class CompanyRef(BaseModel):
    name: str
    project_id: str
    brand_id: str


class WindowInfo(BaseModel):
    start_date: str
    end_date: str
    days: int


class Baseline(BaseModel):
    total_chats: int
    chats_mentioning_brand: int
    visibility_score: float  # 0–100


class CompetitorPresence(BaseModel):
    brand_id: str
    brand_name: str
    mention_chats: int


class GapUrl(BaseModel):
    url: str
    retrieval_count: int
    citation_count: int
    competitors_present: list[CompetitorPresence]
    contributing_chats: int  # |contributing_chats(u)| for this URL alone


class PricingInfo(BaseModel):
    low_usd: Optional[int]
    high_usd: Optional[int]
    source: str  # URL or "ESTIMATE"
    notes: str


class ContactInfo(BaseModel):
    email: Optional[str]                 # explicitly found via Tavily; None if not surfaced
    source_url: Optional[str]            # where the email came from
    notes: str = ""


class AcvInfo(BaseModel):
    value_eur: float
    source: str  # URL, "user-provided", or "DEFAULT"
    notes: str


class PaidMediaOpportunity(BaseModel):
    domain: str
    classification: Classification
    classification_confidence: float
    pricing: PricingInfo
    contact: ContactInfo                 # advertising/partnerships email + source URL (Tavily)
    gap_urls: list[GapUrl]               # trimmed to top 2 by contributing_chats
    contributing_chat_count: int
    delta_chats_pessimistic: float       # 0.60 × contributing_chat_count, IF-ALONE
    delta_chats_optimistic: float        # 1.00 × contributing_chat_count, IF-ALONE
    delta_visibility_pp_pessimistic: float  # percentage points, IF-ALONE
    delta_visibility_pp_optimistic: float


class ProjectedScenario(BaseModel):
    visibility_score: float  # 0–100
    delta: float             # percentage points vs baseline


class ProjectedVisibility(BaseModel):
    pessimistic: ProjectedScenario
    optimistic: ProjectedScenario


class PreparationPayload(BaseModel):
    company: CompanyRef
    window: WindowInfo
    baseline: Baseline
    paid_media_opportunities: list[PaidMediaOpportunity]
    projected: ProjectedVisibility
    warnings: list[str] = []
