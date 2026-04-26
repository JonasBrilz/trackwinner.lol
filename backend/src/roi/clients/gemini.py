import json
from google import genai
from google.genai import errors as genai_errors
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..config import GEMINI_API_KEY, GEMINI_MODEL

def _client():
    return genai.Client(api_key=GEMINI_API_KEY)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            return inner.strip()
    return text


def _is_rate_limit(exc: BaseException) -> bool:
    return isinstance(exc, genai_errors.ClientError) and exc.status_code == 429


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception_type(genai_errors.ClientError),
    reraise=True,
)
async def _call_gemini(contents: str) -> str:
    response = await _client().aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )
    return response.text


async def generate_json(prompt: str) -> dict:
    for attempt in range(2):
        suffix = "" if attempt == 0 else "\n\nOUTPUT ONLY VALID JSON. NO MARKDOWN. NO EXPLANATION."
        text = _strip_fences(await _call_gemini(prompt + suffix))
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if attempt == 1:
                raise RuntimeError(f"Gemini returned non-JSON after retry:\n{text}")
    raise RuntimeError("Unreachable")


async def generate_text(prompt: str) -> str:
    return await _call_gemini(prompt)


async def _call_gemini_no_retry(contents: str) -> str:
    """One-shot Gemini call without tenacity retries. Used for non-critical paths
    where we want to fail fast instead of waiting through a 60s retry chain."""
    response = await _client().aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )
    return response.text


async def synthesize_umbrella_summary(facts: dict, timeout_s: float = 20.0) -> str:
    """Single executive summary covering BOTH the pessimistic and optimistic scenarios.

    Same safety net as `synthesize_summary` — returns "" on any failure.
    Used by /roi/full-analysis so the response has one summary rather than two."""
    prompt = (
        f"You are writing an executive summary for a B2B sales/marketing leader at "
        f"{facts.get('company', 'this company')}.\n"
        f"The data shows their current AI-search visibility, the revenue at risk under "
        f"two scenarios (pessimistic = 60% effectiveness, optimistic = 100%), and the "
        f"top paid-media platforms where competitors appear and they don't.\n\n"
        f"Write 3-4 sentences in plain prose. Lead with the revenue lift as a RANGE "
        f"in € (pessimistic → optimistic) and the customer-equivalent range. Name the "
        f"competitor they trail and the visibility gap in percentage points. End with "
        f"a concrete focus call: name 1-2 specific paid-media platforms where placement "
        f"would close the gap.\n\n"
        f"Rules: no headings, bullets, intro, or preamble. No marketing buzzwords. "
        f"Use the specific numbers from the data. Frame the range honestly.\n\n"
        f"Data:\n{json.dumps(facts, indent=2)}"
    )
    try:
        text = await asyncio.wait_for(_call_gemini_no_retry(prompt), timeout=timeout_s)
        return (text or "").strip()[:1000]
    except Exception as e:
        print(f"[gemini] synthesize_umbrella_summary failed ({type(e).__name__}: {e}); returning empty")
        return ""


async def synthesize_summary(facts: dict, timeout_s: float = 20.0) -> str:
    """Generate a 2-3 sentence executive summary from computed stats.

    Engineered to be unbreakable: rate limits, timeouts, network errors, malformed
    responses, and any other failure all silently return "". The caller is expected
    to assign the result to FinalReport.executive_summary regardless — empty is fine.
    Uses a no-retry call so a slow/rate-limited Gemini fails fast instead of blocking.
    """
    prompt = (
        f"You are writing an executive summary for a B2B sales/marketing leader at "
        f"{facts.get('company', 'this company')}.\n"
        f"The data shows their current AI-search visibility and the revenue at risk.\n\n"
        f"Write 2-3 sentences in plain prose. Lead with the annual revenue lift in € "
        f"and the customer-equivalent count. Name the competitor they trail and the "
        f"visibility gap in percentage points. End with the focus call: the top-3 "
        f"prompts capture X% of total lift.\n\n"
        f"Rules: no headings, bullets, intro, or preamble. No marketing buzzwords. "
        f"Use the specific numbers from the data.\n\n"
        f"Data:\n{json.dumps(facts, indent=2)}"
    )
    try:
        text = await asyncio.wait_for(_call_gemini_no_retry(prompt), timeout=timeout_s)
        return (text or "").strip()[:800]
    except Exception as e:
        print(f"[gemini] synthesize_summary failed ({type(e).__name__}: {e}); returning empty")
        return ""
