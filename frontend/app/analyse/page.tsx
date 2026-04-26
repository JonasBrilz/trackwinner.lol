"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Database,
  TrendingUp,
  Calculator,
  Check,
  Loader2,
  ArrowRight,
} from "lucide-react";
import BrandMark from "@/components/BrandMark";
import { STORAGE_KEY } from "@/lib/paidMedia";
type StepState = "pending" | "active" | "done";

const NODES = [
  {
    id: "data",
    title: "Data capture",
    desc: "We pull together all relevant business data — revenue, costs, market position.",
    icon: Database,
  },
  {
    id: "analysis",
    title: "Market analysis",
    desc: "Benchmarked against competitors and scanned for optimization potential.",
    icon: TrendingUp,
  },
  {
    id: "calc",
    title: "Untapped potential",
    desc: "We compute the revenue you’re leaving on the table, lever by lever.",
    icon: Calculator,
  },
];

const THINKING_PER_NODE: string[][] = [
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

const STEP_DURATION = 900;

export default function AnalysePage() {
  const router = useRouter();
  const [activeNode, setActiveNode] = useState(0);
  const [thinkingIdx, setThinkingIdx] = useState(0);
  const [doneNodes, setDoneNodes] = useState<number[]>([]);

  useEffect(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* noop */
    }
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setThinkingIdx((prev) => {
        const stepsForCurrent = THINKING_PER_NODE[activeNode];
        if (prev < stepsForCurrent.length - 1) {
          return prev + 1;
        }
        // Step für diesen Knoten fertig
        setDoneNodes((d) => (d.includes(activeNode) ? d : [...d, activeNode]));
        if (activeNode < NODES.length - 1) {
          setActiveNode((n) => n + 1);
          return 0;
        } else {
          clearInterval(timer);
          setTimeout(() => router.push("/report"), 1200);
          return prev;
        }
      });
    }, STEP_DURATION);

    return () => clearInterval(timer);
  }, [activeNode, router]);

  const stateOf = (idx: number): StepState => {
    if (doneNodes.includes(idx)) return "done";
    if (idx === activeNode) return "active";
    return "pending";
  };

  return (
    <main className="min-h-screen flex flex-col">
      <BrandMark className="fixed top-5 left-6 z-50" />

      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        className="flex-1 max-w-7xl mx-auto w-full px-6 py-16"
      >
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-line bg-white text-[13px] mb-5">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Analysis running
          </div>
          <h1 className="text-[clamp(2rem,5vw,3.5rem)] font-semibold tracking-[-0.03em] leading-[1.05]">
            We&apos;re understanding <span className="text-muted">your company</span>
          </h1>
          <p className="mt-4 text-[16px] text-muted max-w-xl mx-auto">
            Three steps. One goal: surface where your profit potential is hiding.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16">
          {/* LEFT — Knoten-System */}
          <div className="relative">
            <svg
              className="absolute left-[27px] top-12 bottom-12 w-0.5 -z-0"
              width="2"
              height="100%"
              preserveAspectRatio="none"
            >
              <line
                x1="1"
                y1="0"
                x2="1"
                y2="100%"
                stroke="#e5e5e2"
                strokeWidth="2"
              />
              <motion.line
                x1="1"
                y1="0"
                x2="1"
                y2="100%"
                stroke="#0a0a0a"
                strokeWidth="2"
                initial={{ pathLength: 0 }}
                animate={{
                  pathLength:
                    activeNode === 0
                      ? 0.15
                      : activeNode === 1
                      ? 0.55
                      : 1,
                }}
                transition={{ duration: 0.8, ease: "easeInOut" }}
              />
            </svg>

            <div className="space-y-6 relative z-10">
              {NODES.map((node, idx) => {
                const state = stateOf(idx);
                const Icon = node.icon;
                return (
                  <motion.div
                    key={node.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.1, duration: 0.5 }}
                    className={`flex gap-4 p-5 rounded-2xl bg-white border transition-all duration-500 ${
                      state === "active"
                        ? "border-l-[3px] border-l-accent border-y-line border-r-line shadow-[0_2px_24px_-12px_rgba(0,0,0,0.15)]"
                        : state === "done"
                        ? "border-line opacity-70"
                        : "border-line opacity-50"
                    }`}
                  >
                    <div
                      className={`flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${
                        state === "done"
                          ? "bg-ink text-white"
                          : state === "active"
                          ? "bg-ink/5 text-ink"
                          : "bg-canvas text-muted"
                      }`}
                    >
                      {state === "done" ? (
                        <Check className="w-5 h-5" />
                      ) : state === "active" ? (
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{
                            duration: 2,
                            repeat: Infinity,
                            ease: "linear",
                          }}
                        >
                          <Icon className="w-5 h-5" />
                        </motion.div>
                      ) : (
                        <Icon className="w-5 h-5" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold text-[16px] tracking-tight">
                          {node.title}
                        </h3>
                        <span className="text-[12px] text-muted">
                          {state === "done"
                            ? "Done"
                            : state === "active"
                            ? "Running…"
                            : "Pending"}
                        </span>
                      </div>
                      <p className="text-[14px] text-muted mt-1 leading-relaxed">
                        {node.desc}
                      </p>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>

          {/* RIGHT — Live Thinking Steps */}
          <div className="lg:sticky lg:top-24 h-fit">
            <div className="rounded-2xl bg-white border border-line p-7">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                  <span className="text-[13px] font-medium uppercase tracking-wider text-muted">
                    Live thinking
                  </span>
                </div>
                <span className="text-[12px] text-muted">
                  Step {activeNode + 1} / {NODES.length}
                </span>
              </div>

              <h2 className="text-[24px] font-semibold tracking-[-0.02em] leading-tight">
                {NODES[activeNode].title}
              </h2>

              <div className="mt-6 space-y-2.5">
                <AnimatePresence mode="popLayout">
                  {THINKING_PER_NODE[activeNode]
                    .slice(0, thinkingIdx + 1)
                    .map((step, i) => (
                      <motion.div
                        key={`${activeNode}-${i}`}
                        layout
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className="flex items-start gap-3 text-[14px]"
                      >
                        {i === thinkingIdx ? (
                          <Loader2 className="w-4 h-4 mt-0.5 text-ink animate-spin flex-shrink-0" />
                        ) : (
                          <Check className="w-4 h-4 mt-0.5 text-ink/60 flex-shrink-0" />
                        )}
                        <span
                          className={
                            i === thinkingIdx ? "text-ink" : "text-muted"
                          }
                        >
                          {step}
                        </span>
                      </motion.div>
                    ))}
                </AnimatePresence>
              </div>

              <div className="mt-7 pt-5 border-t border-line">
                <div className="flex items-center justify-between text-[12px] text-muted">
                  <span>Progress</span>
                  <span>
                    {Math.round(
                      ((doneNodes.length +
                        (thinkingIdx + 1) /
                          THINKING_PER_NODE[activeNode].length) /
                        NODES.length) *
                        100
                    )}
                    %
                  </span>
                </div>
                <div className="mt-2 h-1 rounded-full bg-line overflow-hidden">
                  <motion.div
                    className="h-full bg-ink"
                    animate={{
                      width: `${
                        ((doneNodes.length +
                          (thinkingIdx + 1) /
                            THINKING_PER_NODE[activeNode].length) /
                          NODES.length) *
                        100
                      }%`,
                    }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
              </div>
            </div>

            <div className="mt-4 text-center text-[12px] text-muted flex items-center justify-center gap-2">
              <ArrowRight className="w-3 h-3" />
              Report opens automatically
            </div>
          </div>
        </div>
      </motion.section>
    </main>
  );
}
