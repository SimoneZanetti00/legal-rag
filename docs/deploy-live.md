# Live demo on Hugging Face: deployment

The live demo is a separate Space, **legal-rag-live**, built with the **Docker** SDK. Visitors type
their own questions, and the questions go to Anthropic's API. The replay Space
(`legal-rag-demo`) stays as it is and is the fallback: whenever a limit is reached, the live page
links to it.

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

**Counters live in memory.** They reset when the Space restarts or rebuilds: after a settings
change, an upload or a crash. The hard backstop is the **monthly spend limit in your Anthropic
Console** (Settings → Limits). Set it before going public.

**Visitors.** A visitor is the last address in `X-Forwarded-For`, which the proxy in front of the
Space appends.
- A client can add addresses in front of it, but not change it.
- If Hugging Face ever put two proxies in front, every visitor would share one counter: stricter,
  not looser.
- The address is kept only as a keyed hash, in memory.

**Nothing personal is logged.** The server logs method, path and status, plus one line per
question with the day's count and spend. It never logs the question or the address.

**The page states** that questions and the retrieved provisions are sent to Anthropic's API, and
that they should not contain personal data. Visitors also tick the research-mode confirmation
before asking.

**Framing.** Only `huggingface.co` may frame the page, as the Space page does; no other site may.

## Settings (in the Space, never in a file)

In the Space, open **Settings → Variables and secrets**:

| Name | Kind | Value |
|---|---|---|
| `ANTHROPIC_API_KEY` | **New secret** | An API key from the Claude Console. Prefer a key used for this Space only, so that you can revoke it alone. |
| `LLM_PROVIDER` | **New variable** | `anthropic` |
| `LLM_MODEL` | **New variable** | `claude-sonnet-5-5` |

Docker Spaces receive secrets and variables as environment variables when the container runs. A
change restarts the Space. Nothing else needs setting: every other setting has a default (see
`.env.example`).

## Deploy

1. **Assemble the Space folder** (on the machine that has the corpus build):

   ```powershell
   .\.venv\Scripts\python.exe deploy\live-space\prepare.py
   ```

   It writes `dist\live-space\`: 59 files, 4.2 MB.
   - `Dockerfile`, `README.md` (the Space card), `NOTICE.md` (sources, attribution and
     licences) and `requirements.txt`.
   - `src\`: 43 files of code and the page.
   - `data\`: exactly the 12 files the live path reads. These are the recorded build with its
     anchors, the instrument registry, the two inventories and the review ledger. There are no
     source PDFs.

2. **Create the Space.** On huggingface.co, choose **New Space**, then:
   - name: `legal-rag-live`;
   - SDK: **Docker**, template **Blank**;
   - hardware: the free **CPU basic**;
   - visibility: **Public**, or Private until you have tried it.

3. **Set the secret and the two variables** as above, before uploading, so that the first build
   starts with them.

4. **Upload the contents of `dist\live-space\`.** In the Space, choose **Files → Add file → Upload
   files**. Drag the four files and the two folders `src` and `data` onto the page, and commit.
   - Check the commit preview: the paths must read `src/web_demo.py`,
     `data/processed/builds/…` and `data/reference/…`.
   - If the uploader drops the folder structure, use git instead:

     ```powershell
     git clone https://huggingface.co/spaces/SimoneZanetti00/legal-rag-live hf-live
     Copy-Item -Recurse -Force dist\live-space\* hf-live\
     cd hf-live; git add .; git commit -m "Live demo"; git push
     ```

     Git asks for a Hugging Face access token with write permission. No file is over 10 MB, so Git
     LFS is not needed.

5. **Watch the build.** The Space builds the image, then shows its logs. The last lines should read
   `Legal RAG live demo (public): listening on 0.0.0.0:7860` followed by the limits.

6. **Try one question.** The log then shows
   `live: 1 question(s) today, $0.0… of $1.50 spent`. A typical question costs about $0.05
   (local smoke test, 2026-11-24: $0.047).

**To update**, run step 1 again and upload the files that changed; the Space rebuilds.

**To stop spending at once**, delete the `ANTHROPIC_API_KEY` secret, or pause the Space. Every
question then fails, with no cost.

## What a public Space exposes

The Space's files are public with the Space. That includes `data/processed/…/corpus.jsonl`, the
full extracted text of both acts:
- the GDPR, as published in the Official Journal;
- the Privacy Code, from the **unofficial transcription** supplied by the user.

Its PDF is not uploaded, but its text is. The page and the source status mark the transcription
as unofficial and unverified.

`NOTICE.md`, linked from the Space card, gives:
- the EUR-Lex attribution (CC BY 4.0);
- the Normattiva formula («testo non autentico e gratuito»);
- the statement that the Privacy Code text is an unverified user transcription;
- the software licences. PyMuPDF is AGPL-3.0 and is imported by the corpus code at run time, so
  the card links the public source repository.
