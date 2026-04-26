import asyncio
from ..clients.peec import PeecClient
from ..models import Brand, Prompt, ProjectSetup


def _to_brand(raw: dict) -> Brand:
    return Brand(
        id=str(raw.get("id", "")),
        name=str(raw.get("name", "Unknown")),
        is_own=bool(raw.get("is_own", False)),
    )


def _to_prompt(raw: dict) -> Prompt:
    messages = raw.get("messages", [])
    message = messages[0].get("content", "") if messages else raw.get("text", raw.get("message", ""))
    location = None
    loc = raw.get("user_location")
    if isinstance(loc, dict):
        location = loc.get("country")
    # Prefer search_volume (real Google search volume); volume is Peec's internal sample count
    search_volume = int(raw.get("search_volume", 0) or 0)
    return Prompt(
        id=str(raw.get("id", "")),
        message=str(message),
        search_volume=search_volume,
        tags=[t.get("id", "") for t in raw.get("tags", [])],
        topics=[raw["topic"]["id"]] if raw.get("topic") else [],
        location=location,
    )


async def run(project_id: str) -> ProjectSetup:
    print(f"[step1] fetching brands and prompts for project {project_id}")
    client = PeecClient()
    try:
        raw_brands, raw_prompts = await asyncio.gather(
            client.list_brands(project_id),
            client.list_prompts(project_id),
        )
    finally:
        await client.close()

    print(f"[step1] got {len(raw_brands)} brands, {len(raw_prompts)} prompts")

    all_brands = [_to_brand(b) for b in raw_brands if b.get("id")]
    own_brand = next((b for b in all_brands if b.is_own), None)
    competitors = [b for b in all_brands if not b.is_own]

    if own_brand is None:
        raise ValueError("No own brand found in Peec project — mark your brand as 'own' in Peec settings")

    print(f"[step1] own brand: {own_brand.name}, competitors: {[c.name for c in competitors]}")

    prompts = [_to_prompt(rp) for rp in raw_prompts if rp.get("id")]
    with_volume = sum(1 for p in prompts if p.search_volume > 0)
    print(f"[step1] {len(prompts)} prompts parsed, {with_volume} with search_volume>0")
    if with_volume:
        sample = [(p.message[:40], p.search_volume) for p in prompts if p.search_volume > 0][:3]
        print(f"[step1] search_volume sample: {sample}")

    return ProjectSetup(
        project_id=project_id,
        own_brand=own_brand,
        competitors=competitors,
        all_brands=all_brands,
        prompts=prompts,
    )
