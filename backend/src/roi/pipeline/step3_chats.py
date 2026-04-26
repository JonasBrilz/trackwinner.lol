from datetime import date, timedelta
from collections import defaultdict
from ..clients.peec import PeecClient
from ..models import ProjectSetup


async def run(setup: ProjectSetup) -> dict[str, int]:
    """Returns {prompt_id: chats_last_30_days}. Used as fallback when prompt.search_volume is 0."""
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()

    print(f"[step3] fetching chats {start} to {end}")
    client = PeecClient()
    try:
        chats, was_capped = await client.list_chats(setup.project_id, start, end)
    finally:
        await client.close()

    print(f"[step3] got {len(chats)} chats (capped={was_capped})")

    counts: dict[str, int] = defaultdict(int)
    for chat in chats:
        pid = str(chat.get("prompt", {}).get("id", ""))
        if pid:
            counts[pid] += 1

    nonzero = sum(1 for v in counts.values() if v > 0)
    print(f"[step3] {len(counts)} prompts with chat counts, {nonzero} non-zero")
    if counts:
        sample = dict(list(counts.items())[:3])
        print(f"[step3] sample chat counts: {sample}")
    return dict(counts)
