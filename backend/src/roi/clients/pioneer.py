"""Pioneer (Fastino) client for per-prompt AI summaries.

Sends a prompt-revenue JSON block, gets back a one-sentence analyst summary.
Engineered to be unbreakable: missing key, network errors, timeouts, and
malformed responses all return None so the caller can fall back gracefully.
The model is still training (per Pioneer team), so failures are expected
and must not break the rest of the report.
"""
import asyncio
import json
import httpx
from ..config import PIONEER_API_KEY, PIONEER_API_URL, PIONEER_JOB_ID

_SEM = asyncio.Semaphore(5)
_TIMEOUT_S = 10.0
_MAX_TOKENS = 100

_SYSTEM_PROMPT = (
    "You are a marketing revenue analyst specializing in AI brand visibility. "
    "Given a prompt analysis JSON from the PEEC AI platform, respond with exactly "
    "one concise sentence that summarizes the brand's current visibility standing "
    "and the revenue opportunity. Be specific: mention the prompt topic, current "
    "position vs competitor if relevant, and the revenue lift opportunity in EUR. "
    "Keep it under 30 words."
)

_SYSTEM_PROMPT_DUAL = (
    "You are a marketing revenue analyst specializing in AI brand visibility. "
    "Given a prompt analysis JSON from the PEEC AI platform that contains both "
    "pessimistic (60% effectiveness) and optimistic (100% effectiveness) scenarios, "
    "respond with exactly one concise sentence summarizing the brand's current "
    "visibility standing and the revenue opportunity as a RANGE. Mention the prompt "
    "topic, current position vs the top competitor if relevant, and the revenue lift "
    "as €X to €Y (pessimistic to optimistic). Keep it under 35 words."
)


def _payload_for_prompt(pr) -> dict:
    """Extract the fields Pioneer cares about from a PromptRevenue (or dict)."""
    g = pr.model_dump() if hasattr(pr, "model_dump") else dict(pr)
    return {
        "prompt_id": g.get("prompt_id"),
        "prompt_message": g.get("prompt_message"),
        "your_visibility": g.get("your_visibility"),
        "your_position": g.get("your_position"),
        "top_competitor_name": g.get("top_competitor_name"),
        "annual_mentions": g.get("annual_mentions"),
        "current_annual_revenue_eur": g.get("current_annual_revenue_eur"),
        "target_annual_revenue_eur": g.get("target_annual_revenue_eur"),
        "revenue_lift_eur": g.get("revenue_lift_eur"),
    }


async def _post(payload: dict, system_prompt: str) -> str | None:
    if not PIONEER_API_KEY:
        return None
    async with _SEM:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                resp = await client.post(
                    PIONEER_API_URL,
                    headers={
                        "Authorization": f"Bearer {PIONEER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": PIONEER_JOB_ID,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(payload)},
                        ],
                        "max_tokens": _MAX_TOKENS,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
                return text or None
        except Exception as e:
            print(f"[pioneer] failed for prompt_id={str(payload.get('prompt_id', '?'))[:20]}: {type(e).__name__}: {str(e)[:120]}")
            return None


async def summarize(payload: dict) -> str | None:
    """Single-scenario summary. Returns text or None on any failure."""
    return await _post(payload, _SYSTEM_PROMPT)


async def summarize_dual(payload: dict) -> str | None:
    """Dual-scenario summary covering both pessimistic and optimistic. Returns
    text or None on any failure."""
    return await _post(payload, _SYSTEM_PROMPT_DUAL)


async def summarize_prompt_revenues(prompt_revenues: list) -> list[str | None]:
    """Parallel: summarize a list of PromptRevenue objects (or dicts).
    Returns summaries in the same order; None for any that failed."""
    if not prompt_revenues:
        return []
    if not PIONEER_API_KEY:
        print("[pioneer] PIONEER_API_KEY not set, skipping all summaries")
        return [None] * len(prompt_revenues)
    payloads = [_payload_for_prompt(pr) for pr in prompt_revenues]
    print(f"[pioneer] summarizing {len(payloads)} prompt_revenues (sem=5)")
    results = await asyncio.gather(*[summarize(p) for p in payloads])
    found = sum(1 for r in results if r)
    print(f"[pioneer] returned {found}/{len(payloads)} summaries")
    return results


def dual_payload(dual_pr) -> dict:
    """Extract the dual-scenario payload from a PromptRevenueDual. This is the
    exact JSON shape Pioneer needs to retrain on for the new task."""
    g = dual_pr.model_dump() if hasattr(dual_pr, "model_dump") else dict(dual_pr)
    return {
        "prompt_id": g.get("prompt_id"),
        "prompt_message": g.get("prompt_message"),
        "your_visibility": g.get("your_visibility"),
        "your_position": g.get("your_position"),
        "top_competitor_name": g.get("top_competitor_name"),
        "top_competitor_visibility": g.get("top_competitor_visibility"),
        "annual_mentions": g.get("annual_mentions"),
        "current_annual_revenue_eur": g.get("current_annual_revenue_eur"),
        "pessimistic": g.get("pessimistic"),
        "optimistic": g.get("optimistic"),
    }


async def summarize_dual_prompt_revenues(dual_prs: list) -> list[str | None]:
    """Parallel: summarize a list of PromptRevenueDual objects with one combined
    Pioneer call each (covers both scenarios). Returns summaries in input order."""
    if not dual_prs:
        return []
    if not PIONEER_API_KEY:
        print("[pioneer] PIONEER_API_KEY not set, skipping dual summaries")
        return [None] * len(dual_prs)
    payloads = [dual_payload(d) for d in dual_prs]
    print(f"[pioneer] summarizing {len(payloads)} dual prompt_revenues (sem=5)")
    results = await asyncio.gather(*[summarize_dual(p) for p in payloads])
    found = sum(1 for r in results if r)
    print(f"[pioneer] returned {found}/{len(payloads)} dual summaries")
    return results
