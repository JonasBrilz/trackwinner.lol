FROM python:3.13-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY . .
RUN uv sync --no-dev
EXPOSE 8080
CMD uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
