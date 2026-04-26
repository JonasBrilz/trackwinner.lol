// Paid-Media offer state. The card content is now derived from
// prep.paid_media_opportunities in lib/peec.ts; this module only keeps
// the persistent state-machine plumbing and shared constants.

export type CardState = "estimate" | "sending" | "received" | "accepted";

export type Figures = {
  cost: string;
  gain: string;
  gainDelta: string;
};

export const STORAGE_KEY = "peec.paidmedia.state.v1";
export const CONTEXT_KEY = "peec.offer.context.v1";
export const ANALYSIS_FLAG = "peec.hasAnalysis";
export const NOTIFY_EMAIL = "kalwajonas@gmail.com";

export type OfferContext = {
  visitToLead?: number;
  leadToCustomer?: number;
  avgRevenuePerCustomer?: number;
};

export function loadContext(): OfferContext | undefined {
  try {
    const raw = localStorage.getItem(CONTEXT_KEY);
    return raw ? (JSON.parse(raw) as OfferContext) : undefined;
  } catch {
    return undefined;
  }
}

export function saveContext(ctx: OfferContext): void {
  try {
    localStorage.setItem(CONTEXT_KEY, JSON.stringify(ctx));
  } catch {
    /* noop */
  }
}
