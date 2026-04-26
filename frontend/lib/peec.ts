// Live data accessor for the /report page. Fetches the full ROI analysis
// from the deployed backend and exposes the UI types + small formatters
// used across sections.

export type Competitor = {
  competitor_name: string;
  prompts_won_against_you: number;
  competitor_avg_visibility: number;
  your_avg_visibility: number;
};

export type PromptRevenueScenario = {
  target_visibility: number;
  target_position: number;
  target_annual_revenue_eur: number;
  revenue_lift_eur: number;
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
  pessimistic: PromptRevenueScenario;
  optimistic: PromptRevenueScenario;
  ai_summary?: string;
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

export type Acv = {
  value_eur: number;
  source?: string;
  notes?: string;
};

export type PeecRoot = {
  company_name: string;
  executive_summary?: string;
  acv?: Acv;
  bracket: Bracket;
  prompt_revenues: PromptRevenue[];
  pessimistic: ReportSlice;
  optimistic: ReportSlice;
  prep: PrepData;
};

export const API_BASE_URL = "https://hackathon-470511209824.europe-west1.run.app";
export const DEFAULT_PROJECT_ID = "or_47ccb54e-0f32-4c95-b460-6a070499d084";
export const FETCH_TIMEOUT_MS = 120_000;

export async function fetchReport(
  projectId: string = DEFAULT_PROJECT_ID,
  signal?: AbortSignal,
): Promise<PeecRoot> {
  // Routed through the Next.js proxy (app/api/roi/full-analysis) to avoid
  // browser CORS — the backend doesn't set Access-Control-Allow-Origin.
  const url = `/api/roi/full-analysis?peec_project_id=${encodeURIComponent(projectId)}`;
  const res = await fetch(url, { signal, cache: "no-store" });
  if (!res.ok) {
    throw new Error(`backend ${res.status}`);
  }
  return (await res.json()) as PeecRoot;
}

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

export function lowestVisibilityPrompts(
  root: PeecRoot,
  n: number,
): PromptRevenue[] {
  return [...root.prompt_revenues]
    .sort((a, b) => a.your_visibility - b.your_visibility)
    .slice(0, n);
}

export function topActions(slice: ReportSlice, n: number): TopAction[] {
  return slice.top_actions.slice(0, n);
}

export function competitorsRanked(slice: ReportSlice): Competitor[] {
  return [...slice.competitive_landscape].sort(
    (a, b) => b.prompts_won_against_you - a.prompts_won_against_you,
  );
}

export type PromptDetail = Omit<PromptRevenue, "pessimistic" | "optimistic"> &
  PromptRevenueScenario & {
    pessimistic_revenue_lift_eur: number;
    optimistic_revenue_lift_eur: number;
    action: TopAction | null;
  };

export function allPromptsByLift(
  root: PeecRoot,
  slice: ReportSlice,
): PromptDetail[] {
  const actionsById = new Map(slice.top_actions.map((a) => [a.prompt_id, a]));
  return root.prompt_revenues
    .map((p) => {
      const { pessimistic: pess, optimistic: opt, ...rest } = p;
      return {
        ...rest,
        ...opt,
        pessimistic_revenue_lift_eur: pess.revenue_lift_eur,
        optimistic_revenue_lift_eur: opt.revenue_lift_eur,
        action: actionsById.get(p.prompt_id) ?? null,
      };
    })
    .sort((a, b) => b.revenue_lift_eur - a.revenue_lift_eur);
}

export function paidMediaOpportunities(
  root: PeecRoot,
  n = 3,
): PaidMediaOpportunity[] {
  return root.prep.paid_media_opportunities.slice(0, n);
}
