# Deploying Clausewise

API on Fly, web on Vercel. About twenty minutes end to end.

The order matters and it is circular: the web app needs the API's URL at **build**
time, and the API needs the web app's URL for CORS. So it goes API → web → back to
the API once, to close the loop.

Prerequisites: [`flyctl`](https://fly.io/docs/flyctl/install/) and
[`vercel`](https://vercel.com/docs/cli) installed and logged in
(`fly auth login`, `vercel login`).

---

## 1. API → Fly

```bash
cd apps/api

# Creates the app without deploying — fly.toml is already written, so decline
# any offer to generate one or to add a database.
fly launch --no-deploy --copy-config --name clausewise-api --region lhr

fly secrets set \
  ANTHROPIC_API_KEY="sk-ant-..." \
  GROQ_API_KEY="gsk_..." \
  LLM_PROVIDER="anthropic" \
  LLM_FALLBACK_PROVIDERS="groq" \
  ALLOWED_ORIGINS="http://localhost:3000"

fly deploy
fly status          # expect exactly one machine, started
curl https://clausewise-api.fly.dev/health
```

`{"status":"ok","environment":"production"}` means you are up. Note the URL.

**Do not scale this app.** `fly.toml` pins it to one always-on machine, and the
comment at the top of that file explains why: results live in the worker's memory
and an upload spans two requests, so a second machine serves polls for an analysis
it has never heard of, and auto-stop kills background work after the 202 has
already gone out. Both constraints lift the moment the repository is backed by
Postgres or Redis.

---

## 2. Web → Vercel

From the repo root, not `apps/web` — this is a pnpm workspace and Vercel needs to
see `pnpm-lock.yaml`.

```bash
vercel link          # create a new project when asked
```

Then set the project's **Root Directory** to `apps/web` (Vercel → Settings →
General). Framework and build commands are detected from there; leave them alone.

```bash
vercel env add NEXT_PUBLIC_API_URL production
# paste: https://clausewise-api.fly.dev   (no trailing slash)

vercel --prod
```

> `NEXT_PUBLIC_*` is **inlined at build time**, not read at runtime. Changing the
> API URL later means a redeploy, not just an env var edit — a restart will not
> pick it up.

---

## 3. Close the CORS loop

The API is still only accepting `localhost:3000`, so the deployed site cannot call
it. Point it at the real domain:

```bash
cd apps/api
fly secrets set ALLOWED_ORIGINS="https://clausewise-henna.vercel.app"
```

Setting a secret restarts the machine on its own — no redeploy needed.

The production domain is `clausewise-henna.vercel.app`. **Preview deployments get a fresh URL every
time and will be blocked by CORS**, which is correct rather than broken: the
alternative is a wildcard origin on an endpoint that spends money on every call.
If you want previews working, add them explicitly:

```bash
fly secrets set ALLOWED_ORIGINS="https://clausewise-henna.vercel.app,https://clausewise-git-main-ihemz.vercel.app"
```

---

## 4. Check it end to end

Open the site and upload `apps/api/evals/contracts/saas-msa.pdf`. You should see
the 202 land immediately with the contract text readable, the clause counter climb,
findings appear as they are found, then the results split.

If something is off:

```bash
fly logs                      # live
fly logs | grep llm_usage     # per-call provider, tokens, cost
fly logs | grep provider_failover
```

| Symptom | Cause |
| --- | --- |
| Upload fails instantly, browser console shows a CORS error | Step 3 not done, or the domain does not match exactly |
| Counter starts, then the analysis never finishes | Provider credit exhausted — `fly logs \| grep -i "unavailable"` |
| Polling 404s intermittently | More than one machine. `fly scale count 1` |
| "No model provider is configured" | Secrets missing — `fly secrets list` |
| Results vanish after a while | Expected. In-memory, 100-entry cap, and a deploy wipes them |

---

## What this deployment does not do

Worth knowing before it goes in front of anyone:

- **Results do not survive a restart or a deploy.** Storage is a bounded
  in-memory dict. A shared link works until the next deploy, then 404s.
- **There is no auth and no rate limit.** Anyone with the URL can spend your
  provider credit. Fine for a demo you control the link to; not fine indexed.
  Fly's `[http_service]` can front this with a firewall rule, or put the API
  behind a token if the link goes anywhere public.
- **Uploads are capped at 15MB** in `core/extraction.py`, and Fly's proxy will
  refuse considerably larger bodies before that check runs.
- **One machine means one point of failure.** A crash is a few seconds of
  downtime while Fly restarts it, and any in-flight analysis is lost.

None of these are hard to fix; all of them are deliberate for a demo whose point
is the grounding, not the infrastructure.

---

## Cost

One `shared-cpu-1x` / 512MB machine, always on, is roughly **$3–4 per month**. It
cannot be cheaper without auto-stop, and auto-stop is what breaks the background
analysis — see step 1.

Model calls are the real cost and they scale with use, not uptime. `fly logs |
grep llm_usage` gives per-call tokens and an estimated USD figure.
