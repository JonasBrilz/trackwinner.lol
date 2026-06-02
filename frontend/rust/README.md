# trackwinner-frontend-rs

A **Rust/WebAssembly port of the trackwinner.lol app**, built with **Leptos (CSR)**.
It reproduces the full demo flow as a client-side WASM SPA (client-side routed) that reads
the `Mock.json` fixture in the browser:

```
/         login  (fake — accepts anything, stores username in sessionStorage)
/home     conversion-rate setup + "Start analysis"
/analyse  the computing animation (3-node pipeline, live "thinking" steps) → auto-advances
/report   the AI-visibility revenue report
```

## Why a rewrite?

The original is a Next.js 15 / React 19 app deployed as a **standalone Node server** on Cloud Run,
so every instance carries a Node runtime (~80–150 MB resident). This port compiles to a **static
bundle** — `index.html` + one `.wasm` + one `.css` — with **no server runtime at all**:

| | Next.js (Node standalone) | Leptos CSR (this) |
|---|---|---|
| Server runtime | Node process per instance (~80–150 MB) | **none** — static file host (~0) |
| Deploy artifact | `.next/standalone` + node_modules | `dist/`: html + wasm + css |
| Payload | React + framer-motion + hydration JS | **~493 KB wasm (178 KB gzip)** + 25 KB css |

Because it's pure static output, you can host it on any CDN/object store/`nginx` — there's no
server process to consume memory.

## What's ported

The login screen, the home setup page, the **computing animation**, and the report — wired together
with `leptos_router`. The report, faithfully:

- **Data + accessors** (`src/data.rs`) — Rust port of `lib/peec.ts`: the `PeecRoot`/`EnhancedFinalReport`
  model and every helper (`formatEuro`, `formatPct`, `formatUsdRange`, `allPromptsByLift`,
  `competitorsRanked`, `lowestVisibilityPrompts`, `paidMediaOpportunities`, `hostnameOf`,
  `classificationLabel`, `buildMedia`). The fixture is embedded with `include_str!` and parsed client-side.
- **Components** (`src/main.rs`) — `Header`, `Hero`, `PaidMedia` + `MediaCard`, `VisibilityGap` + `Bar`,
  `InvisibleCallout` (animated count-up), `Competitive`, `PromptsTable` (expandable rows), `Methodology`,
  `CTA`, `BrandMark`.
- **Interactivity** — the paid-media card state machine (estimate → sending → received → accepted),
  `localStorage` persistence (same `peec.paidmedia.state.v1` key + format), `mailto:` outreach,
  `window.print()` export, and expandable prompt detail rows. Built on Leptos signals.
- **Styling** — the same Tailwind theme (`canvas`/`ink`/`muted`/`line`/`accent`/`gain`, Inter font) and
  the `globals.css` dot-grid + print stylesheet. framer-motion entrance animations are replaced with
  equivalent CSS (`.enter` fade/slide + animated bar fills).
- **Icons** (`src/icons.rs`) — the lucide icons used by the page, inlined as SVG (no JS icon lib).

## Build & run

Needs the WASM target and [Trunk](https://trunkrs.dev) (Trunk auto-installs `wasm-bindgen` and the
`tailwindcss` standalone CLI on first build):

```bash
rustup target add wasm32-unknown-unknown
cargo install trunk      # or grab a prebuilt binary

trunk serve              # dev server with autoreload at http://127.0.0.1:8080
trunk build --release    # → dist/  (static; deploy anywhere)
```

Serve the release output with anything static:

```bash
python3 -m http.server -d dist 8090   # or nginx, S3, Cloudflare Pages, …
```

## Layout

```
index.html            Trunk entry (links wasm + tailwind-css + Inter)
tailwind.config.js    theme (scans src/**/*.rs for classes)
styles/input.css      @tailwind + globals (dot-grid, print, entrance anims)
data/Mock.json        embedded demo fixture (shape = EnhancedFinalReport)
src/
├── main.rs           Router + Login / Home / Analyse / Report pages + all components
├── data.rs           data model + peec.ts helpers
└── icons.rs          inlined lucide icons
```

> Ported routes: `/` (login), `/home`, `/analyse` (computing animation), `/report`, plus the
> `/auswertung → /report` redirect. The `/content-plan` route is not ported.
