// Data accessor for the /report page. Reads the mock JSON the backend
// will eventually serve, narrows to the UI-relevant fields, and exposes
// small formatters used across sections.

import raw from "@/Data/Mock.json";

export type Competitor = {
  competitor_name: string;
  prompts_won_against_you: number;
  competitor_avg_visibility: number;
  your_avg_visibility: number;
};

export type PromptRevenue = {
  prompt_id: string;
  prompt_message: string;
  volume_source: string;
  search_volume: number;
  volume_source_urls: string[];
  your_visibility: number;
  your_position: number;
  top_competitor_visibility: number;
  top_competitor_name: string;
  annual_mentions: number;
  current_annual_revenue_eur: number;
  target_visibility: number;
  target_position: number;
  target_annual_revenue_eur: number;
  revenue_lift_eur: number;
};

export type TopAction = {
  prompt_id: string;
  prompt_message: string;
  revenue_lift_eur: number;
  action_type: string;
  rationale: string;
  evidence_signals: string[];
  suggested_targets: string[];
};

export type ReportSlice = {
  total_revenue_lift_eur: number;
  total_prompts: number;
  untapped_prompt_count: number;
  prompts_using_real_volume: number;
  overall_your_visibility: number;
  leader_name: string;
  leader_visibility: number;
  visibility_gap_pp: number;
  top3_lift_share_pct: number;
  customer_equivalents: number;
  competitive_landscape: Competitor[];
  market_estimate: {
    ai_query_share: number;
    sources: string[];
    rationale: string;
  };
  prompt_revenues: PromptRevenue[];
  top_actions: TopAction[];
  executive_summary?: string;
};

export type Bracket = {
  pessimistic_visibility_increase_pp: number;
  optimistic_visibility_increase_pp: number;
  pessimistic_total_revenue_lift_eur: number;
  optimistic_total_revenue_lift_eur: number;
  pessimistic_customer_equivalents: number;
  optimistic_customer_equivalents: number;
};

export type PaidMediaPricing = {
  low_usd: number | null;
  high_usd: number | null;
  source: string;
  notes: string;
};

export type GapUrlCompetitor = {
  brand_id: string;
  brand_name: string;
  mention_chats: number;
};

export type GapUrl = {
  url: string;
  retrieval_count: number;
  citation_count: number;
  contributing_chats: number;
  competitors_present: GapUrlCompetitor[];
};

export type PaidMediaOpportunity = {
  domain: string;
  classification: string;
  classification_confidence: number;
  pricing: PaidMediaPricing;
  gap_urls: GapUrl[];
  contributing_chat_count: number;
  delta_chats_pessimistic: number;
  delta_chats_optimistic: number;
  delta_visibility_pp_pessimistic: number;
  delta_visibility_pp_optimistic: number;
};

export type PrepData = {
  company: { name: string; project_id?: string; brand_id?: string };
  window: { start_date: string; end_date: string; days: number };
  baseline: {
    total_chats: number;
    chats_mentioning_brand: number;
    visibility_score: number;
  };
  paid_media_opportunities: PaidMediaOpportunity[];
  projected: {
    pessimistic: { visibility_score: number; delta: number };
    optimistic: { visibility_score: number; delta: number };
  };
  warnings: string[];
};

export type PeecRoot = {
  company_name: string;
  bracket: Bracket;
  pessimistic: ReportSlice;
  optimistic: ReportSlice;
  prep: PrepData;
};

const root = raw as unknown as PeecRoot;

export const BRAND = root.company_name;
export const bracket = root.bracket;
export const prep = root.prep;
export const pessimistic = root.pessimistic;
export const optimistic = root.optimistic;

// Default scenario the rest of the report renders against.
export const data = optimistic;

export function formatEuro(n: number, withSign = false): string {
  const rounded = Math.round(n);
  const formatted = rounded.toLocaleString("en-US");
  if (withSign && rounded > 0) return `+€${formatted}`;
  return `€${formatted}`;
}

export function formatPct(ratio: number, digits = 0): string {
  return `${(ratio * 100).toFixed(digits)}%`;
}

export function formatUsdRange(p: PaidMediaPricing): string {
  const lo = p.low_usd;
  const hi = p.high_usd;
  if (lo == null && hi == null) return "RFQ";
  if (lo != null && hi != null) {
    if (lo === hi) return `$${lo.toLocaleString("en-US")}`;
    return `$${lo.toLocaleString("en-US")} – $${hi.toLocaleString("en-US")}`;
  }
  if (lo != null) return `from $${lo.toLocaleString("en-US")}`;
  return `up to $${(hi ?? 0).toLocaleString("en-US")}`;
}

export function lowestVisibilityPrompts(n: number): PromptRevenue[] {
  return [...data.prompt_revenues]
    .sort((a, b) => a.your_visibility - b.your_visibility)
    .slice(0, n);
}

export function topActions(n: number): TopAction[] {
  return data.top_actions.slice(0, n);
}

export function competitorsRanked(): Competitor[] {
  return [...data.competitive_landscape].sort(
    (a, b) => b.prompts_won_against_you - a.prompts_won_against_you
  );
}

export type PromptDetail = PromptRevenue & {
  action: TopAction | null;
};

export function allPromptsByLift(): PromptDetail[] {
  const actionsById = new Map(data.top_actions.map((a) => [a.prompt_id, a]));
  return [...data.prompt_revenues]
    .sort((a, b) => b.revenue_lift_eur - a.revenue_lift_eur)
    .map((p) => ({ ...p, action: actionsById.get(p.prompt_id) ?? null }));
}

export function paidMediaOpportunities(n = 3): PaidMediaOpportunity[] {
  return prep.paid_media_opportunities.slice(0, n);
}
