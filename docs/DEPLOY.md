# Deployment

Two-service split: the **backend** (FastAPI + LangGraph + SQLite) runs on
Hugging Face Spaces using the Docker SDK; the **frontend** (Next.js 15)
runs on Vercel. Everything that's bundled into the HF image, every
environment variable that needs to be set, and the small CORS knob to
let Vercel preview URLs through, is described here.

If you're looking for *why* the backend can't be deployed as the bare
`backend/Dockerfile`, the comment at the top of the repo-root
[`Dockerfile`](../Dockerfile) is the canonical answer.

---

## Backend → Hugging Face Spaces (Docker SDK)

### 1. Create the Space

1. <https://huggingface.co/new-space> → **Docker** SDK, blank template.
2. Pick a hardware tier. The free CPU basic tier works for the mock
   provider and Gemini Flash. Don't enable persistent storage unless
   you actually need claim history to survive restarts (see
   [Persistent storage](#persistent-storage) below).
3. Clone the empty Space:
   ```bash
   git clone https://huggingface.co/spaces/<user>/<space>.git hf-space
   ```

### 2. Push this repo to the Space

The repo-root `Dockerfile`, `README.md` YAML front-matter, and
`.dockerignore` are wired up so the Space builds straight from a copy
of this repo — no separate "deployment branch" needed.

```bash
cd hf-space
git remote add upstream /path/to/this/repo  # or your GitHub fork
git pull upstream main --allow-unrelated-histories
git push origin main
```

Spaces will detect the `Dockerfile`, build, and serve on `app_port: 7860`
(declared in the README front-matter). First build takes ~3–5 minutes.

### 3. Set the Space secrets / variables

In the Space's **Settings → Variables and secrets**:

| Key | Type | Value |
| --- | --- | --- |
| `CORS_ORIGINS` | Variable | `https://<your-vercel-app>.vercel.app` (comma-separated for multiple) |
| `CORS_ORIGIN_REGEX` | Variable (optional) | `^https://<your-vercel-app>(-[a-z0-9-]+)?\.vercel\.app$` — lets every Vercel **preview** URL through too |
| `LLM_PROVIDER` | Variable | `mock` (default) or `gemini` |
| `GEMINI_API_KEY` | **Secret** | only required if `LLM_PROVIDER=gemini` |

Defaults baked into the image already cover the rest
(`DATABASE_URL=sqlite+aiosqlite:////tmp/claims.db`,
`POLICY_TERMS_PATH=/policy/policy_terms.json`, etc.). Override them
only if you've changed the Dockerfile layout.

### 4. Verify

```bash
curl https://<user>-<space>.hf.space/health
# → {"status":"ok","llm_provider":"mock"}

curl https://<user>-<space>.hf.space/api/policy | head -c 200
```

### Persistent storage

The defaults write `claims.db` to `/tmp`, which is wiped on every
container restart (sleep, redeploy, hardware change). That's fine for
demos — every claim is reprocessable from the inputs you sent. If you
need to keep the eval/audit history:

1. Enable **persistent storage** in the Space hardware settings (paid).
2. Override the env var: `DATABASE_URL=sqlite+aiosqlite:////data/claims.db`.

### Cold starts

Free Spaces sleep after ~48h of inactivity. The first request after a
sleep takes ~30–60s while the container wakes. The frontend's
`apiFetch` doesn't currently render a "waking up" state — consider
adding one if cold-start UX matters for your demo.

---

## Frontend → Vercel

### 1. Import the repo

In Vercel, **Add New → Project**, pick the GitHub repo, and set the
**Root Directory** to `frontend/`. Vercel auto-detects Next.js 15;
leave the build command, output directory, and install command at
their defaults.

### 2. Set environment variables

| Key | Environment | Value |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | Production + Preview + Development | `https://<user>-<space>.hf.space` |

This is baked at build time (because of the `NEXT_PUBLIC_` prefix), so
any change requires a redeploy.

If you don't want the dev-only "simulate component failure" checkbox in
the production submit form, also set:

| `NEXT_PUBLIC_DEV_MODE` | Production | `false` |

### 3. Deploy

`git push` to the branch you set as Production. Vercel builds in ~2
minutes. Visit the production URL; the form should populate from the
HF backend's `/api/members` and `/api/policy` calls.

---

## Sanity checklist before going live

- [ ] HF Space build succeeded; `/health` returns `200`.
- [ ] `CORS_ORIGINS` (and/or `CORS_ORIGIN_REGEX`) includes the Vercel
      production URL exactly — no trailing slash, scheme matters.
- [ ] Vercel `NEXT_PUBLIC_API_URL` points at the HF URL (no trailing
      slash, scheme matters).
- [ ] If you're using Gemini, `GEMINI_API_KEY` is set as a **Secret**,
      not a Variable, and `LLM_PROVIDER=gemini`.
- [ ] You're aware that `/tmp/claims.db` is ephemeral unless you opted
      into persistent storage.

---

## What did *not* change in this repo for HF support

The existing local-dev flow is untouched:

- `make dev` / `docker-compose up` still use `backend/Dockerfile` with
  the bind-mounted JSON files.
- `pytest` still reads `policy_terms.json` from the repo root via
  `Settings()` defaults.
- The frontend's `npm run dev` still talks to `http://localhost:8000`.

The only runtime change to the backend code is the new optional
`CORS_ORIGIN_REGEX` setting — when unset, CORS behaves exactly as it
did before.
