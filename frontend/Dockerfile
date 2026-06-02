# Build the Leptos (Rust/WASM) frontend to a static bundle, then serve it with
# static-web-server — a tiny single-binary static server (scratch-based image).
# No Node, no nginx; idles at a few MB on Cloud Run.

FROM rust:1-bookworm AS builder
WORKDIR /app
RUN rustup target add wasm32-unknown-unknown \
 && curl -sSL https://github.com/trunk-rs/trunk/releases/download/v0.21.7/trunk-x86_64-unknown-linux-gnu.tar.gz \
    | tar -xzf - -C /usr/local/bin
COPY . .
# Trunk auto-fetches wasm-bindgen + the tailwindcss standalone CLI on first build.
RUN trunk build --release

# static-web-server's official image is built FROM scratch (tiny). It reads its
# config from SERVER_* env vars, so the entrypoint stays the image default.
FROM ghcr.io/static-web-server/static-web-server:2 AS runner
ENV SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8080 \
    SERVER_ROOT=/public \
    # SPA fallback: any unknown path returns index.html (200) so the client-side
    # router resolves /home, /analyse, /report on hard loads — behaviour identical
    # to the old nginx try_files setup.
    SERVER_FALLBACK_PAGE=/public/index.html
COPY --from=builder /app/dist /public
EXPOSE 8080
