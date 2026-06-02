//! Data model + accessors — Rust port of frontend/lib/peec.ts.
//! The demo fixture (Data/Mock.json) is embedded and parsed client-side.

use serde::Deserialize;

const MOCK_JSON: &str = include_str!("../data/Mock.json");

#[derive(Debug, Clone, Deserialize)]
pub struct PeecRoot {
    pub company_name: String,
    #[serde(default)]
    pub executive_summary: Option<String>,
    #[serde(default)]
    pub acv: Option<Acv>,
    pub bracket: Bracket,
    pub prompt_revenues: Vec<PromptRevenue>,
    #[allow(dead_code)]
    pub pessimistic: ReportSlice,
    pub optimistic: ReportSlice,
    pub prep: PrepData,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Acv {
    #[allow(dead_code)]
    pub value_eur: f64,
    #[serde(default)]
    pub source: Option<String>,
    #[allow(dead_code)]
    #[serde(default)]
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Bracket {
    pub pessimistic_visibility_increase_pp: f64,
    pub optimistic_visibility_increase_pp: f64,
    pub pessimistic_total_revenue_lift_eur: f64,
    pub optimistic_total_revenue_lift_eur: f64,
    pub pessimistic_customer_equivalents: f64,
    pub optimistic_customer_equivalents: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PromptRevenueScenario {
    pub target_visibility: f64,
    pub target_position: f64,
    pub target_annual_revenue_eur: f64,
    pub revenue_lift_eur: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PromptRevenue {
    pub prompt_id: String,
    pub prompt_message: String,
    pub volume_source: String,
    pub search_volume: i64,
    #[allow(dead_code)]
    #[serde(default)]
    pub volume_source_urls: Vec<String>,
    pub your_visibility: f64,
    #[serde(default)]
    pub your_position: f64,
    pub top_competitor_visibility: f64,
    pub top_competitor_name: String,
    pub annual_mentions: f64,
    pub current_annual_revenue_eur: f64,
    pub pessimistic: PromptRevenueScenario,
    pub optimistic: PromptRevenueScenario,
    #[serde(default)]
    pub ai_summary: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Competitor {
    pub competitor_name: String,
    pub prompts_won_against_you: i64,
    #[allow(dead_code)]
    pub competitor_avg_visibility: f64,
    #[allow(dead_code)]
    pub your_avg_visibility: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TopAction {
    pub prompt_id: String,
    #[allow(dead_code)]
    pub prompt_message: String,
    #[allow(dead_code)]
    pub revenue_lift_eur: f64,
    pub action_type: String,
    #[allow(dead_code)]
    #[serde(default)]
    pub rationale: String,
    #[serde(default)]
    pub evidence_signals: Vec<String>,
    #[serde(default)]
    pub suggested_targets: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MarketEstimate {
    pub ai_query_share: f64,
    #[serde(default)]
    pub sources: Vec<String>,
    #[allow(dead_code)]
    #[serde(default)]
    pub rationale: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ReportSlice {
    #[allow(dead_code)]
    pub total_revenue_lift_eur: f64,
    pub total_prompts: i64,
    pub untapped_prompt_count: i64,
    pub prompts_using_real_volume: i64,
    pub overall_your_visibility: f64,
    pub leader_name: String,
    pub leader_visibility: f64,
    pub visibility_gap_pp: f64,
    pub top3_lift_share_pct: f64,
    #[allow(dead_code)]
    pub customer_equivalents: f64,
    pub competitive_landscape: Vec<Competitor>,
    pub market_estimate: MarketEstimate,
    pub top_actions: Vec<TopAction>,
    #[allow(dead_code)]
    #[serde(default)]
    pub executive_summary: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PaidMediaPricing {
    pub low_usd: Option<i64>,
    pub high_usd: Option<i64>,
    #[allow(dead_code)]
    pub source: String,
    #[allow(dead_code)]
    pub notes: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PaidMediaOpportunity {
    pub domain: String,
    pub classification: String,
    pub classification_confidence: f64,
    pub pricing: PaidMediaPricing,
    #[allow(dead_code)]
    #[serde(default)]
    pub gap_urls: Vec<serde_json::Value>,
    pub contributing_chat_count: i64,
    #[allow(dead_code)]
    pub delta_chats_pessimistic: f64,
    #[allow(dead_code)]
    pub delta_chats_optimistic: f64,
    pub delta_visibility_pp_pessimistic: f64,
    pub delta_visibility_pp_optimistic: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PrepData {
    #[serde(default)]
    pub paid_media_opportunities: Vec<PaidMediaOpportunity>,
}

/// Flattened per-prompt detail (mirrors PromptDetail in peec.ts): optimistic
/// scenario fields hoisted + both scenario lifts + matched action.
#[derive(Debug, Clone)]
pub struct PromptDetail {
    pub prompt_id: String,
    pub prompt_message: String,
    pub volume_source: String,
    pub search_volume: i64,
    pub your_visibility: f64,
    pub your_position: f64,
    pub top_competitor_visibility: f64,
    pub top_competitor_name: String,
    pub annual_mentions: f64,
    pub current_annual_revenue_eur: f64,
    pub ai_summary: Option<String>,
    // from optimistic scenario:
    pub target_visibility: f64,
    pub target_position: f64,
    pub target_annual_revenue_eur: f64,
    pub revenue_lift_eur: f64,
    pub pessimistic_revenue_lift_eur: f64,
    pub optimistic_revenue_lift_eur: f64,
    pub action: Option<TopAction>,
}

pub fn get_report() -> PeecRoot {
    serde_json::from_str(MOCK_JSON).expect("Mock.json should parse")
}

// ---- helpers (ports of the formatters/accessors in peec.ts) ----

fn comma(n: i64) -> String {
    let neg = n < 0;
    let digits = n.abs().to_string();
    let bytes = digits.as_bytes();
    let mut out = String::new();
    let len = bytes.len();
    for (i, b) in bytes.iter().enumerate() {
        if i > 0 && (len - i) % 3 == 0 {
            out.push(',');
        }
        out.push(*b as char);
    }
    if neg {
        format!("-{out}")
    } else {
        out
    }
}

pub fn format_euro(n: f64) -> String {
    let rounded = n.round() as i64;
    format!("€{}", comma(rounded))
}

pub fn format_pct(ratio: f64, digits: usize) -> String {
    format!("{:.*}%", digits, ratio * 100.0)
}

pub fn format_usd_range(p: &PaidMediaPricing) -> String {
    match (p.low_usd, p.high_usd) {
        (None, None) => "RFQ".to_string(),
        (Some(lo), Some(hi)) => {
            if lo == hi {
                format!("${}", comma(lo))
            } else {
                format!("${} – ${}", comma(lo), comma(hi))
            }
        }
        (Some(lo), None) => format!("from ${}", comma(lo)),
        (None, Some(hi)) => format!("up to ${}", comma(hi)),
    }
}

pub fn hostname_of(url: &str) -> String {
    let after = if let Some(idx) = url.find("//") {
        &url[idx + 2..]
    } else {
        url
    };
    let host = after.split(['/', '?', '#']).next().unwrap_or(after);
    host.strip_prefix("www.").unwrap_or(host).to_string()
}

pub fn classification_label(c: &str) -> String {
    c.replace('_', " ")
        .to_lowercase()
        .split(' ')
        .map(|w| {
            let mut ch = w.chars();
            match ch.next() {
                Some(f) => f.to_uppercase().collect::<String>() + ch.as_str(),
                None => String::new(),
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

pub fn paid_media_opportunities(root: &PeecRoot, n: usize) -> Vec<PaidMediaOpportunity> {
    root.prep
        .paid_media_opportunities
        .iter()
        .take(n)
        .cloned()
        .collect()
}

pub fn competitors_ranked(slice: &ReportSlice) -> Vec<Competitor> {
    let mut v = slice.competitive_landscape.clone();
    v.sort_by(|a, b| b.prompts_won_against_you.cmp(&a.prompts_won_against_you));
    v
}

pub fn lowest_visibility_prompts(root: &PeecRoot, n: usize) -> Vec<PromptRevenue> {
    let mut v = root.prompt_revenues.clone();
    v.sort_by(|a, b| a.your_visibility.total_cmp(&b.your_visibility));
    v.into_iter().take(n).collect()
}

pub fn all_prompts_by_lift(root: &PeecRoot, slice: &ReportSlice) -> Vec<PromptDetail> {
    let mut out: Vec<PromptDetail> = root
        .prompt_revenues
        .iter()
        .map(|p| {
            let action = slice
                .top_actions
                .iter()
                .find(|a| a.prompt_id == p.prompt_id)
                .cloned();
            PromptDetail {
                prompt_id: p.prompt_id.clone(),
                prompt_message: p.prompt_message.clone(),
                volume_source: p.volume_source.clone(),
                search_volume: p.search_volume,
                your_visibility: p.your_visibility,
                your_position: p.your_position,
                top_competitor_visibility: p.top_competitor_visibility,
                top_competitor_name: p.top_competitor_name.clone(),
                annual_mentions: p.annual_mentions,
                current_annual_revenue_eur: p.current_annual_revenue_eur,
                ai_summary: p.ai_summary.clone(),
                target_visibility: p.optimistic.target_visibility,
                target_position: p.optimistic.target_position,
                target_annual_revenue_eur: p.optimistic.target_annual_revenue_eur,
                revenue_lift_eur: p.optimistic.revenue_lift_eur,
                pessimistic_revenue_lift_eur: p.pessimistic.revenue_lift_eur,
                optimistic_revenue_lift_eur: p.optimistic.revenue_lift_eur,
                action,
            }
        })
        .collect();
    out.sort_by(|a, b| b.revenue_lift_eur.total_cmp(&a.revenue_lift_eur));
    out
}
