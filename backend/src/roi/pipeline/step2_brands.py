from datetime import date, timedelta
from collections import defaultdict
from ..clients.peec import PeecClient
from ..models import ProjectSetup, BrandsReportSummary


def _thirty_days_ago() -> tuple[str, str]:
    today = date.today()
    return (today - timedelta(days=30)).isoformat(), today.isoformat()


async def run(
    setup: ProjectSetup,
) -> tuple[dict[str, BrandsReportSummary], dict[tuple[str, str], float]]:
    """Returns (summaries, brand_vis_map).

    summaries: prompt_id → own brand stats + top competitor.
    brand_vis_map: (prompt_id, brand_id) → visibility (used for head-to-head stats).
    """
    start, end = _thirty_days_ago()
    print(f"[step2] fetching brands report {start} to {end}")
    client = PeecClient()
    try:
        rows = await client.brands_report(setup.project_id, start, end)
    finally:
        await client.close()

    print(f"[step2] got {len(rows)} rows from brands report")
    if rows:
        print(f"[step2] sample row: {rows[0]}")

    # Accumulate per (prompt_id, brand_id) across models
    # visibility = sum(visibility_count) / sum(visibility_total)
    acc: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"vis_count": 0, "vis_total": 0, "pos_sum": 0.0, "pos_count": 0}
    )

    for row in rows:
        brand = row.get("brand", {})
        prompt = row.get("prompt", {})
        brand_id = str(brand.get("id", ""))
        prompt_id = str(prompt.get("id", ""))
        if not brand_id or not prompt_id:
            continue

        vis_count = int(row.get("visibility_count", 0))
        vis_total = int(row.get("visibility_total", 0))
        pos_sum = float(row.get("position_sum", 0.0))
        pos_count = int(row.get("position_count", 0))

        key = (prompt_id, brand_id)
        acc[key]["vis_count"] += vis_count
        acc[key]["vis_total"] += vis_total
        acc[key]["pos_sum"] += pos_sum
        acc[key]["pos_count"] += pos_count

    aggregated: dict[tuple[str, str], tuple[float, float | None]] = {}
    for (prompt_id, brand_id), vals in acc.items():
        vis = vals["vis_count"] / vals["vis_total"] if vals["vis_total"] else 0.0
        pos = vals["pos_sum"] / vals["pos_count"] if vals["pos_count"] else None
        aggregated[(prompt_id, brand_id)] = (vis, pos)

    brand_name_by_id = {b.id: b.name for b in setup.all_brands}
    own_id = setup.own_brand.id
    prompt_ids = {p.id for p in setup.prompts}

    summaries: dict[str, BrandsReportSummary] = {}
    for prompt_id in prompt_ids:
        own_vis, own_pos = aggregated.get((prompt_id, own_id), (0.0, None))
        top_comp_vis = 0.0
        top_comp_id = ""
        for comp in setup.competitors:
            vis, _ = aggregated.get((prompt_id, comp.id), (0.0, None))
            if vis > top_comp_vis:
                top_comp_vis = vis
                top_comp_id = comp.id
        summaries[prompt_id] = BrandsReportSummary(
            your_visibility=own_vis,
            your_position=own_pos,
            top_competitor_visibility=top_comp_vis,
            top_competitor_id=top_comp_id,
            top_competitor_name=brand_name_by_id.get(top_comp_id, "Unknown"),
        )

    nonzero = sum(1 for s in summaries.values() if s.your_visibility > 0)
    print(f"[step2] {len(summaries)} summaries, {nonzero} with non-zero own visibility")
    if summaries:
        sample = next(iter(summaries.values()))
        print(f"[step2] sample summary: vis={sample.your_visibility:.2f}, pos={sample.your_position}, top_comp={sample.top_competitor_name}({sample.top_competitor_visibility:.2f})")

    brand_vis_map = {key: vis for key, (vis, _) in aggregated.items()}
    return summaries, brand_vis_map
