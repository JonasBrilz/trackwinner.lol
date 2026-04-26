import { NextRequest } from "next/server";
import { API_BASE_URL } from "@/lib/peec";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

export async function GET(req: NextRequest) {
  const upstream = `${API_BASE_URL}/roi/full-analysis?${req.nextUrl.searchParams.toString()}`;
  const res = await fetch(upstream, {
    cache: "no-store",
    signal: req.signal,
  });
  return new Response(res.body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}
