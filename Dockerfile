# syntax=docker/dockerfile:1.6
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS builder

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY src ./src
COPY README.md ./README.md

RUN useradd --create-home --uid 10001 app \
    && chown -R app:app /app /opt/venv
USER app

ENTRYPOINT ["rob2"]
CMD ["-h"]
