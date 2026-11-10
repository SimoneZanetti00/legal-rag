# Roadmap

What the `ask` pipeline does today, what it does not, and what comes next. The longer design
documents are [the architecture proposal](architecture/LEGAL_ASSISTANT_ARCHITECTURE.md) (§10,
steps P0–P8) and [the research report](research/LEXROOM_TECHNICAL_REVERSE_ENGINEERING.md)
(§10.2 citation resolver, §18 phases R0–R7).

## Implemented (MVP)

| Capability | Where |
|---|---|
| Recorded corpus build with hashed identity; exact provision anchors and passage links | `src/corpus_build.py`, `src/provision_anchors.py` |
| Provision store with eligibility tiers gated by human review (the ledger is still empty) | `src/provisions.py` |
| BM25 search mapped to provisions; dense, hybrid and reranking retrievers (evaluation only) | `src/provision_explorer.py`, `src/retrieval.py`, `src/dense_retrieval.py`, `src/hybrid_retrieval.py`, `src/reranking.py` |
| Deterministic evidence assembly (E1..En, budgets, one hop of references) | `src/evidence.py` |
| LLM client (mock, Anthropic) with schema-checked JSON and one bounded retry | `src/llm.py` |
| Query analysis: issues and Italian search queries | `src/query_analysis.py` |
| **Citation resolution**: instrument-aware references with `resolved`, `partially_resolved`, `ambiguous`, `unresolved`; explicit names, context, outside acts | `src/citations.py` |
| **References in the question** become exact lookups (resolved ones only) | `answer_generation.answer_question()` |
| **Cross-instrument expansion**, one hop (Privacy Code «Regolamento» to the GDPR) | `src/evidence.py` |
| Grounded generation; claim validation (exact quotations, citable evidence, instrument and article together, recitals, documents, act numbers) | `src/answer_generation.py` |
| **Evidence-support check** of each claim by a model, which can be switched off (`SEMANTIC_VERIFICATION`) | `src/support_verification.py` |
| Corpus preflight (no LLM call when nothing may be cited); privacy-safe logs; abstention with reason codes | `src/answer_generation.py`, `src/llm.py` |
| CLI: `python -m src.cli ask`, `lookup`, `search` | `src/provision_cli.py`, `src/cli.py` |
| **Offline demonstration** (`python -m src.demo`): real-corpus evidence, provenance and abstention; a synthetic end-to-end run with scripted MockLLM replies | `src/demo.py` |

## Known limitations

- **Nothing is citable yet.** The M1 human review is not recorded, so `ask` always abstains on
  the real corpus. Generation and the support check have run only against mocks.
- **The support check is a model's judgment.** It can miss or wrongly flag a claim. It sees only
  the cited evidence, so it cannot notice a condition or exception that was never retrieved.
  It is not legal validation.
- **Support check details.**
  - The check sees each evidence item's article number without its instrument, so GDPR
    Art. 33 and Code Art. 33 look alike to it. Instrument and article are checked
    deterministically before it.
  - `generate_answer()` runs the check only when asked (`verify_support=True`); `ask` runs
    it by default (`SEMANTIC_VERIFICATION=true`).
  - No test yet covers a provider error or a refusal during the check, or
    `SEMANTIC_VERIFICATION=false` through `answer_question()`.
- **Citation grammar is small.** It handles articles, lists («artt. 15, 16 e 17»), attached
  paragraphs, points and letters, recitals and numbered documents. A range («artt. 15-22») or
  «e ss.» yields only its first article. «del medesimo decreto» and «ivi» are not followed back
  to the act named before, so they stay unresolved.
- **Some article headings are read as references.** When references are followed, four Code
  articles bring in one wrong article each:
  - the headings «Art. 2-sex-decies», «Art. 2-septies-decies» and «Art. 2-quaterdecies.1»,
    whose labels the grammar does not read whole;
  - the heading of another act's article, quoted inside Code Art. 175.
- **Parts are checked against line markers.** Paragraphs «N.», points «N)» and letters «x)» at
  line start. Parts are not provisions with their own IDs.
- **The instrument table is code.** Aliases live in `CitationInstrument` entries, because editing
  the registry would change its hash and stale the build's anchors.
- **Outside acts are compared by number only.** When a claim cites an act that is not in the
  corpus, the check compares the act's number with the evidence's: «D.Lgs. 101/2018» and
  «n. 101» do not match, while two different acts numbered 101/2018 would.
- **Ambiguous references are shown, not clarified.** There is no dialogue to ask which act
  the user means.
- **Only two instruments,** with no historical versions: the GDPR as published in 2016, and
  the Privacy Code as an unverified transcription.
- **The demo's model replies are scripted.** The synthetic part shows what the checks do with
  a model's output, not how well a model answers. The real-corpus part uses a retrieval plan
  written by hand, in place of the query analysis.

## Future improvements

1. **Record the M1 review.** Once a person has reviewed the demo articles (GDPR Arts. 4, 33,
   34 and 55; Code Art. 2-bis), enter their decisions in the ledger so the demo can answer.
   Decide first whether a user transcription may ever be `primary`.
2. **Richer citation grammar:** ranges, «e ss.», «del medesimo» and «ivi» (following the act
   named before), nested parts, and annexes.
3. **Fine-grained provisions:** paragraph, point and letter IDs, so citations resolve below
   article level.
4. **More sources and official onboarding.** Each new source needs:
   - registration in `data/reference/instruments.json` and an inventory;
   - a new recorded build with anchors;
   - provenance, and an official-source check;
   - finally, one `CitationInstrument` entry, with no change to the resolver.

   Candidates: D.Lgs. 101/2018, Directive 2002/58, Garante decisions, CJEU cases (CELEX,
   Normattiva URNs).
5. **Temporal resolution:** versions over time, «come modificato da», and answers as of a date.
6. **Stronger verification and evaluation:**
   - a human-written benchmark of questions, citations and expected outcomes;
   - measurement of agreement between the support check and human reviewers;
   - a separate verifier model.
7. **Clarification workflow:** ask the user which act an ambiguous reference means, one
   question at a time.
8. **Citations in uploaded documents:** resolve references inside the user's own documents.
9. **More jurisdictions:** other member states' implementing laws, with their own instrument
   tables.
