# Hosted replay: deployment

The hosted demo is a **replay**. It shows the saved answers of one benchmark run in the same page
as the local web demo. A visitor chooses one of the development questions and sees its saved
answer. Nothing can be asked: the page makes no model call, and no API key exists anywhere in it.
The page says so at the top: "Replay of saved answers generated on <date> with <model>. No live
model calls."

## Recommendation: a static export, served as a Hugging Face static Space

`python -m src.web_replay` writes a folder of five files: `index.html`, `app.css`, `app.js`,
`replay.json` and `README.md`. Any static host can serve that folder. On Hugging Face, it becomes
a Space with the **Static** SDK.

Reasons to prefer the static export over a Space that runs the Python server:

- **Nothing to run.** A replay serves fixed files. A server Space would need:
  - a Docker image;
  - a public port;
  - a process that sleeps and cold-starts.

  None of that adds anything to a replay.
- **No secret and no spend.** The site holds no key, so nothing can leak and no visitor can spend
  API credit.
- **No new attack surface.** The local server's protections (Host and Origin checks, 127.0.0.1
  only) are designed for a local process. A public server would need them reworked. A static host
  serves files and nothing else.
- **Portable.** The same folder works on GitHub Pages, Netlify or any web server.
- **Same rendering.** The replay runs the live page's own code, `app.js`. Visitors see an answer
  exactly as the local demo shows it.

## Steps

1. **Export** (local; needs the recorded corpus build, as the local demo does):

   ```powershell
   .\.venv\Scripts\python.exe -m src.web_replay
   .\.venv\Scripts\python.exe -m src.web_replay --run data\evaluation\answers-v0\runs\<run-id>
   ```

   - **Defaults:** the dev questions (a01–a12), and the most recent saved run that has all of
     them.
   - **Output:** `dist/replay/`, which git ignores.
   - **Sources' status:** each source's status comes from the corpus build. The export refuses a
     run made on a different build.
2. **Preview:**

   ```powershell
   .\.venv\Scripts\python.exe -m http.server --bind 127.0.0.1 --directory dist\replay 8001
   ```

   Open http://127.0.0.1:8001/. The only requests should be for the page's own files.
3. **Create the Space.** On huggingface.co, choose *New Space*, set the SDK to **Static**, and
   pick a name and a visibility. Private is fine while you check it.
4. **Upload the five files** from `dist/replay/`. Either:
   - **In the browser:** *Files* → *Add file* → *Upload files*.
   - **With git:**

     ```powershell
     git clone https://huggingface.co/spaces/<user>/<space> hf-space
     Copy-Item dist\replay\* hf-space\
     cd hf-space; git add .; git commit -m "Replay of run <run-id>"; git push
     ```

     Git asks for a Hugging Face access token with write permission. That token belongs to your
     Hugging Face account. Keep it out of this repository and out of its `.env`.

   The exported `README.md` is the Space's card: its front matter sets `sdk: static` and
   `app_file: index.html`. It replaces the default card.
5. **Update.** After a new run, export again and upload the files again. The label names the
   new run's date and model.

## What is published

`replay.json` holds, for each question, the saved `AnswerResult.to_dict()`, plus the two fields
the live server adds: each source's status and the qualifications as displayed. That includes:

- the question;
- the model's analysis;
- the evidence texts:
  - GDPR provisions, from the Official Journal;
  - Privacy Code excerpts, from the unofficial user transcription, labelled as such on the page;
- the claims with their quotations;
- the model notes.

It holds no prompt, no raw model reply and no key. Twelve answers come to about 0.7 MB.

The page carries a Content-Security-Policy (`default-src 'self'`). The policy cannot set
`frame-ancestors`, because a `<meta>` tag cannot. That suits Hugging Face, which shows a Space
inside a frame.
