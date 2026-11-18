# `legal-v1`: the first real legal retrieval benchmark (PROVISIONAL)

> **Status: every question and judgment is a candidate.**
> - **Drafted** by an AI assistant (Claude, in a Claude Code session) on 2026-11-11, from the
>   recorded corpus.
> - **Reviewed** by no one yet: not the project owner, not a legal expert.
> - **Not legally validated:** it says nothing about whether any provision is valid, in force
>   or applicable.
>
> Its scores must not be presented as validated retrieval quality.

Its schema, grades, judging rules and metric conventions are defined in
[docs/evaluation/guidelines.md](../../../docs/evaluation/guidelines.md). The evaluator is
`src/provision_eval.py`.

## Scope

- **Corpus:** the recorded build `build-f76ff6031f2fc82c4852f0a2bde27807`.
  - **GDPR** (`eu-reg-2016-679@oj-l119-2016-it`): the 2016 original publication in the
    Official Journal. It does not include later corrigenda.
  - **Privacy Code** (`it-dlgs-2003-196@transcription-vigente-2026-11-05`): a user-provided
    transcription, main body only. Its authenticity and legal validity are not established.
- **What relevance means:** judged against the text in that corpus, as it stands. A grade
  does not say that the text is current consolidated law. Some transcribed provisions, for
  example Art. 2-quaterdecies.1, have not been checked against an official source.
- **What it measures:** the BM25 provision search of `ask` (`ProvisionExplorer.search`), at
  article level. Each question has fixed Italian search queries, written by hand, so query
  analysis is not measured.

## Files

| File | Read by the evaluator | Content |
|---|---|---|
| `benchmark.json` | yes | the manifest: `legal`, version `1`, kind `real` |
| `questions.jsonl` | yes | 24 questions. `notes` gives each one's intended information need. |
| `judgments.jsonl` | yes | 388 article-level judgments |
| `pool.jsonl` | no | for each question, the top 10 articles of each pooling retriever, and the articles added by the judge |

Reports record the SHA-256 of the first three files.

## Questions

| ID | Split | Category | Expected outcome | Question |
|---|---|---|---|---|
| q01 | dev | definition | answerable | Che cosa si intende per dato personale? |
| q02 | dev | definition | answerable | Quando si verifica una violazione dei dati personali? |
| q03 | test | definition | answerable | Quali requisiti deve avere il consenso dell'interessato per essere valido? |
| q04 | dev | procedure | answerable | Entro quanto tempo il titolare deve notificare al Garante una violazione dei dati personali? |
| q05 | dev | procedure | answerable | Quando il titolare deve avvisare le persone coinvolte in una violazione dei loro dati? |
| q06 | test | obligation | answerable | In quali casi è obbligatoria una valutazione d'impatto sulla protezione dei dati? |
| q07 | dev | obligation | answerable | Chi deve tenere il registro delle attività di trattamento e che cosa deve contenere? |
| q08 | dev | obligation | answerable | Quando è obbligatorio designare un responsabile della protezione dei dati? |
| q09 | test | obligation | answerable | Quali informazioni deve fornire il titolare quando raccoglie i dati direttamente presso l'interessato? |
| q10 | dev | rights | answerable | Come può una persona sapere quali dati personali che la riguardano vengono trattati? |
| q11 | dev | rights | answerable | In quali casi si può ottenere la cancellazione dei propri dati personali? |
| q12 | test | rights | answerable | Si possono ricevere i propri dati in un formato leggibile per trasferirli a un altro fornitore? |
| q13 | dev | rights | answerable | Quando l'interessato può opporsi al trattamento dei suoi dati, ad esempio per il marketing diretto? |
| q14 | dev | authority | answerable | Quale autorità controlla in Italia l'applicazione della normativa sulla protezione dei dati personali? |
| q15 | test | authority | answerable | Quali poteri di indagine e correttivi ha l'autorità di controllo? |
| q16 | dev | explicit_citation | answerable | Che cosa prevede l'articolo 2-ter del Codice privacy? |
| q17 | dev | explicit_citation | answerable | Cosa stabilisce l'articolo 9 del GDPR sulle categorie particolari di dati? |
| q18 | test | cross_instrument | answerable | A che età un minore può dare da solo il consenso al trattamento dei suoi dati per i servizi online in Italia? |
| q19 | dev | cross_instrument | answerable | Chi può esercitare i diritti sui dati personali di una persona deceduta? |
| q20 | dev | cross_instrument | answerable | Come si applicano in Italia le sanzioni amministrative pecuniarie previste dal GDPR? |
| q21 | test | other | out_of_scope | Come si calcola l'IVA su una fattura emessa a un cliente estero? |
| q22 | dev | other | out_of_scope | Quali sono i requisiti per un licenziamento per giusta causa? |
| q23 | dev | other | not_in_corpus | Quali obblighi ha il fornitore di un sistema di intelligenza artificiale ad alto rischio? |
| q24 | test | other | not_in_corpus | Quali sanzioni ha inflitto il Garante nel 2025 alle società di telemarketing? |

**Coverage by category:**

| Category | Questions |
|---|---|
| `definition` | 3 |
| `obligation` | 4 |
| `procedure` | 2 |
| `rights` | 4 |
| `authority` | 2 |
| `explicit_citation` | 2 |
| `cross_instrument` | 3 |
| `other` (out of scope or not in the corpus) | 4 |

**Expected outcomes:** 20 are answerable, 2 are out of scope and 2 are not in the corpus. The
last four have no relevant judgment, so the evaluator lists them but does not score them.
There is no `needs_clarification` question yet.

## Split

The split is deterministic and was fixed before any evaluation was run:
- **test** (8): every question whose number is a multiple of 3 (q03, q06, q09, q12, q15, q18,
  q21 and q24);
- **dev** (16): all the others.

The test split is held out. Retrieval configurations are chosen on dev results only. Test
results are looked at once, to report a configuration already chosen.

## Judgments

| Instrument | Grade 2 | Grade 1 | Grade 0 | Total |
|---|---|---|---|---|
| GDPR (`eu-reg-2016-679`) | 18 | 20 | 174 | 212 |
| Privacy Code (`it-dlgs-2003-196`) | 5 | 11 | 160 | 176 |
| **All** | **23** | **31** | **334** | **388** |

How the grades were drafted, conservatively:
- **Grade 2** is given only to the provision that states the answer. Shared wording alone is
  never enough.
- **Grade 1** is given to:
  - definitions the answer relies on;
  - related obligations, exceptions and procedures;
  - the Privacy Code's implementing provisions.
- **Every other pooled article is judged 0.** Its rationale names what the article concerns,
  taken from its title in the corpus.
- **Where a grade depends on a specific detail, it was checked against the article text in
  the corpus.** That covers every Privacy Code article graded 1 or 2, and GDPR details such
  as the 16 and 13 years of Art. 8, Art. 58(2)(e), Art. 23(1)'s reference to Art. 34, and the
  definitions in Art. 4.
- **The other GDPR grades rest on the article's title in the corpus and its well-known
  content.** These are Arts. 7, 13, 15, 17, 20, 21, 30, 35, 37, 51 and 83, among others. The
  owner review must confirm them.
- **Point judgments:** GDPR Art. 4, points 1, 11, 12 and 21 (definitions).
- **Repealed articles** in the transcription (for example Code Arts. 37 and 162-ter) are
  judged 0.

## Pooling

All the candidates come from actual retrieval results, judged afterwards. No retrieved
article was assumed to be relevant.

| Source | How the candidates were found |
|---|---|
| **BM25** | the evaluator itself (`src.provision_eval.rank_articles`, so `ProvisionExplorer.search`), chunk depth 20; the top 10 articles |
| **Dense** | `src.dense_retrieval.DenseRetriever` over the build's `corpus.jsonl` (880 chunks), model `intfloat/multilingual-e5-small` from the local Hugging Face cache (revision `614241f622f5`); the top 20 chunks per query, mapped to articles; the top 10 |
| **Hybrid** | `src.hybrid_retrieval.HybridRetriever`, BM25 and dense fused with Reciprocal Rank Fusion (`BM25_TOP_K` 20, `DENSE_TOP_K` 20, `RRF_K` 60), mapped the same way; the top 10 |
| **Added by the judge** | 6 essential articles that no retriever ranked in its top 10: q04 Code Art. 2-bis and GDPR Art. 4 point 12; q14 Code Art. 153; q15 Code Arts. 154-bis, 157 and 158 |

- **Mapping chunks to articles** follows the evaluator's rules: chunks without article text
  add nothing, an article counts once at its best rank, and several queries are interleaved
  by rank.
- **What was judged:** for each question, the union of the three top-10 lists plus the
  judge's additions, 9 to 20 articles. The whole BM25 top 10 of every question is therefore
  judged.
- **Where the record is:** `pool.jsonl` records each list.
- **How dense and hybrid were run:** offline (`HF_HUB_OFFLINE=1`, no model download), with
  the embedding cache kept outside the repository. Their mapping to articles was done by a
  one-off script that is not in the repository: evaluating dense and hybrid retrieval at
  article level is a later phase (P4).
- **The reranker** (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) is in the local cache but
  was not used for pooling.

## Review status and next steps

1. **The project owner reviews** every question, grade and rationale. A question or judgment
   that passes is then marked `owner_reviewed`, with the reviewer and the date.
   **Owner review is not expert legal validation.**
2. **Expert review**, if it happens, is recorded as `expert_reviewed` with the expert's name.
3. **Any change after review becomes a new version** (`"version": "2"`), because reports
   record the benchmark version and file hashes.

## Running

```powershell
.\.venv\Scripts\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v1 `
    --output data/processed/evaluation/legal-v1-bm25.json
```

Write reports to a git-ignored place, such as `data/processed/`. While anything is still a
candidate, every report warns about it.

## Limitations

- **Unreviewed:** the judgments are candidates drafted by an AI assistant.
- **Small:** 24 questions, 20 of them scored, give unstable means. There are no confidence
  intervals yet.
- **Incomplete pools:** they come from the top 10 of three retrievers. Relevant articles that
  none of them ranked count as not relevant, unless the judge added them.
- **Article level:** points are recorded, but scored as their article.
- **Explicit-citation questions** (q16, q17) measure BM25 only. In `ask`, the citation
  resolver would look up the named article directly, and that is not measured here.
- **Not current law:** the texts are the GDPR as published in 2016 and an unverified
  transcription of the Code.
- **Italian only,** with uneven coverage by category, and no `needs_clarification` question.
