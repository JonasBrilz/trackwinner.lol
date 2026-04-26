# AI Visibility Revenue Impact Calculator

Most companies don't know how much money they're losing because AI assistants (ChatGPT, Gemini, Perplexity) aren't recommending them. Given a Peec project ID, this tool quantifies that gap in euros, identifies paid-media platforms where competitors appear and you don't, and tells you what to do about it.

## Pipeline

1. **Pull project setup** — fetch own brand, competitors, and prompts from Peec
2. **Pull brands report** — per-prompt visibility + position for own brand and each competitor
3. **Pull chat counts** — how many AI conversations per prompt over 30 days
4. **Research market multipliers** — Tavily for `ai_query_share` (% of search queries on AI now) + per-prompt search-volume lookup
5. **Run prep pipeline** — find paid-media domains where competitors are present and your brand isn't (G2, Forbes Advisor, Gartner, etc.); classify them, fetch pricing, find contact emails, compute set-based visibility deltas
6. **Resolve ACV** — use the user-provided value, or auto-research average revenue per customer via Tavily
7. **Compute lift twice** — run the revenue algorithm with the prep pipeline's pessimistic delta (60% effectiveness) and optimistic delta (100% effectiveness)
8. **Assemble report** — head-to-head competitor stats, top-3 paid-media opportunities with contact emails, executive summary via Gemini, dual-scenario revenue bracket

## Quick Start

```bash
uv sync
cp .env.example .env   # fill in PEEC_API_KEY, TAVILY_API_KEY, GEMINI_API_KEY
uv run uvicorn main:app --reload
```

## Usage

Single GET request — the auto-research path means you don't even need to know your ACV:

```bash
curl "http://localhost:8000/roi/full-analysis?peec_project_id=<your-peec-project-id>"
```

Optional overrides:

```bash
curl "http://localhost:8000/roi/full-analysis?peec_project_id=or_xxx&acv_eur=12000&visit_to_lead_rate=0.03&lead_to_customer_rate=0.15"
```

Returns one JSON with: `acv` (researched + sourced), `bracket` (pessimistic + optimistic lift), `pessimistic` and `optimistic` full reports (revenue, customer equivalents, competitive landscape, top actions), and `prep` (top-3 paid-media platforms with classification, pricing, contact email, gap URLs, projected visibility).
