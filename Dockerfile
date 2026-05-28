# Hugging Face Spaces image (Docker SDK).
#
# Why this lives at the repo root and not in backend/:
#
#   - HF Spaces (Docker SDK) reads ./Dockerfile from the Space repo root
#     and exposes the port declared in README.md's YAML front-matter
#     (`app_port: 7860`). 7860 is also the Spaces default — keep them
#     in sync if you change one.
#   - The pipeline needs `policy_terms.json`, `policy_rules.json`, and
#     `test_cases.json`, which live at the repo root (one source of
#     truth for both docker-compose and the local dev flow). The
#     existing backend/Dockerfile uses ./backend as build context and
#     can't reach those files; this Dockerfile uses the repo root so
#     it can bundle them into the image. docker-compose still uses
#     backend/Dockerfile and is unaffected.
#   - Spaces' rootfs is read-only except /tmp (and /data with paid
#     persistent storage). We default DATABASE_URL to /tmp so the
#     SQLite write at first request succeeds. Each container restart
#     wipes this — switch to /data + persistent storage if you need
#     the eval history to survive restarts.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LLM_PROVIDER=mock \
    DATABASE_URL=sqlite+aiosqlite:////tmp/claims.db \
    POLICY_TERMS_PATH=/policy/policy_terms.json \
    POLICY_RULES_PATH=/policy/policy_rules.json \
    TEST_CASES_PATH=/policy/test_cases.json \
    LOG_LEVEL=INFO \
    CORS_ORIGINS=http://localhost:3000

WORKDIR /app

# Install Python deps first so this layer caches across source-only edits.
COPY backend/pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

# Application source.
COPY backend/ /app/

# Policy + fixture data, bundled (not bind-mounted as in docker-compose).
RUN mkdir -p /policy
COPY policy_terms.json policy_rules.json test_cases.json /policy/

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
