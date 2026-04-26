"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Download,
  CalendarRange,
  EyeOff,
  Users,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Target,
  Mail,
  MailCheck,
  Loader2,
  Globe2,
  Briefcase,
  Cpu,
  RotateCcw,
  Plus,
  type LucideIcon,
} from "lucide-react";
import BrandMark from "@/components/BrandMark";
import {
  DEFAULT_PROJECT_ID,
  allPromptsByLift,
  cachedReport,
  competitorsRanked,
  formatEuro,
  formatPct,
  formatUsdRange,
  lowestVisibilityPrompts,
  paidMediaOpportunities,
  type Bracket,
  type PaidMediaOpportunity,
  type PeecRoot,
  type PromptDetail,
} from "@/lib/peec";
import {
  ANALYSIS_FLAG,
  NOTIFY_EMAIL,
  STORAGE_KEY,
  type CardState,
} from "@/lib/paidMedia";

type Media = {
  id: string;
  title: string;
  domain: string;
  audience: string;
  icon: LucideIcon;
  cost: string;
  gainRange: string;
  gainDeltaRange: string;
  gainLow: string;
  partnerEmail: string;
};

const CARD_ICONS: LucideIcon[] = [Globe2, Briefcase, Cpu];

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function classificationLabel(c: string): string {
  return c
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function buildMedia(
  o: PaidMediaOpportunity,
  i: number,
  bracket: Bracket,
): Media {
  const confidencePct = Math.round(o.classification_confidence * 100);
  const audience = `${classificationLabel(o.classification)} · ${confidencePct}% confidence · ${o.contributing_chat_count} contributing chats`;

  // Per-partner euro lift = partner share of total visibility lift × total
  // revenue lift, computed for both ends of the bracket.
  const pessShare =
    bracket.pessimistic_visibility_increase_pp > 0
      ? o.delta_visibility_pp_pessimistic /
        bracket.pessimistic_visibility_increase_pp
      : 0;
  const optShare =
    bracket.optimistic_visibility_increase_pp > 0
      ? o.delta_visibility_pp_optimistic /
        bracket.optimistic_visibility_increase_pp
      : 0;
  const pessLiftEur = pessShare * bracket.pessimistic_total_revenue_lift_eur;
  const optLiftEur = optShare * bracket.optimistic_total_revenue_lift_eur;

  return {
    id: o.domain,
    title: o.domain,
    domain: o.domain,
    audience,
    icon: CARD_ICONS[i % CARD_ICONS.length],
    cost: formatUsdRange(o.pricing),
    gainRange: `${formatEuro(pessLiftEur)} – ${formatEuro(optLiftEur)}`,
    gainDeltaRange: `${o.delta_visibility_pp_pessimistic.toFixed(2)}–${o.delta_visibility_pp_optimistic.toFixed(2)} pp visibility`,
    gainLow: formatEuro(pessLiftEur),
    partnerEmail: `partnerships@${o.domain}`,
  };
}

type CardData = { state: CardState };
type StateMap = Record<string, CardData>;

const buildInitialStateMap = (media: Media[]): StateMap =>
  media.reduce<StateMap>((acc, m) => {
    acc[m.id] = { state: "estimate" };
    return acc;
  }, {});

export default function ReportPage() {
  return (
    <Suspense fallback={null}>
      <ReportPageInner />
    </Suspense>
  );
}

function ReportPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project") ?? DEFAULT_PROJECT_ID;

  // The report page never fetches itself — /analyse is the only place
  // that talks to the backend, so the cool loading screen is the only
  // loading screen the user ever sees. If the cache is empty (direct
  // navigation, refresh after sessionStorage cleared), bounce back to
  // /analyse, which will fetch and redirect here when ready.
  const [root, setRoot] = useState<PeecRoot | null>(null);

  useEffect(() => {
    const cached = cachedReport(projectId);
    if (cached) {
      setRoot(cached);
      return;
    }
    const target =
      projectId === DEFAULT_PROJECT_ID
        ? "/analyse"
        : `/analyse?project=${encodeURIComponent(projectId)}`;
    router.replace(target);
  }, [projectId, router]);

  if (!root) return null;
  return <ReportView root={root} />;
}

function ReportView({ root }: { root: PeecRoot }) {
  const brand = root.company_name;
  const bracket = root.bracket;
  const scenario = root.optimistic;
  const executiveSummary = root.executive_summary ?? "";

  const media = useMemo(
    () => paidMediaOpportunities(root, 3).map((o, i) => buildMedia(o, i, bracket)),
    [root, bracket],
  );

  const [paidMediaStates, setPaidMediaStates] = useState<StateMap>(() =>
    buildInitialStateMap(media),
  );
  const [hydrated, setHydrated] = useState(false);
  const [username, setUsername] = useState<string>(brand);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const initial = buildInitialStateMap(media);
      if (raw) {
        const parsed = JSON.parse(raw) as Record<string, CardData>;
        const merged: StateMap = { ...initial, ...parsed };
        // On re-entry: any card the user sent a request for is now treated
        // as answered. Untouched cards keep their estimate state.
        for (const m of media) {
          if (merged[m.id]?.state === "sending") {
            merged[m.id] = { state: "received" };
          }
        }
        setPaidMediaStates(merged);
      } else {
        setPaidMediaStates(initial);
      }
      localStorage.setItem(ANALYSIS_FLAG, "1");
      const stored = sessionStorage.getItem("peec.user");
      if (stored && stored.trim()) setUsername(stored.trim());
    } catch {
      /* noop */
    }
    setHydrated(true);
  }, [media]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(paidMediaStates));
    } catch {
      /* noop */
    }
  }, [paidMediaStates, hydrated]);

  const setCard = (id: string, next: CardData) =>
    setPaidMediaStates((s) => ({ ...s, [id]: next }));

  const handleSend = (m: Media) => {
    const subject = `Sponsorship inquiry — paid placement on ${m.domain}`;
    const body =
      `Dear ${m.title} team,\n\n` +
      `My name is ${username} and I am reaching out regarding a potential paid ` +
      `placement on ${m.domain}. As part of our AI-search visibility analysis ` +
      `(conducted with Peec AI), ${m.domain} was identified as a high-impact ` +
      `channel for our brand.\n\n` +
      `For planning purposes, our internal model projects the following for a ` +
      `quarterly placement:\n\n` +
      `  • Indicative budget: ${m.cost} per quarter\n` +
      `  • Projected annual revenue contribution: ${m.gainRange}\n\n` +
      `Could you please share your current rate card, available slot windows ` +
      `for the upcoming quarter, and any audience or traffic data we can ` +
      `incorporate into our planning?\n\n` +
      `Replies can be directed to ${NOTIFY_EMAIL}.\n\n` +
      `Kind regards,\n` +
      `${username}\n` +
      `(analysis powered by Peec AI)`;

    const mailto =
      `mailto:${m.partnerEmail}` +
      `?cc=${encodeURIComponent(NOTIFY_EMAIL)}` +
      `&subject=${encodeURIComponent(subject)}` +
      `&body=${encodeURIComponent(body)}`;

    window.open(mailto, "_self");
    setCard(m.id, { state: "sending" });
  };

  const handleReset = (id: string) => setCard(id, { state: "estimate" });

  const handleAccept = (id: string) =>
    setPaidMediaStates((s) => {
      const current = s[id];
      if (!current || current.state !== "received") return s;
      return { ...s, [id]: { state: "accepted" } };
    });

  const competitors = competitorsRanked(scenario);
  const allPrompts = allPromptsByLift(root, scenario);
  const weakPrompts = lowestVisibilityPrompts(root, 3);

  return (
    <main className="min-h-screen flex flex-col">
      <BrandMark className="fixed top-5 left-6 z-50 no-print" />

      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
        className="flex-1 max-w-6xl mx-auto w-full px-6 py-16"
      >
        <Header brand={username.toUpperCase()} />

        <Hero
          brand={brand}
          pessimisticLift={bracket.pessimistic_total_revenue_lift_eur}
          optimisticLift={bracket.optimistic_total_revenue_lift_eur}
          pessimisticCustomers={bracket.pessimistic_customer_equivalents}
          optimisticCustomers={bracket.optimistic_customer_equivalents}
          pessimisticPp={bracket.pessimistic_visibility_increase_pp}
          optimisticPp={bracket.optimistic_visibility_increase_pp}
          summary={executiveSummary}
          acvSource={root.acv?.source}
        />

        <PaidMedia
          media={media}
          states={paidMediaStates}
          onSend={handleSend}
          onReset={handleReset}
          onAccept={handleAccept}
        />

        <VisibilityGap
          brand={brand}
          you={scenario.overall_your_visibility}
          leader={scenario.leader_visibility}
          leaderName={scenario.leader_name}
          gapPp={scenario.visibility_gap_pp}
        />

        <InvisibleCallout
          brand={brand}
          untapped={scenario.untapped_prompt_count}
          total={scenario.total_prompts}
          examples={weakPrompts}
        />

        <Competitive
          brand={brand}
          competitors={competitors}
          totalPrompts={scenario.total_prompts}
        />

        <PromptsTable
          prompts={allPrompts}
          sharePct={scenario.top3_lift_share_pct}
        />

        <Methodology
          aiQueryShare={scenario.market_estimate.ai_query_share}
          realVolume={scenario.prompts_using_real_volume}
          totalPrompts={scenario.total_prompts}
          source={scenario.market_estimate.sources[0]}
        />

        <CTA />
      </motion.section>
    </main>
  );
}

function Header({ brand }: { brand: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.05 }}
      className="text-center mb-12"
    >
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-line bg-white text-[13px] mb-5">
        <CheckCircle2 className="w-3.5 h-3.5 text-gain" />
        Analysis complete · {brand}
      </div>
      <h1 className="text-[clamp(2.25rem,6vw,4rem)] font-semibold tracking-[-0.04em] leading-[1.02] max-w-3xl mx-auto">
        <span className="text-ink">Where {brand} loses pipeline</span>
        <br />
        <span className="text-muted">in AI-driven discovery.</span>
      </h1>
    </motion.div>
  );
}

function Hero({
  brand,
  pessimisticLift,
  optimisticLift,
  pessimisticCustomers,
  optimisticCustomers,
  pessimisticPp,
  optimisticPp,
  summary,
  acvSource,
}: {
  brand: string;
  pessimisticLift: number;
  optimisticLift: number;
  pessimisticCustomers: number;
  optimisticCustomers: number;
  pessimisticPp: number;
  optimisticPp: number;
  summary: string;
  acvSource?: string;
}) {
  const fmtCust = (n: number) =>
    n.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.15 }}
      className="rounded-3xl bg-ink text-white p-10 md:p-14 mb-8 relative overflow-hidden print-bg-light"
    >
      <div className="absolute inset-0 dot-grid opacity-[0.06]" />
      <div className="relative">
        <div className="text-[13px] uppercase tracking-wider text-white/60 mb-3 flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5" />
          Potential financial gain for {brand}
        </div>
        <div className="text-[clamp(2.5rem,8.5vw,5.5rem)] font-semibold tracking-[-0.04em] leading-[1.02] text-gain tabular-nums">
          {formatEuro(pessimisticLift)}
          <span className="text-gain font-normal text-[0.55em] mx-4 align-middle">
            –
          </span>
          {formatEuro(optimisticLift)}
        </div>
        <div className="mt-5 text-[17px] text-white/70 leading-relaxed flex items-center gap-2 flex-wrap">
          <Users className="w-4 h-4 text-white/60" />
          ≈{" "}
          <strong className="text-white tabular-nums">
            {fmtCust(pessimisticCustomers)}–{fmtCust(optimisticCustomers)} new customers
          </strong>
          , currently won by competitors across the AI answers your buyers see.
        </div>
        <div className="mt-2 text-[13px] text-white/50 tabular-nums">
          {pessimisticPp.toFixed(2)}–{optimisticPp.toFixed(2)} pp visibility upside
        </div>
        {acvSource && (
          <div className="mt-1 text-[12px] text-white/40">
            ACV researched from{" "}
            <a
              href={acvSource}
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-white/20 underline-offset-2 hover:text-white/70"
            >
              {hostnameOf(acvSource)}
            </a>
          </div>
        )}

        {summary && (
          <div className="mt-10 pt-7 border-t border-white/15 max-w-3xl">
            <div className="text-[11px] uppercase tracking-wider text-white/50 mb-2.5">
              Executive summary
            </div>
            <p className="text-[15px] text-white/80 leading-relaxed">
              {summary}
            </p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function VisibilityGap({
  brand,
  you,
  leader,
  leaderName,
  gapPp,
}: {
  brand: string;
  you: number;
  leader: number;
  leaderName: string;
  gapPp: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.25 }}
      className="rounded-2xl bg-white border border-line p-7 mb-8"
    >
      <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
        <div>
          <h2 className="text-[22px] font-semibold tracking-[-0.02em]">
            {Math.round(gapPp)} pp visibility gap
          </h2>
          <p className="text-muted text-[14px] mt-1">
            Share of voice across AI answers — {brand} vs. {leaderName}.
          </p>
        </div>
      </div>

      <div className="space-y-5">
        <Bar label={brand} value={you} tone="muted" />
        <Bar label={leaderName} value={leader} tone="accent" />
      </div>
    </motion.div>
  );
}

function Bar({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "muted" | "accent";
}) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-[15px] font-medium">{label}</span>
        <span className="text-[20px] font-semibold tracking-tight tabular-nums">
          {pct}%
        </span>
      </div>
      <div className="h-3 rounded-full bg-canvas border border-line overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.9, delay: 0.4, ease: "easeOut" }}
          className={`h-full rounded-full ${
            tone === "accent" ? "bg-ink" : "bg-ink/30"
          }`}
        />
      </div>
    </div>
  );
}

function InvisibleCallout({
  brand,
  untapped,
  total,
  examples,
}: {
  brand: string;
  untapped: number;
  total: number;
  examples: { prompt_id: string; prompt_message: string; your_visibility: number }[];
}) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const target = untapped;
    const duration = 1100;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setCount(Math.round(eased * target));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [untapped]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.35 }}
      className="rounded-2xl bg-white border border-line p-7 mb-8"
    >
      <div className="flex items-start gap-5 flex-wrap">
        <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-canvas border border-line flex items-center justify-center">
          <EyeOff className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-[44px] font-semibold tracking-[-0.03em] tabular-nums leading-none">
              {count}
            </span>
            <span className="text-[20px] text-muted tabular-nums">
              / {total}
            </span>
            <span className="text-[14px] text-muted ml-2">
              prompts where {brand} never surfaces in AI answers.
            </span>
          </div>
          <div className="mt-5 grid sm:grid-cols-3 gap-2">
            {examples.map((p) => (
              <div
                key={p.prompt_id}
                className="rounded-lg bg-canvas border border-line px-3.5 py-3"
              >
                <div className="text-[11px] uppercase tracking-wider text-muted">
                  Visibility {Math.round(p.your_visibility * 100)}%
                </div>
                <div className="text-[13px] mt-1 leading-snug line-clamp-3">
                  &ldquo;{p.prompt_message}&rdquo;
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function Competitive({
  brand,
  competitors,
  totalPrompts,
}: {
  brand: string;
  competitors: { competitor_name: string; prompts_won_against_you: number }[];
  totalPrompts: number;
}) {
  const max = Math.max(...competitors.map((c) => c.prompts_won_against_you));
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.45 }}
      className="rounded-2xl bg-white border border-line p-7 mb-8"
    >
      <h2 className="text-[22px] font-semibold tracking-[-0.02em] mb-1">
        Competitive landscape
      </h2>
      <p className="text-muted text-[14px] mb-6">
        Who outranks {brand} across the {totalPrompts} prompts in scope.
      </p>
      <div className="space-y-4">
        {competitors.map((c, i) => {
          const pct = Math.round((c.prompts_won_against_you / totalPrompts) * 100);
          const widthPct = Math.round((c.prompts_won_against_you / max) * 100);
          return (
            <div key={c.competitor_name}>
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="text-[14px] font-medium">
                  {c.competitor_name}
                </span>
                <span className="text-[13px] text-muted tabular-nums">
                  {c.prompts_won_against_you} / {totalPrompts} prompts
                  <span className="text-muted/60"> · {pct}%</span>
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-canvas border border-line overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${widthPct}%` }}
                  transition={{ duration: 0.7, delay: 0.5 + i * 0.07 }}
                  className="h-full bg-ink rounded-full"
                />
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

function PromptsTable({
  prompts,
  sharePct,
}: {
  prompts: PromptDetail[];
  sharePct: number;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const total = prompts.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.55 }}
      className="rounded-2xl bg-white border border-line p-7 mb-8"
    >
      <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
        <div>
          <h2 className="text-[22px] font-semibold tracking-[-0.02em]">
            All {total} prompts
          </h2>
          <p className="text-muted text-[14px] mt-1">
            The top 3 hold{" "}
            <span className="text-ink font-medium">{sharePct}%</span> of the
            lift. Open any row for the full read.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 text-[12px] text-muted">
          <Target className="w-3.5 h-3.5" />
          ranked by revenue lift
        </div>
      </div>

      <div className="border border-line rounded-xl overflow-hidden">
        {prompts.map((p, i) => {
          const isOpen = open === p.prompt_id;
          const isTop3 = i < 3;
          return (
            <div
              key={p.prompt_id}
              className={`${
                i > 0 ? "border-t border-line" : ""
              } ${isTop3 ? "bg-canvas/40" : "bg-white"}`}
            >
              <button
                onClick={() => setOpen(isOpen ? null : p.prompt_id)}
                className="w-full text-left flex items-center gap-4 p-4 hover:bg-canvas transition"
              >
                <span
                  className={`flex-shrink-0 w-7 h-7 rounded-full text-[12px] font-semibold flex items-center justify-center ${
                    isTop3
                      ? "bg-ink text-white"
                      : "bg-canvas border border-line text-muted"
                  }`}
                >
                  {i + 1}
                </span>
                <span className="flex-1 min-w-0 text-[14px] leading-snug">
                  {p.prompt_message}
                </span>
                <span className="hidden sm:inline-flex items-center gap-1 text-[12px] text-muted whitespace-nowrap tabular-nums">
                  vis {Math.round(p.your_visibility * 100)}%
                </span>
                <span className="text-[15px] font-semibold tabular-nums whitespace-nowrap text-gain">
                  {formatEuro(p.revenue_lift_eur)}
                </span>
                <span className="text-muted">
                  {isOpen ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                </span>
              </button>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="overflow-hidden"
                  >
                    <PromptDetailView prompt={p} />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

function PromptDetailView({ prompt }: { prompt: PromptDetail }) {
  const summary =
    prompt.ai_summary && prompt.ai_summary !== "this will be the ai summary"
      ? prompt.ai_summary
      : null;
  return (
    <div className="px-4 pb-5 pt-1">
      {summary && (
        <div className="mb-3 rounded-lg bg-ink/5 border border-line p-4 text-[13px] leading-relaxed text-ink/80">
          <span className="text-[11px] uppercase tracking-wider text-muted mr-2">
            TLDR
          </span>
          {summary}
        </div>
      )}
      <div className="grid md:grid-cols-3 gap-3">
      <Stat
        label="Your visibility"
        value={`${Math.round(prompt.your_visibility * 100)}%`}
        sub={`avg position ${prompt.your_position.toFixed(1)}`}
      />
      <Stat
        label={`Top competitor · ${prompt.top_competitor_name}`}
        value={`${Math.round(prompt.top_competitor_visibility * 100)}%`}
        sub="avg visibility"
      />
      <Stat
        label="Annual mentions"
        value={Math.round(prompt.annual_mentions).toLocaleString("en-US")}
        sub={
          prompt.volume_source === "chat_fallback"
            ? "sample-extrapolation"
            : `search_volume ${prompt.search_volume.toLocaleString("en-US")}`
        }
      />
      <Stat
        label="Current annual revenue"
        value={formatEuro(prompt.current_annual_revenue_eur)}
      />
      <Stat
        label="Target annual revenue"
        value={formatEuro(prompt.target_annual_revenue_eur)}
        sub={`if visibility → ${Math.round(prompt.target_visibility * 100)}% @ pos ${prompt.target_position.toFixed(1)}`}
      />
      <Stat
        label="Revenue lift"
        value={`${formatEuro(prompt.pessimistic_revenue_lift_eur)} – ${formatEuro(prompt.optimistic_revenue_lift_eur)}`}
        accent="gain"
      />

      {prompt.action && (
        <div className="md:col-span-3 rounded-lg bg-white border border-line p-4 mt-1">
          <div className="flex items-start justify-between flex-wrap gap-3 mb-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted">
                Recommended action
              </div>
              <div className="text-[14px] font-medium capitalize mt-0.5">
                {prompt.action.action_type.replace(/_/g, " ")}
              </div>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted mb-1.5">
                Suggested targets
              </div>
              <ul className="space-y-1 text-[13px] text-muted">
                {prompt.action.suggested_targets.map((t) => (
                  <li key={t} className="leading-snug">
                    · {t}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted mb-1.5">
                Evidence
              </div>
              <ul className="space-y-1 text-[13px] text-muted">
                {prompt.action.evidence_signals.map((s) => (
                  <li key={s} className="leading-snug">
                    · {s}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "gain";
}) {
  return (
    <div className="rounded-lg bg-white border border-line p-3.5">
      <div className="text-[11px] uppercase tracking-wider text-muted">
        {label}
      </div>
      <div
        className={`mt-1 text-[18px] font-semibold tracking-tight tabular-nums leading-tight ${
          accent === "gain" ? "text-gain" : ""
        }`}
      >
        {value}
      </div>
      {sub && (
        <div className="mt-0.5 text-[12px] text-muted leading-snug">{sub}</div>
      )}
    </div>
  );
}

function Methodology({
  aiQueryShare,
  realVolume,
  totalPrompts,
  source,
}: {
  aiQueryShare: number;
  realVolume: number;
  totalPrompts: number;
  source: string;
}) {
  const fallback = totalPrompts - realVolume;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.7 }}
      className="rounded-xl bg-white/60 border border-line/70 p-5 mb-10 text-[12px] text-muted leading-relaxed"
    >
      <div className="flex items-start gap-2 flex-wrap">
        <span className="font-medium text-muted/90 uppercase tracking-wider text-[10px]">
          Methodology
        </span>
        <span>·</span>
        <span>
          <code className="text-ink/80">ai_query_share</code> ={" "}
          {formatPct(aiQueryShare)} sourced via Tavily
        </span>
        <a
          href={source}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-0.5 underline decoration-line underline-offset-2 hover:text-ink"
        >
          [link]
          <ExternalLink className="w-2.5 h-2.5" />
        </a>
        <span>·</span>
        <span>
          {realVolume} of {totalPrompts} prompts has sourced volume; the other{" "}
          {fallback} use a sample-extrapolation method.
        </span>
      </div>
    </motion.div>
  );
}

function PaidMedia({
  media,
  states,
  onSend,
  onReset,
  onAccept,
}: {
  media: Media[];
  states: StateMap;
  onSend: (m: Media) => void;
  onReset: (id: string) => void;
  onAccept: (id: string) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.65 }}
      className="mb-8"
    >
      <div className="flex items-end justify-between flex-wrap gap-4 mb-5">
        <div>
          <h2 className="text-[22px] font-semibold tracking-[-0.02em]">
            Paid media outreach
          </h2>
          <p className="text-muted text-[15px] mt-1">
            Each card shows the projected revenue range for placement on that
            partner — request a quote to confirm the spend.
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-4 gap-5">
        {media.map((m, i) => (
          <MediaCard
            key={m.id}
            media={m}
            index={i}
            card={states[m.id] ?? { state: "estimate" }}
            onSend={() => onSend(m)}
            onReset={() => onReset(m.id)}
            onAccept={() => onAccept(m.id)}
          />
        ))}
        <SeeMoreCard index={media.length} />
      </div>
    </motion.div>
  );
}

function SeeMoreCard({ index }: { index: number }) {
  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.7 + index * 0.07 }}
      className="print-card group rounded-2xl bg-white/40 border border-dashed border-line p-6 flex flex-col items-center justify-center text-center min-h-[360px] hover:bg-white hover:border-ink/30 transition-colors no-print"
    >
      <div className="w-11 h-11 rounded-xl bg-canvas border border-line flex items-center justify-center mb-4 group-hover:border-ink/30 transition-colors">
        <Plus className="w-5 h-5 text-muted group-hover:text-ink transition-colors" />
      </div>
      <div className="text-[15px] font-semibold tracking-tight">See more</div>
      <p className="text-[12px] text-muted mt-1.5 max-w-[16ch] leading-snug">
        More partner placements available in your full plan
      </p>
      <span className="mt-4 inline-flex items-center gap-1 text-[12px] text-ink/70 group-hover:text-ink transition-colors">
        Browse all
        <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
      </span>
    </motion.button>
  );
}

function MediaCard({
  media,
  index,
  card,
  onSend,
  onReset,
  onAccept,
}: {
  media: Media;
  index: number;
  card: CardData;
  onSend: () => void;
  onReset: () => void;
  onAccept: () => void;
}) {
  const Icon = media.icon;
  const accepted = card.state === "accepted";
  const received = card.state === "received";
  const highlight = accepted || received;

  const statusLabel = accepted
    ? "Accepted"
    : received
      ? "Offer in"
      : card.state === "sending"
        ? "Awaiting reply"
        : "Forecast";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.7 + index * 0.07 }}
      className={`print-card group rounded-2xl bg-white border p-6 flex flex-col transition-colors ${
        highlight
          ? "border-ink/40 shadow-[0_2px_24px_-12px_rgba(0,0,0,0.18)]"
          : "border-line hover:border-ink/30"
      }`}
    >
      <div className="flex items-start justify-between mb-5">
        <div className="w-11 h-11 rounded-xl bg-canvas flex items-center justify-center">
          <Icon className="w-5 h-5" />
        </div>
        <span
          className={`text-[11px] px-2 py-0.5 rounded-full border whitespace-nowrap transition-colors ${
            highlight
              ? "border-ink/20 bg-ink/5 text-ink"
              : "border-line bg-canvas text-muted"
          }`}
        >
          {statusLabel}
        </span>
      </div>

      <div className="text-[12px] text-muted mb-1">#{index + 1} Paid media</div>
      <h3 className="text-[20px] font-semibold tracking-tight leading-tight">
        {media.title}
      </h3>
      <div className="text-[13px] text-muted mt-0.5 truncate">{media.domain}</div>
      <div className="text-[12px] text-muted mt-2 leading-snug">
        {media.audience}
      </div>

      <div className="mt-5 space-y-2.5">
        <FigureRow
          label="Estimated cost"
          value={media.cost}
          sub="/ quarter"
        />
        <FigureRow
          label="Projected revenue gain"
          value={media.gainRange}
          sub="/ year"
          delta={media.gainDeltaRange}
          accent="gain"
        />
      </div>

      <div className="mt-6 pt-5 border-t border-line no-print">
        <AnimatePresence mode="wait" initial={false}>
          {card.state === "estimate" && (
            <motion.button
              key="estimate"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              onClick={onSend}
              className="w-full h-11 rounded-xl bg-ink text-white text-[14px] font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition"
            >
              <Mail className="w-4 h-4" />
              Request offer
            </motion.button>
          )}

          {card.state === "sending" && (
            <motion.div
              key="sending"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              className="w-full h-11 rounded-xl bg-canvas border border-line text-[13px] text-muted flex items-center justify-center gap-2"
            >
              <Loader2 className="w-4 h-4 animate-spin" />
              Request sent · Waiting for response
            </motion.div>
          )}

          {card.state === "received" && (
            <motion.div
              key="received"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col gap-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-[13px] text-ink">
                  <MailCheck className="w-4 h-4 text-gain" />
                  Offer received
                </span>
                <button
                  onClick={onReset}
                  className="inline-flex items-center gap-1 text-[12px] text-muted hover:text-ink transition"
                  title="Request again"
                >
                  <RotateCcw className="w-3 h-3" />
                  request again
                </button>
              </div>
              <button
                onClick={onAccept}
                className="w-full h-10 rounded-xl bg-gain text-white text-[13px] font-medium flex items-center justify-center gap-2 hover:bg-gain/90 transition"
              >
                <CheckCircle2 className="w-4 h-4" />
                Accept offer
              </button>
            </motion.div>
          )}

          {card.state === "accepted" && (
            <motion.div
              key="accepted"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col gap-2"
            >
              <div className="w-full h-10 rounded-xl bg-gain/10 border border-gain/30 text-gain text-[13px] font-medium flex items-center justify-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                Offer accepted
              </div>
              <button
                onClick={onReset}
                className="inline-flex items-center justify-center gap-1 text-[12px] text-muted hover:text-ink transition"
                title="Reset"
              >
                <RotateCcw className="w-3 h-3" />
                start over
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function FigureRow({
  label,
  value,
  sub,
  delta,
  accent,
}: {
  label: string;
  value: string;
  sub: string;
  delta?: string;
  accent?: "gain";
}) {
  return (
    <div className="rounded-xl bg-canvas border border-line px-3.5 py-3">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-[11px] uppercase tracking-wider text-muted">
          {label}
        </div>
        <span className="text-[11px] text-muted whitespace-nowrap">{sub}</span>
      </div>
      <div
        className={`mt-1 text-[16px] font-semibold tracking-tight leading-tight tabular-nums ${
          accent === "gain" ? "text-gain" : ""
        }`}
      >
        {value}
      </div>
      {delta && (
        <div className="mt-0.5 text-[11px] text-gain font-medium tabular-nums">
          {delta}
        </div>
      )}
    </div>
  );
}

function CTA() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.8 }}
      className="flex flex-col sm:flex-row gap-3 justify-center no-print"
    >
      <button
        onClick={() => window.print()}
        className="px-5 h-12 rounded-xl bg-white border border-line text-[15px] font-medium hover:bg-canvas transition flex items-center justify-center gap-2"
      >
        <Download className="w-4 h-4" />
        Export report
      </button>
      <Link
        href="/content-plan"
        className="px-5 h-12 rounded-xl bg-white border border-line text-[15px] font-medium hover:bg-canvas transition flex items-center justify-center gap-2 group"
      >
        <CalendarRange className="w-4 h-4" />
        Create content plan
        <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
      </Link>
      <Link
        href="/home"
        className="px-6 h-12 rounded-xl bg-ink text-white text-[15px] font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition group"
      >
        Start new analysis
        <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
      </Link>
    </motion.div>
  );
}
