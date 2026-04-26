"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  CalendarRange,
  CheckCircle2,
  Download,
  Linkedin,
  Mail,
  Megaphone,
  PenLine,
  Search,
  Video,
} from "lucide-react";
import BrandMark from "@/components/BrandMark";

type Channel = "Blog" | "LinkedIn" | "Email" | "Video" | "Paid Ads";

const CHANNEL_ICON: Record<Channel, React.ReactNode> = {
  Blog: <PenLine className="w-3.5 h-3.5" />,
  LinkedIn: <Linkedin className="w-3.5 h-3.5" />,
  Email: <Mail className="w-3.5 h-3.5" />,
  Video: <Video className="w-3.5 h-3.5" />,
  "Paid Ads": <Megaphone className="w-3.5 h-3.5" />,
};

type PlanItem = {
  week: string;
  title: string;
  channel: Channel;
  goal: string;
  lever: string;
};

const PLAN: PlanItem[] = [
  {
    week: "Week 1",
    title: "Launch story: pricing update, transparently explained",
    channel: "Blog",
    goal: "Awareness · Trust",
    lever: "Pricing",
  },
  {
    week: "Week 1",
    title: "Founder post: why we’re adjusting our prices",
    channel: "LinkedIn",
    goal: "Reach · Reputation",
    lever: "Pricing",
  },
  {
    week: "Week 2",
    title: "Case study: 12% margin lift in 6 weeks",
    channel: "Blog",
    goal: "Conversion · Proof",
    lever: "Pricing",
  },
  {
    week: "Week 2",
    title: "VIP mailing to top-23% segment",
    channel: "Email",
    goal: "Upsell",
    lever: "Segmentation",
  },
  {
    week: "Week 3",
    title: "Re-targeting on high-ROAS channels",
    channel: "Paid Ads",
    goal: "Performance",
    lever: "Cost",
  },
  {
    week: "Week 3",
    title: "60s video: three-step lever explained",
    channel: "Video",
    goal: "Engagement",
    lever: "Brand",
  },
  {
    week: "Week 4",
    title: "End-of-quarter newsletter with insights",
    channel: "Email",
    goal: "Retention",
    lever: "Segmentation",
  },
  {
    week: "Week 4",
    title: "LinkedIn carousel: 5 lessons learned",
    channel: "LinkedIn",
    goal: "Reach",
    lever: "Brand",
  },
];

const WEEKS = ["Week 1", "Week 2", "Week 3", "Week 4"];

export default function ContentPlanPage() {
  return (
    <main className="min-h-screen flex flex-col">
      <BrandMark className="fixed top-5 left-6 z-50" />

      <div className="fixed inset-x-0 bottom-0 h-72 dot-grid opacity-40 pointer-events-none -z-10" />

      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="flex-1 max-w-7xl mx-auto w-full px-6 py-16"
      >
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-line bg-white text-[13px] mb-8"
        >
          <CalendarRange className="w-3.5 h-3.5" />
          Content plan · auto-generated
        </motion.div>

        <div className="grid lg:grid-cols-12 gap-10 mb-14">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05 }}
            className="lg:col-span-7"
          >
            <h1 className="text-[clamp(2.5rem,6.5vw,4.75rem)] font-semibold tracking-[-0.04em] leading-[1.02]">
              Your 4-week
              <br />
              <span className="text-muted">campaign</span>
            </h1>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="lg:col-span-5 flex flex-col justify-end"
          >
            <p className="text-[17px] text-muted leading-relaxed">
              Based on your profit analysis we&apos;ve mapped out a campaign —
              channels, topics, goals, and which lever each post activates.
            </p>
          </motion.div>
        </div>

        {/* Quick stats */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10"
        >
          <Stat label="Posts" value="8" />
          <Stat label="Channels" value="5" />
          <Stat label="Weeks" value="4" />
          <Stat label="Expected lift" value="+18%" highlight />
        </motion.div>

        {/* Plan cards by week */}
        <div className="space-y-8">
          {WEEKS.map((wk, wIdx) => (
            <motion.div
              key={wk}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 + wIdx * 0.08 }}
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-ink text-white flex items-center justify-center text-[12px] font-semibold">
                  {wIdx + 1}
                </div>
                <h2 className="text-[20px] font-semibold tracking-tight">
                  {wk}
                </h2>
                <div className="flex-1 border-t border-line" />
                <span className="text-[12px] text-muted">
                  {PLAN.filter((p) => p.week === wk).length} posts
                </span>
              </div>

              <div className="grid md:grid-cols-2 gap-3">
                {PLAN.filter((p) => p.week === wk).map((item, i) => (
                  <div
                    key={i}
                    className="group rounded-2xl bg-white border border-line p-5 hover:border-ink/30 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-canvas border border-line text-[12px]">
                        {CHANNEL_ICON[item.channel]}
                        {item.channel}
                      </span>
                      <span className="text-[11px] px-2 py-0.5 rounded-full border border-ink/15 bg-ink/5 text-ink">
                        Lever: {item.lever}
                      </span>
                    </div>
                    <h3 className="text-[16px] font-semibold tracking-tight leading-snug mb-2">
                      {item.title}
                    </h3>
                    <div className="flex items-center gap-2 text-[12px] text-muted">
                      <Search className="w-3 h-3" />
                      <span>Goal: {item.goal}</span>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Outcome */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.7 }}
          className="mt-12 rounded-3xl bg-ink text-white p-8 md:p-10 relative overflow-hidden"
        >
          <div className="absolute inset-0 dot-grid opacity-[0.06]" />
          <div className="relative grid md:grid-cols-3 gap-6 items-center">
            <div className="md:col-span-2">
              <div className="text-[12px] uppercase tracking-wider text-white/60 mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Outcome
              </div>
              <h3 className="text-[24px] font-semibold tracking-[-0.02em] leading-tight">
                This campaign activates all three identified levers and turns
                the untapped potential into revenue in{" "}
                <strong>~6 weeks</strong>.
              </h3>
            </div>
            <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
              <div className="text-[11px] uppercase tracking-wider text-white/50">
                Expected impact
              </div>
              <div className="text-[40px] font-semibold tracking-tight mt-1 leading-none text-gain">
                +€95k
              </div>
              <div className="text-[12px] text-white/60 mt-2">
                in the first 90 days
              </div>
            </div>
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.85 }}
          className="mt-10 flex flex-col sm:flex-row gap-3 justify-center no-print"
        >
          <button
            onClick={() => window.print()}
            className="px-5 h-12 rounded-xl bg-white border border-line text-[15px] font-medium hover:bg-canvas transition flex items-center justify-center gap-2"
          >
            <Download className="w-4 h-4" />
            Export plan
          </button>
          <Link
            href="/report"
            className="px-5 h-12 rounded-xl bg-white border border-line text-[15px] font-medium hover:bg-canvas transition flex items-center justify-center gap-2"
          >
            Back to report
          </Link>
          <Link
            href="/home"
            className="px-6 h-12 rounded-xl bg-ink text-white text-[15px] font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition group"
          >
            Start new analysis
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </motion.div>
      </motion.section>
    </main>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl bg-white border p-5 ${
        highlight ? "border-l-[3px] border-l-gain border-y-line border-r-line" : "border-line"
      }`}
    >
      <div className="text-[12px] uppercase tracking-wider text-muted">
        {label}
      </div>
      <div
        className={`text-[28px] font-semibold tracking-tight mt-1 ${
          highlight ? "text-gain" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
