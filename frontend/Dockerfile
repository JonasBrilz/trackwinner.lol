# Build the Leptos (Rust/WASM) frontend to a static bundle, then serve it with
# nginx. Replaces the old Next.js/Node image — no Node runtime, ~static memory.

FROM rust:1-bookworm AS builder
WORKDIR /app
RUN rustup target add wasm32-unknown-unknown \
 && curl -sSL https://github.com/trunk-rs/trunk/releases/download/v0.21.7/trunk-x86_64-unknown-linux-gnu.tar.gz \
    | tar -xzf - -C /usr/local/bin
COPY . .
# Trunk auto-fetches wasm-bindgen + the tailwindcss standalone CLI on first build.
RUN trunk build --release

FROM nginx:alpine AS runner
# Cloud Run routes to port 8080; serve the SPA with a fallback to index.html
# so client-side routes (/home, /analyse, /report) resolve on hard loads.
RUN printf 'server {\n  listen 8080;\n  root /usr/share/nginx/html;\n  location / {\n    try_files $uri $uri/ /index.html;\n  }\n}\n' \
    > /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
