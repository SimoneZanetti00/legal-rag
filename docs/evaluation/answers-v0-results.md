# Benchmark answers-v0: results and findings

*All results below are on **candidate expectations, not owner-reviewed** (scope "all rows").
The owner-reviewed scope covers a01–a13 since the owner's review of 2026-11-18 (final
section). Runs are saved under
`data/evaluation/answers-v0/runs/` and re-scored offline with
`python -m src.answer_benchmark_run report --run-id <id>`. Research mode, claude-sonnet-5-5,
build `build-f76ff6031f2fc82c4852f0a2bde27807`.*

## Runs

| Run | Change | Evidence limits | Analysis | Generation and support check |
|---|---|---|---|---|
| `2026-11-17-research-baseline` | none | 5 items / 3,000 tokens | live | live |
| `2026-11-17-research-t6` | evidence selection (T6) | 12 items / 12,000 tokens | replayed from the baseline | live (20 of 20 answered questions: every evidence set changed) |
| `2026-11-17-research-t7-prompt` | query-analysis prompt v3: only the issues asked, at most 4; at most 8 lookups | 12 items / 12,000 tokens | live | live |
| `2026-11-17-research-t7-outcome-rule` | outcome rule, first version (rejected, below) | 12 items / 12,000 tokens | replayed from t7-prompt | replayed (offline: no model call) |
| `2026-11-17-research-t7-outcome-rule-2` | outcome rule, adopted version (below) | 12 items / 12,000 tokens | re-scored from t7-prompt's saved results (`rescore`: outcome only, no model call) | same |
| `2026-11-24-research-repair` | repair pass, dev questions only (last section) | 12 items / 12,000 tokens | replayed from `2026-11-17-final` | generation and first support check replayed; repair calls and the support check of the rewrites live |
| `2026-11-24-research-repair-caveat` | new Art. 33 caveat (application text only) | 12 items / 12,000 tokens | replayed | replayed (offline: no model call) |
| `2026-11-26-repair-v1-before` | none: the baseline for the widening change, on 25 questions (a23–a25 added) | 12 items / 12,000 tokens | a01–a12 replayed offline from `2026-11-24-research-repair-caveat`; a13–a22 replayed from `2026-11-17-final`; a23–a25 live | a13–a22: repair calls live; a23–a25: live |
| `2026-11-26-repair-v2` | repair prompt v2: a quotation may be widened within the same provision (last section) | 12 items / 12,000 tokens | replayed from `2026-11-26-repair-v1-before` | generation and first support check replayed; repair calls and the support check of the rewrites live |
| `2026-11-26-repair-v2-cap350` | widening cap raised to 350 characters (`claim-repair-v2.1`), after the results of `2026-11-26-repair-v2`; a07 and a24 only | 12 items / 12,000 tokens | replayed from `2026-11-26-repair-v1-before` | as `2026-11-26-repair-v2` |

## Stage metrics (22 questions, means over questions with core rows)

| Metric | Baseline | T6 | T7-prompt | T7, rule v1 (rejected) | T7, rule v2 (adopted) |
|---|---|---|---|---|---|
| Issues per question | 4–8 | 4–8 | 1–2 | 1–2 | 1–2 |
| Core recall in candidates | 100% | 100% | 100% | 100% | 100% |
| Core recall in final evidence | 76% | 97% | 99% | 99% | 99% |
| Core recall in main-answer citations | 81% | 95% | 98% | 98% | 98% |
| Outcome matches | 3/22 | 8/22 | 9/22 | 22/22 | 17/22 |
| Claims in the answer / held apart | 175 / 10 | 200 / 10 | 121 / 13 | 121 / 13 | 121 / 13 |
| Claims removed by the checks | 6 | 4 | 2 | 2 | 2 |
| Core rows missing from evidence | 15 (10 `max_items`, 5 excerpt without the unit) | 4 (`reserved_for_search`) | 2 (`max_items`) | 2 (`max_items`) | 2 (`max_items`) |

**Outcome rule, adopted (v2):** `answer` when every issue is covered by a claim of the main
answer rated SUPPORTED by the support check, and the model reported no issue as not or only
partly answered; otherwise `answer_limited`. Held-apart claims and removed claims do not
downgrade an answer by themselves; they stay visible in the result. Before T7 (the original
rule), any of them, or the model's own outcome label, made the answer `answer_limited`.

**Rule v1, rejected:** the same without the model's report. It scored 22/22 because five
answers (a06, a07, a14, a15, a22) became `answer` although the model had reported their only
issue as only partly answered, and the result listed that report under unanswered issues next to
a "complete" outcome. The model's report is the only signal that the evidence missed part of a
question (an overview question, as in a06 and a07, or a part the evidence does not cover), so
discarding it made the outcome claim more than the system knows. v2 keeps it, and the five
return to `answer_limited`: the 17/22 is the honest figure.

The candidate and evidence figures of T6 are deterministic given the replayed analysis. The
citation and outcome figures also include run-to-run variation of the live generation and
support calls; one run of each cannot separate the two.

## Findings

1. **Retrieval is not the bottleneck on this benchmark.** Every core provision is already among
   the candidates (core recall in candidates 100% in both runs), so a better retriever cannot
   raise any metric here. The planned comparison of BM25, hybrid and hybrid+rerank (T7) was
   dropped for this reason. It would need a benchmark whose questions BM25 plus the analysis's
   lookups do not already cover.
2. **Evidence selection was the bottleneck at 5 items / 3,000 tokens.** Ten core rows were
   dropped by the item limit and five fell outside the excerpt chosen for a long article. T6
   removes both causes; the four remaining misses (a06 Arts. 21–22, a07 Arts. 35 and 37) are
   lookups beyond the eight lookup slots left when search adds new articles.
3. **The outcome gap comes from query analysis.** The analysis splits a question into 4–8
   issues, including related obligations the user did not ask about, and the model then
   reports at least one issue as unanswered and returns `answer_limited` itself (10 of 11
   answered dev questions in the baseline). This is addressed in the query-analysis prompt,
   not in retrieval or selection.
4. **Most of the remaining outcome gap was the outcome rule.** With one or two issues per
   question, the 13 wrong outcomes of T7-prompt were answers whose issues had supported claims
   but also a partially supported claim (7), a removed claim (1), or the model's own report that
   the issue was only partly answered (5). Under the adopted rule (v2) the first eight become
   `answer`; the five the model reported as partly answered stay `answer_limited` (17/22). Those
   five are open: a06 and a07 are overview questions; for a14, a15 and a22 the model reported
   part of the question as not answered by the evidence it was given (why has not been
   investigated).
5. **Scorer caveat.** Citation recall counts a quotation whose words also occur inside the
   expected unit, wherever it was quoted from, so it can exceed evidence recall (baseline a14
   and a16).

## Final run: `2026-11-17-final`

**This is a single run. Model variance is not measured.** Every generation and support-check
figure below comes from one sample of each live call, so the differences from T7 combine the
changes and run-to-run variation. Repeated runs were not made, to keep within the budget.

**Configuration**
- **Code:** commit `fa2810a`. The only uncommitted files were three untracked documents
  outside the pipeline.
- **Prompts:** query-analysis-v3, answer-generation-v5 and claim-verification-v3. The support
  check rates each claim against its own quotations.
- **Rules and additions:** outcome rule v2. The T9 qualifications and summary are added by the
  application.
- **Evidence and model:** 12 items / 12,000 tokens, research mode, claude-sonnet-5-5.

**Model calls**
- **Analysis:** all 22 calls replayed from `2026-11-17-research-t7-prompt`. The prompt and
  messages are unchanged.
- **Generation and support check:** 40 live calls, with no retries.

**Cost: $1.08** in total, $0.57 for the 12 dev questions.
- **Tokens:** 309,210 input and 46,266 output (output includes thinking).
- **Prices:** $2 input and $10 output per million tokens.
- **Budget:** $2.50, enforced by `--budget-usd`. It was not reached.

| Question | Split | Outcome | Expected | Match | Core in evidence | Core in citations | Claims in answer / held apart | Cost |
|---|---|---|---|---|---|---|---|---|
| a01 | dev | `answer` | `answer` | yes | 100% | 100% | 7 / 2 | $0.052 |
| a02 | dev | `answer` | `answer` | yes | 100% | 100% | 1 / 1 | $0.027 |
| a03 | dev | `answer` | `answer` | yes | 100% | 100% | 5 / 0 | $0.033 |
| a04 | dev | `answer` | `answer` | yes | 100% | 100% | 7 / 1 | $0.066 |
| a05 | dev | `answer` | `answer` | yes | 100% | 100% | 5 / 2 | $0.044 |
| a06 | dev | `answer_limited` | `answer` | **no** | 86% | 71% | 8 / 1 | $0.091 |
| a07 | dev | `answer_limited` | `answer` | **no** | 89% | 56% | 6 / 4 | $0.094 |
| a08 | dev | `answer` | `answer` | yes | 100% | 100% | 10 / 2 | $0.064 |
| a09 | dev | `abstain` | `abstain` | yes | — | — | 0 / 0 | $0.000 |
| a10 | dev | `answer` | `answer` | yes | 100% | 100% | 5 / 1 | $0.035 |
| a11 | dev | `answer` | `answer` | yes | 100% | 100% | 3 / 1 | $0.036 |
| a12 | dev | `answer` | `answer` | yes | 100% | 100% | 3 / 1 | $0.031 |
| a13 | test | `answer` | `answer` | yes | 100% | 100% | 3 / 0 | $0.028 |
| a14 | test | `answer` | `answer` | yes | 100% | 100% | 5 / 2 | $0.060 |
| a15 | test | `answer_limited` | `answer` | **no** | 100% | 100% | 5 / 1 | $0.053 |
| a16 | test | `answer` | `answer` | yes | 100% | 100% | 7 / 3 | $0.065 |
| a17 | test | `answer` | `answer` | yes | 100% | 100% | 5 / 0 | $0.041 |
| a18 | test | `answer_limited` | `answer_limited` | yes | 100% | 0% | 0 / 3 | $0.033 |
| a19 | test | `abstain` | `abstain` | yes | — | — | 0 / 0 | $0.000 |
| a20 | test | `answer` | `answer` | yes | 100% | 100% | 7 / 4 | $0.083 |
| a21 | test | `answer` | `answer` | yes | 100% | 100% | 3 / 2 | $0.065 |
| a22 | test | `answer_limited` | `answer` | **no** | 100% | 100% | 10 / 2 | $0.081 |

| Metric (22 questions) | T7, rule v2 | Final |
|---|---|---|
| Core recall in candidates | 100% | 100% |
| Core recall in final evidence | 99% | 99% |
| Core recall in main-answer citations | 98% | 91% |
| Outcome matches | 17/22 | 18/22 |
| Claims in the answer / held apart | 121 / 13 | 105 / 33 |
| Claims removed by the checks | 2 | 4 (`unsupported_reference`) |
| Core rows missing from evidence | 2 (`max_items`) | 2 (`max_items`: a06 Art. 22, a07 Art. 34) |

**Owner-reviewed scope (a01–a13).** The owner reviewed these questions and their rows on
2026-11-18, with a second opinion from an AI assistant (Claude, claude.ai) on each row; the
decisions are the owner's. All rows were accepted as drafted, and GDPR Art. 34(4) was added to
a03 as supporting. Re-scored offline, with no model call:

| Owner-reviewed scope (13 questions) | Baseline | T6 | T7-prompt | T7, rule v2 | Final |
|---|---|---|---|---|---|
| Core recall in candidates | 100% | 100% | 100% | 100% | 100% |
| Core recall in final evidence | 81% | 96% | 98% | 98% | 98% |
| Core recall in main-answer citations | 81% | 95% | 97% | 97% | 94% |
| Outcome matches | 1/13 | 3/13 | 6/13 | 11/13 | 11/13 |

In the final run, the two mismatches are a06 and a07, both overview questions. Every saved
report was regenerated; their all-rows figures are unchanged.

**Reading.**

1. **The stricter support check moves claims out of the answer.** Each claim is now rated
   against its own quotations, and 33 claims are held apart (13 in T7). Citation recall falls
   from 98% to 91%, and the fall is concentrated in three questions:
   - a06 and a07, overview questions;
   - a18, whose three claims were all held apart. Its expected outcome is `answer_limited`, so
     its outcome still matches.

   This is the intended trade: a claim whose quotations do not cover every element it states
   is no longer part of the answer.
2. **Four wrong outcomes remain, all `answer_limited` where `answer` was expected.** In each,
   the model reported its only issue as partly answered, and rule v2 keeps that report:
   - a06 and a07 are overview questions;
   - for a15 and a22, the model reported part of the question as not covered by the evidence.

   a14 had the same report in T7 and is an `answer` here. One run cannot tell whether the
   prompt change or run-to-run variation caused that.
3. **The summary was withheld in 17 of 20 answers.** The rule was all-or-nothing: a summary
   was shown only if every claim it cited was rated SUPPORTED. Under the stricter check, almost
   every summary cited at least one claim that is held apart.

   **The rule now works sentence by sentence.** A sentence is shown only if every claim it
   cites is SUPPORTED and in the main answer and it passes the reference check. If no sentence
   is left, no summary is shown.

   **Re-render.** The run was re-rendered offline under the new rule as
   `2026-11-17-final-summary`:
   - every call was replayed from this run, with no model call;
   - the results are identical apart from the summary fields;
   - the report is identical.

   Summaries now appear in 18 of 20 answers, 15 of them with some sentences left out.

   **Limits of the sentence rule** (open):
   - **It checks citations, not content.** It confirms that a sentence's cited claims are
     supported, not that the sentence says what they say. In a01 the only sentence left is "The
     evidence does not contain any sector-specific rules [C3]", and C3 is the definition of a
     breach.
   - **Some sentences do not stand alone.** In a05, a06 and a07 the sentence left starts with
     "…adds", "They" or "It", which refer back to a sentence that was left out.

   **The summary display is now off by default** (`SHOW_SUMMARY=false`), until a per-sentence
   support check exists (TECHNICAL_DEBT.md TD-067). The run was re-rendered offline once more,
   as `2026-11-17-final-nosummary`:
   - no model call;
   - no summary;
   - results and report otherwise identical.

   The replay in `demo/replay/` comes from this re-render.

## Repair pass: `2026-11-24-research-repair`

**This is a single run on the 12 dev questions. Model variance is not measured.**

**What changed.** After the support check, each claim rated partially supported or uncertain goes
to one repair call (`claim-repair-v1`):
- the model rewrites the claim to state only what its own quotations state, keeping some of
  them, possibly shortened or split;
- each rewrite is re-validated by the deterministic checks and support-checked once more;
- a confirmed rewrite enters the answer, marked as repaired. Otherwise the original stays held
  apart.

The outcome rule is unchanged.

**How it ran.**
- **Replayed:** analysis, generation and the first support check, from `2026-11-17-final`. Their
  prompts and messages are unchanged, so the comparison isolates the repair pass.
- **Live:** only the repair calls and the support check of the rewrites. They cost $0.094 under
  a $1.40 budget guard.
- **A discarded first attempt** ($0.097) returned the rewrites of English answers in Italian. The
  repair message now names the answer's language.
- **Re-render:** `2026-11-24-research-repair-caveat` re-renders the run offline with the new Art.
  33 caveat. Only the qualifications of the five answers citing Art. 33 changed, and the report is
  identical. The replay in `demo/replay/` comes from this re-render.

| Question | Expected | Outcome (before → after) | Claims in answer / held apart (before → after) | Core in citations (before → after) | Repaired / not confirmed |
|---|---|---|---|---|---|
| a01 | answer | answer → answer | 7/2 → 9/0 | 100% → 100% | 2 / 0 |
| a02 | answer | answer → answer | 1/1 → 2/0 | 100% → 100% | 1 / 0 |
| a03 | answer | answer → answer | 5/0 → 5/0 | 100% → 100% | 0 / 0 |
| a04 | answer | answer → answer | 7/1 → 7/1 | 100% → 100% | 0 / 1 |
| a05 | answer | answer → answer | 5/2 → 6/1 | 100% → 100% | 1 / 1 |
| a06 | answer | answer_limited → answer_limited | 8/1 → 9/1 | 71% → 86% | 1 / 1 |
| a07 | answer | answer_limited → answer_limited | 6/4 → 8/3 | 56% → 78% | 2 / 3 |
| a08 | answer | answer → answer | 10/2 → 12/0 | 100% → 100% | 2 / 0 |
| a09 | abstain | abstain → abstain | 0/0 → 0/0 | — | 0 / 0 |
| a10 | answer | answer → answer | 5/1 → 6/0 | 100% → 100% | 1 / 0 |
| a11 | answer | answer → answer | 3/1 → 3/1 | 100% → 100% | 0 / 1 |
| a12 | answer | answer → answer | 3/1 → 3/1 | 100% → 100% | 0 / 1 |
| **Total** | | **10/12 → 10/12** | **60/16 → 70/8** | **93% → 97%** | **10 / 8** |

**Reading.**

1. **Ten rewrites were confirmed and entered the answer.** Eight were not confirmed, and their
   original claims stay held apart. No rewrite failed the deterministic checks.

   Example, a01: the claim said "The only exception is where the breach is unlikely to present a
   risk"; the quotation does not say "only". The rewrite, "…unless the breach is unlikely to
   present a risk…", was confirmed.
2. **Outcomes are unchanged.** In a06 and a07 the model reported the question as only partly
   answered, and the rule keeps that report.
3. **Citation recall rose from 93% to 97%** on these questions (a06, a07), as repaired claims
   now cite core provisions in the main answer.
4. **Accepted imperfections** (owner's decision): two rewrites read awkwardly.
   - a02 begins with "Secondo la citazione, …".
   - a06's confirmed part of a split claim is a fragment.
5. **Claims of absence cannot be quoted** (TECHNICAL_DEBT.md TD-068). a12's claim that the GDPR
   sets no 96-hour deadline stays held apart, also after repair. The main answer states the
   72-hour rule. The Art. 33 caveat now names the proposal: it "would limit notification to
   high-risk breaches and extend the deadline to 96 hours".

## Quotation widening: `2026-11-26-repair-v2`

**This is a single run on 25 questions: a01–a22 and the candidates a23–a25 from the live demo.
Model variance is not measured. Each repair call is a new sample, so part of the difference from
the baseline is run-to-run variation of the repair pass, not the widening.**

**What changed** (TECHNICAL_DEBT.md TD-070). The repair prompt is now `claim-repair-v2`:
- for a claim rated partially supported, the repair call also receives the text of the provisions
  it quotes;
- a rewrite may replace a quotation with a longer passage of the same provision, to include a
  condition the claim needs, and must then state the condition;
- the widened passage must contain the whole original quotation, add at most 300 characters (600
  in all, normalised), and be an exact passage of the same evidence item. A widening that fails
  drops that rewrite. The cap was later raised to 350 characters, after these results (below);
- the rewrites then go through the usual deterministic checks and the support check
  (`claim-verification-v3`), both unchanged;
- a confirmed widened quotation is marked on the page and in the CLI, with its original.

The outcome rule is unchanged.

**How it ran.**
- **Baseline** `2026-11-26-repair-v1-before`: the pipeline as it was (`claim-repair-v1`) on all 25
  questions, for $0.284:
  - a01–a12 replayed offline from `2026-11-24-research-repair-caveat`;
  - a13–a22 replayed from `2026-11-17-final`, with the repair calls live ($0.093);
  - a23–a25 fully live ($0.191).
- **After** `2026-11-26-repair-v2`: everything replayed from the baseline except the repair calls
  and the support check of the rewrites. These cost $0.416 under a $0.50 budget guard, more than
  the $0.25 estimated, because the repair messages now carry provision texts.

| Question | Split | Expected | Outcome (before → after) | Claims in answer / held apart (before → after) | Core in citations (before → after) |
|---|---|---|---|---|---|
| a01 | dev | answer | answer → answer | 9/0 → 9/0 | 100% → 100% |
| a02 | dev | answer | answer → answer | 2/0 → 2/1 | 100% → 100% |
| a03 | dev | answer | answer → answer | 5/0 → 5/0 | 100% → 100% |
| a04 | dev | answer | answer → answer | 7/1 → 8/0 | 100% → 100% |
| a05 | dev | answer | answer → answer | 6/1 → 7/1 | 100% → 100% |
| a06 | dev | answer | answer_limited → answer_limited | 9/1 → 9/0 | 86% → 86% |
| a07 | dev | answer | answer_limited → answer_limited | 8/3 → 10/1 | 78% → 89% |
| a08 | dev | answer | answer → answer | 12/0 → 11/1 | 100% → 100% |
| a09 | dev | abstain | abstain → abstain | 0/0 → 0/0 | — |
| a10 | dev | answer | answer → answer | 6/0 → 6/1 | 100% → 100% |
| a11 | dev | answer | answer → answer | 3/1 → 4/0 | 100% → 100% |
| a12 | dev | answer | answer → answer | 3/1 → 4/0 | 100% → 100% |
| a13 | test | answer | answer → answer | 3/0 → 3/0 | 100% → 100% |
| a14 | test | answer | answer → answer | 5/2 → 6/1 | 100% → 100% |
| a15 | test | answer | answer_limited → answer_limited | 6/0 → 6/1 | 100% → 100% |
| a16 | test | answer | answer → answer | 9/2 → 10/1 | 100% → 100% |
| a17 | test | answer | answer → answer | 5/0 → 5/0 | 100% → 100% |
| a18 | test | answer_limited | answer_limited → answer_limited | 2/3 → 2/2 | 100% → 100% |
| a19 | test | abstain | abstain → abstain | 0/0 → 0/0 | — |
| a20 | test | answer | answer → answer | 8/3 → 10/1 | 100% → 100% |
| a21 | test | answer | answer → answer | 3/2 → 5/0 | 100% → 100% |
| a22 | test | answer | answer_limited → answer_limited | 11/1 → 12/1 | 100% → 100% |
| a23 | candidate | answer | answer → answer | 4/1 → 4/1 | 100% → 100% |
| a24 | candidate | answer | answer → answer | 2/3 → 3/1 | 100% → 100% |
| a25 | candidate | answer | answer → answer | 4/1 → 3/1 | 100% → 100% |
| **Total** | | | **21/25 → 21/25** | **132/26 → 144/15** | **98% → 99%** |

In the owner-reviewed scope (a01–a13), outcomes are 11/13 in both runs, and claims in answer /
held apart went from 73/8 to 78/5.

**Widenings.** The model proposed 34:
- 22 were confirmed and entered the answer, in 20 claims;
- 7 were not confirmed by the support check, so their original claims stay held apart;
- 5 quotations, in 4 rewrites, were refused by the length cap.

**Reading.**

1. **The case TD-070 describes works.**
   - GDPR Art. 37(4), «Nei casi diversi da quelli di cui al paragrafo 1»: widened and confirmed in
     a24 (33), not confirmed in a15 (19).
   - The Art. 33(1) exception, «a meno che sia improbabile che la violazione … presenti un
     rischio»: added and confirmed in a07, a10, a11 and a12 (10, 14–16).
   - The Art. 20(1)(a) condition, consent or contract: confirmed in a06 (7).
2. **Not every widening adds a condition.** The prompt asks for conditions only, but the model
   also widens a quotation for other text the claim states. In my reading:
   - 13 of the 22 confirmed widenings add a condition, an exception or a limit (3, 7, 10, 11,
     14–17, 22, 23, 27, 28, 33);
   - 9 add other text that the claim states (1, 2, 5, 6, 8, 20, 25, 26, 32). Examples: in a01, the
     sentence after Art. 33(5)'s documentation duty; in a07, «Dette misure sono riesaminate e
     aggiornate qualora necessario».

   Whether a widening adds a condition cannot be checked mechanically. **Owner's decision
   (2026-11-26): these widenings are accepted, and the prompt stays as it is.** The guarantee is
   the same for every widening: the widened text is an exact passage of the same provision, it
   contains the original quotation, it is within the cap, and the support check confirmed the
   rewrite.
3. **The cap refused the Art. 30(5) exception twice**, at +329 characters (a07 and a24; 9, 34).
   In a24 this is the claim that puts the 250-employee threshold in the records duty, so it stays
   held apart. The cap was then raised (next section).
4. **Five questions are worse at the claim level** (a02, a08, a10, a15, a25):
   - a08 and a25 have one claim fewer in the answer. A claim that the v1 repair had brought into
     the answer stays out: in a08 its widening was refused by the cap (12, 13), and in a25 neither
     part of the new split was confirmed. A refused widening drops the whole rewrite; nothing falls
     back to a narrower rewrite.
   - a02, a10 and a15 have one more claim held apart. The new repair split a claim and only one
     part was confirmed, so the original also stays held apart; v1's single rewrite had been
     confirmed.
5. **Outcomes are unchanged.** In a06, a07, a15 and a22 the model reported the question as only
   partly answered, and the rule keeps that report.

### The cap raised to 350 characters: `2026-11-26-repair-v2-cap350`

**The cap was raised after the results above, not set in advance.** At 300 characters it had
refused the Art. 30(5) exception (+329) in a07 and a24.
- **What changed:** on the owner's decision (2026-11-26), a widening may add up to 350
  characters (`claim-repair-v2.1`). Only that number in the prompt changed; the total of 600 and
  every check are unchanged.
- **How it ran:** a07 and a24 only, from the same baseline, for $0.063.

| Question | Outcome (unchanged) | Claims in answer / held apart (v2 → v2.1) | Core in citations (v2 → v2.1) |
|---|---|---|---|
| a07 | answer_limited | 10/1 → 10/2 | 89% → 89% |
| a24 | answer | 3/1 → 3/1 | 100% → 100% |

- **a24:** the Art. 30(5) widening was confirmed. The claim that the exemption for fewer than 250
  employees concerns the records of processing ("subject to exceptions") is now in the answer.
  Another claim (C1, the cases of Art. 37(1)) was not confirmed this time, so the counts are the
  same.
- **a07:** the Art. 30(5) widening passed the cap, but the rewrite left the exception out of its
  own text, and the support check rated it partially supported. One part of another split claim
  (C8) was not confirmed either, so one more claim is held apart.
- **The other 23 questions were not run again.** Each of their saved widenings either added at
  most 300 characters or more than 350 (a05 +417, a08 +402). So the new cap does not change how
  those proposals are checked. A new repair call would be a new sample, which this does not
  measure.

The six widened quotations of this re-run:

1. **a07 C1**, GDPR art. 24: confirmed (+63 characters)
   - Original: «il titolare del trattamento mette in atto misure tecniche e organizzative adeguate per garantire, ed essere in grado di dimostrare, che il trattamento è effettuato conformemente al presente regolamento.»
   - Widened: «il titolare del trattamento mette in atto misure tecniche e organizzative adeguate per garantire, ed essere in grado di dimostrare, che il trattamento è effettuato conformemente al presente regolamento. Dette misure sono riesaminate e aggiornate qualora necessario.»
   - Rewrite: The controller must put in place appropriate technical and organisational measures to ensure, and be able to demonstrate, that processing is carried out in compliance with the Regulation. These measures are reviewed and updated where necessary.
2. **a07 C4.2**, GDPR art. 30: not confirmed (partially_supported) (+329 characters)
   - Original: «Gli obblighi di cui ai paragrafi 1 e 2 non si applicano alle imprese o organizzazioni con meno di 250 dipendenti»
   - Widened: «Gli obblighi di cui ai paragrafi 1 e 2 non si applicano alle imprese o organizzazioni con meno di 250 dipendenti, a meno che il trattamento che esse effettuano possa presentare un rischio per i diritti e le libertà dell'interessato, il trattamento non sia occasionale o includa il trattamento di categorie particolari di dati di cui all'articolo 9, paragrafo 1, o i dati personali relativi a condanne penali e a reati di cui all'articolo 10.»
   - Rewrite: The obligations in paragraphs 1 and 2 do not apply to enterprises or organisations with fewer than 250 employees.
3. **a07 C6**, GDPR art. 33: confirmed (+135 characters)
   - Original: «il titolare del trattamento notifica la violazione all'autorità di controllo competente a norma dell'articolo 55 senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza»
   - Widened: «il titolare del trattamento notifica la violazione all'autorità di controllo competente a norma dell'articolo 55 senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza, a meno che sia improbabile che la violazione dei dati personali presenti un rischio per i diritti e le libertà delle persone fisiche.»
   - Rewrite: In case of a personal data breach the controller must notify the competent supervisory authority without undue delay and, where possible, within 72 hours of becoming aware of it, unless it is unlikely that the breach presents a risk to the rights and freedoms of natural persons.
4. **a07 C8.2**, GDPR art. 35: confirmed (+251 characters)
   - Original: «il titolare del trattamento effettua, prima di procedere al trattamento, una valutazione dell'impatto dei trattamenti previsti sulla protezione dei dati personali.»
   - Widened: «Quando un tipo di trattamento, allorché prevede in particolare l'uso di nuove tecnologie, considerati la natura, l'oggetto, il contesto e le finalità del trattamento, può presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare del trattamento effettua, prima di procedere al trattamento, una valutazione dell'impatto dei trattamenti previsti sulla protezione dei dati personali.»
   - Rewrite: Where a type of processing may present a high risk to the rights and freedoms of natural persons, the controller must carry out, before processing, an assessment of the impact of the envisaged processing on the protection of personal data.
5. **a24 C3**, GDPR art. 37: confirmed (+244 characters)
   - Original: «possono o, se previsto dal diritto dell'Unione o degli Stati membri, devono designare un responsabile della protezione dei dati»
   - Widened: «Nei casi diversi da quelli di cui al paragrafo 1, il titolare e del trattamento, il responsabile del trattamento o le associazioni e gli altri organismi rappresentanti le categorie di titolari del trattamento o di responsabili del trattamento possono o, se previsto dal diritto dell'Unione o degli Stati membri, devono designare un responsabile della protezione dei dati.»
   - Rewrite: In cases other than those in Article 37(1), controllers and processors may designate a DPO or, if provided for by Union or Member State law, must do so.
6. **a24 C4**, GDPR art. 30: confirmed (+329 characters)
   - Original: «Gli obblighi di cui ai paragrafi 1 e 2 non si applicano alle imprese o organizzazioni con meno di 250 dipendenti»
   - Widened: «Gli obblighi di cui ai paragrafi 1 e 2 non si applicano alle imprese o organizzazioni con meno di 250 dipendenti, a meno che il trattamento che esse effettuano possa presentare un rischio per i diritti e le libertà dell'interessato, il trattamento non sia occasionale o includa il trattamento di categorie particolari di dati di cui all'articolo 9, paragrafo 1, o i dati personali relativi a condanne penali e a reati di cui all'articolo 10.»
   - Rewrite: The obligations in paragraphs 1 and 2 of the GDPR article on records of processing activities do not apply to enterprises or organisations with fewer than 250 employees, subject to exceptions.

### The widened quotations (34)

Character counts are in the normalised form. The rewrite is the claim as the repair pass wrote it.

1. **a01 C9**, GDPR art. 33: confirmed (+104 characters)
   - Original: «Il titolare del trattamento documenta qualsiasi violazione dei dati personali, comprese le circostanze a essa relative, le sue conseguenze e i provvedimenti adottati per porvi rimedio.»
   - Widened: «Il titolare del trattamento documenta qualsiasi violazione dei dati personali, comprese le circostanze a essa relative, le sue conseguenze e i provvedimenti adottati per porvi rimedio. Tale documentazione consente all'autorità di controllo di verificare il rispetto del presente articolo.»
   - Rewrite: The controller must document any personal data breach, including the circumstances relating to it, its consequences and the measures taken to remedy it. This documentation enables the supervisory authority to verify compliance with the article.
2. **a02 C2.2**, GDPR art. 4: confirmed (+136 characters)
   - Original: «comporta accidentalmente o in modo illecito la distruzione, la perdita, la modifica»
   - Widened: «la violazione di sicurezza che comporta accidentalmente o in modo illecito la distruzione, la perdita, la modifica, la divulgazione non autorizzata o l'accesso ai dati personali trasmessi, conservati o comunque trattati»
   - Rewrite: Secondo la definizione di violazione dei dati personali, la violazione di sicurezza può comportare, accidentalmente o in modo illecito, distruzione, perdita o modifica dei dati personali trasmessi, conservati o comunque trattati.
3. **a04 C7**, GDPR art. 56: confirmed (+29 characters)
   - Original: «ogni autorità di controllo è competente per la gestione dei reclami a essa proposti o di eventuali violazioni del presente regolamento se l'oggetto riguarda unicamente uno stabilimento nel suo Stato membro o incide in modo sostanziale sugli interessati unicamente nel suo Stato membro.»
   - Widened: «2. In deroga al paragrafo 1, ogni autorità di controllo è competente per la gestione dei reclami a essa proposti o di eventuali violazioni del presente regolamento se l'oggetto riguarda unicamente uno stabilimento nel suo Stato membro o incide in modo sostanziale sugli interessati unicamente nel suo Stato membro.»
   - Rewrite: In deroga al paragrafo 1 dell'articolo 56, ogni autorità di controllo è competente per la gestione dei reclami a essa proposti o di eventuali violazioni del regolamento se l'oggetto riguarda unicamente uno stabilimento nel suo Stato membro o incide in modo sostanziale sugli interessati unicamente nel suo Stato membro.
4. **a05 C5.2**, GDPR art. 5: refused: widened_too_long (+417 characters)
   - Original: «conservati in una forma che consenta l'identificazione degli interessati per un arco di tempo non superiore al conseguimento delle finalità per le quali sono trattati;»
   - Widened: «conservati in una forma che consenta l'identificazione degli interessati per un arco di tempo non superiore al conseguimento delle finalità per le quali sono trattati; i dati personali possono essere conservati per periodi più lunghi a condizione che siano trattati esclusivamente a fini di archiviazione nel pubblico interesse, di ricerca scientifica o storica o a fini statistici, conformemente all'articolo 89, paragrafo 1, fatta salva l'attuazione di misure tecniche e organizzative adeguate richieste dal presente regolamento a tutela dei diritti e delle libertà dell'interessato»
   - Rewrite: Under Article 5(1)(e), personal data may be kept for longer periods provided they are processed exclusively for archiving in the public interest, scientific or historical research or statistical purposes, in accordance with Article 89(1), subject to appropriate technical and organisational measures required by the Regulation to protect the rights and freedoms of the data subject (storage limitation).
5. **a05 C6**, GDPR art. 5: confirmed (+131 characters)
   - Original: «trattati in maniera da garantire un'adeguata sicurezza dei dati personali, compresa la protezione, mediante misure tecniche e organizzative adeguate»
   - Widened: «trattati in maniera da garantire un'adeguata sicurezza dei dati personali, compresa la protezione, mediante misure tecniche e organizzative adeguate, da trattamenti non autorizzati o illeciti e dalla perdita, dalla distruzione o dal danno accidentali («integrità e riservatezza»)»
   - Rewrite: Under Article 5(1)(f), personal data must be processed so as to ensure appropriate security of the data, including protection by appropriate technical and organisational measures, against unauthorised or unlawful processing and against accidental loss, destruction or damage (integrity and confidentiality).
6. **a06 C5**, GDPR art. 20: confirmed (+160 characters)
   - Original: «L'interessato ha il diritto di ricevere in un formato strutturato, di uso comune e leggibile da dispositivo automatico i dati personali che lo riguardano forniti a un titolare del trattamento»
   - Widened: «L'interessato ha il diritto di ricevere in un formato strutturato, di uso comune e leggibile da dispositivo automatico i dati personali che lo riguardano forniti a un titolare del trattamento e ha il diritto di trasmettere tali dati a un altro titolare del trattamento senza impedimenti da parte del titolare del trattamento cui li ha forniti qualora:»
   - Rewrite: The data subject has the right to receive the personal data they have provided to a controller in a structured, commonly used, machine-readable format, and the right to transmit those data to another controller without hindrance from the controller to whom they were provided. This applies where the processing is based on consent or on a contract and is carried out by automated means (Article 20).
7. **a06 C5**, GDPR art. 20: confirmed (+208 characters)
   - Original: «il trattamento sia effettuato con mezzi automatizzati.»
   - Widened: «a) il trattamento si basi sul consenso ai sensi dell'articolo 6, paragrafo 1, lettera a), o dell'articolo 9, paragrafo 2, lettera a), o su un contratto ai sensi dell'articolo 6, paragrafo 1, lettera b); e b) il trattamento sia effettuato con mezzi automatizzati.»
   - Rewrite: The data subject has the right to receive the personal data they have provided to a controller in a structured, commonly used, machine-readable format, and the right to transmit those data to another controller without hindrance from the controller to whom they were provided. This applies where the processing is based on consent or on a contract and is carried out by automated means (Article 20).
8. **a07 C1**, GDPR art. 24: confirmed (+63 characters)
   - Original: «il titolare del trattamento mette in atto misure tecniche e organizzative adeguate per garantire, ed essere in grado di dimostrare, che il trattamento è effettuato conformemente al presente regolamento.»
   - Widened: «il titolare del trattamento mette in atto misure tecniche e organizzative adeguate per garantire, ed essere in grado di dimostrare, che il trattamento è effettuato conformemente al presente regolamento. Dette misure sono riesaminate e aggiornate qualora necessario.»
   - Rewrite: The controller must put in place appropriate technical and organisational measures to ensure, and be able to demonstrate, that processing is carried out in accordance with the Regulation. These measures are reviewed and updated where necessary.
9. **a07 C4.2**, GDPR art. 30: refused: widened_too_long (+329 characters)
   - Original: «Gli obblighi di cui ai paragrafi 1 e 2 non si applicano alle imprese o organizzazioni con meno di 250 dipendenti»
   - Widened: «Gli obblighi di cui ai paragrafi 1 e 2 non si applicano alle imprese o organizzazioni con meno di 250 dipendenti, a meno che il trattamento che esse effettuano possa presentare un rischio per i diritti e le libertà dell'interessato, il trattamento non sia occasionale o includa il trattamento di categorie particolari di dati di cui all'articolo 9, paragrafo 1, o i dati personali relativi a condanne penali e a reati di cui all'articolo 10.»
   - Rewrite: The obligations of paragraphs 1 and 2 do not apply to enterprises or organisations with fewer than 250 employees, unless the processing they carry out is likely to present a risk to the data subject's rights and freedoms, is not occasional, or includes special categories of data or data on criminal convictions and offences.
10. **a07 C6**, GDPR art. 33: confirmed (+177 characters)
   - Original: «il titolare del trattamento notifica la violazione all'autorità di controllo competente a norma dell'articolo 55 senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza»
   - Widened: «In caso di violazione dei dati personali, il titolare del trattamento notifica la violazione all'autorità di controllo competente a norma dell'articolo 55 senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza, a meno che sia improbabile che la violazione dei dati personali presenti un rischio per i diritti e le libertà delle persone fisiche.»
   - Rewrite: In case of a personal data breach the controller must notify the competent supervisory authority without undue delay and, where possible, within 72 hours of becoming aware of it, unless the breach is unlikely to present a risk to individuals' rights and freedoms.
11. **a07 C8**, GDPR art. 35: confirmed (+251 characters)
   - Original: «il titolare del trattamento effettua, prima di procedere al trattamento, una valutazione dell'impatto dei trattamenti previsti sulla protezione dei dati personali.»
   - Widened: «Quando un tipo di trattamento, allorché prevede in particolare l'uso di nuove tecnologie, considerati la natura, l'oggetto, il contesto e le finalità del trattamento, può presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare del trattamento effettua, prima di procedere al trattamento, una valutazione dell'impatto dei trattamenti previsti sulla protezione dei dati personali.»
   - Rewrite: Where a type of processing may present a high risk to individuals' rights and freedoms, the controller must carry out, before processing, an assessment of the impact of the envisaged processing on the protection of personal data.
12. **a08 C11**, GDPR art. 9: refused: widened_too_long (+228 characters)
   - Original: «il trattamento è necessario per motivi di interesse pubblico rilevante sulla base del diritto dell'Unione o degli Stati membri»
   - Widened: «il trattamento è necessario per motivi di interesse pubblico rilevante sulla base del diritto dell'Unione o degli Stati membri, che deve essere proporzionato alla finalità perseguita, rispettare l'essenza del diritto alla protezione dei dati e prevedere misure appropriate e specifiche per tutelare i diritti fondamentali e gli interessi dell'interessato»
   - Rewrite: Article 9(1) does not apply where processing is necessary for reasons of substantial public interest on the basis of Union or Member State law, which must be proportionate to the aim pursued, respect the essence of the right to data protection and provide suitable and specific measures to safeguard the data subject's fundamental rights and interests. It also does not apply where processing is necessary for reasons of public interest in the area of public health, on the basis of Union or Member State law providing suitable and specific measures to safeguard the data subject's rights and freedoms, in particular professional secrecy.
13. **a08 C11**, GDPR art. 9: refused: widened_too_long (+402 characters)
   - Original: «il trattamento è necessario per motivi di interesse pubblico nel settore della sanità pubblica»
   - Widened: «il trattamento è necessario per motivi di interesse pubblico nel settore della sanità pubblica, quali la protezione da gravi minacce per la salute a carattere transfrontaliero o la garanzia di parametri elevati di qualità e sicurezza dell'assistenza sanitaria e dei medicinali e dei dispositivi medici, sulla base del diritto dell'Unione o degli Stati membri che prevede misure appropriate e specifiche per tutelare i diritti e le libertà dell'interessato, in particolare il segreto professionale»
   - Rewrite: Article 9(1) does not apply where processing is necessary for reasons of substantial public interest on the basis of Union or Member State law, which must be proportionate to the aim pursued, respect the essence of the right to data protection and provide suitable and specific measures to safeguard the data subject's fundamental rights and interests. It also does not apply where processing is necessary for reasons of public interest in the area of public health, on the basis of Union or Member State law providing suitable and specific measures to safeguard the data subject's rights and freedoms, in particular professional secrecy.
14. **a10 C5.1**, GDPR art. 33: confirmed (+134 characters)
   - Original: «senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza»
   - Widened: «senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza, a meno che sia improbabile che la violazione dei dati personali presenti un rischio per i diritti e le libertà delle persone fisiche»
   - Rewrite: Il titolare del trattamento notifica la violazione all'autorità di controllo senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza, a meno che sia improbabile che la violazione presenti un rischio per i diritti e le libertà delle persone fisiche.
15. **a11 C1**, GDPR art. 33: confirmed (+135 characters)
   - Original: «In caso di violazione dei dati personali, il titolare del trattamento notifica la violazione all'autorità di controllo competente a norma dell'articolo 55 senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza»
   - Widened: «In caso di violazione dei dati personali, il titolare del trattamento notifica la violazione all'autorità di controllo competente a norma dell'articolo 55 senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza, a meno che sia improbabile che la violazione dei dati personali presenti un rischio per i diritti e le libertà delle persone fisiche.»
   - Rewrite: In caso di violazione dei dati personali, il titolare del trattamento notifica la violazione all'autorità di controllo competente senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza, a meno che sia improbabile che la violazione presenti un rischio per i diritti e le libertà delle persone fisiche.
16. **a12 C3**, GDPR art. 33: confirmed (+181 characters)
   - Original: «entro 72 ore dal momento in cui ne è venuto a conoscenza»
   - Widened: «senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza, a meno che sia improbabile che la violazione dei dati personali presenti un rischio per i diritti e le libertà delle persone fisiche»
   - Rewrite: Il titolare del trattamento notifica la violazione all'autorità di controllo, ove possibile, entro 72 ore dal momento in cui ne è venuto a conoscenza, a meno che sia improbabile che la violazione presenti un rischio per i diritti e le libertà delle persone fisiche.
17. **a14 C1**, GDPR art. 35: confirmed (+167 characters)
   - Original: «può presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare del trattamento effettua, prima di procedere al trattamento, una valutazione dell'impatto dei trattamenti previsti sulla protezione dei dati personali.»
   - Widened: «Quando un tipo di trattamento, allorché prevede in particolare l'uso di nuove tecnologie, considerati la natura, l'oggetto, il contesto e le finalità del trattamento, può presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare del trattamento effettua, prima di procedere al trattamento, una valutazione dell'impatto dei trattamenti previsti sulla protezione dei dati personali.»
   - Rewrite: Quando un tipo di trattamento, in particolare con l'uso di nuove tecnologie e considerati natura, oggetto, contesto e finalità, può presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare effettua una valutazione d'impatto sulla protezione dei dati prima di procedere al trattamento.
18. **a14 C7**, GDPR art. 35: not confirmed (partially_supported) (+270 characters)
   - Original: «i paragrafi da 1 a 7 non si applicano, salvo che gli Stati membri ritengano necessario effettuare tale valutazione prima di procedere alle attività di trattamento.»
   - Widened: «tale diritto disciplini il trattamento specifico o l'insieme di trattamenti in questione, e sia già stata effettuata una valutazione d'impatto sulla protezione dei dati nell'ambito di una valutazione d'impatto generale nel contesto dell'adozione di tale base giuridica, i paragrafi da 1 a 7 non si applicano, salvo che gli Stati membri ritengano necessario effettuare tale valutazione prima di procedere alle attività di trattamento.»
   - Rewrite: Quando il diritto che costituisce la base giuridica disciplina il trattamento specifico o l'insieme di trattamenti in questione e una valutazione d'impatto generale è già stata effettuata nel contesto dell'adozione di tale base giuridica, i paragrafi da 1 a 7 non si applicano, salvo che gli Stati membri ritengano necessario effettuare tale valutazione prima di procedere alle attività di trattamento.
19. **a15 C6.2**, GDPR art. 37: not confirmed (partially_supported) (+259 characters)
   - Original: «Nei casi diversi da quelli di cui al paragrafo 1, il titolare e del trattamento, il responsabile del trattamento»
   - Widened: «Nei casi diversi da quelli di cui al paragrafo 1, il titolare e del trattamento, il responsabile del trattamento o le associazioni e gli altri organismi rappresentanti le categorie di titolari del trattamento o di responsabili del trattamento possono o, se previsto dal diritto dell'Unione o degli Stati membri, devono designare un responsabile della protezione dei dati.»
   - Rewrite: Nei casi diversi da quelli del paragrafo 1, il titolare e il responsabile del trattamento possono designare un responsabile della protezione dei dati o, se previsto dal diritto dell'Unione o degli Stati membri, devono designarlo.
20. **a16 C2**, GDPR art. 17: confirmed (+256 characters)
   - Original: «se sussiste uno dei motivi seguenti:»
   - Widened: «L'interessato ha il diritto di ottenere dal titolare del trattamento la cancellazione dei dati personali che lo riguardano senza ingiustificato ritardo e il titolare del trattamento ha l'obbligo di cancellare senza ingiustificato ritardo i dati personali, se sussiste uno dei motivi seguenti:»
   - Rewrite: Il titolare del trattamento ha l'obbligo di cancellare i dati personali senza ingiustificato ritardo se sussiste uno dei motivi elencati nell'articolo 17, paragrafo 1.
21. **a18 C3.2**, GDPR art. 34: not confirmed (partially_supported) (+98 characters)
   - Original: «Quando la violazione dei dati personali è suscettibile di presentare un rischio elevato per i diritti e le libertà delle persone fisiche»
   - Widened: «Quando la violazione dei dati personali è suscettibile di presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare del trattamento comunica la violazione all'interessato senza ingiustificato ritardo.»
   - Rewrite: Secondo l'art. 34, quando la violazione dei dati personali è suscettibile di presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare del trattamento la comunica all'interessato.
22. **a20 C5**, GDPR art. 46: confirmed (+68 characters)
   - Original: «le disposizioni da inserire in accordi amministrativi tra autorità pubbliche o organismi pubblici»
   - Widened: «le disposizioni da inserire in accordi amministrativi tra autorità pubbliche o organismi pubblici che comprendono diritti effettivi e azionabili per gli interessati.»
   - Rewrite: Fatta salva l'autorizzazione dell'autorità di controllo competente, possono costituire garanzie adeguate le clausole contrattuali tra il titolare o il responsabile del trattamento e il titolare, il responsabile o il destinatario dei dati, e le disposizioni da inserire in accordi amministrativi tra autorità pubbliche o organismi pubblici che comprendono diritti effettivi e azionabili per gli interessati.
23. **a20 C8**, GDPR art. 49: confirmed (+99 characters)
   - Original: «il trasferimento sia necessario per tutelare gli interessi vitali dell'interessato o di altre persone»
   - Widened: «il trasferimento sia necessario per tutelare gli interessi vitali dell'interessato o di altre persone, qualora l'interessato si trovi nell'incapacità fisica o giuridica di prestare il proprio consenso»
   - Rewrite: Tra le deroghe previste figurano il trasferimento necessario per importanti motivi di interesse pubblico, per accertare, esercitare o difendere un diritto in sede giudiziaria, e per tutelare gli interessi vitali dell'interessato o di altre persone qualora l'interessato si trovi nell'incapacità fisica o giuridica di prestare il proprio consenso.
24. **a20 C9**, GDPR art. 49: not confirmed (partially_supported) (+79 characters)
   - Original: «soltanto se non è ripetitivo, riguarda un numero limitato di interessati, è necessario per il perseguimento degli interessi legittimi cogenti del titolare del trattamento»
   - Widened: «soltanto se non è ripetitivo, riguarda un numero limitato di interessati, è necessario per il perseguimento degli interessi legittimi cogenti del titolare del trattamento, su cui non prevalgano gli interessi o i diritti e le libertà dell'interessato»
   - Rewrite: In un trasferimento non basato sugli articoli 45 o 46 né su una deroga, il trasferimento è ammesso soltanto se non è ripetitivo, riguarda un numero limitato di interessati ed è necessario per il perseguimento degli interessi legittimi cogenti del titolare del trattamento, su cui non prevalgano gli interessi o i diritti e le libertà dell'interessato; il titolare del trattamento informa del trasferimento l'autorità di controllo.
25. **a20 C10**, GDPR art. 46: confirmed (+284 characters)
   - Original: «In mancanza di una decisione ai sensi dell'articolo 45, paragrafo 3»
   - Widened: «In mancanza di una decisione ai sensi dell'articolo 45, paragrafo 3, il titolare del trattamento o il responsabile del trattamento può trasferire dati personali verso un paese terzo o un'organizzazione internazionale solo se ha fornito garanzie adeguate e a condizione che gli interessati dispongano di diritti azionabili e mezzi di ricorso effettivi.»
   - Rewrite: In mancanza di una decisione ai sensi dell'articolo 45, paragrafo 3, il trasferimento verso un paese terzo è ammesso solo se sono fornite garanzie adeguate e gli interessati dispongono di diritti azionabili e mezzi di ricorso effettivi; in mancanza anche di garanzie adeguate, è ammesso soltanto se si verifica una delle condizioni elencate nell'articolo 49.
26. **a20 C10**, GDPR art. 49: confirmed (+228 characters)
   - Original: «In mancanza di una decisione di adeguatezza ai sensi dell'articolo 45, paragrafo 3, o di garanzie adeguate ai sensi dell'articolo 46»
   - Widened: «In mancanza di una decisione di adeguatezza ai sensi dell'articolo 45, paragrafo 3, o di garanzie adeguate ai sensi dell'articolo 46, comprese le norme vincolanti d'impresa, è ammesso il trasferimento o un complesso di trasferimenti di dati personali verso un paese terzo o un'organizzazione internazionale soltanto se si verifica una delle seguenti condizioni»
   - Rewrite: In mancanza di una decisione ai sensi dell'articolo 45, paragrafo 3, il trasferimento verso un paese terzo è ammesso solo se sono fornite garanzie adeguate e gli interessati dispongono di diritti azionabili e mezzi di ricorso effettivi; in mancanza anche di garanzie adeguate, è ammesso soltanto se si verifica una delle condizioni elencate nell'articolo 49.
27. **a21 C4**, GDPR art. 34: confirmed (+138 characters)
   - Original: «il titolare del trattamento comunica la violazione all'interessato senza ingiustificato ritardo.»
   - Widened: «Quando la violazione dei dati personali è suscettibile di presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare del trattamento comunica la violazione all'interessato senza ingiustificato ritardo.»
   - Rewrite: Secondo l'art. 34, paragrafo 1, quando la violazione dei dati personali è suscettibile di presentare un rischio elevato per i diritti e le libertà delle persone fisiche, il titolare del trattamento comunica la violazione all'interessato senza ingiustificato ritardo.
28. **a21 C5**, GDPR art. 83: confirmed (+200 characters)
   - Original: «l'importo totale della sanzione amministrativa pecuniaria non supera l'importo specificato per la violazione più grave.»
   - Widened: «Se, in relazione allo stesso trattamento o a trattamenti collegati, un titolare del trattamento o un responsabile del trattamento viola, con dolo o colpa, varie disposizioni del presente regolamento, l'importo totale della sanzione amministrativa pecuniaria non supera l'importo specificato per la violazione più grave.»
   - Rewrite: Se un titolare o un responsabile del trattamento viola, con dolo o colpa, varie disposizioni del regolamento in relazione allo stesso trattamento o a trattamenti collegati, l'importo totale della sanzione amministrativa pecuniaria non supera l'importo specificato per la violazione più grave.
29. **a22 C9**, Codice art. 143: not confirmed (partially_supported) (+126 characters)
   - Original: «Il Garante decide il reclamo entro nove mesi dalla data di presentazione e, in ogni caso, entro tre mesi dalla predetta data informa l'interessato sullo stato del procedimento.»
   - Widened: «Il Garante decide il reclamo entro nove mesi dalla data di presentazione e, in ogni caso, entro tre mesi dalla predetta data informa l'interessato sullo stato del procedimento. In presenza di motivate esigenze istruttorie, che il Garante comunica all'interessato, il reclamo è deciso entro dodici mesi.»
   - Rewrite: Il Garante decide il reclamo entro nove mesi dalla data di presentazione e, in ogni caso, entro tre mesi dalla predetta data informa l'interessato sullo stato del procedimento; in presenza di motivate esigenze istruttorie, comunicate all'interessato, il reclamo è deciso entro dodici mesi.
30. **a23 C3.1**, GDPR art. 8: not confirmed (partially_supported) (+151 characters)
   - Original: «il trattamento di dati personali del minore è lecito ove il minore abbia almeno 16 anni.»
   - Widened: «Qualora si applichi l'articolo 6, paragrafo 1, lettera a), per quanto riguarda l'offerta diretta di servizi della società dell'informazione ai minori, il trattamento di dati personali del minore è lecito ove il minore abbia almeno 16 anni.»
   - Rewrite: Il Regolamento prevede che il trattamento di dati personali del minore sia lecito ove il minore abbia almeno 16 anni, quando si applica l'articolo 6, paragrafo 1, lettera a), all'offerta diretta di servizi della società dell'informazione ai minori.
31. **a23 C3.2**, GDPR art. 8: not confirmed (partially_supported) (+195 characters)
   - Original: «il trattamento di dati personali del minore è lecito ove il minore abbia almeno 16 anni.»
   - Widened: «il trattamento di dati personali del minore è lecito ove il minore abbia almeno 16 anni. Ove il minore abbia un'età inferiore ai 16 anni, tale trattamento è lecito soltanto se e nella misura in cui tale consenso è prestato o autorizzato dal titolare della responsabilità genitoriale.»
   - Rewrite: Il Regolamento prevede che, ove il minore abbia meno di 16 anni, il trattamento sia lecito soltanto se e nella misura in cui il consenso è prestato o autorizzato dal titolare della responsabilità genitoriale.
32. **a24 C1**, GDPR art. 37: confirmed (+71 characters)
   - Original: «le attività principali del titolare del trattamento o del responsabile del trattamento consistono nel trattamento, su larga scala, di categorie particolari di dati personali di cui all'articolo 9»
   - Widened: «le attività principali del titolare del trattamento o del responsabile del trattamento consistono nel trattamento, su larga scala, di categorie particolari di dati personali di cui all'articolo 9 o di dati relativi a condanne penali e a reati di cui all'articolo 10.»
   - Rewrite: Article 37(1) GDPR lists, among the cases in which a DPO is to be designated, processing carried out by a public authority or body, except courts acting in their judicial capacity; core activities that require regular and systematic monitoring of data subjects on a large scale; and core activities consisting of large-scale processing of special categories of personal data under Article 9.
33. **a24 C3**, GDPR art. 37: confirmed (+244 characters)
   - Original: «possono o, se previsto dal diritto dell'Unione o degli Stati membri, devono designare un responsabile della protezione dei dati»
   - Widened: «Nei casi diversi da quelli di cui al paragrafo 1, il titolare e del trattamento, il responsabile del trattamento o le associazioni e gli altri organismi rappresentanti le categorie di titolari del trattamento o di responsabili del trattamento possono o, se previsto dal diritto dell'Unione o degli Stati membri, devono designare un responsabile della protezione dei dati.»
   - Rewrite: In cases other than those in Article 37(1), controllers, processors or associations representing them may designate a DPO or, if Union or Member State law provides for it, must designate one.
34. **a24 C4**, GDPR art. 30: refused: widened_too_long (+329 characters)
   - Original: «Gli obblighi di cui ai paragrafi 1 e 2 non si applicano alle imprese o organizzazioni con meno di 250 dipendenti»
   - Widened: «Gli obblighi di cui ai paragrafi 1 e 2 non si applicano alle imprese o organizzazioni con meno di 250 dipendenti, a meno che il trattamento che esse effettuano possa presentare un rischio per i diritti e le libertà dell'interessato, il trattamento non sia occasionale o includa il trattamento di categorie particolari di dati di cui all'articolo 9, paragrafo 1, o i dati personali relativi a condanne penali e a reati di cui all'articolo 10.»
   - Rewrite: Article 30 GDPR, on records of processing activities, provides that the obligations in paragraphs 1 and 2 do not apply to enterprises or organisations with fewer than 250 employees, subject to exceptions.
