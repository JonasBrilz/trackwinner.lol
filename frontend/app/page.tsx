"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, User, Lock } from "lucide-react";
import BrandMark from "@/components/BrandMark";

const USER_KEY = "peec.user";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) return;
    setSubmitting(true);
    try {
      sessionStorage.setItem(USER_KEY, trimmed);
    } catch {
      /* noop */
    }
    router.push("/home");
  };

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 relative">
      <div className="fixed inset-x-0 bottom-0 h-72 dot-grid opacity-40 pointer-events-none -z-10" />

      <div className="absolute top-6 left-6">
        <BrandMark />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
        className="w-full max-w-sm"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-line bg-white text-[13px] mb-7">
          <Sparkles className="w-3.5 h-3.5" />
          Profit Analysis
        </div>

        <h1 className="text-[clamp(2rem,5vw,3rem)] font-semibold tracking-[-0.035em] leading-[1.05] mb-2">
          Sign in
        </h1>
        <p className="text-[15px] text-muted mb-8 leading-relaxed">
          Use any username and password — the demo accepts everything.
        </p>

        <form onSubmit={onSubmit} className="space-y-3">
          <Field
            id="username"
            label="Username"
            icon={<User className="w-4 h-4 text-muted" />}
            value={username}
            onChange={setUsername}
            autoComplete="username"
            type="text"
            placeholder="e.g. attio"
          />
          <Field
            id="password"
            label="Password"
            icon={<Lock className="w-4 h-4 text-muted" />}
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            type="password"
            placeholder="anything"
          />

          <button
            type="submit"
            disabled={!username.trim() || submitting}
            className="mt-3 w-full h-12 rounded-xl bg-ink text-white text-[15px] font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition disabled:opacity-40 disabled:cursor-not-allowed group"
          >
            Sign in
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </button>
        </form>
      </motion.div>
    </main>
  );
}

function Field({
  id,
  label,
  icon,
  value,
  onChange,
  type,
  autoComplete,
  placeholder,
}: {
  id: string;
  label: string;
  icon: React.ReactNode;
  value: string;
  onChange: (v: string) => void;
  type: string;
  autoComplete: string;
  placeholder?: string;
}) {
  return (
    <label htmlFor={id} className="block">
      <span className="text-[13px] text-muted">{label}</span>
      <div className="mt-1.5 relative">
        <span className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
          {icon}
        </span>
        <input
          id={id}
          type={type}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full h-12 pl-10 pr-3.5 rounded-xl bg-white border border-line text-[15px] focus:outline-none focus:border-ink/40 transition"
        />
      </div>
    </label>
  );
}
