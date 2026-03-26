# ── Stage 1: Build ──────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml .
COPY codevista/ codevista/

RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Runtime ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 codevista \
    && useradd --uid 1000 --gid codevista --shell /bin/sh --create-home codevista

COPY --from=builder /install /usr/local

WORKDIR /workspace
RUN chown codevista:codevista /workspace
USER codevista

ENTRYPOINT ["codevista"]
CMD ["--help"]
