# AI Visibility Revenue Impact Calculator — Full Context

## What It Does

Takes a Peec project ID and conversion rates, computes how much money AI invisibility costs per year, and outputs a sorted top-10 list of "do this Monday" actions with € revenue lift attached to each.

All backend. Call it from the terminal with curl. No frontend.

---

## How to Run

```bash
# Start server
uv run uvicorn main:app --reload

# Basic call (GET)
curl "http://localhost:8000/roi/analyze?peec_project_id=or_47ccb54e-0f32-4c95-b460-6a070499d084&visit_to_lead_rate=0.03&lead_to_customer_rate=0.15&acv_eur=10000&visibility_increase_pp=5"

# Full call (POST, all params)
curl -X POST http://localhost:8000/roi/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "peec_project_id": "or_47ccb54e-0f32-4c95-b460-6a070499d084",
    "visit_to_lead_rate": 0.03,
    "lead_to_customer_rate": 0.15,
    "acv_eur": 10000,
    "visibility_increase_pp": 5.0
  }'

# Debug: see raw data without revenue calc
curl "http://localhost:8000/roi/debug?peec_project_id=or_47ccb54e-0f32-4c95-b460-6a070499d084"

# Decode project ID from API key
curl http://localhost:8000/roi/projects

# Check Tavily quota usage
curl http://localhost:8000/roi/quota
```

---

## Input Parameters

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `peec_project_id` | required | Peec project UUID |
| `visit_to_lead_rate` | 0.03 | 3% of website visits become leads |
| `lead_to_customer_rate` | 0.15 | 15% of leads become customers |
| `acv_eur` | 10000 | Annual Contract Value per customer in € |
| `visibility_increase_pp` | 5.0 | How many percentage points of visibility to model as the "lift" scenario |

---

## Revenue Formula

```
annual_mentions  = chats_30d × 12 × multiplier × visibility
annual_actions   = annual_mentions × action_rate × position_weight
annual_revenue   = annual_actions × visit_to_lead × lead_to_customer × ACV

revenue_lift     = target_revenue - current_revenue

target_visibility = min(current_visibility + visibility_increase_pp/100, 1.0)
target_position   = max(current_position - 2, 1)
```

- `chats_30d`: Peec-sampled AI conversations mentioning your brand in last 30 days
- `multiplier`: Peec captures ~10% of global AI query volume → multiplier = 10x (hardcoded, well-researched)
- `visibility`: fraction of responses where your brand appears (0.0–1.0)
- `action_rate`: fraction of AI mentions that drive a measurable user action (search, click, visit). Fetched daily via Tavily, default 12%
- `position_weight`: higher position (earlier in response) → more clicks

### Position Weights

```
position 1 → 1.5×
position 2 → 1.3×
position 3 → 1.0×
position 4 → 0.8×
position 5 → 0.6×
None       → 0.0  (brand never appears → zero revenue contribution)
```

### Untapped Floor

Prompts where your visibility is 0 are still modeled with a floor of 0.005 (0.5%) so the revenue lift is non-zero — these are opportunities.

---

## Peec API

**Base URL:** `https://api.peec.ai/customer/v1`  
**Auth:** `X-API-Key: <key>` header (NOT Bearer token)  
**Keys are project-scoped.** You cannot list all projects — the project ID is encoded in the key itself.

### Decode project ID from key

```python
# Key format: or_<base64-encoded-project-id>-<suffix>
parts = PEEC_API_KEY.split("-", 2)
project_id = base64.b64decode(parts[1] + "==").decode()
# Example: or_47ccb54e → project_id = "or_47ccb54e-0f32-4c95-b460-6a070499d084"
```

### Endpoints Used

#### GET /brands?project_id=<id>
Returns list of brands. Each brand:
```json
{"id": "br_...", "name": "Attio", "is_own": true}
```
Own brand identified by `is_own: true`.

#### GET /prompts?project_id=<id>
Returns list of prompts. Each prompt:
```json
{
  "id": "pr_...",
  "messages": [{"content": "best CRM for startups", "role": "user"}],
  "search_volume": 0,
  "volume": 3
}
```
**Important:** `volume` is Peec's internal sample count (always ~3), not real search volume. Use `chats_last_30_days` from the chats endpoint instead. Prompt message is at `messages[0].content`, NOT a top-level `text` field.

#### POST /reports/brands (brands visibility report)
```json
{
  "project_id": "or_...",
  "start_date": "2025-01-01",
  "end_date": "2025-04-25",
  "group_by": ["prompt", "brand"]
}
```
Returns rows. **Critical:** brand and prompt are nested objects, not flat IDs:
```json
{
  "brand": {"id": "br_...", "name": "Attio"},
  "prompt": {"id": "pr_...", "message": "..."},
  "visibility_count": 45,
  "visibility_total": 100,
  "position_sum": 135,
  "position_count": 45
}
```
Visibility = `visibility_count / visibility_total`. Position = `position_sum / position_count`.

#### POST /reports/chats (chat volume per prompt)
```json
{
  "project_id": "or_...",
  "start_date": "2025-01-01",
  "end_date": "2025-04-25",
  "group_by": ["prompt"]
}
```
Returns rows. **Critical:** prompt is a nested object:
```json
{
  "prompt": {"id": "pr_...", "message": "..."},
  "chats_last_30_days": 11
}
```
Use `chat["prompt"]["id"]`, NOT `chat["prompt_id"]` (that field doesn't exist).

#### POST /reports/domains
Returns domains mentioned alongside your brand in AI responses.

#### POST /reports/urls  
Returns specific URLs mentioned.

---

## Pipeline Steps

### Step 1 — Project Setup (`step1_setup.py`)
- Calls Peec `/brands` and `/prompts`
- Identifies own brand via `is_own: true`
- Returns `(ProjectSetup, dict[prompt_id → chat_volume])`
- Also returns prompt volumes from `/prompts` endpoint as fallback

### Step 2 — Brands Report (`step2_brands.py`)
- Calls Peec `/reports/brands` for all brands
- Groups by prompt+brand, picks the row for own brand
- Also finds top competitor (highest visibility among other brands)
- Returns `dict[prompt_id → BrandsReportSummary]`

### Step 3 — Chat Volumes (`step3_chats.py`)
- Calls Peec `/reports/chats` grouped by prompt
- Returns `dict[prompt_id → chats_last_30_days]`
- Falls back to step1 prompt volumes if chat report is empty

### Step 4+5 — Market Estimates (`step4_market.py`)
- One Tavily search per day for action rate
- Query: "what percentage of users click or search brand after seeing it mentioned in ChatGPT answer 2025"
- Extracts % from answer using regex, clamps to 5–25% range
- Multiplier is hardcoded at 10x (Peec captures ~10% of global AI query volume)
- Caches results in `.research_cache.json` (daily, not per-call)
- Returns `(MarketEstimate, ActionRateEstimate)`

### Step 6 — Position Weighting (`step6_position.py`)
- Pure function: `position_weight(position)` → float
- None position → 0.0 (brand not mentioned)

### Step 7 — Conversion Rates (`step7_conversion.py`)
- Just reads `visit_to_lead_rate` and `lead_to_customer_rate` from inputs

### Step 9 — Current Revenue (`step9_revenue.py`)
- `annual_mentions = chats_30d * 12 * multiplier * visibility`
- `annual_revenue = annual_mentions * action_rate * position_weight * v2l * l2c * acv`

### Step 10 — Upside / Revenue Lift (`step10_upside.py`)
- Computes current vs target revenue
- Target visibility = current + `visibility_increase_pp / 100`
- Target position = max(current - 2, 1)
- `revenue_lift = max(0, target_rev - current_rev)`

### Step 11 — Action Recommendations (`step11_actions.py`)
- Fetches `/reports/domains` and `/reports/urls` for top prompts
- Classifies actions into 5 types:
  - `pr_placement` — get PR coverage on competitor domains
  - `comparison_page` — create comparison landing page
  - `schema_enhancement` — add structured data markup
  - `page_refresh` — update existing content
  - `ugc_engagement` — engage with user-generated content
- Returns list of `ActionRecommendation` sorted by revenue lift

### Step 12 — Synthesis (`step12_synthesize.py`)
- Assembles `FinalReport` from all computed data
- No LLM calls (Gemini removed due to rate limits)
- Sums total current/potential revenue across all prompts

---

## Known Gotchas

### Nested fields in Peec API responses
Peec wraps brand and prompt info in nested objects. Never assume flat `brand_id` or `prompt_id` fields — always use `row["brand"]["id"]` and `row["prompt"]["id"]`.

### Volume field is useless
`prompts.volume` is always ~3 (Peec's internal sample count). Real traffic signal is `chats_last_30_days` from the chats report, which ranges from 2–50+ for real prompts.

### Multiplier calibration
- Multiplier of 200x → revenue comes out at €14M+ (too high)
- Multiplier of 10x → revenue comes out at €150K–600K (correct range for Attio)
- 10x means Peec samples ~10% of relevant AI query volume

### Action rate calibration
- Default 12% (0.12)
- Tavily answer extraction can go wrong → regex clamps to 5–25%
- Values outside that range are ignored and the default is used

### Gemini removed
Steps 4, 5, and 12 previously called Gemini. Removed entirely due to:
- Rate limits (429 Resource Exhausted) on free and Tier 1
- Gemini was only adding rationale text, not driving numbers
- Tavily `include_answer=True` gives direct answers without LLM overhead

### Daily cache
`.research_cache.json` is written on first Tavily call each day. Delete it to force a fresh fetch. The cache stores: `date`, `multiplier`, `action_rate`, `sources`.

### Position None = zero revenue
Prompts where your brand never appears have `position=None`. `position_weight(None)` returns 0.0, so current revenue is €0. The lift calculation uses the untapped floor (0.5%) for these.

---

## Project Structure

```
main.py                         # FastAPI entry point
src/roi/
  config.py                     # Env vars: PEEC_API_KEY, TAVILY_API_KEY, PEEC_BASE_URL
  models.py                     # All Pydantic models + dataclasses
  router.py                     # FastAPI routes: GET/POST /analyze, /debug, /projects, /quota
  clients/
    peec.py                     # Peec API client (X-API-Key auth, all report calls)
    tavily.py                   # Tavily client with quota tracking
    gemini.py                   # Gemini client (still present, not used in pipeline)
  pipeline/
    step1_setup.py              # Fetch brands + prompts from Peec
    step2_brands.py             # Compute visibility/position per prompt
    step3_chats.py              # Fetch chat volumes per prompt
    step4_market.py             # Market multiplier + action rate (Tavily)
    step5_action.py             # Stub (absorbed into step4)
    step6_position.py           # Position weight lookup table
    step7_conversion.py         # Pass-through for conversion rates
    step9_revenue.py            # Current revenue formula
    step10_upside.py            # Target revenue + lift
    step11_actions.py           # Action recommendations from domain/URL reports
    step12_synthesize.py        # Assemble FinalReport
tools/                          # Hackathon tool stubs (separate from roi/)
  gemini.py
  tavily.py
  telli.py
  gradium.py
```

---

## Attio-Specific Data (Validated)

- Project ID: `or_47ccb54e-0f32-4c95-b460-6a070499d084`
- Average chats/prompt: ~11/month
- Visibility on best prompts: 40–60%
- Expected revenue range: €150K–600K/year current, with €50K–200K lift at +5pp visibility

---

## Environment Variables

```
PEEC_API_KEY=or_...
TAVILY_API_KEY=tvly-...
GEMINI_API_KEY=...   # not used in pipeline currently
```

Load via `python-dotenv`. Never hardcode. `.env` is gitignored.
