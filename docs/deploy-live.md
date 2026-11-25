# Live demo on Render: deployment

The live demo is a **Render free web service** built from this GitHub repository with the
Blueprint in [render.yaml](../render.yaml). Visitors type their own questions, and the questions
go to Anthropic's API. The replay Space on Hugging Face (`legal-rag-demo`) stays as it is and is
the fallback: whenever a limit is reached, the live page links to it.

## How it runs

| | |
|---|---|
| Python | 3.13, from [.python-version](../.python-version). A `PYTHON_VERSION` environment variable would override it, and must then be a full version such as `3.13.5`. Render's own default for new services is 3.14. |
| Build command | `pip install -r deploy/live-space/requirements.txt`: the live demo's dependencies only (anthropic, rank-bm25, numpy, PyMuPDF, python-dotenv). No torch and no test runner. |
| Start command | `python -m src.web_demo --public --port $PORT`: the project's own server, on 0.0.0.0 and the port Render provides (10000 by default). |
| Health check | `GET /api/health` |
| Files read at run time | All tracked in the repository: `src/` (code and page), `data/reference/` (the instrument registry, two inventories and the review ledger), and the recorded build `data/processed/builds/build-f76ff6031f2fc82c4852f0a2bde27807/`. |

**The build is tracked for this deployment.** `.gitignore` excepts it, and `.gitattributes`
stores it byte for byte (`-text`), because its files are recorded by hash. No preparation step is
needed.

## What the live demo enforces (in code)

`python -m src.web_demo --public` enforces the following (`src/web_demo.py`,
`src/live_limits.py`):

| Protection | Value |
|---|---|
| Mode | Research only, with its notice; a verified-mode request is refused |
| Question length | At most 300 characters |
| Per visitor | 3 questions per rolling hour, 10 per UTC day |
| All visitors | 40 questions per UTC day |
| Spend | $1.50 per UTC day |

**How the spend cap works.**
- The spend is the token usage the API reports for every reply, priced at the list prices in
  `src/llm.py`.
- A question is refused when the spend so far plus the most expensive question so far today (at
  least $0.10) could exceed the cap.
- Failed questions count too.

**When a limit is reached**, the API answers HTTP 429, and the page says which limit it was and
links to the replay.

**Nothing personal is logged.** The server logs method, path and status, plus one line per
question with the day's count and spend. It never logs the question or the address.

**The page states** that questions and the retrieved provisions are sent to Anthropic's API, and
that they should not contain personal data. Visitors also tick the research-mode confirmation
before asking.

## The free plan: sleep, restarts and counters

Per Render's documentation for free web services:
- **Sleep.** The service spins down after 15 minutes without inbound traffic. The next visitor
  waits about a minute while it spins up, and Render shows a loading page meanwhile.
- **Restarts.** Render may restart a free service at any time. The filesystem is ephemeral.
- **Hours.** Each workspace gets 750 free instance hours per month; when they run out, free
  services are suspended until the next month.

**The counters live in memory, so every spin-down, restart and redeploy resets them,
including the daily spend cap.** The per-visitor counts and the 40-question limit start again
too. The $1.50 cap therefore bounds the spend between two restarts, not the spend of a calendar
day. A service woken several times a day can spend $1.50 after each wake-up.

**The backstop is the monthly spend limit in your Anthropic Console** (Settings → Limits).
- Set it before going public, at the most you accept to lose in a month.
- Use an API key made for this service only, so that you can revoke it alone.

## Visitors and the client address

**What the docs say.** Render's documentation does not say what `X-Forwarded-For` contains for a
web service. It says only that Render's load balancer terminates TLS, and that Cloudflare
provides DDoS protection.

**How the server counts a visitor.** It uses the header named by `LIVE_CLIENT_IP_HEADER`
(render.yaml: `CF-Connecting-IP`, as observed below):
- for `X-Forwarded-For`, the **last** entry, the one appended by the proxy closest to the server.
  A client can add entries in front of it, but not change it;
- for any other header, its whole value.

The address is kept only as a keyed hash, in memory.

**Check it once the service is live**, with `GET /api/visitor`. It returns the visitor key, the
header used, whether that header was present, the number of `X-Forwarded-For` entries, and which
forwarding headers arrived. It never returns an address.

1. **Same browser:** open `https://<service>.onrender.com/api/visitor` twice. The `visitor` key
   must be the same both times.
2. **Another network:** open it from a phone on mobile data, not Wi-Fi. The key must differ.
3. **Spoofing:** from a terminal, run:

   ```powershell
   curl.exe -H "X-Forwarded-For: 203.0.113.99" https://<service>.onrender.com/api/visitor
   ```

   Then run the same command without the `-H` part. The key must not change: a client-supplied
   entry must not move the count.

**If step 1 gives a different key on each request** (the last entry is a changing proxy address),
or **step 2 gives the same key** (every visitor looks alike):
1. Look at `forwarding_headers` in the reply.
2. Set `LIVE_CLIENT_IP_HEADER` to the header that carries the client's address, for example
   `True-Client-IP`, in the service's **Environment** page. The service restarts.
3. Repeat the three checks.

The global limits hold in every case: 40 questions and $1.50 between restarts.

**What we observed on Render** (`legal-rag-live.onrender.com`, 2026-11-24 and 2026-11-25):
- Requests arrive with **3 `X-Forwarded-For` entries**, and with **`True-Client-IP`** and
  **`CF-Connecting-IP`**.
- **The last `X-Forwarded-For` entry is not the client.** With the default setting, the same PC
  got different visitor keys from the browser and from curl.
- **`CF-Connecting-IP` is.** With `LIVE_CLIENT_IP_HEADER=CF-Connecting-IP`, the startup log
  reads "visitors counted by CF-Connecting-IP", and the key is stable for one PC.
- **Forged headers do not move the count.** A request with a forged `X-Forwarded-For` entry or a
  forged `True-Client-IP` header keeps the same key. A request that sends its own
  `CF-Connecting-IP` is rejected by Cloudflare (error 1000) before it reaches the service.

render.yaml therefore sets `LIVE_CLIENT_IP_HEADER=CF-Connecting-IP`, so the setting survives
Blueprint syncs.

## Settings

The Blueprint sets `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-sonnet-5-5` and
`LIVE_CLIENT_IP_HEADER=CF-Connecting-IP`.

`ANTHROPIC_API_KEY` is declared with `sync: false`:
- Render asks for its value once, when the Blueprint is created. It is never in the repository.
- To change it later, open the service's **Environment** page in the dashboard. Render does not
  re-prompt on later Blueprint syncs.

Every other setting has a default (`.env.example`).

## Deploy

The click-by-click steps on the Render website:

1. **Sign in.** Go to https://dashboard.render.com and sign in with GitHub, or connect GitHub from
   **Account Settings → GitHub** if you signed up another way. Give Render access to the
   `legal-rag` repository.
2. **Start a Blueprint.** Click **New +** (top right), then **Blueprint**.
3. **Connect the repository.** Choose `SimoneZanetti00/legal-rag`, and click **Connect**.
4. **Choose the branch.**
   - The live demo is on `feature/real-legal-corpus-trial` until it is merged into `main`.
   - Select that branch in the branch selector. Leave the Blueprint path as `render.yaml`.
5. **Name the Blueprint**, for example `legal-rag`.
   - Render reads `render.yaml` and lists one web service, `legal-rag-live` (Python, Free,
     Frankfurt).
   - Render asks for the value of `ANTHROPIC_API_KEY`. Paste the key made for this service.
6. **Apply.** Click **Apply** (or **Deploy Blueprint**). Render creates the service and starts the
   first build.
7. **Watch the deploy.** Open the service **legal-rag-live**, then **Logs**.
   - The build ends with pip installing the requirements.
   - The run starts with `Legal RAG live demo (public): listening on 0.0.0.0:10000`, followed by
     the limits.
   - The service becomes **Live** once `/api/health` answers.
8. **Open the service.** Use the URL at the top of the service page,
   `https://legal-rag-live….onrender.com`. The page shows the live-demo notice and research mode
   only.
9. **Check the visitor key** as described in "Visitors and the client address".
10. **Ask one question.** The log then shows `live: 1 question(s) today, $0.0… of $1.50 spent`. A
    typical question costs about $0.05 (local smoke test, 2026-11-24: $0.047).

**To update**, push to the branch: `render.yaml` sets `autoDeployTrigger: commit`.

**To stop spending at once**, do either of the following; every question then fails, at no cost:
- delete `ANTHROPIC_API_KEY` in the service's **Environment** page; or
- open the service's **Settings** and click **Suspend Web Service**.

## What becomes public

The repository now contains the recorded build, including `corpus.jsonl`: the full extracted text
of both acts.
- the GDPR, as published in the Official Journal;
- the Privacy Code, from an **unofficial transcription supplied by the author**, not verified
  against Normattiva or the Gazzetta Ufficiale.

Its PDF is not in the repository. The sources, attribution and licences are in
[deploy/live-space/NOTICE.md](../deploy/live-space/NOTICE.md).

## Earlier attempt: Hugging Face Spaces

`deploy/live-space/` holds the attempt on a Hugging Face Space and is not used by Render:
- `prepare.py`, `app.py` for the Gradio SDK, the Space card, and a Dockerfile.

A Hugging Face Space was not usable for the live demo:
- Docker Spaces are not available on the owner's account.
- Gradio Spaces run on ZeroGPU with Python 3.10, and the code needs 3.11 or later.

Render uses only `deploy/live-space/requirements.txt` from that folder. `NOTICE.md` there gives
the sources of the text in the tracked build. The public mode still lets `huggingface.co` frame
the page; this does no harm on Render.
