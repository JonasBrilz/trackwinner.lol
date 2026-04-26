# Paid Media Visibility Preparation Pipeline

**Status:** v1.1
**Changelog:**
- v1.1 — Replaced the naive per-URL summation in Step 7 with proper set-based aggregation. The factor (60% / 100%) is now a per-chat probability rather than a multiplier on aggregate counts. Fixes overcounting when the same chat retrieves multiple gap URLs.
- v1.0 — Initial spec.

**Scope:** Preparation pipeline that gathers all inputs needed by the existing analytics backend. Produces a structured payload containing baseline visibility, paid-media gap URLs, pricing data, and projected visibility (pessimistic and optimistic).
**Out of scope:** Customer-acquisition math, revenue projection, ROI calculation. The existing analytics backend handles those.

---

## 1. Purpose

Given a company name, gather everything the analytics backend needs to score paid-media opportunities:

1. The brand's current visibility score in Peec AI.
2. The list of paid-media domains where the brand is absent but competitors are present.
3. Pricing estimates for getting placed on those domains.
4. Projected visibility scores (pessimistic and optimistic) if the brand bought placement.

The output is a single JSON payload. The analytics backend consumes it and produces the user-facing report.

## 2. Inputs and outputs

### Input

```json
{
  "company_name": "Attio"
}
```

That is the only required field. Everything else is configurable via constants in the implementation.

### Output

```typescript
interface PreparationPayload {
  company: { name: string; project_id: string; brand_id: string };
  window: { start_date: string; end_date: string; days: number };
  baseline: {
    total_chats: number;
    chats_mentioning_brand: number;
    visibility_score: number;             // percentage, 0-100
  };
  paid_media_opportunities: PaidMediaOpportunity[];
  projected: {
    pessimistic: { visibility_score: number; delta: number };
    optimistic:  { visibility_score: number; delta: number };
  };
  warnings: string[];
}

interface PaidMediaOpportunity {
  domain: string;                          // e.g. "g2.com"
  classification: string;                  // from Tavily: DIRECT_PAID | AFFILIATE_PAID | ANALYST_PAID
  classification_reasoning: string;        // human-readable from Tavily
  pricing: {
    low_usd: number | null;
    high_usd: number | null;
    source: string;                        // URL or "ESTIMATE"
    notes: string;
  };
  gap_urls: GapUrl[];
  contributing_chat_count: number;         // |contributing_chats(p)|: chats that retrieve a gap URL on this platform AND mention a competitor AND don't mention own brand
  delta_chats_pessimistic: number;         // 0.60 × contributing_chat_count, IF-ALONE estimate
  delta_chats_optimistic: number;          // 1.00 × contributing_chat_count, IF-ALONE estimate
}

interface GapUrl {
  url: string;
  retrieval_count: number;
  citation_count: number;
  competitors_present: { brand_id: string; brand_name: string; mention_chats: number }[];
  contributing_chats: number;              // |contributing_chats(u)| for this URL alone
}
```

**Note on per-platform values:** `delta_chats_pessimistic` and `delta_chats_optimistic` on a platform are "if alone" estimates. They will NOT sum to the totals in `projected.pessimistic` / `projected.optimistic` because the same chat can retrieve gap URLs on multiple platforms. The `projected` totals are computed via set union and are the authoritative numbers.

## 3. Pipeline overview

```
INPUT: company_name

  Step 1  Resolve company to Peec project + brand
  Step 2  Pull baseline (total chats, chats mentioning brand, visibility)
  Step 3  Pull domain inventory from Peec
  Step 4  Classify domains as paid media via Tavily
  Step 5  For each paid domain, pull gap URLs from Peec
  Step 6  For each paid domain, fetch pricing via Tavily
  Step 7  Compute pessimistic and optimistic visibility deltas
  Step 8  Assemble payload, return

OUTPUT: PreparationPayload
```

## 4. Steps in detail

### Step 1: Resolve company to project + brand

Use Peec MCP. Fail fast if the company is not tracked.

```python
projects = peec.list_projects()
project = next((p for p in projects if company_name.lower() in p.name.lower()), None)
if project is None:
    raise CompanyNotTracked(company_name)

brands = peec.list_brands(project.id)
own_brand = next((b for b in brands if b.is_own), None)
competitors = [b for b in brands if not b.is_own]

if own_brand is None or not competitors:
    raise InvalidProjectSetup("missing own brand or competitors")
```

### Step 2: Pull baseline

Pull all chat-level data for the available window. The window is auto-detected (use the actual data range, do not hardcode 30 days).

```python
# Pull max 90 days; the response shows what's actually available
url_data = peec.get_url_report(
    project_id=project.id,
    start_date=today - timedelta(days=90),
    end_date=today,
    dimensions=["chat_id", "date"],
    limit=10000,
)

# Auto-detect actual window
dates = sorted({row.date for row in url_data.rows})
actual_start, actual_end = dates[0], dates[-1]
actual_days = (actual_end - actual_start).days + 1

# Build chat -> brands map
chat_brands = defaultdict(set)
for row in url_data.rows:
    chat_brands[row.chat_id].update(row.mentioned_brand_ids or [])

total_chats = len(chat_brands)
chats_mentioning_brand = sum(1 for brands in chat_brands.values() if own_brand.id in brands)
visibility_score = (chats_mentioning_brand / total_chats) * 100
```

If `total_chats < 40` or `actual_days < 7`, append a warning to the payload but do not fail. The analytics backend can decide what to do.

### Step 3: Pull domain inventory

```python
domains_data = peec.get_domain_report(
    project_id=project.id,
    start_date=actual_start,
    end_date=actual_end,
    order_by=[{"field": "retrieval_count", "direction": "desc"}],
    limit=200,
)
```

200 is the practical ceiling. Domains beyond rank ~150 are noise.

### Step 4: Classify domains via Tavily

For each domain, query Tavily to determine if it accepts paid placement. Use a structured prompt and parse the response for a category.

**Tavily query template:**

```
Does the website {domain} accept paid placements, sponsored content,
sponsored listings, or affiliate partnerships? Specifically, can a vendor
in the {category_hint} category pay to be listed, ranked higher, or
featured on this site? Provide the answer in this exact JSON format:

{
  "classification": "DIRECT_PAID" | "AFFILIATE_PAID" | "ANALYST_PAID" | "EDITORIAL_NO_BUY" | "UGC" | "OTHER",
  "reasoning": "<one or two sentences>",
  "confidence": 0.0-1.0
}

Definitions:
  DIRECT_PAID: vendor pays a fee for a slot, sponsored listing, or boosted ranking (e.g. G2, business.com)
  AFFILIATE_PAID: site earns commission per click/sale; vendor joins their affiliate network (e.g. Forbes Advisor, NerdWallet)
  ANALYST_PAID: vendor pays for analyst access; correlated with positioning (e.g. Gartner)
  EDITORIAL_NO_BUY: editorial coverage only; no paid path to placement (e.g. The Verge, PCMag)
  UGC: user-generated; community-driven (e.g. Reddit, YouTube)
  OTHER: anything else

Only the JSON, nothing else.
```

`category_hint` should be derived from the project (CRM, smartphones, automotive, etc.). If the project has tags or topics in Peec, use those. Otherwise pass an empty string.

Filter to keep only `DIRECT_PAID`, `AFFILIATE_PAID`, `ANALYST_PAID`. Cache classifications by domain because they don't change often.

```python
paid_buckets = {"DIRECT_PAID", "AFFILIATE_PAID", "ANALYST_PAID"}
paid_domains = []
for domain in domains_data.rows:
    classification = tavily_classify_domain(domain.domain, category_hint)
    if classification.classification in paid_buckets and classification.confidence >= 0.6:
        paid_domains.append((domain.domain, classification))
```

If Tavily confidence is below 0.6, flag for manual review and skip from the paid list.

### Step 5: Pull gap URLs

For each paid domain, find URLs where competitors are present but our brand is not.

```python
gap_data = peec.get_url_report(
    project_id=project.id,
    start_date=actual_start,
    end_date=actual_end,
    dimensions=["chat_id"],
    filters=[
        {"field": "domain", "operator": "in", "values": [d for d, _ in paid_domains]},
        {"field": "gap", "operator": "gte", "value": 1},
    ],
    limit=10000,
)

# Aggregate per URL
urls = defaultdict(lambda: {
    "chats": set(),
    "competitor_mentions": defaultdict(set),  # competitor_id -> set of chat_ids
    "citation_count": 0,
})

for row in gap_data.rows:
    u = row.url
    urls[u]["chats"].add(row.chat_id)
    urls[u]["citation_count"] = row.citation_count  # URL-level, repeated per row
    for brand_id in row.mentioned_brand_ids or []:
        if brand_id in {c.id for c in competitors}:
            urls[u]["competitor_mentions"][brand_id].add(row.chat_id)

# Drop URLs with retrieval_count < 2 (noise)
urls = {u: v for u, v in urls.items() if len(v["chats"]) >= 2}
```

For each URL, compute the addressable pool (chats that retrieve this URL but don't already mention our brand from any other URL):

```python
addressable_chats = sum(
    1 for chat_id in url_data["chats"]
    if own_brand.id not in chat_brands[chat_id]
)
```

### Step 6: Pricing via Tavily

For each paid domain, query for current placement pricing.

**Tavily query template:**

```
What is the current pricing to be listed, sponsored, or featured on
{domain}? Look for sponsored placement cost, advertising rate card,
vendor program pricing, or affiliate commission structure for the
{category_hint} category. Return the result in this exact JSON format:

{
  "low_usd": <integer annual USD or null>,
  "high_usd": <integer annual USD or null>,
  "source_url": "<URL where you found the figure or 'ESTIMATE' if industry benchmark>",
  "notes": "<one to three sentences explaining the pricing model>"
}

If no public pricing is available, provide industry-benchmark estimates
and set source_url to 'ESTIMATE'. Only the JSON.
```

Pricing is the weakest part of the pipeline. Most B2B paid-media platforms hide rate cards. Expect a high `ESTIMATE` rate. Always present `low_usd` and `high_usd` as a range, never a single point.

If Tavily returns nulls for both, set pricing to `{"low_usd": null, "high_usd": null, ...}` and let the analytics backend handle it (likely by surfacing "RFQ required" in the UI).

### Step 7: Compute visibility delta

The math operates on **sets of chat IDs**, not aggregate counts. This is critical: visibility is binary per chat (a chat either mentions the brand or it doesn't), so the same chat retrieving multiple gap URLs cannot be counted multiple times.

**Per gap URL u (build the contributing chat set):**

```
chats_retrieving(u)        = set of chat_ids that retrieved u
competitor_chats(u)        = chats_retrieving(u) ∩ {chats that mention any competitor brand}
addressable_chats(u)       = chats_retrieving(u) − {chats that already mention own brand}
contributing_chats(u)      = competitor_chats(u) ∩ addressable_chats(u)
```

In words: `contributing_chats(u)` is the set of chats where (a) URL u was retrieved, (b) at least one competitor was mentioned (proving the URL drives mentions), and (c) our brand is not already mentioned from any source. These are the chats where placing our brand on URL u would plausibly add a new mention.

**Aggregate per platform p (set union, NOT sum):**

```
contributing_chats(p) = ⋃ over gap URLs u on platform p of contributing_chats(u)
```

The union is what makes this correct. If chat #5 retrieves URLs A and B, both on the same platform, it appears in `contributing_chats(p)` exactly once.

**Aggregate across all platforms (set union again):**

```
contributing_chats(total) = ⋃ over platforms p of contributing_chats(p)
```

A chat retrieving gap URLs across G2 AND business.com still counts once toward the global delta.

**Apply the 60-100% factor as a per-chat probability:**

```
delta_chats_pessimistic = 0.60 × |contributing_chats(total)|
delta_chats_optimistic  = 1.00 × |contributing_chats(total)|
```

Interpretation: each contributing chat has a probability between 60% and 100% of mentioning our brand once we are placed on at least one of the gap URLs it retrieves. The factor captures uncertainty about how AI engines treat a newly-added brand on a sponsored or affiliate placement.

**Per-platform deltas for display:**

```
delta_chats_platform_pessimistic(p) = 0.60 × |contributing_chats(p)|
delta_chats_platform_optimistic(p)  = 1.00 × |contributing_chats(p)|
```

These represent the lift if that platform alone were purchased. **Per-platform deltas will not sum to the total delta** when the same chat retrieves gap URLs across multiple platforms. This is correct behavior, not a bug. The output schema must surface this clearly: per-platform numbers are "if-alone" estimates, the total is the realistic combined number.

**Final visibility:**

```
visibility_pessimistic = (chats_mentioning_brand + delta_chats_pessimistic) / total_chats × 100
visibility_optimistic  = (chats_mentioning_brand + delta_chats_optimistic)  / total_chats × 100
```

No additional cap is needed. The set-based math automatically prevents projected visibility from exceeding 100%, because:
- `contributing_chats(total)` is a subset of addressable chats by construction
- `addressable chats = total_chats − chats_mentioning_brand`
- So `chats_mentioning_brand + delta_chats ≤ total_chats`

### Step 8: Assemble payload

Build the `PreparationPayload` per §2 schema. Sort `paid_media_opportunities` by `delta_chats_optimistic` descending. Append warnings for any of:

- `actual_days < 7`
- `total_chats < 40`
- baseline visibility above 0.9 (ceiling effect)
- any platform with zero gap URLs above the confidence floor
- any platform where Tavily classification confidence was below 0.8
- any platform with null pricing

## 5. Why the 60-100% range is the right shape

The user-specified range encodes a real uncertainty: when a brand is added to a sponsored slot or affiliate listicle, AI engines sometimes treat the new entry as equal to existing entries (high end of range) and sometimes deprioritize it as visibly sponsored (low end). Without empirical A/B data, picking a single point estimate is dishonest. The range is honest.

Two caveats the analytics backend should surface:

1. **The "60% floor" is not a guarantee.** If the placement is poorly executed (bad copy, low quality vendor profile), the actual lift can be near zero. The pessimistic case assumes adequate execution.
2. **The "100% ceiling" assumes the brand gets equal treatment to existing competitors.** This is rarely true on day one. Even competitive placements take 4-16 weeks to reach steady-state visibility. Day-one impact is closer to the pessimistic case.

These caveats belong in the user-facing UI, not in the math.

## 6. Implementation guidance

### Project structure suggestion

```
preparation/
  __init__.py
  pipeline.py              # main orchestrator (Steps 1-8)
  peec_client.py           # thin wrapper over Peec MCP
  tavily_client.py         # thin wrapper over Tavily API
  classifier.py            # paid-media classification (Tavily call)
  pricing.py               # pricing lookup (Tavily call)
  impact.py                # Step 7 formulas (pure functions)
  schemas.py               # pydantic models for the output payload
  cache.py                 # memoize Tavily classifications by domain
```

### Key constants

```python
WINDOW_DAYS_MAX = 90
MIN_RETRIEVALS_PER_URL = 2
MIN_TAVILY_CONFIDENCE = 0.6
PESSIMISTIC_FACTOR = 0.60
OPTIMISTIC_FACTOR = 1.00
MIN_TOTAL_CHATS = 40
MIN_WINDOW_DAYS = 7
```

Expose these as environment variables so the analytics team can tune them without a redeploy.

### Caching

Tavily calls are slow and cost money. Cache aggressively:

- Domain classifications: 30-day TTL, keyed by `(domain, category_hint)`.
- Pricing: 7-day TTL, keyed by `(domain, category_hint)`.

A simple Redis or even SQLite cache is fine.

### Error handling

If Peec MCP fails, propagate. The pipeline cannot run.

If Tavily fails on a single domain, skip that domain and add a warning. Do not fail the whole pipeline.

If Tavily fails on pricing, set pricing to nulls and add a warning.

## 7. Worked example: Attio (verified against real Peec data, set-based math)

Inputs:
```json
{ "company_name": "Attio" }
```

After Steps 1 to 5:

```
window: 30 days
total_chats: 394
chats_mentioning_brand: 228
visibility_score: 57.87
addressable_chats_total: 166
```

After Step 6 and 7 (set-based aggregation):

```
Per-platform "if alone" estimates:
  Platform           Gap URLs    |contributing|    ΔV pessimistic    ΔV optimistic
  Forbes Advisor            1                 6              0.91%            1.52%
  Gartner                   2                 6              0.91%            1.52%
  MarketsandMarkets         3                 5              0.76%            1.27%
  business.com              3                 4              0.61%            1.02%
  TechnologyAdvice          1                 3              0.46%            0.76%
  crm.org                   1                 1              0.15%            0.25%
  G2                        1                 1              0.15%            0.25%

Sum of |contributing_chats(p)| naively: 26 chats
Union |contributing_chats(total)|:      23 chats   (3 chats overlap across platforms)

Total deltas (using union, not sum):
  delta_chats_pessimistic = 0.60 × 23 = 13.8
  delta_chats_optimistic  = 1.00 × 23 = 23.0

Projected visibility:
  pessimistic = (228 + 13.8) / 394 × 100 = 61.37%
  optimistic  = (228 + 23.0) / 394 × 100 = 63.71%
```

Note the 3-chat overcount that the old "sum + cap" approach would have introduced. With 12 gap URLs across 7 platforms, the overlap is small. With more gap URLs or higher-traffic categories, it can be much larger. The set-based math handles it correctly without parameter tuning.

## 8. Edge cases checklist

| Case | Behavior |
|---|---|
| Company not in Peec | Raise `CompanyNotTracked`. Backend should prompt user to set up the project first. |
| Company tracked but no competitors | Raise `InvalidProjectSetup`. Cannot compute gaps. |
| Window is 0 days (no data yet) | Return baseline=null, opportunities=[], warning="project has no data yet" |
| Window is 1-6 days | Run pipeline, append warning="short window, results are noisy" |
| Total chats < 40 | Run pipeline, append warning="low chat volume, confidence reduced" |
| Baseline visibility > 90% | Run pipeline, append warning="high baseline; ceiling effect limits delta" |
| No paid-media domains found | Return opportunities=[], warning="no paid-media surface in this category" |
| All Tavily classification confidence below threshold | Return opportunities=[], warning="paid-media classification uncertain, manual review needed" |
| Tavily pricing returns null for all platforms | Return opportunities with pricing=null, warning="pricing unavailable, RFQ required" |
| Cross-URL overlap exceeds total addressable | Cap is applied automatically in Step 7 |
| Same chat retrieves multiple gap URLs on same domain | Counted once per chat-domain pair (handled by set semantics in Step 5) |

## 9. Code snippet for the existing project

Drop this into the existing analytics backend as the `preparation` module. The orchestrator is:

```python
# preparation/pipeline.py
from .peec_client import PeecClient
from .tavily_client import TavilyClient
from .classifier import classify_domains
from .pricing import fetch_pricing
from .impact import compute_visibility_delta
from .schemas import PreparationPayload

def run_preparation(company_name: str) -> PreparationPayload:
    peec = PeecClient()
    tavily = TavilyClient()

    # Step 1
    project, own_brand, competitors = peec.resolve_company(company_name)

    # Step 2
    chats, window = peec.pull_baseline(project.id, days_max=90)
    baseline = compute_baseline(chats, own_brand.id)

    # Step 3
    domains = peec.pull_domain_inventory(project.id, window)

    # Step 4
    paid_domains = classify_domains(tavily, domains, category_hint=project.category)

    # Step 5
    gap_urls_by_domain = peec.pull_gap_urls(project.id, window, paid_domains)

    # Step 6
    pricing_by_domain = fetch_pricing(tavily, paid_domains, category_hint=project.category)

    # Step 7
    opportunities, projected = compute_visibility_delta(
        baseline=baseline,
        gap_urls_by_domain=gap_urls_by_domain,
        pricing_by_domain=pricing_by_domain,
        chat_brands=chats.chat_brands,
        own_brand_id=own_brand.id,
        pessimistic_factor=0.60,
        optimistic_factor=1.00,
    )

    return PreparationPayload(
        company={"name": company_name, "project_id": project.id, "brand_id": own_brand.id},
        window=window,
        baseline=baseline,
        paid_media_opportunities=opportunities,
        projected=projected,
        warnings=collect_warnings(baseline, window, opportunities),
    )
```

The pure-function core in `impact.py` (most testable):

```python
# preparation/impact.py
from typing import Iterable

def contributing_chats_for_url(url_chats: set[str],
                                url_chat_brands: dict[str, set[str]],
                                competitor_ids: set[str],
                                own_brand_id: str,
                                chat_brands_global: dict[str, set[str]]) -> set[str]:
    """
    Returns the set of chat_ids that:
      - retrieved this URL
      - mentioned at least one competitor in this retrieval
      - do NOT already mention the own brand from any source
    """
    out = set()
    for cid in url_chats:
        if own_brand_id in chat_brands_global[cid]:
            continue
        if url_chat_brands.get(cid, set()) & competitor_ids:
            out.add(cid)
    return out

def contributing_chats_for_platform(urls: Iterable, competitor_ids, own_brand_id, chat_brands_global):
    """Set union across all gap URLs on the platform."""
    out = set()
    for u in urls:
        out |= contributing_chats_for_url(
            u.chats, u.chat_brands, competitor_ids, own_brand_id, chat_brands_global
        )
    return out

def compute_visibility_delta(baseline, gap_urls_by_domain, pricing_by_domain,
                              chat_brands_global, own_brand_id, competitor_ids,
                              pessimistic_factor, optimistic_factor):
    opportunities = []
    all_contributing = set()  # union across all platforms

    for domain, urls in gap_urls_by_domain.items():
        platform_chats = contributing_chats_for_platform(
            urls, competitor_ids, own_brand_id, chat_brands_global
        )
        all_contributing |= platform_chats

        # Per-platform "if alone" estimates
        n = len(platform_chats)
        opportunities.append({
            "domain": domain,
            "contributing_chat_count": n,
            "delta_chats_pessimistic": n * pessimistic_factor,
            "delta_chats_optimistic": n * optimistic_factor,
            "gap_urls": [build_gap_url_dict(u, competitor_ids, own_brand_id,
                                             chat_brands_global) for u in urls],
            "pricing": pricing_by_domain.get(domain),
            # ... classification fields
        })

    # Total via set union, NOT sum of per-platform deltas
    total_n = len(all_contributing)
    total_pess = total_n * pessimistic_factor
    total_opt = total_n * optimistic_factor

    new_chats_pess = baseline.chats_mentioning_brand + total_pess
    new_chats_opt  = baseline.chats_mentioning_brand + total_opt

    projected = {
        "pessimistic": {
            "visibility_score": new_chats_pess / baseline.total_chats * 100,
            "delta": total_pess / baseline.total_chats * 100,
        },
        "optimistic": {
            "visibility_score": new_chats_opt / baseline.total_chats * 100,
            "delta": total_opt / baseline.total_chats * 100,
        },
    }
    opportunities.sort(key=lambda o: -o["delta_chats_optimistic"])
    return opportunities, projected
```

The critical correctness point: `compute_visibility_delta` does NOT sum the per-platform `delta_chats_optimistic` values to compute the total. It maintains a separate `all_contributing` set, unions per-platform sets into it, and computes the total from that set's size. This is what prevents double-counting chats that retrieve gap URLs across multiple platforms.

A unit test worth writing:

```python
def test_chat_in_two_platforms_counted_once():
    # Chat #5 retrieves URL on G2 and URL on business.com
    # Both URLs have competitors mentioned, neither has own brand
    # Chat #5 is NOT in chats_mentioning_brand
    # Expected: total contributing = 1, not 2
    ...
```

## 10. What to push back on

A few things in the original design that the team should reconsider:

1. **Pricing via Tavily will be unreliable.** B2B paid-media platforms hide rate cards. Tavily will return many `ESTIMATE` results or nulls. The pipeline tolerates this gracefully but the user-facing report needs to surface pricing as ranges, not point estimates.
2. **The 60-100% range is a strong claim with no empirical grounding yet.** It is internally defensible, but if the analytics report quotes specific percentage point gains as if they were predictions, the company will get embarrassed when reality differs. Frame outputs as "expected range" not "forecast."
3. **One-day data windows happen.** New Peec projects produce dramatic-looking but unreliable numbers. The pipeline emits warnings but the analytics backend must visibly suppress recommendations when warnings fire, not just print them as small text.
4. **Tavily classification of "paid media" is fuzzy.** Some sites both run editorial content and accept sponsored slots (e.g. forbes.com vs forbes.com/advisor). The classification should ideally be at the URL level, not the domain level, but URL-level Tavily classification is too expensive in v1. Document this gap.

These don't block shipping. They block claiming the output is more precise than it is.
