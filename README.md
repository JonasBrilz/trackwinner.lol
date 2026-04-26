# trackwinner.lol

Built at [Big Berlin Hack 2026](https://discord.gg/d4HJCNF54x) — competing in the **[Peec AI](https://peec.ai) track: 0 → 1 AI Marketer**.

> Help an early-stage brand win distribution against bigger competitors using AI visibility data.

## What it does

trackwinner.lol uses the Peec AI MCP to track how brands appear across LLMs, quantifies the revenue gap caused by low AI visibility, and surfaces actionable distribution opportunities — helping small teams close the gap with much bigger competitors.

## Tech Stack

| Tool | Role |
|---|---|
| [Peec AI](https://peec.ai) | AI visibility tracking & brand mention data via MCP |
| [Google DeepMind](https://deepmind.google/) | Frontier multimodal AI models and Deployment on [trackwinner.lol](https://trackwinner.lol/) |
| [Tavily](https://www.tavily.com/) | Real-time web search & research |
| [Pioneer](https://pioneer.ai/) by [Fastino](https://fastino.ai/) | Customized AI responses via fine-tuned models |

## Repo Structure

```
trackwinner.lol/
├── frontend/    # Next.js app → Cloud Run (bighack-berlin)
├── backend/     # Python/FastAPI app → Cloud Run (hackathon)
├── SETUP.md
└── METHODOLOGY.md
```

See [SETUP.md](./SETUP.md) for deployment details and [METHODOLOGY.md](./METHODOLOGY.md) for the approach.
