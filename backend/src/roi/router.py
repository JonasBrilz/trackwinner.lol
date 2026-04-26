import asyncio
from typing import Optional
from fastapi import APIRouter
from .models import (
    UserInputs, FinalReport, EnhancedFinalReport, ScenarioBracket,
    PromptRevenueDual, ScenarioOutcome,
)
from .pipeline import (
    step1_setup, step1_5_volume, step2_brands, step3_chats,
    step4_market, step7_conversion,
    step10_upside, step11_actions, step12_synthesize,
)
from .prep import pipeline as prep_pipeline, acv as acv_research
from .prep.schemas import AcvInfo
from .clients import tavily as tavily_client

router = APIRouter(prefix="/roi", tags=["roi"])


@router.get("/analyze", response_model=FinalReport)
async def analyze(
    peec_project_id: str,
    visit_to_lead_rate: float = 0.03,
    lead_to_customer_rate: float = 0.15,
    acv_eur: Optional[float] = None,         # if omitted, researched via Tavily
    visibility_increase_pp: float = 5.0,
) -> FinalReport:
    inputs = UserInputs(
        peec_project_id=peec_project_id,
        visit_to_lead_rate=visit_to_lead_rate,
        lead_to_customer_rate=lead_to_customer_rate,
        acv_eur=acv_eur,
        visibility_increase_pp=visibility_increase_pp,
    )
    return await _run_pipeline(inputs)


@router.post("/analyze", response_model=FinalReport)
async def analyze_post(inputs: UserInputs) -> FinalReport:
    return await _run_pipeline(inputs)


@router.get("/full-analysis", response_model=EnhancedFinalReport)
async def full_analysis(
    peec_project_id: str,
    visit_to_lead_rate: float = 0.03,
    lead_to_customer_rate: float = 0.15,
    acv_eur: Optional[float] = None,         # if omitted, researched via Tavily
) -> EnhancedFinalReport:
    """End-to-end report: prep pipeline finds paid-media gap opportunities,
    derives pessimistic + optimistic visibility deltas, and runs the lift math
    twice — once per scenario. Returns both reports + all prep data."""
    inputs = UserInputs(
        peec_project_id=peec_project_id,
        visit_to_lead_rate=visit_to_lead_rate,
        lead_to_customer_rate=lead_to_customer_rate,
        acv_eur=acv_eur,
        visibility_increase_pp=0.0,  # overridden per-scenario
    )
    return await _run_full_pipeline(inputs)


async def _fetch_data(inputs: UserInputs) -> dict:
    """Fetch all the scenario-invariant data: project setup, brands report,
    chat counts, search-volume, market estimates, and resolve ACV."""
    print(f"\n{'='*60}")
    print(f"[pipeline] fetching data for {inputs.peec_project_id}")
    print(f"[pipeline] v2l={inputs.visit_to_lead_rate}, l2c={inputs.lead_to_customer_rate}, acv={'auto' if inputs.acv_eur is None else f'€{inputs.acv_eur}'}")

    setup = await step1_setup.run(inputs.peec_project_id)
    (summaries, brand_vis), chat_volumes, volumes, acv_dict = await asyncio.gather(
        step2_brands.run(setup),
        step3_chats.run(setup),
        step1_5_volume.run(setup.prompts),
        acv_research.get_acv(setup.own_brand.name, inputs.acv_eur),
    )
    market, action_rate = await step4_market.run()
    visit_to_lead, lead_to_customer = step7_conversion.get_conversion_rates(inputs)
    acv_info = AcvInfo(**acv_dict)

    return {
        "inputs": inputs,
        "setup": setup,
        "summaries": summaries,
        "brand_vis": brand_vis,
        "chat_volumes": chat_volumes,
        "volumes": volumes,
        "market": market,
        "action_rate": action_rate,
        "visit_to_lead": visit_to_lead,
        "lead_to_customer": lead_to_customer,
        "acv": acv_info,
    }


async def _assemble_report(
    data: dict,
    delta_pp: float,
    label: str = "",
    skip_summary: bool = False,
    skip_pioneer: bool = False,
) -> tuple[FinalReport, list]:
    """Run lift math + step11/12 with a specific visibility-increase delta.
    Returns (FinalReport with top_10, full_prompt_revenues_list) — the full list
    is needed by the dual-scenario merge step."""
    inputs = data["inputs"]
    setup = data["setup"]
    summaries = data["summaries"]
    chat_volumes = data["chat_volumes"]
    volumes = data["volumes"]
    market = data["market"]
    action_rate = data["action_rate"]
    visit_to_lead = data["visit_to_lead"]
    lead_to_customer = data["lead_to_customer"]
    brand_vis = data["brand_vis"]
    acv_eur = data["acv"].value_eur

    tag = f"[{label}] " if label else ""
    print(f"{tag}assembling report with visibility_increase_pp={delta_pp}, acv=€{acv_eur:,.0f}")

    prompt_revenues = []
    skipped_no_summary = 0
    skipped_no_signal = 0
    for prompt in setup.prompts:
        summary = summaries.get(prompt.id)
        if summary is None:
            skipped_no_summary += 1
            continue
        chats_30d = chat_volumes.get(prompt.id, 0)
        vol, vol_sources = volumes.get(prompt.id, (0, []))
        volume_from_tavily = (prompt.search_volume == 0 and vol > 0)
        if vol == 0 and chats_30d == 0:
            skipped_no_signal += 1
            continue
        pr = step10_upside.build_prompt_revenue(
            prompt, summary, chats_30d,
            search_volume=vol,
            volume_source_urls=vol_sources,
            volume_from_tavily=volume_from_tavily,
            market=market, action=action_rate,
            visit_to_lead=visit_to_lead, lead_to_customer=lead_to_customer,
            acv_eur=acv_eur,
            visibility_increase_pp=delta_pp,
        )
        prompt_revenues.append(pr)

    print(f"{tag}{len(prompt_revenues)} prompts, skipped {skipped_no_summary} no-summary, {skipped_no_signal} no-signal")
    top_10 = sorted(prompt_revenues, key=lambda p: -p.revenue_lift_eur)[:10]
    actions = await step11_actions.run(setup, top_10)
    final = await step12_synthesize.run(
        prompt_revenues, actions, market, action_rate,
        visit_to_lead, lead_to_customer,
        setup=setup, summaries=summaries, brand_vis=brand_vis,
        acv_eur=acv_eur,
        skip_summary=skip_summary,
        skip_pioneer=skip_pioneer,
    )
    print(f"{tag}lift=€{final.total_revenue_lift_eur:,.0f}")
    return final, prompt_revenues


async def _run_pipeline(inputs: UserInputs) -> FinalReport:
    data = await _fetch_data(inputs)
    final, _ = await _assemble_report(data, inputs.visibility_increase_pp, label="single")
    print(f"{'='*60}\n")
    return final


async def _run_full_pipeline(inputs: UserInputs) -> EnhancedFinalReport:
    """Fetch data + run prep pipeline (parallel), then assemble two reports
    with the prep-derived pessimistic + optimistic deltas."""
    print(f"\n{'='*60}")
    print(f"[full] starting full analysis for {inputs.peec_project_id}")

    # Step 1 first (need ProjectSetup for prep + ACV)
    setup = await step1_setup.run(inputs.peec_project_id)

    # Now run main data-fetch + prep pipeline + ACV research in parallel
    print("[full] fetching ROI data + running prep pipeline + ACV (parallel)")
    (summaries, brand_vis), chat_volumes, volumes, market_action, prep_payload, acv_dict = await asyncio.gather(
        step2_brands.run(setup),
        step3_chats.run(setup),
        step1_5_volume.run(setup.prompts),
        step4_market.run(),
        prep_pipeline.run(setup),
        acv_research.get_acv(setup.own_brand.name, inputs.acv_eur),
    )
    market, action_rate = market_action
    visit_to_lead, lead_to_customer = step7_conversion.get_conversion_rates(inputs)
    acv_info = AcvInfo(**acv_dict)
    print(f"[full] ACV resolved: €{acv_info.value_eur:,.0f} (source={acv_info.source[:60]})")

    data = {
        "inputs": inputs,
        "setup": setup,
        "summaries": summaries,
        "brand_vis": brand_vis,
        "chat_volumes": chat_volumes,
        "volumes": volumes,
        "market": market,
        "action_rate": action_rate,
        "visit_to_lead": visit_to_lead,
        "lead_to_customer": lead_to_customer,
        "acv": acv_info,
    }

    pess_delta = prep_payload.projected.pessimistic.delta
    opt_delta = prep_payload.projected.optimistic.delta
    print(f"[full] prep deltas — pessimistic={pess_delta:+.2f}pp, optimistic={opt_delta:+.2f}pp")

    # Run lift assembly twice in parallel — skip per-scenario summaries AND
    # per-scenario Pioneer calls. We'll merge into PromptRevenueDual entries
    # below and run Pioneer ONCE per merged entry.
    (pess_report, pess_full), (opt_report, opt_full) = await asyncio.gather(
        _assemble_report(data, pess_delta, label="pess", skip_summary=True, skip_pioneer=True),
        _assemble_report(data, opt_delta, label="opt", skip_summary=True, skip_pioneer=True),
    )

    bracket = ScenarioBracket(
        pessimistic_visibility_increase_pp=pess_delta,
        optimistic_visibility_increase_pp=opt_delta,
        pessimistic_total_revenue_lift_eur=pess_report.total_revenue_lift_eur,
        optimistic_total_revenue_lift_eur=opt_report.total_revenue_lift_eur,
        pessimistic_customer_equivalents=pess_report.customer_equivalents,
        optimistic_customer_equivalents=opt_report.customer_equivalents,
    )

    # Merge into PromptRevenueDual entries — invariants taken from optimistic,
    # scenario-specific fields drawn from each full list.
    merged = await _merge_and_summarize(opt_full, pess_full, top_n=10)
    # The merged list IS the canonical detail — empty the per-scenario lists.
    pess_report.prompt_revenues = []
    opt_report.prompt_revenues = []

    # Top-3 paid platforms by name for the umbrella summary
    top_platforms = [o.domain for o in prep_payload.paid_media_opportunities[:3]]

    umbrella_facts = {
        "company": setup.own_brand.name,
        "lift_pessimistic_eur": int(pess_report.total_revenue_lift_eur),
        "lift_optimistic_eur": int(opt_report.total_revenue_lift_eur),
        "customers_pessimistic": pess_report.customer_equivalents,
        "customers_optimistic": opt_report.customer_equivalents,
        "current_visibility_pct": prep_payload.baseline.visibility_score,
        "leader_name": opt_report.leader_name,
        "leader_visibility_pct": round(opt_report.leader_visibility * 100, 1),
        "visibility_gap_pp": opt_report.visibility_gap_pp,
        "prompts_total": opt_report.total_prompts,
        "prompts_untapped": opt_report.untapped_prompt_count,
        "top_paid_platforms": top_platforms,
    }
    print(f"[full] generating umbrella executive_summary")
    umbrella_summary = await _safe_umbrella_summary(umbrella_facts)
    if umbrella_summary:
        print(f"[full] umbrella: {umbrella_summary[:160]}{'...' if len(umbrella_summary) > 160 else ''}")
    else:
        print("[full] umbrella: (empty — Gemini unavailable)")

    print(f"[full] BRACKET: lift €{bracket.pessimistic_total_revenue_lift_eur:,.0f} (pess) → €{bracket.optimistic_total_revenue_lift_eur:,.0f} (opt)")
    print(f"{'='*60}\n")

    return EnhancedFinalReport(
        company_name=setup.own_brand.name,
        executive_summary=umbrella_summary,
        acv=acv_info,
        bracket=bracket,
        prompt_revenues=merged,
        pessimistic=pess_report,
        optimistic=opt_report,
        prep=prep_payload,
    )


def _has_enough_info_for_pioneer(entry: PromptRevenueDual) -> bool:
    """Skip prompts where Pioneer can't produce a meaningful summary.
    Requirements: a real top competitor + positive lift in at least one scenario."""
    name = (entry.top_competitor_name or "").strip().lower()
    if not name or name == "unknown":
        return False
    if entry.optimistic.revenue_lift_eur <= 0 and entry.pessimistic.revenue_lift_eur <= 0:
        return False
    return True


async def _merge_and_summarize(
    opt_full: list,
    pess_full: list,
    top_n: int = 10,
) -> list[PromptRevenueDual]:
    """Build PromptRevenueDual entries from the two scenarios' full PromptRevenue lists.
    Picks top N by optimistic lift. Runs Pioneer ONLY on entries with enough info;
    the rest get an empty string for ai_summary."""
    pess_by_id = {pr.prompt_id: pr for pr in pess_full}

    merged: list[PromptRevenueDual] = []
    for opr in sorted(opt_full, key=lambda p: -p.revenue_lift_eur):
        ppr = pess_by_id.get(opr.prompt_id)
        if ppr is None:
            continue  # shouldn't happen — both scenarios run on the same prompt set
        merged.append(PromptRevenueDual(
            prompt_id=opr.prompt_id,
            prompt_message=opr.prompt_message,
            volume_source=opr.volume_source,  # type: ignore[arg-type]
            search_volume=opr.search_volume,
            volume_source_urls=opr.volume_source_urls,
            your_visibility=opr.your_visibility,
            your_position=opr.your_position,
            top_competitor_visibility=opr.top_competitor_visibility,
            top_competitor_name=opr.top_competitor_name,
            annual_mentions=opr.annual_mentions,
            current_annual_revenue_eur=opr.current_annual_revenue_eur,
            pessimistic=ScenarioOutcome(
                target_visibility=ppr.target_visibility,
                target_position=ppr.target_position,
                target_annual_revenue_eur=ppr.target_annual_revenue_eur,
                revenue_lift_eur=ppr.revenue_lift_eur,
            ),
            optimistic=ScenarioOutcome(
                target_visibility=opr.target_visibility,
                target_position=opr.target_position,
                target_annual_revenue_eur=opr.target_annual_revenue_eur,
                revenue_lift_eur=opr.revenue_lift_eur,
            ),
        ))
        if len(merged) >= top_n:
            break

    # Partition: only send entries with enough info to Pioneer; rest get "".
    to_pioneer: list[PromptRevenueDual] = []
    skipped = 0
    for entry in merged:
        if _has_enough_info_for_pioneer(entry):
            to_pioneer.append(entry)
        else:
            entry.ai_summary = ""
            skipped += 1
    if skipped:
        print(f"[full] {skipped}/{len(merged)} merged entries skipped Pioneer (insufficient info, ai_summary='')")

    # Pioneer dual summary — best-effort, leaves placeholder on per-entry failure
    if to_pioneer:
        try:
            from .clients import pioneer
            summaries = await pioneer.summarize_dual_prompt_revenues(to_pioneer)
            for entry, summary in zip(to_pioneer, summaries):
                if summary:
                    entry.ai_summary = summary
        except Exception as e:
            print(f"[full] dual Pioneer unavailable ({type(e).__name__}: {e})")

    return merged


async def _safe_umbrella_summary(facts: dict) -> str:
    """Belt-and-suspenders wrapper around the umbrella Gemini call."""
    try:
        from .clients import gemini
        return await gemini.synthesize_umbrella_summary(facts)
    except Exception as e:
        print(f"[full] umbrella summary unavailable ({type(e).__name__}: {e})")
        return ""


@router.get("/debug")
async def debug(peec_project_id: str):
    setup = await step1_setup.run(peec_project_id)
    (summaries, _), chat_volumes = await asyncio.gather(
        step2_brands.run(setup),
        step3_chats.run(setup),
    )

    matched = [
        p.id for p in setup.prompts
        if p.id in summaries and (p.search_volume > 0 or chat_volumes.get(p.id, 0) > 0)
    ]
    return {
        "prompts_count": len(setup.prompts),
        "prompts_with_search_volume": sum(1 for p in setup.prompts if p.search_volume > 0),
        "brands_report_keys": len(summaries),
        "brands_report_sample": {k: v.__dict__ for k, v in list(summaries.items())[:3]},
        "chat_volumes_keys": len(chat_volumes),
        "chat_volumes_sample": dict(list(chat_volumes.items())[:5]),
        "prompt_ids_sample": [p.id for p in setup.prompts[:5]],
        "search_volume_sample": [(p.message[:60], p.search_volume) for p in setup.prompts[:10]],
        "matched_prompts": len(matched),
    }


@router.get("/projects")
async def list_projects():
    import base64
    from .config import PEEC_API_KEY
    try:
        parts = PEEC_API_KEY.split("-", 2)
        middle = parts[1] if len(parts) >= 2 else ""
        project_id = base64.b64decode(middle + "==").decode()
    except Exception:
        project_id = "could not decode — check PEEC_API_KEY in .env"
    return {"project_id": project_id}


@router.get("/quota")
async def quota():
    return {
        "searches_used": tavily_client.searches_used(),
        "remaining": tavily_client.remaining_quota(),
        "monthly_limit": tavily_client.MONTHLY_QUOTA,
    }
