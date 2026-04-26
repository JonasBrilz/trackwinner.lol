"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Database,
  TrendingUp,
  Calculator,
  Check,
  Loader2,
  ArrowRight,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";
import BrandMark from "@/components/BrandMark";
import { STORAGE_KEY } from "@/lib/paidMedia";
import {
  DEFAULT_PROJECT_ID,
  FETCH_TIMEOUT_MS,
  cacheReport,
  fetchReport,
} from "@/lib/peec";
type StepState = "pending" | "active" | "done";

const NODES = [
  {
    id: "data",
    title: "Data capture",
    desc: "We aggregate the business data that matters — revenue, costs, market position.",
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
    desc: "We model the missed revenue across every relevant prompt.",
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
  return (
    <Suspense fallback={null}>
      <AnalysePageInner />
    </Suspense>
  );
}

function AnalysePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project") ?? DEFAULT_PROJECT_ID;

  const [activeNode, setActiveNode] = useState(0);
  const [thinkingIdx, setThinkingIdx] = useState(0);
  const [doneNodes, setDoneNodes] = useState<number[]>([]);
  const [fetchStatus, setFetchStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const reachedFinalRef = useRef(false);
  const animationDoneRef = useRef(false);
  const [animationDone, setAnimationDone] = useState(false);
  const [, forceRender] = useState(0);

  useEffect(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* noop */
    }
  }, []);

  // Kick off the real fetch on mount; cache the result so /report can render
  // immediately without showing its own loading screen.
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    setFetchStatus("loading");

    fetchReport(projectId, controller.signal)
      .then((root) => {
        cacheReport(projectId, root);
        setFetchStatus("ready");
      })
      .catch(() => setFetchStatus("error"))
      .finally(() => clearTimeout(timeout));

    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [projectId]);

  // Animation loop: advance through the three nodes. Stops on the final
  // step and waits for the fetch to resolve before navigating to /report.
  useEffect(() => {
    if (fetchStatus === "error") return;

    const timer = setInterval(() => {
      setThinkingIdx((prev) => {
        const stepsForCurrent = THINKING_PER_NODE[activeNode];
        if (prev < stepsForCurrent.length - 1) {
          return prev + 1;
        }
        if (activeNode < NODES.length - 1) {
          setDoneNodes((d) =>
            d.includes(activeNode) ? d : [...d, activeNode],
          );
          setActiveNode((n) => n + 1);
          return 0;
        }
        // Reached the final node's last thinking step: stop the cycle.
        // Don't mark it done yet — we keep the spinner running until
        // the fetch lands.
        reachedFinalRef.current = true;
        clearInterval(timer);
        animationDoneRef.current = true;
        setAnimationDone(true);
        forceRender((n) => n + 1);
        return prev;
      });
    }, STEP_DURATION);

    return () => clearInterval(timer);
  }, [activeNode, fetchStatus]);

  // When both the animation has reached the final step AND the fetch
  // resolved, mark the third node done and navigate.
  useEffect(() => {
    if (fetchStatus !== "ready" || !animationDone) return;
    setDoneNodes((d) =>
      d.includes(NODES.length - 1) ? d : [...d, NODES.length - 1],
    );
    const t = setTimeout(() => {
      const target = projectId === DEFAULT_PROJECT_ID
        ? "/report"
        : `/report?project=${encodeURIComponent(projectId)}`;
      router.push(target);
    }, 700);
    return () => clearTimeout(t);
  }, [fetchStatus, animationDone, projectId, router]);

  const stateOf = (idx: number): StepState => {
    if (doneNodes.includes(idx)) return "done";
    if (idx === activeNode) return "active";
    return "pending";
  };

  if (fetchStatus === "error") {
    return <AnalyseError />;
  }

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
            Mapping your <span className="text-muted">AI-search footprint</span>
          </h1>
          <p className="mt-4 text-[16px] text-muted max-w-xl mx-auto">
            Three passes. One outcome: surface the pipeline you're missing in AI search.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16">
          {/* LEFT — Knoten-System */}
          <div>
            <div className="relative">
              <svg
                className="absolute left-[27px] top-12 bottom-[60px] w-0.5 -z-0"
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

function AnalyseError() {
  return (
    <main className="min-h-screen flex flex-col">
      <BrandMark className="fixed top-5 left-6 z-50" />
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6 gap-4">
        <div className="w-12 h-12 rounded-xl bg-canvas border border-line flex items-center justify-center">
          <AlertTriangle className="w-5 h-5 text-ink/70" />
        </div>
        <div className="text-[20px] font-semibold tracking-tight">
          Analysis service unavailable
        </div>
        <p className="text-muted text-[14px] max-w-md leading-relaxed">
          We couldn&rsquo;t reach the analysis backend. Please try again in a
          moment.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 px-4 h-10 rounded-xl bg-ink text-white text-[14px] font-medium hover:bg-ink/90 transition flex items-center gap-2"
        >
          <RotateCcw className="w-4 h-4" />
          Try again
        </button>
      </div>
    </main>
  );
}
