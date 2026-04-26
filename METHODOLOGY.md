# Peec Performance

*How our forecasts revenue lift from AI-engine visibility, what is measured vs. assumed, and what a real CRM connection replaces.*

---

## TL;DR

The model is a five-step chain from AI-engine visibility to closed revenue. Three steps come from Peec data. The remaining steps come from industry benchmarks plus one company-level constant (ARPU). Every input below is labeled as **measured**, **benchmarked**, or **assumed**, and paired with the system of record that would replace it once a brand connects its CRM, analytics, and billing.

---

## 1. The model in one chain

For each tracked prompt:

```
visibility gap
  → annual mentions on AI engines     (Peec, extrapolated to a year)
  → user actions (clicks / visits)    × action_rate
  → leads                             × visit_to_lead_rate
  → customers                         × lead_to_customer_rate
  → revenue lift (€)                  × ARPU
```

Each `×` is a multiplier. The accuracy of the bottom line is the product of the accuracy of every step.

---

## 2. The Peec data window

Peec projects that are recently created surface **one day of chats at a time**. Our mock data is pre-aggregated against a 90-day window so the shape of the output is legible; the pipeline itself does not depend on window length and runs identically against one day or ninety. In a real deployment we would pair Peec with real customer data that has been collected over months.

---

## 3. Inventory of inputs

Each row below is a number that influences the forecast. Type column: **M** = measured from Peec, **B** = industry benchmark, **A** = internal assumption.

| # | Input | Value (mock) | Type | Where it lives | Replaced in production by |
|---|-------|--------------|------|----------------|---------------------------|
| 1 | `ai_query_share` | 0.10 | B | `market_estimate` in Mock.json | GA4 or Plausible: real share of sessions arriving from AI referrers (chatgpt.com, perplexity.ai, gemini.google.com, claude.ai) |
| 2 | `peec_to_global_multiplier` | 10× | A | `market_estimate` fallback when `search_volume = 0` | Real per-prompt search volume from Ahrefs, Semrush, or Google Search Console |
| 3 | `action_rate_estimate.base_rate` | 0.12 | B | per-prompt revenue calculation | GA4 engagement and click-through rate on AI-referred traffic, segmented by topic |
| 4 | `visit_to_lead_rate` | 0.03 | B | per-prompt revenue calculation | CRM (HubSpot, Salesforce): real MQL conversion rate by traffic source |
| 5 | `lead_to_customer_rate` | 0.15 | B | per-prompt revenue calculation | CRM: real MQL to Closed-Won rate by source and segment |
| 6 | `ARPU` | €4,800 in `paidMedia.ts`, €10,000 implied in mock | A | `paidMedia.ts` constant and mock generation | True ARPU, segmented by plan tier through research / outreach |
| 7 | Pessimistic capture rate | 60% of optimistic | A | `delta_chats_pessimistic` in `prep` | Historical placement-to-mention conversion from prior paid campaigns on comparable domains |
| 8 | Classification confidence threshold | 0.75 retained, 0.8 noted | M | `prep.warnings` | Editorial review of the long tail; SerpAPI for confirmed paid signals; outreach pipeline for RFQ pricing |
| 9 | Annual mention extrapolation | linear × 365 / window_days | A | per-prompt `annual_mentions` | Multi-month Peec data with seasonality controls (Q4 and Q1 in B2B SaaS can differ meaningfully) |
| 10 | Per-prompt visibility ceiling | leader visibility | A | `target_visibility` in mock | A/B test results from real placements; today we assume the entire visibility gap is closeable |

### The two highest-leverage rows

- **Row 2.** Because 49 of 50 prompts in the current dataset lack real search volume, the `peec_to_global_multiplier` scales most of the forecast. A real SEO data integration on day one of a client engagement removes this single largest source of error.
- **Row 3.** A 12% conversion from "appears in an AI response" to "user takes action" sits at the upper end of public AI-referral benchmarks. A brand's own GA4 can typically settle this within a week of measurement.

---

## 4. From benchmarks to real proxies

For a real client engagement, the minimum integration footprint, in order:

1. **Web analytics (GA4 or equivalent).** One-day setup. Replaces rows 1, 3, and partially 9.
2. **CRM (HubSpot, Salesforce, Attio).** If data hygiene exists, quickly implementable. Replaces rows 4 and 5.
3. **Outreach information and Billing System (Stripe, Chargebee).** Replaces row 6 with real, segmented ARPU.
4. **SEO tooling (Ahrefs API, Semrush, GSC).** Replaces row 2 directly.
5. **Long term Peec data** Replaces row 9, adds seasonality.

After all five, the forecast becomes measurement-driven with only row 7 remaining as a benchmark. Row 7 can only be properly calibrated through observed lift on actual paid-media campaigns.

---

## 5. Where benchmarks beat proxies

Not every number should be replaced. Some industry benchmarks are stable enough across e.g. SaaS to act as sensible defaults:

- `visit_to_lead_rate` and `lead_to_customer_rate` for early-stage clients with under a few hundred closed-won deals per year, where the brand's own data is too noisy to be statistically meaningful.
- `action_rate_estimate.base_rate` for new product launches with no AI-referral history yet.

The right default is: use the brand's own proxy when it exists, fall back to benchmarks with explicit confidence bands when it does not, and label every output line with which inputs were measured vs. assumed.

---

## 6. What stays assumed at full integration

Two things this model cannot measure even with every system connected:

1. **Counterfactual lift.** Did the customer convert *because* of the AI mention, or were they coming anyway? Last-click attribution is a workaround, not an answer. Holdout experiments (geo splits, time-series interventions) are the honest fix, but remain a huge challenge in general.
2. **Latency.** A visibility improvement in month 1 does not produce revenue in month 1. The model collapses this into an annualized number for legibility; the actual cash impact lags the visibility shift by the brand's sales cycle.

---

## 7. Bottom line

The forecast is one company-specific number (ARPU) and ten multipliers stacked on top of Peec data. Five of those ten have public industry data behind them, two are model outputs, and three are internal assumptions. A CRM and analytics connection removes the assumptions and gives the brand a measurement-grade version of the same forecast within weeks. The methodology does not change with data quality; only the confidence does.

---

# Part 2: How we compute the lift in euros
... (59 Zeilen verbleibend)
