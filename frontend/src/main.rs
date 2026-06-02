//! Leptos CSR port of frontend/app/report/page.tsx.

mod data;
mod icons;

use data::*;
use icons::Icon;
use leptos::*;
use leptos_router::*;
use std::collections::HashMap;

const STORAGE_KEY: &str = "peec.paidmedia.state.v1";
const ANALYSIS_FLAG: &str = "peec.hasAnalysis";
const CONTEXT_KEY: &str = "peec.offer.context.v1";
const USER_KEY: &str = "peec.user";
const NOTIFY_EMAIL: &str = "kalwajonas@gmail.com";

#[derive(Clone, Copy, PartialEq, Eq)]
enum CardState {
    Estimate,
    Sending,
    Received,
    Accepted,
}
impl CardState {
    fn as_str(&self) -> &'static str {
        match self {
            CardState::Estimate => "estimate",
            CardState::Sending => "sending",
            CardState::Received => "received",
            CardState::Accepted => "accepted",
        }
    }
    fn from_str(s: &str) -> CardState {
        match s {
            "sending" => CardState::Sending,
            "received" => CardState::Received,
            "accepted" => CardState::Accepted,
            _ => CardState::Estimate,
        }
    }
}

type StateMap = HashMap<String, CardState>;

#[derive(Clone)]
struct Media {
    id: String,
    title: String,
    domain: String,
    audience: String,
    icon: &'static str,
    cost: String,
    gain_range: String,
    gain_delta_range: String,
    partner_email: String,
}

const CARD_ICONS: [&str; 3] = ["globe-2", "briefcase", "cpu"];

fn build_media(o: &PaidMediaOpportunity, i: usize, bracket: &Bracket) -> Media {
    let confidence_pct = (o.classification_confidence * 100.0).round() as i64;
    let audience = format!(
        "{} · {}% confidence · {} contributing chats",
        classification_label(&o.classification),
        confidence_pct,
        o.contributing_chat_count
    );
    let pess_share = if bracket.pessimistic_visibility_increase_pp > 0.0 {
        o.delta_visibility_pp_pessimistic / bracket.pessimistic_visibility_increase_pp
    } else {
        0.0
    };
    let opt_share = if bracket.optimistic_visibility_increase_pp > 0.0 {
        o.delta_visibility_pp_optimistic / bracket.optimistic_visibility_increase_pp
    } else {
        0.0
    };
    let pess_lift = pess_share * bracket.pessimistic_total_revenue_lift_eur;
    let opt_lift = opt_share * bracket.optimistic_total_revenue_lift_eur;
    Media {
        id: o.domain.clone(),
        title: o.domain.clone(),
        domain: o.domain.clone(),
        audience,
        icon: CARD_ICONS[i % CARD_ICONS.len()],
        cost: format_usd_range(&o.pricing),
        gain_range: format!("{} – {}", format_euro(pess_lift), format_euro(opt_lift)),
        gain_delta_range: format!(
            "{:.2}–{:.2} pp visibility",
            o.delta_visibility_pp_pessimistic, o.delta_visibility_pp_optimistic
        ),
        partner_email: format!("partnerships@{}", o.domain),
    }
}

fn initial_state_map(media: &[Media]) -> StateMap {
    media.iter().map(|m| (m.id.clone(), CardState::Estimate)).collect()
}

// ---- localStorage helpers ----

fn local_get(key: &str) -> Option<String> {
    web_sys::window()?.local_storage().ok()??.get_item(key).ok()?
}
fn local_set(key: &str, val: &str) {
    if let Some(Ok(Some(s))) = web_sys::window().map(|w| w.local_storage()) {
        let _ = s.set_item(key, val);
    }
}
fn session_get(key: &str) -> Option<String> {
    web_sys::window()?.session_storage().ok()??.get_item(key).ok()?
}
fn session_set(key: &str, val: &str) {
    if let Some(Ok(Some(s))) = web_sys::window().map(|w| w.session_storage()) {
        let _ = s.set_item(key, val);
    }
}

fn serialize_states(m: &StateMap) -> String {
    let obj: serde_json::Map<String, serde_json::Value> = m
        .iter()
        .map(|(k, v)| {
            (
                k.clone(),
                serde_json::json!({ "state": v.as_str() }),
            )
        })
        .collect();
    serde_json::to_string(&serde_json::Value::Object(obj)).unwrap_or_default()
}

fn main() {
    console_error_panic_hook_noop();
    mount_to_body(|| view! { <App /> });
}

#[component]
fn App() -> impl IntoView {
    view! {
        <Router>
            <Routes>
                <Route path="/" view=LoginPage />
                <Route path="/home" view=HomePage />
                <Route path="/analyse" view=AnalysePage />
                <Route path="/report" view=|| view! { <ReportView root=get_report() /> } />
                // Legacy alias — the Next.js app redirects /auswertung → /report.
                <Route path="/auswertung" view=|| view! { <Redirect path="/report" /> } />
            </Routes>
        </Router>
    }
}

/// Tiny stand-in so a panic surfaces in the console without an extra dep.
fn console_error_panic_hook_noop() {
    std::panic::set_hook(Box::new(|info| {
        web_sys::console::error_1(&format!("panic: {info}").into());
    }));
}

#[component]
fn BrandMark(#[prop(into, default = String::new())] class: String) -> impl IntoView {
    view! {
        <A href="/home" class=format!("inline-flex items-center gap-3 {class}")>
            <svg width="30" height="20" viewBox="0 0 30 20" fill="none" aria-hidden="true">
                <rect x="6" y="2" width="18" height="5" rx="2" fill="#000000"></rect>
                <rect x="0" y="10" width="18" height="8" rx="2.5" fill="#000000"></rect>
            </svg>
            <span class="font-medium text-[20px] tracking-tight text-ink leading-none">"Peec AI"</span>
        </A>
    }
}

#[component]
fn ReportView(root: PeecRoot) -> impl IntoView {
    let brand = root.company_name.clone();
    let bracket = root.bracket.clone();
    let scenario = root.optimistic.clone();
    let exec_summary = root.executive_summary.clone().unwrap_or_default();
    let acv_source = root.acv.as_ref().and_then(|a| a.source.clone());

    let media: Vec<Media> = paid_media_opportunities(&root, 3)
        .iter()
        .enumerate()
        .map(|(i, o)| build_media(o, i, &bracket))
        .collect();

    let states = create_rw_signal(initial_state_map(&media));
    let username = create_rw_signal(brand.clone());

    // On mount: hydrate state from localStorage; mark analysis flag; pull username.
    {
        let media = media.clone();
        create_effect(move |prev: Option<()>| {
            if prev.is_some() {
                return;
            }
            let mut merged = initial_state_map(&media);
            if let Some(raw) = local_get(STORAGE_KEY) {
                if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&raw) {
                    for m in &media {
                        if let Some(st) = parsed.get(&m.id).and_then(|v| v.get("state")).and_then(|v| v.as_str()) {
                            let mut cs = CardState::from_str(st);
                            // On re-entry, a pending "sending" is treated as answered.
                            if cs == CardState::Sending {
                                cs = CardState::Received;
                            }
                            merged.insert(m.id.clone(), cs);
                        }
                    }
                }
            }
            states.set(merged);
            local_set(ANALYSIS_FLAG, "1");
            if let Some(u) = session_get("peec.user") {
                if !u.trim().is_empty() {
                    username.set(u.trim().to_string());
                }
            }
        });
    }

    // Persist on change.
    create_effect(move |_| {
        let snapshot = states.get();
        local_set(STORAGE_KEY, &serialize_states(&snapshot));
    });

    let competitors = competitors_ranked(&scenario);
    let all_prompts = all_prompts_by_lift(&root, &scenario);
    let weak_prompts = lowest_visibility_prompts(&root, 3);

    let total_prompts = scenario.total_prompts;
    let header_brand = move || username.get().to_uppercase();

    view! {
        <main class="min-h-screen flex flex-col">
            <BrandMark class="fixed top-5 left-6 z-50 no-print".to_string() />
            <section class="enter flex-1 max-w-6xl mx-auto w-full px-6 py-16">
                // Header
                <div class="enter text-center mb-12" style="--d:0.05s">
                    <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-line bg-white text-[13px] mb-5">
                        <Icon name="check-circle-2" class="w-3.5 h-3.5 text-gain" />
                        "Analysis complete · " {header_brand}
                    </div>
                    <h1 class="text-[clamp(2.25rem,6vw,4rem)] font-semibold tracking-[-0.04em] leading-[1.02] max-w-3xl mx-auto">
                        <span class="text-ink">"Where " {brand.clone()} " loses pipeline"</span>
                        <br />
                        <span class="text-muted">"in AI-driven discovery."</span>
                    </h1>
                </div>

                <Hero
                    brand=brand.clone()
                    bracket=bracket.clone()
                    summary=exec_summary
                    acv_source=acv_source
                />

                <PaidMedia media=media.clone() states=states username=username />

                <VisibilityGap
                    brand=brand.clone()
                    you=scenario.overall_your_visibility
                    leader=scenario.leader_visibility
                    leader_name=scenario.leader_name.clone()
                    gap_pp=scenario.visibility_gap_pp
                />

                <InvisibleCallout
                    brand=brand.clone()
                    untapped=scenario.untapped_prompt_count
                    total=total_prompts
                    examples=weak_prompts
                />

                <Competitive
                    brand=brand.clone()
                    competitors=competitors
                    total_prompts=total_prompts
                />

                <PromptsTable prompts=all_prompts share_pct=scenario.top3_lift_share_pct />

                <Methodology
                    ai_query_share=scenario.market_estimate.ai_query_share
                    real_volume=scenario.prompts_using_real_volume
                    total_prompts=total_prompts
                    source=scenario.market_estimate.sources.first().cloned().unwrap_or_default()
                />

                <CTA />
            </section>
        </main>
    }
}

#[component]
fn Hero(
    brand: String,
    bracket: Bracket,
    summary: String,
    acv_source: Option<String>,
) -> impl IntoView {
    let fmt_cust = |n: f64| format!("{n:.1}");
    let has_summary = !summary.is_empty();
    view! {
        <div class="enter rounded-3xl bg-ink text-white p-10 md:p-14 mb-8 relative overflow-hidden print-bg-light" style="--d:0.15s">
            <div class="absolute inset-0 dot-grid opacity-[0.06]"></div>
            <div class="relative">
                <div class="text-[13px] uppercase tracking-wider text-white/60 mb-3 flex items-center gap-2">
                    <Icon name="sparkles" class="w-3.5 h-3.5" />
                    "Potential financial gain for " {brand}
                </div>
                <div class="text-[clamp(2.5rem,8.5vw,5.5rem)] font-semibold tracking-[-0.04em] leading-[1.02] text-gain tabular-nums">
                    {format_euro(bracket.pessimistic_total_revenue_lift_eur)}
                    <span class="text-gain font-normal text-[0.55em] mx-4 align-middle">"–"</span>
                    {format_euro(bracket.optimistic_total_revenue_lift_eur)}
                </div>
                <div class="mt-5 text-[17px] text-white/70 leading-relaxed flex items-center gap-2 flex-wrap">
                    <Icon name="users" class="w-4 h-4 text-white/60" />
                    "≈ "
                    <strong class="text-white tabular-nums">
                        {fmt_cust(bracket.pessimistic_customer_equivalents)} "–" {fmt_cust(bracket.optimistic_customer_equivalents)} " new customers"
                    </strong>
                    ", currently won by competitors across the AI answers your buyers see."
                </div>
                <div class="mt-2 text-[13px] text-white/50 tabular-nums">
                    {format!("{:.2}", bracket.pessimistic_visibility_increase_pp)} "–" {format!("{:.2}", bracket.optimistic_visibility_increase_pp)} " pp visibility upside"
                </div>
                {acv_source.map(|src| {
                    let host = hostname_of(&src);
                    view! {
                        <div class="mt-1 text-[12px] text-white/40">
                            "ACV researched from "
                            <a href=src target="_blank" rel="noopener noreferrer" class="underline decoration-white/20 underline-offset-2 hover:text-white/70">{host}</a>
                        </div>
                    }
                })}
                {has_summary.then(|| view! {
                    <div class="mt-10 pt-7 border-t border-white/15 max-w-3xl">
                        <div class="text-[11px] uppercase tracking-wider text-white/50 mb-2.5">"Executive summary"</div>
                        <p class="text-[15px] text-white/80 leading-relaxed">{summary}</p>
                    </div>
                })}
            </div>
        </div>
    }
}

#[component]
fn VisibilityGap(
    brand: String,
    you: f64,
    leader: f64,
    leader_name: String,
    gap_pp: f64,
) -> impl IntoView {
    view! {
        <div class="enter rounded-2xl bg-white border border-line p-7 mb-8" style="--d:0.25s">
            <div class="flex items-start justify-between flex-wrap gap-4 mb-6">
                <div>
                    <h2 class="text-[22px] font-semibold tracking-[-0.02em]">{gap_pp.round() as i64} " pp visibility gap"</h2>
                    <p class="text-muted text-[14px] mt-1">"Share of voice across AI answers — " {brand} " vs. " {leader_name.clone()} "."</p>
                </div>
            </div>
            <div class="space-y-5">
                <Bar label=leader_name.clone() value=you accent=false />
                <Bar label=leader_name value=leader accent=true />
            </div>
        </div>
    }
}

#[component]
fn Bar(label: String, value: f64, accent: bool) -> impl IntoView {
    let pct = (value * 100.0).round() as i64;
    let fill_class = if accent { "bg-ink" } else { "bg-ink/30" };
    view! {
        <div>
            <div class="flex items-baseline justify-between mb-2">
                <span class="text-[15px] font-medium">{label}</span>
                <span class="text-[20px] font-semibold tracking-tight tabular-nums">{pct} "%"</span>
            </div>
            <div class="h-3 rounded-full bg-canvas border border-line overflow-hidden">
                <div class=format!("bar-fill h-full rounded-full {fill_class}") style=format!("width:{pct}%")></div>
            </div>
        </div>
    }
}

#[component]
fn InvisibleCallout(
    brand: String,
    untapped: i64,
    total: i64,
    examples: Vec<PromptRevenue>,
) -> impl IntoView {
    let count = create_rw_signal(0i64);
    // Cubic ease-out count-up over ~1100ms.
    {
        let target = untapped;
        let start = window_now();
        let duration = 1100.0;
        let handle = create_rw_signal::<Option<leptos::leptos_dom::helpers::IntervalHandle>>(None);
        let h = set_interval_with_handle(
            move || {
                let t = ((window_now() - start) / duration).min(1.0);
                let eased = 1.0 - (1.0 - t).powi(3);
                count.set((eased * target as f64).round() as i64);
                if t >= 1.0 {
                    if let Some(hh) = handle.get_untracked() {
                        hh.clear();
                    }
                }
            },
            std::time::Duration::from_millis(16),
        )
        .ok();
        handle.set_untracked(h);
    }

    let example_views = examples
        .into_iter()
        .map(|p| {
            let vis = (p.your_visibility * 100.0).round() as i64;
            view! {
                <div class="rounded-lg bg-canvas border border-line px-3.5 py-3">
                    <div class="text-[11px] uppercase tracking-wider text-muted">"Visibility " {vis} "%"</div>
                    <div class="text-[13px] mt-1 leading-snug line-clamp-3">"“" {p.prompt_message} "”"</div>
                </div>
            }
        })
        .collect_view();

    view! {
        <div class="enter rounded-2xl bg-white border border-line p-7 mb-8" style="--d:0.35s">
            <div class="flex items-start gap-5 flex-wrap">
                <div class="flex-shrink-0 w-12 h-12 rounded-xl bg-canvas border border-line flex items-center justify-center">
                    <Icon name="eye-off" class="w-5 h-5" />
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-baseline gap-2 flex-wrap">
                        <span class="text-[44px] font-semibold tracking-[-0.03em] tabular-nums leading-none">{move || count.get()}</span>
                        <span class="text-[20px] text-muted tabular-nums">" / " {total}</span>
                        <span class="text-[14px] text-muted ml-2">"prompts where " {brand} " never surfaces in AI answers."</span>
                    </div>
                    <div class="mt-5 grid sm:grid-cols-3 gap-2">{example_views}</div>
                </div>
            </div>
        </div>
    }
}

#[component]
fn Competitive(
    brand: String,
    competitors: Vec<Competitor>,
    total_prompts: i64,
) -> impl IntoView {
    let max = competitors
        .iter()
        .map(|c| c.prompts_won_against_you)
        .max()
        .unwrap_or(1)
        .max(1);
    let rows = competitors
        .into_iter()
        .map(|c| {
            let pct = ((c.prompts_won_against_you as f64 / total_prompts as f64) * 100.0).round() as i64;
            let width_pct = ((c.prompts_won_against_you as f64 / max as f64) * 100.0).round() as i64;
            view! {
                <div>
                    <div class="flex items-baseline justify-between mb-1.5">
                        <span class="text-[14px] font-medium">{c.competitor_name}</span>
                        <span class="text-[13px] text-muted tabular-nums">
                            {c.prompts_won_against_you} " / " {total_prompts} " prompts"
                            <span class="text-muted/60">" · " {pct} "%"</span>
                        </span>
                    </div>
                    <div class="h-2.5 rounded-full bg-canvas border border-line overflow-hidden">
                        <div class="bar-fill h-full bg-ink rounded-full" style=format!("width:{width_pct}%")></div>
                    </div>
                </div>
            }
        })
        .collect_view();
    view! {
        <div class="enter rounded-2xl bg-white border border-line p-7 mb-8" style="--d:0.45s">
            <h2 class="text-[22px] font-semibold tracking-[-0.02em] mb-1">"Competitive landscape"</h2>
            <p class="text-muted text-[14px] mb-6">"Who outranks " {brand} " across the " {total_prompts} " prompts in scope."</p>
            <div class="space-y-4">{rows}</div>
        </div>
    }
}

#[component]
fn PromptsTable(prompts: Vec<PromptDetail>, share_pct: f64) -> impl IntoView {
    let open = create_rw_signal::<Option<String>>(None);
    let total = prompts.len();
    let share_str = format!("{share_pct}");
    let rows = prompts
        .into_iter()
        .enumerate()
        .map(|(i, p)| {
            let is_top3 = i < 3;
            let id = p.prompt_id.clone();
            let id_for_click = id.clone();
            let id_for_open = id.clone();
            let border_top = if i > 0 { "border-t border-line" } else { "" };
            let bg = if is_top3 { "bg-canvas/40" } else { "bg-white" };
            let badge = if is_top3 {
                "bg-ink text-white"
            } else {
                "bg-canvas border border-line text-muted"
            };
            let vis = (p.your_visibility * 100.0).round() as i64;
            let lift = format_euro(p.revenue_lift_eur);
            let detail = p.clone();
            view! {
                <div class=format!("{border_top} {bg}")>
                    <button
                        on:click=move |_| {
                            open.update(|o| {
                                *o = if o.as_deref() == Some(id_for_click.as_str()) { None } else { Some(id_for_click.clone()) };
                            })
                        }
                        class="w-full text-left flex items-center gap-4 p-4 hover:bg-canvas transition"
                    >
                        <span class=format!("flex-shrink-0 w-7 h-7 rounded-full text-[12px] font-semibold flex items-center justify-center {badge}")>{i + 1}</span>
                        <span class="flex-1 min-w-0 text-[14px] leading-snug">{p.prompt_message.clone()}</span>
                        <span class="hidden sm:inline-flex items-center gap-1 text-[12px] text-muted whitespace-nowrap tabular-nums">"vis " {vis} "%"</span>
                        <span class="text-[15px] font-semibold tabular-nums whitespace-nowrap text-gain">{lift}</span>
                        <span class="text-muted">
                            {move || if open.get().as_deref() == Some(id_for_open.as_str()) {
                                view! { <Icon name="chevron-down" class="w-4 h-4" /> }
                            } else {
                                view! { <Icon name="chevron-right" class="w-4 h-4" /> }
                            }}
                        </span>
                    </button>
                    {move || (open.get().as_deref() == Some(id.as_str())).then(|| view! { <PromptDetailView prompt=detail.clone() /> })}
                </div>
            }
        })
        .collect_view();
    view! {
        <div class="enter rounded-2xl bg-white border border-line p-7 mb-8" style="--d:0.55s">
            <div class="flex items-start justify-between flex-wrap gap-4 mb-6">
                <div>
                    <h2 class="text-[22px] font-semibold tracking-[-0.02em]">"All " {total} " prompts"</h2>
                    <p class="text-muted text-[14px] mt-1">"The top 3 hold " <span class="text-ink font-medium">{share_str} "%"</span> " of the lift. Open any row for the full read."</p>
                </div>
                <div class="inline-flex items-center gap-2 text-[12px] text-muted">
                    <Icon name="target" class="w-3.5 h-3.5" /> "ranked by revenue lift"
                </div>
            </div>
            <div class="border border-line rounded-xl overflow-hidden">{rows}</div>
        </div>
    }
}

#[component]
fn PromptDetailView(prompt: PromptDetail) -> impl IntoView {
    let summary = prompt
        .ai_summary
        .clone()
        .filter(|s| !s.is_empty() && s != "this will be the ai summary");
    let mentions_comma = comma_str(prompt.annual_mentions.round() as i64);
    let vol_sub = if prompt.volume_source == "chat_fallback" {
        "sample-extrapolation".to_string()
    } else {
        format!("search_volume {}", comma_str(prompt.search_volume))
    };
    let action_view = prompt.action.clone().map(|a| {
        let action_type = a.action_type.replace('_', " ");
        let targets = a.suggested_targets.into_iter().map(|t| view! { <li class="leading-snug">"· " {t}</li> }).collect_view();
        let evidence = a.evidence_signals.into_iter().map(|s| view! { <li class="leading-snug">"· " {s}</li> }).collect_view();
        view! {
            <div class="md:col-span-3 rounded-lg bg-white border border-line p-4 mt-1">
                <div class="flex items-start justify-between flex-wrap gap-3 mb-3">
                    <div>
                        <div class="text-[11px] uppercase tracking-wider text-muted">"Recommended action"</div>
                        <div class="text-[14px] font-medium capitalize mt-0.5">{action_type}</div>
                    </div>
                </div>
                <div class="grid sm:grid-cols-2 gap-3">
                    <div>
                        <div class="text-[11px] uppercase tracking-wider text-muted mb-1.5">"Suggested targets"</div>
                        <ul class="space-y-1 text-[13px] text-muted">{targets}</ul>
                    </div>
                    <div>
                        <div class="text-[11px] uppercase tracking-wider text-muted mb-1.5">"Evidence"</div>
                        <ul class="space-y-1 text-[13px] text-muted">{evidence}</ul>
                    </div>
                </div>
            </div>
        }
    });
    view! {
        <div class="px-4 pb-5 pt-1">
            {summary.map(|s| view! {
                <div class="mb-3 rounded-lg bg-ink/5 border border-line p-4 text-[13px] leading-relaxed text-ink/80">
                    <span class="text-[11px] uppercase tracking-wider text-muted mr-2">"TLDR"</span> {s}
                </div>
            })}
            <div class="grid md:grid-cols-3 gap-3">
                <Stat label=format!("Your visibility") value=format!("{}%", (prompt.your_visibility*100.0).round() as i64) sub=Some(format!("avg position {:.1}", prompt.your_position)) accent=false />
                <Stat label=format!("Top competitor · {}", prompt.top_competitor_name) value=format!("{}%", (prompt.top_competitor_visibility*100.0).round() as i64) sub=Some("avg visibility".to_string()) accent=false />
                <Stat label="Annual mentions".to_string() value=mentions_comma sub=Some(vol_sub) accent=false />
                <Stat label="Current annual revenue".to_string() value=format_euro(prompt.current_annual_revenue_eur) sub=None accent=false />
                <Stat label="Target annual revenue".to_string() value=format_euro(prompt.target_annual_revenue_eur) sub=Some(format!("if visibility → {}% @ pos {:.1}", (prompt.target_visibility*100.0).round() as i64, prompt.target_position)) accent=false />
                <Stat label="Revenue lift".to_string() value=format!("{} – {}", format_euro(prompt.pessimistic_revenue_lift_eur), format_euro(prompt.optimistic_revenue_lift_eur)) sub=None accent=true />
                {action_view}
            </div>
        </div>
    }
}

#[component]
fn Stat(
    label: String,
    value: String,
    sub: Option<String>,
    accent: bool,
) -> impl IntoView {
    let val_class = if accent { "text-gain" } else { "" };
    view! {
        <div class="rounded-lg bg-white border border-line p-3.5">
            <div class="text-[11px] uppercase tracking-wider text-muted">{label}</div>
            <div class=format!("mt-1 text-[18px] font-semibold tracking-tight tabular-nums leading-tight {val_class}")>{value}</div>
            {sub.map(|s| view! { <div class="mt-0.5 text-[12px] text-muted leading-snug">{s}</div> })}
        </div>
    }
}

#[component]
fn Methodology(
    ai_query_share: f64,
    real_volume: i64,
    total_prompts: i64,
    source: String,
) -> impl IntoView {
    let fallback = total_prompts - real_volume;
    view! {
        <div class="enter rounded-xl bg-white/60 border border-line/70 p-5 mb-10 text-[12px] text-muted leading-relaxed" style="--d:0.7s">
            <div class="flex items-start gap-2 flex-wrap">
                <span class="font-medium text-muted/90 uppercase tracking-wider text-[10px]">"Methodology"</span>
                <span>"·"</span>
                <span><code class="text-ink/80">"ai_query_share"</code> " = " {format_pct(ai_query_share, 0)} " sourced via Tavily"</span>
                <a href=source target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-0.5 underline decoration-line underline-offset-2 hover:text-ink">
                    "[link]" <Icon name="external-link" class="w-2.5 h-2.5" />
                </a>
                <span>"·"</span>
                <span>{real_volume} " of " {total_prompts} " prompts has sourced volume; the other " {fallback} " use a sample-extrapolation method."</span>
            </div>
        </div>
    }
}

#[component]
fn PaidMedia(media: Vec<Media>, states: RwSignal<StateMap>, username: RwSignal<String>) -> impl IntoView {
    let count = media.len();
    let cards = media
        .into_iter()
        .enumerate()
        .map(|(i, m)| view! { <MediaCard media=m index=i states=states username=username /> })
        .collect_view();
    view! {
        <div class="enter mb-8" style="--d:0.65s">
            <div class="flex items-end justify-between flex-wrap gap-4 mb-5">
                <div>
                    <h2 class="text-[22px] font-semibold tracking-[-0.02em]">"Paid media outreach"</h2>
                    <p class="text-muted text-[15px] mt-1">"Each card shows the projected revenue range for placement on that partner — request a quote to confirm the spend."</p>
                </div>
            </div>
            <div class="grid md:grid-cols-4 gap-5">
                {cards}
                <SeeMoreCard index=count />
            </div>
        </div>
    }
}

#[component]
fn SeeMoreCard(index: usize) -> impl IntoView {
    let _ = index;
    view! {
        <button type="button" class="enter print-card group rounded-2xl bg-white/40 border border-dashed border-line p-6 flex flex-col items-center justify-center text-center min-h-[360px] hover:bg-white hover:border-ink/30 transition-colors no-print">
            <div class="w-11 h-11 rounded-xl bg-canvas border border-line flex items-center justify-center mb-4 group-hover:border-ink/30 transition-colors">
                <Icon name="plus" class="w-5 h-5 text-muted group-hover:text-ink transition-colors" />
            </div>
            <div class="text-[15px] font-semibold tracking-tight">"See more"</div>
            <p class="text-[12px] text-muted mt-1.5 max-w-[16ch] leading-snug">"More partner placements available in your full plan"</p>
            <span class="mt-4 inline-flex items-center gap-1 text-[12px] text-ink/70 group-hover:text-ink transition-colors">
                "Browse all" <Icon name="arrow-right" class="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </span>
        </button>
    }
}

#[component]
fn MediaCard(media: Media, index: usize, states: RwSignal<StateMap>, username: RwSignal<String>) -> impl IntoView {
    let id = media.id.clone();
    let state_of = {
        let id = id.clone();
        move || states.with(|m| m.get(&id).copied().unwrap_or(CardState::Estimate))
    };
    let set_card = move |next: CardState| {
        let id = id.clone();
        states.update(move |m| {
            m.insert(id, next);
        });
    };

    let id_status = media.id.clone();
    let status_label = {
        let state_of = state_of.clone();
        move || match state_of() {
            CardState::Accepted => "Accepted",
            CardState::Received => "Offer in",
            CardState::Sending => "Awaiting reply",
            CardState::Estimate => "Forecast",
        }
    };
    let highlight = {
        let state_of = state_of.clone();
        move || matches!(state_of(), CardState::Accepted | CardState::Received)
    };

    let m_send = media.clone();
    let on_send = {
        let set_card = set_card.clone();
        move |_| {
            send_mailto(&m_send, &username.get_untracked());
            set_card(CardState::Sending);
        }
    };
    let on_reset = {
        let set_card = set_card.clone();
        move |_| set_card(CardState::Estimate)
    };
    let on_reset2 = on_reset.clone();
    let id_accept = media.id.clone();
    let on_accept = move |_| {
        states.update(|m| {
            if m.get(&id_accept).copied() == Some(CardState::Received) {
                m.insert(id_accept.clone(), CardState::Accepted);
            }
        })
    };

    let card_class = {
        let highlight = highlight.clone();
        move || {
            let base = "print-card group rounded-2xl bg-white border p-6 flex flex-col transition-colors";
            if highlight() {
                format!("{base} border-ink/40 shadow-[0_2px_24px_-12px_rgba(0,0,0,0.18)]")
            } else {
                format!("{base} border-line hover:border-ink/30")
            }
        }
    };
    let badge_class = {
        let highlight = highlight.clone();
        move || {
            let base = "text-[11px] px-2 py-0.5 rounded-full border whitespace-nowrap transition-colors";
            if highlight() {
                format!("{base} border-ink/20 bg-ink/5 text-ink")
            } else {
                format!("{base} border-line bg-canvas text-muted")
            }
        }
    };

    let icon = media.icon;
    let title = media.title.clone();
    let domain = media.domain.clone();
    let audience = media.audience.clone();
    let cost = media.cost.clone();
    let gain_range = media.gain_range.clone();
    let gain_delta = media.gain_delta_range.clone();
    let _ = id_status;

    let state_for_btn = state_of.clone();

    view! {
        <div class=card_class>
            <div class="flex items-start justify-between mb-5">
                <div class="w-11 h-11 rounded-xl bg-canvas flex items-center justify-center">
                    <Icon name=icon class="w-5 h-5" />
                </div>
                <span class=badge_class>{status_label}</span>
            </div>
            <div class="text-[12px] text-muted mb-1">"#" {index + 1} " Paid media"</div>
            <h3 class="text-[20px] font-semibold tracking-tight leading-tight">{title}</h3>
            <div class="text-[13px] text-muted mt-0.5 truncate">{domain}</div>
            <div class="text-[12px] text-muted mt-2 leading-snug">{audience}</div>
            <div class="mt-5 space-y-2.5">
                <FigureRow label="Estimated cost".to_string() value=cost sub="/ quarter".to_string() delta=None accent=false />
                <FigureRow label="Projected revenue gain".to_string() value=gain_range sub="/ year".to_string() delta=Some(gain_delta) accent=true />
            </div>
            <div class="mt-6 pt-5 border-t border-line no-print">
                {move || match state_for_btn() {
                    CardState::Estimate => view! {
                        <button on:click=on_send.clone() class="w-full h-11 rounded-xl bg-ink text-white text-[14px] font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition">
                            <Icon name="mail" class="w-4 h-4" /> "Request offer"
                        </button>
                    }.into_view(),
                    CardState::Sending => view! {
                        <div class="w-full h-11 rounded-xl bg-canvas border border-line text-[13px] text-muted flex items-center justify-center gap-2">
                            <Icon name="loader-2" class="w-4 h-4 animate-spin" /> "Request sent · Waiting for response"
                        </div>
                    }.into_view(),
                    CardState::Received => view! {
                        <div class="flex flex-col gap-2">
                            <div class="flex items-center justify-between gap-2">
                                <span class="inline-flex items-center gap-1.5 text-[13px] text-ink">
                                    <Icon name="mail-check" class="w-4 h-4 text-gain" /> "Offer received"
                                </span>
                                <button on:click=on_reset.clone() class="inline-flex items-center gap-1 text-[12px] text-muted hover:text-ink transition" title="Request again">
                                    <Icon name="rotate-ccw" class="w-3 h-3" /> "request again"
                                </button>
                            </div>
                            <button on:click=on_accept.clone() class="w-full h-10 rounded-xl bg-gain text-white text-[13px] font-medium flex items-center justify-center gap-2 hover:bg-gain/90 transition">
                                <Icon name="check-circle-2" class="w-4 h-4" /> "Accept offer"
                            </button>
                        </div>
                    }.into_view(),
                    CardState::Accepted => view! {
                        <div class="flex flex-col gap-2">
                            <div class="w-full h-10 rounded-xl bg-gain/10 border border-gain/30 text-gain text-[13px] font-medium flex items-center justify-center gap-2">
                                <Icon name="check-circle-2" class="w-4 h-4" /> "Offer accepted"
                            </div>
                            <button on:click=on_reset2.clone() class="inline-flex items-center justify-center gap-1 text-[12px] text-muted hover:text-ink transition" title="Reset">
                                <Icon name="rotate-ccw" class="w-3 h-3" /> "start over"
                            </button>
                        </div>
                    }.into_view(),
                }}
            </div>
        </div>
    }
}

#[component]
fn FigureRow(
    label: String,
    value: String,
    sub: String,
    delta: Option<String>,
    accent: bool,
) -> impl IntoView {
    let val_class = if accent { "text-gain" } else { "" };
    view! {
        <div class="rounded-xl bg-canvas border border-line px-3.5 py-3">
            <div class="flex items-baseline justify-between gap-2">
                <div class="text-[11px] uppercase tracking-wider text-muted">{label}</div>
                <span class="text-[11px] text-muted whitespace-nowrap">{sub}</span>
            </div>
            <div class=format!("mt-1 text-[16px] font-semibold tracking-tight leading-tight tabular-nums {val_class}")>{value}</div>
            {delta.map(|d| view! { <div class="mt-0.5 text-[11px] text-gain font-medium tabular-nums">{d}</div> })}
        </div>
    }
}

#[component]
fn CTA() -> impl IntoView {
    view! {
        <div class="enter flex flex-col sm:flex-row gap-3 justify-center no-print" style="--d:0.8s">
            <button on:click=move |_| { let _ = web_sys::window().map(|w| w.print()); }
                class="px-5 h-12 rounded-xl bg-white border border-line text-[15px] font-medium hover:bg-canvas transition flex items-center justify-center gap-2">
                <Icon name="download" class="w-4 h-4" /> "Export report"
            </button>
            <a href="/content-plan" class="px-5 h-12 rounded-xl bg-white border border-line text-[15px] font-medium hover:bg-canvas transition flex items-center justify-center gap-2 group">
                <Icon name="calendar-range" class="w-4 h-4" /> "Create content plan"
                <Icon name="arrow-right" class="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </a>
            <A href="/home" class="px-6 h-12 rounded-xl bg-ink text-white text-[15px] font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition group">
                "Start new analysis"
                <Icon name="arrow-right" class="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </A>
        </div>
    }
}

// ======================= Login (/) =======================

#[component]
fn LoginPage() -> impl IntoView {
    let username = create_rw_signal(String::new());
    let password = create_rw_signal(String::new());
    let submitting = create_rw_signal(false);
    let navigate = use_navigate();

    let on_submit = move |ev: leptos::ev::SubmitEvent| {
        ev.prevent_default();
        let trimmed = username.get().trim().to_string();
        if trimmed.is_empty() {
            return;
        }
        submitting.set(true);
        session_set(USER_KEY, &trimmed);
        navigate("/home", Default::default());
    };
    let disabled = move || username.get().trim().is_empty() || submitting.get();

    view! {
        <main class="min-h-screen flex flex-col items-center justify-center px-6 relative">
            <div class="fixed inset-x-0 bottom-0 h-72 dot-grid opacity-40 pointer-events-none -z-10"></div>
            <div class="absolute top-6 left-6"><BrandMark /></div>
            <div class="enter w-full max-w-sm">
                <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-line bg-white text-[13px] mb-7">
                    <Icon name="sparkles" class="w-3.5 h-3.5" /> "Profit Analysis"
                </div>
                <h1 class="text-[clamp(2rem,5vw,3rem)] font-semibold tracking-[-0.035em] leading-[1.05] mb-2">"Sign in"</h1>
                <p class="text-[15px] text-muted mb-8 leading-relaxed">"Use any username and password — the demo accepts everything."</p>
                <form on:submit=on_submit class="space-y-3">
                    <LoginField id="username" label="Username" icon="user" value=username input_type="text" placeholder="e.g. attio" />
                    <LoginField id="password" label="Password" icon="lock" value=password input_type="password" placeholder="anything" />
                    <button
                        type="submit"
                        disabled=disabled
                        class="mt-3 w-full h-12 rounded-xl bg-ink text-white text-[15px] font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition disabled:opacity-40 disabled:cursor-not-allowed group"
                    >
                        "Sign in"
                        <Icon name="arrow-right" class="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                    </button>
                </form>
            </div>
        </main>
    }
}

#[component]
fn LoginField(
    id: &'static str,
    label: &'static str,
    icon: &'static str,
    value: RwSignal<String>,
    input_type: &'static str,
    placeholder: &'static str,
) -> impl IntoView {
    view! {
        <label for=id class="block">
            <span class="text-[13px] text-muted">{label}</span>
            <div class="mt-1.5 relative">
                <span class="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
                    <Icon name=icon class="w-4 h-4 text-muted" />
                </span>
                <input
                    id=id
                    type=input_type
                    prop:value=move || value.get()
                    on:input=move |ev| value.set(event_target_value(&ev))
                    placeholder=placeholder
                    class="w-full h-12 pl-10 pr-3.5 rounded-xl bg-white border border-line text-[15px] focus:outline-none focus:border-ink/40 transition"
                />
            </div>
        </label>
    }
}

// ======================= Home (/home) =======================

#[derive(Clone, Copy, PartialEq, Eq)]
enum RateMode {
    Standard,
    Manual,
    Crm,
}

const STANDARD_VISIT_TO_LEAD: f64 = 2.5;
const STANDARD_LEAD_TO_CUSTOMER: f64 = 15.0;

#[component]
fn Navbar() -> impl IntoView {
    view! {
        <header class="w-full border-b border-line/60 bg-canvas/80 backdrop-blur-sm sticky top-0 z-40">
            <div class="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                <BrandMark />
                <nav class="hidden md:flex items-center gap-8 text-[14px] text-ink/80">
                    <a class="hover:text-ink" href="#">"Pricing"</a>
                    <a class="hover:text-ink" href="#">"Resources"</a>
                    <a class="hover:text-ink" href="#">"Partnerships"</a>
                    <a class="hover:text-ink" href="#">"Careers"</a>
                </nav>
                <div class="w-px"></div>
            </div>
        </header>
    }
}

#[component]
fn HomePage() -> impl IntoView {
    let mode = create_rw_signal(RateMode::Standard);
    let visit_to_lead = create_rw_signal(String::new());
    let lead_to_customer = create_rw_signal(String::new());
    let arpu = create_rw_signal(String::new());
    let has_analysis = create_rw_signal(false);
    let shake = create_rw_signal(false);

    create_effect(move |prev: Option<()>| {
        if prev.is_none() {
            has_analysis.set(local_get(ANALYSIS_FLAG).as_deref() == Some("1"));
        }
    });

    // Persist conversion context (mirrors saveContext in lib/paidMedia.ts).
    create_effect(move |_| {
        let m = mode.get();
        let v2l = if m == RateMode::Manual {
            visit_to_lead.get().parse::<f64>().ok().filter(|n| n.is_finite())
        } else {
            Some(STANDARD_VISIT_TO_LEAD)
        }
        .unwrap_or(STANDARD_VISIT_TO_LEAD);
        let l2c = if m == RateMode::Manual {
            lead_to_customer.get().parse::<f64>().ok().filter(|n| n.is_finite())
        } else {
            Some(STANDARD_LEAD_TO_CUSTOMER)
        }
        .unwrap_or(STANDARD_LEAD_TO_CUSTOMER);
        let arpu_num = arpu.get().parse::<f64>().ok().filter(|n| n.is_finite() && *n > 0.0);
        let ctx = match arpu_num {
            Some(a) => serde_json::json!({"visitToLead": v2l, "leadToCustomer": l2c, "avgRevenuePerCustomer": a}),
            None => serde_json::json!({"visitToLead": v2l, "leadToCustomer": l2c}),
        };
        local_set(CONTEXT_KEY, &ctx.to_string());
    });

    let trigger_shake = move |_| {
        shake.set(true);
        set_timeout(move || shake.set(false), std::time::Duration::from_millis(500));
    };

    view! {
        <main class="min-h-screen flex flex-col">
            <Navbar />
            <div class="fixed inset-x-0 bottom-0 h-72 dot-grid opacity-40 pointer-events-none -z-10"></div>
            <section class="relative max-w-7xl mx-auto w-full px-6 pt-20 pb-24">
                <div class="enter inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-line bg-white text-[13px] mb-8">
                    <Icon name="sparkles" class="w-3.5 h-3.5" /> "Profit Analysis"
                </div>
                <div class="grid lg:grid-cols-12 gap-10">
                    <div class="enter lg:col-span-7" style="--d:0.05s">
                        <h1 class="text-[clamp(2.75rem,7.5vw,5.75rem)] font-semibold tracking-[-0.045em] leading-[1.0]">
                            "Your untapped" <br /> "revenue" <br /> <span class="text-muted">"potential."</span>
                        </h1>
                    </div>
                    <div class="enter lg:col-span-5 flex flex-col justify-end" style="--d:0.15s">
                        <p class="text-[18px] text-muted leading-relaxed">
                            "ChatGPT, Perplexity, Claude, and Gemini already shape a third of every B2B shortlist. Peec AI surfaces the prompts your buyers actually ask, the competitors winning those answers, and the pipeline you unlock by showing up first."
                        </p>
                        <div class="mt-8 flex flex-wrap gap-2">
                            <FeaturePill icon="eye" label="Visibility" />
                            <FeaturePill icon="target" label="Position" />
                            <FeaturePill icon="smile" label="Sentiment" />
                        </div>
                    </div>
                </div>

                <div class="enter mt-16 rounded-2xl bg-white border border-line p-7" style="--d:0.25s">
                    <div class="flex items-start justify-between flex-wrap gap-4 mb-5">
                        <div>
                            <h2 class="text-[18px] font-semibold tracking-tight">"Conversion rates"</h2>
                            <p class="text-[14px] text-muted mt-1">"So we can compute realistic levers — pick how we capture your conversion data."</p>
                        </div>
                        <span class="inline-flex items-center gap-1.5 text-[12px] text-muted">
                            <Icon name="info" class="w-3.5 h-3.5" /> "Required"
                        </span>
                    </div>
                    <div class="grid sm:grid-cols-3 gap-2 mb-6">
                        <ModeTab mode=mode this=RateMode::Standard icon="sliders" label="Defaults" hint="Industry median" />
                        <ModeTab mode=mode this=RateMode::Manual icon="database" label="Enter manually" hint="Your own values" />
                        <ModeTab mode=mode this=RateMode::Crm icon="plug" label="Connect CRM" hint="Coming soon" />
                    </div>
                    {move || match mode.get() {
                        RateMode::Standard => view! {
                            <div class="grid sm:grid-cols-2 gap-3">
                                <ReadOnlyField label="Visit-to-lead rate" value=format!("{STANDARD_VISIT_TO_LEAD}%") sub="B2B SaaS industry median" />
                                <ReadOnlyField label="Lead-to-customer rate" value=format!("{STANDARD_LEAD_TO_CUSTOMER}%") sub="B2B SaaS industry median" />
                            </div>
                        }.into_view(),
                        RateMode::Manual => view! {
                            <div class="grid sm:grid-cols-2 gap-3">
                                <RateInput label="Visit-to-lead rate" placeholder=format!("{STANDARD_VISIT_TO_LEAD}") value=visit_to_lead />
                                <RateInput label="Lead-to-customer rate" placeholder=format!("{STANDARD_LEAD_TO_CUSTOMER}") value=lead_to_customer />
                            </div>
                        }.into_view(),
                        RateMode::Crm => view! {
                            <div class="rounded-xl border border-dashed border-line bg-canvas/50 p-5">
                                <div class="flex items-start gap-3">
                                    <div class="w-9 h-9 rounded-lg bg-white border border-line flex items-center justify-center flex-shrink-0">
                                        <Icon name="plug" class="w-4 h-4 text-muted" />
                                    </div>
                                    <div class="flex-1">
                                        <div class="text-[14px] font-medium">"CRM integration not available yet"</div>
                                        <p class="text-[13px] text-muted mt-1 leading-relaxed">"HubSpot, Salesforce, and Pipedrive are coming soon. Until then, use defaults or enter values manually."</p>
                                        <div class="mt-3 flex flex-wrap gap-2">
                                            {["HubSpot", "Salesforce", "Pipedrive"].into_iter().map(|c| view! {
                                                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-line text-[12px] text-muted">
                                                    {c} <span class="text-[10px] text-muted/70">"soon"</span>
                                                </span>
                                            }).collect_view()}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        }.into_view(),
                    }}
                    <div class="mt-5 pt-5 border-t border-line">
                        <div class="flex items-end justify-between gap-4 flex-wrap">
                            <div class="min-w-0">
                                <label for="arpu" class="text-[13px] text-muted block">
                                    "Average revenue per customer"
                                    <span class="ml-1.5 text-[11px] uppercase tracking-wider text-muted/70">"optional"</span>
                                </label>
                            </div>
                            <div class="relative w-full sm:w-56">
                                <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-[14px] text-muted pointer-events-none">"€"</span>
                                <input
                                    id="arpu" type="number" inputmode="decimal" min="0" step="1" placeholder="value in EUR"
                                    prop:value=move || arpu.get()
                                    on:input=move |ev| arpu.set(event_target_value(&ev))
                                    class="w-full h-11 pl-7 pr-3.5 rounded-xl bg-white border border-line text-[15px] focus:outline-none focus:border-ink/40 transition"
                                />
                            </div>
                        </div>
                    </div>
                </div>

                <div class="enter mt-10 flex flex-col sm:flex-row gap-3 relative z-10" style="--d:0.3s">
                    {move || if has_analysis.get() {
                        view! {
                            <A href="/report" class="group px-5 h-12 rounded-xl bg-white border border-line text-[15px] font-medium flex items-center gap-2 hover:border-ink/40 transition relative">
                                <Icon name="history" class="w-4 h-4 text-muted group-hover:text-ink transition-colors" />
                                "Resume analysis"
                                <Icon name="arrow-right" class="w-4 h-4 text-muted group-hover:text-ink group-hover:translate-x-0.5 transition" />
                            </A>
                        }.into_view()
                    } else {
                        view! {
                            <button
                                on:click=trigger_shake
                                class=move || format!("group px-5 h-12 rounded-xl bg-white border border-line text-[15px] font-medium flex items-center gap-2 cursor-not-allowed hover:border-line/80 transition relative {}", if shake.get() { "shake" } else { "" })
                            >
                                <Icon name="x-circle" class="w-4 h-4 text-muted group-hover:text-accent transition-colors" />
                                "Resume analysis"
                                <span class="absolute -top-2 -right-2 px-1.5 py-0.5 rounded-full bg-canvas border border-line text-[10px] text-muted opacity-0 group-hover:opacity-100 transition">"none yet"</span>
                            </button>
                        }.into_view()
                    }}
                    <A href="/analyse" class="px-6 h-12 rounded-xl bg-ink text-white text-[15px] font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition group">
                        <Icon name="sparkles" class="w-4 h-4" /> "Start analysis"
                        <Icon name="arrow-right" class="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                    </A>
                </div>

                <div class="enter mt-24 grid md:grid-cols-3 gap-4" style="--d:0.5s">
                    <StepCard n="01" title="Plug in" desc="Drop in your revenue model and the prompts your buyers ask. No integration, no setup call — minutes to first signal." />
                    <StepCard n="02" title="Benchmark" desc="We score your visibility against every category leader across ChatGPT, Perplexity, Claude, and Gemini — prompt by prompt." />
                    <StepCard n="03" title="Capture" desc="Get a euro-denominated forecast of the pipeline at stake — with the exact placements and content that win the answer." />
                </div>
            </section>
        </main>
    }
}

#[component]
fn ModeTab(
    mode: RwSignal<RateMode>,
    this: RateMode,
    icon: &'static str,
    label: &'static str,
    hint: &'static str,
) -> impl IntoView {
    let active = move || mode.get() == this;
    let btn_class = move || {
        if active() {
            "text-left px-4 py-3 rounded-xl border transition-all border-l-[3px] border-l-accent border-y-line border-r-line bg-white shadow-[0_2px_24px_-12px_rgba(0,0,0,0.15)]".to_string()
        } else {
            "text-left px-4 py-3 rounded-xl border transition-all border-line bg-white hover:border-ink/30".to_string()
        }
    };
    let icon_class = move || {
        if active() {
            "w-7 h-7 rounded-lg flex items-center justify-center bg-ink text-white".to_string()
        } else {
            "w-7 h-7 rounded-lg flex items-center justify-center bg-canvas text-muted".to_string()
        }
    };
    view! {
        <button type="button" on:click=move |_| mode.set(this) class=btn_class>
            <div class="flex items-center gap-2">
                <span class=icon_class><Icon name=icon class="w-4 h-4" /></span>
                <span class="text-[14px] font-medium">{label}</span>
            </div>
            <div class="text-[12px] text-muted mt-1.5 ml-9">{hint}</div>
        </button>
    }
}

#[component]
fn RateInput(label: &'static str, placeholder: String, value: RwSignal<String>) -> impl IntoView {
    view! {
        <label class="block">
            <span class="text-[13px] text-muted">{label}</span>
            <div class="mt-1.5 relative">
                <input
                    type="number" inputmode="decimal" min="0" max="100" step="0.1" placeholder=placeholder
                    prop:value=move || value.get()
                    on:input=move |ev| value.set(event_target_value(&ev))
                    class="w-full h-11 px-3.5 pr-9 rounded-xl bg-white border border-line text-[15px] focus:outline-none focus:border-ink/40 transition"
                />
                <span class="absolute right-3.5 top-1/2 -translate-y-1/2 text-[14px] text-muted pointer-events-none">"%"</span>
            </div>
        </label>
    }
}

#[component]
fn ReadOnlyField(label: &'static str, value: String, sub: &'static str) -> impl IntoView {
    view! {
        <div class="rounded-xl bg-canvas border border-line px-4 py-3.5">
            <div class="text-[13px] text-muted">{label}</div>
            <div class="mt-1 flex items-baseline gap-2">
                <span class="text-[20px] font-semibold tracking-tight">{value}</span>
                <span class="text-[12px] text-muted">{sub}</span>
            </div>
        </div>
    }
}

#[component]
fn FeaturePill(icon: &'static str, label: &'static str) -> impl IntoView {
    view! {
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-line text-ink text-[14px]">
            <Icon name=icon class="w-3.5 h-3.5" /> {label}
        </span>
    }
}

#[component]
fn StepCard(n: &'static str, title: &'static str, desc: &'static str) -> impl IntoView {
    view! {
        <div class="rounded-2xl bg-white border border-line p-6">
            <div class="text-[12px] font-medium text-muted tracking-wider">{n}</div>
            <h3 class="mt-2 text-[18px] font-semibold tracking-tight">{title}</h3>
            <p class="mt-2 text-[14px] text-muted leading-relaxed">{desc}</p>
        </div>
    }
}

// ======================= Analyse (/analyse) — computing animation =======================

struct AnalyseNode {
    title: &'static str,
    desc: &'static str,
    icon: &'static str,
}

const NODES: [AnalyseNode; 3] = [
    AnalyseNode {
        title: "Data capture",
        desc: "We aggregate the business data that matters — revenue, costs, market position.",
        icon: "database",
    },
    AnalyseNode {
        title: "Market analysis",
        desc: "Benchmarked against competitors and scanned for optimization potential.",
        icon: "trending-up",
    },
    AnalyseNode {
        title: "Untapped potential",
        desc: "We model the missed revenue across every relevant prompt.",
        icon: "calculator",
    },
];

const THINKING: [[&str; 4]; 3] = [
    [
        "Processing analysis…",
        "Ingesting business data…",
        "Filtering historical revenue…",
        "Classifying cost structure…",
    ],
    [
        "Identifying competitors…",
        "Pulling market pricing…",
        "Mapping positioning…",
        "Computing visibility score…",
    ],
    [
        "Quantifying margin gaps…",
        "Calculating missed revenue…",
        "Scoring optimization levers…",
        "Finalizing recommendations…",
    ],
];

const STEP_DURATION_MS: u64 = 900;

#[component]
fn AnalysePage() -> impl IntoView {
    let active = create_rw_signal(0usize);
    let idx = create_rw_signal(0usize);
    let done = create_rw_signal::<Vec<usize>>(Vec::new());
    let navigate = use_navigate();

    // Fresh analysis: drop any saved paid-media card state.
    let _ = web_sys::window()
        .and_then(|w| w.local_storage().ok().flatten())
        .map(|s| s.remove_item(STORAGE_KEY));

    // Drive the steps with a single interval; clear it + navigate when done.
    let handle = create_rw_signal::<Option<leptos::leptos_dom::helpers::IntervalHandle>>(None);
    let nav = navigate.clone();
    let h = set_interval_with_handle(
        move || {
            let a = active.get_untracked();
            let i = idx.get_untracked();
            let steps = THINKING[a].len();
            if i < steps - 1 {
                idx.set(i + 1);
            } else {
                done.update(|d| {
                    if !d.contains(&a) {
                        d.push(a);
                    }
                });
                if a < NODES.len() - 1 {
                    active.set(a + 1);
                    idx.set(0);
                } else {
                    if let Some(hh) = handle.get_untracked() {
                        hh.clear();
                    }
                    let nav = nav.clone();
                    set_timeout(
                        move || nav("/report", Default::default()),
                        std::time::Duration::from_millis(1200),
                    );
                }
            }
        },
        std::time::Duration::from_millis(STEP_DURATION_MS),
    )
    .ok();
    handle.set_untracked(h);

    let state_of = move |i: usize| -> &'static str {
        if done.get().contains(&i) {
            "done"
        } else if i == active.get() {
            "active"
        } else {
            "pending"
        }
    };

    let connector_pct = move || match active.get() {
        0 => 15,
        1 => 55,
        _ => 100,
    };

    let progress = move || {
        let a = active.get();
        let steps = THINKING[a].len() as f64;
        ((((done.get().len() as f64 + (idx.get() as f64 + 1.0) / steps) / NODES.len() as f64) * 100.0).round() as i64).min(100)
    };

    let nodes_view = (0..NODES.len())
        .map(|i| {
            let n = &NODES[i];
            let state_of = state_of;
            let card_class = move || {
                // Keep the card background fully opaque (relative z-10 over the
                // connector) so the line never bleeds through; dimming for
                // done/pending lives on an inner wrapper instead of the whole card.
                let base = "relative z-10 p-5 rounded-2xl bg-white border transition-all duration-500";
                match state_of(i) {
                    "active" => format!("{base} border-l-[3px] border-l-accent border-y-line border-r-line shadow-[0_2px_24px_-12px_rgba(0,0,0,0.15)]"),
                    _ => format!("{base} border-line"),
                }
            };
            let inner_class = move || match state_of(i) {
                "done" => "flex gap-4 opacity-70",
                "active" => "flex gap-4",
                _ => "flex gap-4 opacity-50",
            };
            let icon_box = move || match state_of(i) {
                "done" => "flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center transition-colors bg-ink text-white".to_string(),
                "active" => "flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center transition-colors bg-ink/5 text-ink".to_string(),
                _ => "flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center transition-colors bg-canvas text-muted".to_string(),
            };
            let status = move || match state_of(i) {
                "done" => "Done",
                "active" => "Running…",
                _ => "Pending",
            };
            view! {
                <div class=card_class>
                    <div class=inner_class>
                        <div class=icon_box>
                            {move || match state_of(i) {
                                "done" => view! { <Icon name="check" class="w-5 h-5" /> }.into_view(),
                                "active" => view! { <div class="animate-spin"><Icon name=n.icon class="w-5 h-5" /></div> }.into_view(),
                                _ => view! { <Icon name=n.icon class="w-5 h-5" /> }.into_view(),
                            }}
                        </div>
                        <div class="flex-1">
                            <div class="flex items-center justify-between">
                                <h3 class="font-semibold text-[16px] tracking-tight">{n.title}</h3>
                                <span class="text-[12px] text-muted">{status}</span>
                            </div>
                            <p class="text-[14px] text-muted mt-1 leading-relaxed">{n.desc}</p>
                        </div>
                    </div>
                </div>
            }
        })
        .collect_view();

    let thinking_view = move || {
        let a = active.get();
        let upto = idx.get();
        (0..=upto)
            .map(|i| {
                let step = THINKING[a][i];
                let is_current = i == upto;
                view! {
                    <div class="flex items-start gap-3 text-[14px]">
                        {if is_current {
                            view! { <div class="flex-shrink-0"><Icon name="loader-2" class="w-4 h-4 mt-0.5 text-ink animate-spin" /></div> }.into_view()
                        } else {
                            view! { <div class="flex-shrink-0"><Icon name="check" class="w-4 h-4 mt-0.5 text-ink/60" /></div> }.into_view()
                        }}
                        <span class=if is_current { "text-ink" } else { "text-muted" }>{step}</span>
                    </div>
                }
            })
            .collect_view()
    };

    view! {
        <main class="min-h-screen flex flex-col">
            <BrandMark class="fixed top-5 left-6 z-50".to_string() />
            <section class="enter flex-1 max-w-7xl mx-auto w-full px-6 py-16">
                <div class="enter text-center mb-16">
                    <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-line bg-white text-[13px] mb-5">
                        <Icon name="loader-2" class="w-3.5 h-3.5 animate-spin" /> "Analysis running"
                    </div>
                    <h1 class="text-[clamp(2rem,5vw,3.5rem)] font-semibold tracking-[-0.03em] leading-[1.05]">
                        "Mapping your " <span class="text-muted">"AI-search footprint"</span>
                    </h1>
                    <p class="mt-4 text-[16px] text-muted max-w-xl mx-auto">"Three passes. One outcome: surface the pipeline you're missing in AI search."</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16">
                    // LEFT — node system
                    <div>
                        <div class="relative">
                            <div class="absolute left-[27px] top-12 w-0.5 bg-line" style="height:calc(100% - 108px)"></div>
                            <div class="absolute left-[27px] top-12 w-0.5 bg-ink grow-h" style=move || format!("height:calc((100% - 108px) * {} / 100)", connector_pct())></div>
                            <div class="space-y-6 relative z-10">{nodes_view}</div>
                        </div>
                    </div>
                    // RIGHT — live thinking
                    <div class="lg:sticky lg:top-24 h-fit">
                        <div class="rounded-2xl bg-white border border-line p-7">
                            <div class="flex items-center justify-between mb-5">
                                <div class="flex items-center gap-2">
                                    <span class="w-2 h-2 rounded-full bg-accent animate-pulse"></span>
                                    <span class="text-[13px] font-medium uppercase tracking-wider text-muted">"Live thinking"</span>
                                </div>
                                <span class="text-[12px] text-muted">"Step " {move || active.get() + 1} " / " {NODES.len()}</span>
                            </div>
                            <h2 class="text-[24px] font-semibold tracking-[-0.02em] leading-tight">{move || NODES[active.get()].title}</h2>
                            <div class="mt-6 space-y-2.5">{thinking_view}</div>
                            <div class="mt-7 pt-5 border-t border-line">
                                <div class="flex items-center justify-between text-[12px] text-muted">
                                    <span>"Progress"</span>
                                    <span>{progress} "%"</span>
                                </div>
                                <div class="mt-2 h-1 rounded-full bg-line overflow-hidden">
                                    <div class="h-full bg-ink grow-w" style=move || format!("width:{}%", progress())></div>
                                </div>
                            </div>
                        </div>
                        <div class="mt-4 text-center text-[12px] text-muted flex items-center justify-center gap-2">
                            <Icon name="arrow-right" class="w-3 h-3" /> "Report opens automatically"
                        </div>
                    </div>
                </div>
            </section>
        </main>
    }
}

// ---- small utilities ----

fn window_now() -> f64 {
    web_sys::window()
        .and_then(|w| w.performance())
        .map(|p| p.now())
        .unwrap_or(0.0)
}

fn comma_str(n: i64) -> String {
    data::format_euro(n as f64).trim_start_matches('€').to_string()
}

fn send_mailto(m: &Media, username: &str) {
    let subject = format!("Sponsorship inquiry — paid placement on {}", m.domain);
    let body = format!(
        "Dear {title} team,\n\n\
         My name is {user} and I am reaching out regarding a potential paid \
         placement on {domain}. As part of our AI-search visibility analysis \
         (conducted with Peec AI), {domain} was identified as a high-impact \
         channel for our brand.\n\n\
         For planning purposes, our internal model projects the following for a \
         quarterly placement:\n\n\
         \u{20}\u{20}• Indicative budget: {cost} per quarter\n\
         \u{20}\u{20}• Projected annual revenue contribution: {gain}\n\n\
         Could you please share your current rate card, available slot windows \
         for the upcoming quarter, and any audience or traffic data we can \
         incorporate into our planning?\n\n\
         Replies can be directed to {notify}.\n\n\
         Kind regards,\n{user}\n(analysis powered by Peec AI)",
        title = m.title,
        user = username,
        domain = m.domain,
        cost = m.cost,
        gain = m.gain_range,
        notify = NOTIFY_EMAIL,
    );
    let mailto = format!(
        "mailto:{to}?cc={cc}&subject={subj}&body={body}",
        to = m.partner_email,
        cc = encode_uri(NOTIFY_EMAIL),
        subj = encode_uri(&subject),
        body = encode_uri(&body),
    );
    if let Some(w) = web_sys::window() {
        let _ = w.open_with_url_and_target(&mailto, "_self");
    }
}

fn encode_uri(s: &str) -> String {
    js_sys_encode(s)
}

fn js_sys_encode(s: &str) -> String {
    // encodeURIComponent via web_sys is not directly exposed; do a minimal
    // percent-encode of the characters that matter for mailto bodies.
    let mut out = String::with_capacity(s.len() * 2);
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => out.push(b as char),
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}
