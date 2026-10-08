# Technical debt and known limitations

A cumulative register of known limitations, technical debt, risks and
improvement opportunities in `legal-rag`. It exists to plan a separate
improvement pass once the main framework is implemented. It is not a roadmap
(see [MASTER_PROMPT.md](MASTER_PROMPT.md)) and does not repeat the usage notes
in [README.md](README.md).

- **Baseline:** Phase 5 (hybrid retrieval), written on top of commit `89b58c7`,
  2026-10-08. First version: commit `910b522` (Phase 4B), 2026-10-01.
- **Phases covered:** 1 (setup), 2 (ingestion and chunking), 3 (BM25),
  4A (retrieval evaluation), 4B (dense retrieval), 5 (hybrid retrieval). Later
  phases appear only as risks and questions to revisit.

## How to read an entry

**Kind** says how well an item is supported:

| Kind | Meaning |
|---|---|
| Confirmed | Verified in the current code, or reproduced. |
| Observed | Seen in an actual run, usually once and on synthetic data. Not a general conclusion. |
| Hypothesis | Plausible but not verified. Needs investigation before any fix. |
| Opportunity | A possible improvement. Not a defect; adopt only with evidence. |
| Risk | A question to answer when a later phase is built. |

**Priority:** *critical* = produces wrong or unsafe results now; *high* = blocks
valid conclusions or a coming phase; *medium* = should be fixed in the
improvement pass; *low* = minor, cosmetic or rarely triggered. No item is
currently rated critical.

**Status:** open, investigating, planned, resolved, or deferred.

No retrieval-quality claim in this file is backed by a benchmark, because none
exists yet (TD-015). Items that depend on measured quality say so.

Evidence comes from the code, from the test suite, or from runs made during
development. Unless an entry names a test, its observations were recorded in
the phase reports and are not asserted by the test suite.

## Index

| ID | Title | Area | Kind | Priority | Status |
|---|---|---|---|---|---|
| TD-001 | No OCR for scanned PDFs | Ingestion | Confirmed | Medium | Deferred |
| TD-002 | Ingestion never run on real legal documents | Ingestion | Confirmed | High | Open |
| TD-003 | Structure detection is heuristic and narrow | Chunking | Confirmed | Medium | Open |
| TD-004 | Chunks carry no document title; metadata only via sidecars | Chunking | Confirmed | Medium | Open |
| TD-005 | IDs and file hashes depend on line endings | Ingestion, evaluation | Confirmed | Medium | Open |
| TD-006 | Ingestion CLI crashes on some file names when output is piped | Ingestion | Confirmed | Low | Open |
| TD-007 | Effect of chunking choices on retrieval is unmeasured | Chunking | Hypothesis | Low | Open |
| TD-008 | DOCX and non-UTF-8 text are not supported | Ingestion | Confirmed | Low | Deferred |
| TD-009 | PyMuPDF is AGPL-licensed | Ingestion | Confirmed | Low | Open |
| TD-010 | No stemming, abbreviation or synonym matching | BM25 | Confirmed | Medium | Open |
| TD-011 | Structural tokens have known gaps | BM25 | Confirmed | Low | Open |
| TD-012 | Positive IDF overrides a private method of `rank-bm25` | BM25 | Confirmed | Low | Open |
| TD-013 | Indexes are rebuilt per run; cost at scale is unmeasured | BM25, dense | Hypothesis | Low | Open |
| TD-014 | Document title is not searchable | BM25 | Confirmed | Low | Open |
| TD-015 | No curated legal benchmark | Evaluation | Confirmed | High | Open |
| TD-016 | Judgments are tied to chunk IDs, with no migration | Evaluation | Confirmed | Medium | Open |
| TD-017 | Recall comparison is skewed by result counts | Evaluation | Observed | Medium | Open |
| TD-018 | No significance testing; unjudged chunks count as misses | Evaluation | Confirmed | Medium | Open |
| TD-019 | Reports do not record library versions or model revision | Evaluation | Confirmed | Medium | Open |
| TD-020 | Short cross-language queries can miss | Dense | Observed | Medium | Open |
| TD-021 | Similarity scores are closely bunched | Dense | Observed | Medium | Open |
| TD-022 | Silent truncation at 512 tokens | Dense, chunking | Confirmed | Medium | Open |
| TD-023 | The embedding model is not legally validated | Dense | Confirmed | Medium | Open |
| TD-024 | Dense retrieval ignores structural metadata | Dense | Opportunity | Low | Open |
| TD-025 | Input prefixes are chosen by a name heuristic | Dense | Confirmed | Low | Open |
| TD-026 | No relevance cut-off | Dense | Confirmed | Medium | Open |
| TD-027 | Cache key does not cover model revision or library version | Embedding cache | Confirmed | Medium | Open |
| TD-028 | Model revision is not pinned | Model identity | Confirmed | Medium | Open |
| TD-029 | Cache files are never cleaned up | Embedding cache | Confirmed | Low | Open |
| TD-030 | Dense and hybrid modules import a private helper | Coupling | Confirmed | Low | Open |
| TD-031 | Logic is duplicated across retrievers and CLIs | Coupling | Confirmed | Medium | Open |
| TD-032 | Evaluation depends on the ingestion module | Coupling | Confirmed | Low | Open |
| TD-033 | Most settings are defined but unused | Configuration | Confirmed | Low | Open |
| TD-034 | Layout differs from the spec; no packaging | Project structure | Confirmed | Low | Open |
| TD-035 | Only direct dependencies are pinned | Environment | Confirmed | Medium | Open |
| TD-036 | No CI; tested on one platform only | Environment | Confirmed | Medium | Open |
| TD-037 | The real model is exercised only by opt-in tests | Testing | Confirmed | Medium | Open |
| TD-038 | Behind HTTPS inspection, model downloads fail and cached loads are slow | Environment | Observed | Low | Open |
| TD-039 | Heavy environment and slow first import | Environment | Observed | Low | Open |
| TD-040 | Hybrid retrieval: fusion and comparison questions | Hybrid | Risk | High | Resolved |
| TD-041 | Reranking: unverified model and input limits | Reranking (future) | Risk | Medium | Open |
| TD-042 | Generation: token budget, citations and provenance | Generation (future) | Risk | Medium | Open |
| TD-043 | Abstention thresholds need calibrated scores | Abstention (future) | Risk | High | Open |
| TD-044 | Temporal filtering has no data to work on | Abstention (future) | Confirmed | Medium | Open |
| TD-045 | Privacy and untrusted text in generation | Generation (future) | Risk | High | Open |
| TD-046 | Okapi IDF scored real matches zero or negative | BM25 | Confirmed | High | Resolved |
| TD-047 | Search output could crash on characters the console cannot show | Search CLIs | Confirmed | Low | Resolved |
| TD-048 | A unit test attempted a real model download | Testing | Confirmed | Medium | Resolved |
| TD-049 | RRF parameters are untuned defaults | Hybrid | Confirmed | Medium | Open |
| TD-050 | RRF ignores score magnitude | Hybrid | Confirmed | Low | Open |
| TD-051 | The fused score is not a calibrated confidence | Hybrid | Confirmed | Medium | Open |
| TD-052 | "Found by both" always wins, and small corpora make it meaningless | Hybrid | Confirmed | Medium | Open |
| TD-053 | Ties are common and the chunk-ID tie-break is arbitrary | Hybrid | Confirmed | Medium | Open |
| TD-054 | Hybrid retrieval depends on the dense model, with no fallback | Hybrid | Confirmed | Low | Open |
| TD-055 | Metadata and temporal filters are not implemented | Retrieval | Confirmed | Medium | Deferred |
| TD-056 | Real-model runs print library progress output | Environment | Observed | Low | Open |
| TD-057 | Evaluation cutoffs above the hybrid candidate depth are not comparable | Hybrid, evaluation | Confirmed | Medium | Open |

## Ingestion and chunking (Phase 2)

### TD-001 · No OCR for scanned PDFs
- **Kind:** Confirmed · **Priority:** Medium (affects only scanned sources, and fails loudly) · **Status:** Deferred (the spec asks the MVP to detect the case, not solve it)
- **Evidence:** `src/ingestion.py` rejects image-only PDFs with an explicit OCR message. Image-only pages inside a readable PDF produce a warning and are left out. Both are tested.
- **Impact:** Scanned legislation or case law cannot be ingested. Partially scanned documents are ingested with missing pages.
- **Follow-up:** Decide whether OCR belongs in the project or in a documented manual step before ingestion.

### TD-002 · Ingestion never run on real legal documents
- **Kind:** Confirmed · **Priority:** High (every later result rests on chunk quality) · **Status:** Open
- **Evidence:** `data/raw/` holds only `.gitkeep`. Every ingestion and chunking test builds synthetic TXT, or synthetic PDFs with PyMuPDF's `insert_text`.
- **Impact:** Behaviour on real layouts is unknown: multi-column pages, running headers and footers, footnotes, hyphenation, tables. The README lists these as limitations, but none has been observed or measured.
- **Follow-up:** Ingest a small set of public legal texts the project is permitted to process. Review the chunks by hand and record concrete failure cases here.
- **Depends on:** Choosing a permitted corpus.

### TD-003 · Structure detection is heuristic and narrow
- **Kind:** Confirmed · **Priority:** Medium (wrong boundaries degrade chunks and structural search) · **Status:** Open
- **Evidence:** `src/chunking.py` recognises article and section headings in English and Italian only, and only when the number is followed by nothing, a separator, or a parenthesised title. `Art. 1 Oggetto` and `§ 1` are not recognised. Numbered lists inside articles are treated as paragraphs.
- **Impact:** Unrecognised headings lose their article metadata, which also removes the `art:` token used by BM25 (TD-011).
- **Follow-up:** Extend the patterns only for formats actually found in TD-002. Add each as a test case.
- **Depends on:** TD-002.

### TD-004 · Chunks carry no document title; metadata only via sidecars
- **Kind:** Confirmed · **Priority:** Medium (needed before citations are displayed) · **Status:** Open
- **Evidence:** `LegalChunk` has `chunk_id`, `doc_id`, `text`, `chunk_index`, `location`, `metadata`. `LegalDocument.title` is not written by `src/chunk_store.py`. Legal metadata comes only from optional `<file>.meta.json` sidecars.
- **Impact:** A citation can show a file path but not a title. Jurisdiction, dates and authority are empty unless someone writes sidecars by hand.
- **Follow-up:** Add the title to the chunk record before the citation phase. This is a schema change that needs re-ingestion; chunk IDs would not change.

### TD-005 · IDs and file hashes depend on line endings
- **Kind:** Confirmed (mechanism demonstrated; no current data is affected) · **Priority:** Medium (nothing is broken today; it must be decided before text sources are shared through Git) · **Status:** Open
- **How the values are computed:** `doc_id` is `doc-` plus the first 16 hex characters of the SHA-256 of the file's bytes (`src/ingestion.py`). A chunk ID is `<doc_id>-<index>-<hash of the chunk text>` (`src/chunking.py`). The evaluation report records the SHA-256 of the bytes of the chunk, query and judgment files (`_file_info` in `src/retrieval_eval.py`).
- **Demonstrated:**
  - The same TXT document saved with LF and with CRLF endings gets different `doc_id`s and therefore different chunk IDs. The extracted text, the chunk texts and the text-hash part of each chunk ID are identical.
  - On the development machine (Git for Windows, where `core.autocrlf=true` comes from Git's system configuration), the tracked fixture files are LF in the commit and CRLF in the working copy. The file hash the evaluation report records for them differs accordingly. The repository has no `.gitattributes`.
  - Chunk IDs stored inside a chunk file are literal strings: reading the fixture chunk file gives the same IDs with either line ending.
- **Not demonstrated (potential impact):** No source document is version-controlled (`data/raw/` and `data/processed/` are git-ignored), and no curated judgments exist, so nothing is affected today. If TXT sources were shared through Git and re-ingested on a platform with different line-ending conversion, their chunk IDs would differ and judgments would be rejected as referring to unknown chunks. A benchmark shared as a chunk file would keep its IDs; only the report's file hashes would differ. PDFs are binary and should not be converted by Git; this was not tested.
- **Follow-up:** Add a `.gitattributes` that fixes line endings for data and fixtures, or compute `doc_id` from normalised text. Decide when choosing how the TD-015 corpus is distributed.

### TD-006 · Ingestion CLI crashes on some file names when output is piped
- **Kind:** Confirmed (reproduced by hand with the current code; no automated test covers it) · **Priority:** Low (narrow conditions; the chunk file is still written) · **Status:** Open
- **Evidence in code:** `_print_report` in `src/ingestion.py` prints each ingested file's path to stdout. `main` does not call `sys.stdout.reconfigure(errors="replace")`, which the other three CLIs do.
- **Reproduction:** Running the repository's current `python -m src.ingestion` on Windows with stdout piped (encoding cp1252), on temporary input files created outside the repository:
  - A successfully ingested file named in Greek letters: `UnicodeEncodeError`, exit code 1, no summary printed. The chunk file was written.
  - A file with an accented name that cp1252 can represent (`società.txt`): no error.
  - A Greek-named file that fails ingestion: no error, because failures are printed to stderr, which escapes such characters.
  - The first case with `PYTHONIOENCODING=utf-8` or `PYTHONUTF8=1`: no error.
- **Not tested:** An interactive Windows console, and other operating systems.
- **Impact:** In the failing case the per-file report is lost and the exit code signals failure although ingestion completed.
- **Follow-up:** Apply the same one-line stdout setting to the ingestion CLI, with a test.

### TD-007 · Effect of chunking choices on retrieval is unmeasured
- **Kind:** Hypothesis · **Priority:** Low (no evidence of a problem) · **Status:** Open
- **Evidence:** By design, overlap is applied only when an oversized paragraph is split, chunks never cross article or section headings, and sizes are in characters.
- **Impact:** Unknown. These choices may help or hurt retrieval.
- **Follow-up:** Compare chunk settings on the benchmark. Change nothing without that comparison.
- **Depends on:** TD-015, TD-016.

### TD-008 · DOCX and non-UTF-8 text are not supported
- **Kind:** Confirmed · **Priority:** Low (the spec makes DOCX optional) · **Status:** Deferred
- **Evidence:** `SUPPORTED_SUFFIXES = (".pdf", ".txt")`. Text that is not valid UTF-8 is rejected with a conversion message.
- **Follow-up:** Add only if real sources require it.

### TD-009 · PyMuPDF is AGPL-licensed
- **Kind:** Confirmed · **Priority:** Low (fine for a public academic prototype) · **Status:** Open
- **Evidence:** `requirements.txt` pins `PyMuPDF==1.28.2` and notes the AGPL-3.0 or commercial licence.
- **Impact:** Constrains distributing the project as part of a closed product.
- **Follow-up:** Revisit if the project's licensing goals change.

## BM25 retrieval (Phase 3)

### TD-010 · No stemming, abbreviation or synonym matching
- **Kind:** Confirmed · **Priority:** Medium (a known recall gap in Italian) · **Status:** Open
- **Evidence:** `tests/test_retrieval.py` records non-matches: `obblighi`/`obbligo`, `lavoratori`/`lavoratore`, `sanzioni`/`sanzione`, `decreto legislativo`/`d.lgs.`, `licenziamento`/`recesso`.
- **Impact:** Queries miss passages that use a different word form or an abbreviation.
- **Follow-up:** Evaluate an Italian stemmer on the benchmark. It may merge distinct legal terms, so adopt it only if the measured result is better.
- **Depends on:** TD-015.

### TD-011 · Structural tokens have known gaps
- **Kind:** Confirmed, with one Observed effect · **Priority:** Low · **Status:** Open
- **Evidence:** `art:` and `par:` tokens come only from chunk metadata, so they exist only where the chunker detected a heading (TD-003). Only the first number after a keyword is linked (`artt. 5 e 6`). Observed on a demo corpus where four of six chunks belonged to one article: a chunk citing that article ranked third, above two of its chunks.
- **Impact:** Article lookup is weaker for undetected headings, ranges, and articles that dominate a small corpus.
- **Follow-up:** Revisit with real documents (TD-002).

### TD-012 · Positive IDF overrides a private method of `rank-bm25`
- **Kind:** Confirmed · **Priority:** Low (the dependency is pinned and the formula is tested) · **Status:** Open
- **Evidence:** `_PositiveIdfBM25._calc_idf` in `src/retrieval.py` replaces a private method of `rank_bm25.BM25Okapi` and sets its `average_idf` attribute.
- **Impact:** A library upgrade could change the internals. The hand-computed formula tests would catch a change in results.
- **Follow-up:** Keep the pin, or implement the short BM25 formula in the project and drop the reliance on internals.

### TD-013 · Indexes are rebuilt per run; cost at scale is unmeasured
- **Kind:** Hypothesis · **Priority:** Low (no measured problem) · **Status:** Open
- **Evidence:** `BM25Retriever` tokenises the whole corpus on construction and scores every chunk per query. `DenseRetriever` compares the query with every chunk in memory. `HybridRetriever` (Phase 5) holds both indexes and runs both scans, one after the other, for every query. No timing has been taken on a realistic corpus.
- **Follow-up:** Measure index and query time on the TD-002 corpus before deciding whether persistence or a vector index is needed.
- **Depends on:** TD-002.

### TD-014 · Document title is not searchable
- **Kind:** Confirmed · **Priority:** Low · **Status:** Open
- **Evidence:** A consequence of TD-004. `index_tokens` indexes text, section heading, article and paragraph only.
- **Follow-up:** Index the title once TD-004 adds it.
- **Depends on:** TD-004.

## Retrieval evaluation (Phase 4A)

### TD-015 · No curated legal benchmark
- **Kind:** Confirmed · **Priority:** High (no quality claim or tuning decision is possible without it) · **Status:** Open
- **Evidence:** `data/evaluation/` holds only `.gitkeep`. The only evaluation data is `tests/fixtures/synthetic_retrieval/`: nine invented passages, six queries, eight judgments. On it, `bm25` and `bm25-okapi` produce identical scores.
- **Impact:** The project's research questions (hybrid vs dense, effect of reranking) cannot be answered. Several items here are blocked on it.
- **Follow-up:** Build queries and graded judgments over a real corpus, judged by people qualified to assess legal relevance. Record the labelling guidelines and the chunk settings used.
- **Depends on:** TD-002, TD-005.

### TD-016 · Judgments are tied to chunk IDs, with no migration
- **Kind:** Confirmed · **Priority:** Medium (makes chunking experiments expensive) · **Status:** Open
- **Evidence:** Chunk IDs change with document bytes and with `CHUNK_SIZE`/`CHUNK_OVERLAP`. `check_judged_chunks_exist` detects stale judgments and stops; nothing remaps them.
- **Impact:** Any change to chunking invalidates the benchmark and requires relabelling.
- **Follow-up:** Freeze chunk settings for the benchmark, or judge at a level that survives re-chunking (document plus article, or character span).

### TD-017 · Recall comparison is skewed by result counts
- **Kind:** Observed · **Priority:** Medium (affects every comparison between BM25 and dense or hybrid) · **Status:** Open
- **Evidence:** BM25 returns only chunks that share a query word. Dense retrieval always returns `top_k`, and hybrid retrieval returns results whenever dense does. With a deterministic fake encoder on the nine-chunk fixture, dense recall@10 was 1.000 simply because k exceeded the corpus size. In the Phase 5 smoke run with the real model on the same fixture, mean recall@5 was 0.625 for BM25 and 1.000 for both dense and hybrid; five results out of nine chunks cover most of the corpus.
- **Impact:** Recall at a k near the corpus size favours dense and hybrid retrieval for a reason unrelated to quality.
- **Follow-up:** Compare at k well below the corpus size, and report how many results each retriever returned.
- **Depends on:** TD-015.

### TD-018 · No significance testing; unjudged chunks count as misses
- **Kind:** Confirmed · **Priority:** Medium (small query sets give unstable means) · **Status:** Open
- **Evidence:** `src/retrieval_eval.py` reports unweighted means only. Retrieved chunks without a judgment are treated as not relevant. Relevance is chunk-level only.
- **Follow-up:** Add confidence intervals once a benchmark exists. Judge the pooled top results of every retriever being compared.
- **Depends on:** TD-015.

### TD-019 · Reports do not record library versions or model revision
- **Kind:** Confirmed · **Priority:** Medium (needed to reproduce a dense result) · **Status:** Open
- **Evidence:** The JSON report holds the retriever name, the model name and prefixes, the k values, and input file hashes. For hybrid runs it also holds the fusion method, `rrf_k` and both candidate depths. It holds no package versions and no model revision.
- **Follow-up:** Add the versions of the retrieval libraries and the resolved model revision to `retriever_details`.
- **Depends on:** TD-028.

## Dense retrieval (Phase 4B)

### TD-020 · Short cross-language queries can miss
- **Kind:** Observed (one three-passage synthetic check) · **Priority:** Medium · **Status:** Open
- **Evidence:** With `intfloat/multilingual-e5-small`, the Italian query `notifica di una violazione dei dati` ranked the English data-breach passage last (0.776), behind two unrelated Italian passages (0.822, 0.808). The English query, and a longer Italian query, ranked it first.
- **Impact:** Italian questions may not surface relevant English sources, and the reverse.
- **Follow-up:** Include cross-language queries in the benchmark. Compare other models only against that evidence.
- **Depends on:** TD-015.

### TD-021 · Similarity scores are closely bunched
- **Kind:** Observed · **Priority:** Medium (matters for thresholds and for telling close passages apart) · **Status:** Open
- **Evidence:** On the synthetic fixture, the query `obblighi del datore di lavoro` scored "Obblighi dei lavoratori" 0.9057 and "Obblighi del datore di lavoro" 0.9026. Across the runs made so far, scores ranged from about 0.75 to 0.91, including for unrelated passages.
- **Impact:** Small score differences decide the ranking, and a fixed score threshold would separate relevant from irrelevant poorly.
- **Follow-up:** Measure score distributions for relevant and non-relevant chunks on the benchmark.
- **Depends on:** TD-015.

### TD-022 · Silent truncation at 512 tokens
- **Kind:** Confirmed (limit); measured on synthetic text · **Priority:** Medium (default settings fit, with little margin for citation-dense text) · **Status:** Open
- **Evidence:** The model truncates inputs at 512 tokens. `CHUNK_SIZE` is in characters. Measured with the model's tokenizer: a 1200-character chunk is about 260–280 tokens of prose and about 480 tokens when dense with citations. Prose exceeds the limit between 2,000 and 2,400 characters.
- **Impact:** The tail of a long chunk is left out of its embedding with no warning. Raising `CHUNK_SIZE` makes this common.
- **Follow-up:** Count tokens when embedding, and report how many chunks were truncated.

### TD-023 · The embedding model is not legally validated
- **Kind:** Confirmed (fact); impact unmeasured · **Priority:** Medium · **Status:** Open
- **Evidence:** `intfloat/multilingual-e5-small` is a general multilingual model with no legal-domain tuning. It has been run only on synthetic passages.
- **Follow-up:** Treat it as a baseline. Compare alternatives on the benchmark.
- **Depends on:** TD-015.

### TD-024 · Dense retrieval ignores structural metadata
- **Kind:** Opportunity · **Priority:** Low (no evidence of benefit yet) · **Status:** Open
- **Evidence:** `DenseRetriever` embeds `passage_prefix + chunk.text` only. A chunk that continues an article carries no heading in its embedded text, unlike in the BM25 index.
- **Follow-up:** Test whether adding the section and article heading to the embedded text helps. It would change the cache key and consume tokens (TD-022).
- **Depends on:** TD-015.

### TD-025 · Input prefixes are chosen by a name heuristic
- **Kind:** Confirmed · **Priority:** Low (correct for the configured model) · **Status:** Open
- **Evidence:** `input_prefixes` adds `query: `/`passage: ` when the model name contains an `e5` part, and nothing otherwise.
- **Impact:** A model that needs different instructions, or an E5 model loaded from a renamed local path, would silently get the wrong prefixes.
- **Follow-up:** Make the prefixes explicit settings, or read them from the model's own configuration.

### TD-026 · No relevance cut-off
- **Kind:** Confirmed · **Priority:** Medium (needed for abstention) · **Status:** Open
- **Evidence:** `DenseRetriever.search` returns `top_k` chunks whenever the corpus has that many. `HybridRetriever` inherits this: a query with no lexical match still returns the dense candidates (tested). `MIN_RETRIEVAL_SCORE` is defined in `src/config.py` and read nowhere.
- **Impact:** Unrelated passages are returned for questions the corpus cannot answer.
- **Follow-up:** See TD-043.

## Embedding cache and model identity

### TD-027 · Cache key does not cover model revision or library version
- **Kind:** Confirmed · **Priority:** Medium (can serve stale embeddings silently) · **Status:** Open
- **Evidence:** `_cache_key` hashes a format tag, the model name, the passage prefix, and each chunk's ID and text. It does not include the model's revision, the truncation length, or library versions.
- **Impact:** After a model is updated under the same name, cached embeddings from the old weights are reused. The README tells users to clear the cache by hand.
- **Follow-up:** Add the resolved model revision to the key.
- **Depends on:** TD-028.

### TD-028 · Model revision is not pinned
- **Kind:** Confirmed · **Priority:** Medium (reproducibility) · **Status:** Open
- **Evidence:** `SentenceTransformerEncoder` loads the model by name with no `revision`. The revision cached during verification was `614241f`.
- **Impact:** Two installations can use different weights under the same model name.
- **Follow-up:** Add an optional revision setting and record the resolved revision (TD-019).

### TD-029 · Cache files are never cleaned up
- **Kind:** Confirmed · **Priority:** Low · **Status:** Open
- **Evidence:** Each new combination of chunks and model writes a new `.npy` file under `data/indexes/embeddings/`. Nothing removes old ones.
- **Follow-up:** Document or add a simple prune step if the directory grows.

## Hybrid retrieval (Phase 5)

### TD-049 · RRF parameters are untuned defaults
- **Kind:** Confirmed (fact); effect unmeasured · **Priority:** Medium (they shape every hybrid ranking) · **Status:** Open
- **Evidence:** `RRF_K=60`, `BM25_TOP_K=20` and `DENSE_TOP_K=20` are conventional starting values taken from the existing configuration defaults. Both retrievers have equal weight. None was chosen from data, because no benchmark exists.
- **Impact:** Unknown. Different values can change the fused order (a test shows `rrf_k=1` and `rrf_k=60` ordering the same lists differently).
- **Follow-up:** Tune on the benchmark, and only then consider per-retriever weights.
- **Depends on:** TD-015.

### TD-050 · RRF ignores score magnitude
- **Kind:** Confirmed (by design) · **Priority:** Low (no evidence that it hurts) · **Status:** Open
- **Evidence:** `reciprocal_rank_fusion` uses each chunk's position only. A first place won by a wide margin counts the same as one won narrowly. Scores were deliberately not normalized: BM25 scores are unbounded and corpus-dependent, and dense scores are bunched (TD-021).
- **Follow-up:** Compare with a score-aware fusion only when benchmark data can show a difference.
- **Depends on:** TD-015.

### TD-051 · The fused score is not a calibrated confidence
- **Kind:** Confirmed · **Priority:** Medium (it will be tempting to threshold it for abstention) · **Status:** Open
- **Evidence:** A fused score is a sum of `1 / (rrf_k + rank)` terms. With the defaults it lies between 1/80 and 2/61 whatever the query, including queries the corpus cannot answer. It says nothing about relevance in absolute terms.
- **Impact:** It cannot serve as a relevance threshold, and it is not comparable across queries or settings.
- **Follow-up:** See TD-043.

### TD-052 · "Found by both" always wins, and small corpora make it meaningless
- **Kind:** Confirmed (property of the formula); Observed on the fixture · **Priority:** Medium (it affects any evaluation on a small corpus) · **Status:** Open
- **Evidence:** A chunk returned by both retrievers outranks any chunk returned by only one whenever the candidate depth is below `rrf_k + 2`, which holds at the defaults (20 against 62). A test covers it. Dense retrieval returns candidates for every query (TD-026), so on a corpus with no more chunks than `DENSE_TOP_K` its list is the whole corpus. On the nine-chunk fixture the CLI reports "BM25 5, dense 9" candidates: every BM25 match is automatically "found by both".
- **Impact:** On small corpora the hybrid order is the BM25 matches first, then the remaining chunks in dense order. Hybrid scores on the synthetic fixture therefore say nothing about fusion quality.
- **Follow-up:** Evaluate on a corpus much larger than the candidate depths.
- **Depends on:** TD-002, TD-015.

### TD-053 · Ties are common and the chunk-ID tie-break is arbitrary
- **Kind:** Confirmed (design); Observed on the fixture · **Priority:** Medium (it decided a top result) · **Status:** Open
- **Evidence:** Equal fused scores are ordered by `chunk_id`, which is deterministic but unrelated to relevance, and arbitrary across documents because document IDs are hashes. Ties arise easily: a chunk ranked 1st and 2nd ties exactly with one ranked 2nd and 1st. With the real model on the fixture, the query `obblighi del datore di lavoro` produced exactly that tie for its top two results (both 0.0325), so the first result, and that query's reciprocal rank, were decided by the chunk ID.
- **Impact:** Measured hybrid metrics can depend on the tie-break.
- **Follow-up:** Count how often ties occur on the benchmark before choosing another rule.
- **Depends on:** TD-015.

### TD-054 · Hybrid retrieval depends on the dense model, with no fallback
- **Kind:** Confirmed (by design) · **Priority:** Low · **Status:** Open
- **Evidence:** `HybridRetriever.search` does not catch errors from either retriever, and the CLI exits with code 2 when the embedding model cannot be loaded (both tested). It never returns BM25-only results in place of hybrid ones.
- **Impact:** Hybrid search is unavailable wherever the model is (TD-038), and every search pays for both scans (TD-013).
- **Follow-up:** None. An explicit, visible fallback could be added if a use case needs it.

### TD-055 · Metadata and temporal filters are not implemented
- **Kind:** Confirmed · **Priority:** Medium · **Status:** Deferred (decided when Phase 5 was designed)
- **Evidence:** `MASTER_PROMPT.md` lists "available metadata and temporal filters" under Phase 5. They were left out of the approved Phase 5 scope. No retriever accepts a filter.
- **Reason:** No document has any metadata to filter on (TD-044), and filters would require changing both existing retrievers.
- **Follow-up:** Build them once sources carry metadata.
- **Depends on:** TD-004, TD-044.

### TD-056 · Real-model runs print library progress output
- **Kind:** Observed · **Priority:** Low (cosmetic) · **Status:** Open
- **Evidence:** Running the dense, hybrid or evaluation CLI with the real model prints the embedding library's `Loading weights` progress lines and warnings on stderr, mixed with the program's own messages.
- **Follow-up:** Silence or redirect the library's output in the CLIs.

### TD-057 · Evaluation cutoffs above the hybrid candidate depth are not comparable
- **Kind:** Confirmed (reproduced during the Phase 5 review; tested) · **Priority:** Medium (it can make hybrid look worse in a comparison) · **Status:** Open (flagged by a warning, not prevented)
- **Evidence:** `HybridRetriever` returns at most `bm25_top_k + dense_top_k` results per query (40 by default), while BM25 and dense retrieval return as many as requested. In a review run with the fake encoder on a 120-chunk synthetic corpus where every chunk was judged relevant, at k=100 BM25 and dense each returned 100 results (recall 0.833) and hybrid returned 20 (recall 0.167). Recall@10 was identical for all three. Hybrid returned 20, not 40, because both retrievers had picked the same chunks.
- **Impact:** At a cutoff above the candidate depths, hybrid's lower recall reflects where its ranking ends, not its ranking quality.
- **Mitigation in place:** When a cutoff exceeds a retriever's `max_results`, `src/retrieval_eval.py` adds a warning to the terminal summary and to `warnings` in the report. The metrics are left as computed and the run still succeeds. Tests cover the warning, the unchanged results, and the absence of the warning for BM25, dense, and cutoffs within reach.
- **Remaining gap:** No warning is given for a cutoff between the smaller candidate depth and the maximum, where hybrid may also return fewer results than the cutoff. Each query's `retrieved` list in the report shows the real count.
- **Follow-up:** Decide whether the evaluator should refuse such cutoffs, or whether the candidate depths should grow with the evaluation k. Revisit with TD-049.
- **Depends on:** TD-049.

## Internal coupling and configuration

### TD-030 · Dense and hybrid modules import a private helper
- **Kind:** Confirmed · **Priority:** Low · **Status:** Open
- **Evidence:** `src/dense_retrieval.py` and, since Phase 5, `src/hybrid_retrieval.py` both have `from src.retrieval import _format_passage`. It keeps the three CLIs' output identical without editing the BM25 module.
- **Follow-up:** Make the helper public or move it to a shared module.

### TD-031 · Logic is duplicated across retrievers and CLIs
- **Kind:** Confirmed · **Priority:** Medium (it grew with the third retriever, as predicted) · **Status:** Open
- **Evidence:**
  - Query and `top_k` validation now exists three times: in `BM25Retriever`, `DenseRetriever` and `src/hybrid_retrieval.py`. One test keeps the three identical.
  - The duplicate chunk ID check and `from_jsonl` are repeated in `BM25Retriever` and `DenseRetriever`.
  - The default chunk path literal appears in five modules.
  - Defaults are defined twice and kept equal by tests: the embedding model (`src/config.py`, `src/dense_retrieval.py`), and the two candidate depths and the RRF constant (`src/config.py`, `src/hybrid_retrieval.py`).
  - `src/hybrid_retrieval.py` declares its own two-line `search` protocol, a copy of the one in `src/retrieval_eval.py`, to avoid a circular import.
  - The fake encoder helpers are copied between `tests/test_dense_retrieval.py` and `tests/test_hybrid_retrieval.py`.
- **Decision in Phase 5:** The validation was copied, not extracted, so that the working BM25 and dense modules stayed untouched.
- **Follow-up:** Extract the shared pieces into one small module as a separate refactoring change, before another retriever or the reranker is added.

### TD-032 · Evaluation depends on the ingestion module
- **Kind:** Confirmed · **Priority:** Low · **Status:** Open
- **Evidence:** `src/retrieval_eval.py` imports `display_path` from `src/ingestion.py`, which imports PyMuPDF.
- **Follow-up:** Move the path helper to a module without that dependency.

### TD-033 · Most settings are defined but unused
- **Kind:** Confirmed · **Priority:** Low · **Status:** Open
- **Evidence:** Of the 20 settings, eight are read outside `src/config.py`: `DATA_DIR` (through the raw, processed and evaluation paths), `INDEX_DIR`, `EMBEDDING_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP` and, since Phase 5, `BM25_TOP_K`, `DENSE_TOP_K` and `RRF_K`. The other twelve are read by no code outside `src/config.py`:
  - `RERANKER_ENABLED`, `RERANKER_MODEL`
  - `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`
  - `RERANK_TOP_K`, `FINAL_EVIDENCE_COUNT`
  - `CONTEXT_TOKEN_BUDGET`
  - `MIN_RETRIEVAL_SCORE`, `MIN_RERANK_SCORE`
  - `UNDATED_SOURCE_POLICY`, `MAX_GENERATION_RETRIES`

  Nine of them are checked in `_validate`. `LLM_API_KEY`, `MIN_RETRIEVAL_SCORE` and `MIN_RERANK_SCORE` are only parsed; the only other reader of `LLM_API_KEY` is `Settings.require_llm_api_key()`, which only tests call. (The first version of this entry counted `LLM_API_KEY` as validated; it never was.)
- **Impact:** Documented settings with no effect can mislead. Their defaults, including the reranker model name, have never been exercised.
- **Follow-up:** Verify each setting when its phase lands. Remove any that end up unused.

### TD-034 · Layout differs from the spec; no packaging
- **Kind:** Confirmed · **Priority:** Low · **Status:** Open
- **Evidence:** Compared with the layout suggested in `PROJECT_SPEC.md` §5: evaluation lives in `src/retrieval_eval.py`, not in an `evaluation/` directory; dense and hybrid retrieval each have their own module; `indexing.py` and `utils.py` do not exist, because index building lives in the retriever modules. Modules for later phases (`pipeline.py`, `reranking.py`, `generation.py`, `verification.py`, `app/`) are not due yet. The package is named `src`, there is no `pyproject.toml` or `setup.py`, and `python -m src.…` fails when run from another directory.
- **Follow-up:** Update the spec's layout section to match, or restructure once the pipeline module exists.

## Environment, downloads and reproducibility

### TD-035 · Only direct dependencies are pinned
- **Kind:** Confirmed · **Priority:** Medium (installs are not reproducible) · **Status:** Open
- **Evidence:** `requirements.txt` pins five direct dependencies. Transitive ones are not pinned; development used `torch` 2.14.0, `transformers` 5.17.0, `huggingface-hub` 1.33.0 and `numpy` 2.5.3.
- **Follow-up:** Add a constraints or lock file.

### TD-036 · No CI; tested on one platform only
- **Kind:** Confirmed · **Priority:** Medium · **Status:** Open
- **Evidence:** There is no CI configuration. All runs were on Windows 11 with Python 3.13.2. The README states Python 3.11+, which is untested.
- **Follow-up:** Run the default (offline) suite in CI on Windows and Linux for the supported Python versions.

### TD-037 · The real model is exercised only by opt-in tests
- **Kind:** Confirmed · **Priority:** Medium (integration regressions would go unnoticed) · **Status:** Open
- **Evidence:** The default suite uses fake encoders and replaces the `sentence_transformers` module. Two tests named `test_real_model_smoke`, one for dense and one for hybrid retrieval, run only with `RUN_REAL_MODEL_TESTS=1` and a model already in the local cache.
- **Follow-up:** Run the opt-in tests in a scheduled or manual CI job with a cached model.
- **Depends on:** TD-036.

### TD-038 · Behind HTTPS inspection, model downloads fail and cached loads are slow
- **Kind:** Observed (development machine) · **Priority:** Low (documented, environment-specific) · **Status:** Open
- **Evidence:**
  - Behind antivirus HTTPS inspection, the Hugging Face client failed with `CERTIFICATE_VERIFY_FAILED`. The README documents a manual, verification-preserving procedure.
  - Found in Phase 5: with the model already cached, a dense search without `HF_HUB_OFFLINE=1` still took 238 seconds, logging 48 certificate errors and 40 retries before using the cache. The same command with `HF_HUB_OFFLINE=1` took 24 seconds. The README now recommends the variable.
  - On Windows without symlink support the model cache also runs in a degraded mode that uses more disk space.
- **Impact:** Every dense, hybrid or dense-evaluation run on such a machine is about four minutes slower unless the variable is set.
- **Follow-up:** None planned beyond the documentation. An option to load local files only would remove the need for the variable.

### TD-039 · Heavy environment and slow first import
- **Kind:** Observed · **Priority:** Low · **Status:** Open
- **Evidence:** The environment is about 1 GB. The first import of the embedding library took 28 seconds, which is why it is imported lazily. CPU encoding speed on a realistic corpus is unmeasured.
- **Follow-up:** Measure with TD-013.

## Risks and questions for later phases

### TD-041 · Reranking: unverified model and input limits
- **Kind:** Risk · **Priority:** Medium · **Status:** Open
- **Questions:**
  - The default `RERANKER_MODEL` has never been loaded. Does it exist and suit Italian legal text?
  - Cross-encoders also truncate their input (compare TD-022).
  - What is the CPU cost per query for the configured candidate count?
  - Model downloads face the same obstacle as TD-038.
- **Depends on:** TD-015.

### TD-042 · Generation: token budget, citations and provenance
- **Kind:** Risk · **Priority:** Medium · **Status:** Open
- **Questions:**
  - `CONTEXT_TOKEN_BUDGET` is in tokens, but chunk sizes are in characters and no tokenizer is tied to the LLM.
  - Citations need a title and an exact location; the title is missing from chunks (TD-004).
  - Should overlapping chunks be de-duplicated before they enter the context?
- **Depends on:** TD-004.

### TD-043 · Abstention thresholds need calibrated scores
- **Kind:** Risk · **Priority:** High (abstention is a core requirement of the spec) · **Status:** Open
- **Evidence:** BM25 scores depend on the corpus and the query. Dense scores are bunched (TD-021) and are returned for every query (TD-026). The fused RRF score depends only on ranks (TD-051). None of the three is a probability.
- **Questions:** Can a threshold on either score, on the fused rank, or on a reranker score separate answerable from unanswerable questions? This needs unanswerable queries in the benchmark.
- **Depends on:** TD-015, TD-021, TD-026, TD-051.

### TD-044 · Temporal filtering has no data to work on
- **Kind:** Confirmed · **Priority:** Medium · **Status:** Open
- **Evidence:** Effective dates exist only if a sidecar supplies them (TD-004). No document has one. `UNDATED_SOURCE_POLICY` is unused.
- **Follow-up:** Decide how dates will be supplied for the real corpus before building "as of" filtering.
- **Depends on:** TD-002, TD-004.

### TD-045 · Privacy and untrusted text in generation
- **Kind:** Risk · **Priority:** High (a spec safeguard, not yet designed) · **Status:** Open
- **Evidence:** No LLM code exists. The default provider is `mock`. The spec requires explicit approval before confidential text is sent to an external model, and requires treating retrieved text as untrusted.
- **Questions:** How is approval recorded? How are instructions inside retrieved passages kept from steering the model? What is logged?

## Resolved

### TD-040 · Hybrid retrieval: fusion and comparison questions
- **Kind:** Risk · **Priority:** High · **Status:** Resolved in Phase 5 (design questions answered; what remains is tracked elsewhere)
- **Questions raised before Phase 5, and their outcome:**
  - *How should a BM25 list that can be shorter than k be fused with a dense list that is always full?* With rank-only RRF over fixed candidate depths; a list contributes nothing for chunks it lacks. The side effects are recorded in TD-052.
  - *Is `RRF_K=60` appropriate?* Still unknown. It is in use but untuned (TD-049).
  - *`method_ranks` and `method_scores` were never set.* `reciprocal_rank_fusion` now sets them for every fused result, and tests check them.
  - *The three retrievers must be compared on the same benchmark and k.* The evaluator accepts `bm25`, `dense` and `hybrid` with one dataset, the same metrics and the same report format (tested). The comparison itself still needs a benchmark (TD-015) and care with result counts (TD-017).
- **Verified by:** `tests/test_hybrid_retrieval.py`.

### TD-046 · Okapi IDF scored real matches zero or negative
- **Kind:** Confirmed · **Priority:** High · **Status:** Resolved in Phase 3
- **Evidence:** With `rank_bm25.BM25Okapi`, a word in half the chunks scored 0, and a chunk matching two query words could rank below one matching one.
- **Resolution:** Commit `704e581`. `_PositiveIdfBM25` in `src/retrieval.py` makes the default IDF always positive. The original behaviour remains available as `positive_idf=False`.
- **Verified by:** Seven passing tests in `tests/test_retrieval.py`, including `test_zero_idf_regression`, `test_negative_idf_regression_okapi_inverts_the_ranking`, `test_negative_idf_regression_positive_idf_ranks_the_fuller_match_first`, and the two hand-computed formula tests.

### TD-047 · Search output could crash on characters the console cannot show
- **Kind:** Confirmed (mechanism reproduced; fix tested for one of three CLIs) · **Priority:** Low · **Status:** Resolved for the search, evaluation and dense CLIs
- **Evidence:** On Windows with output piped, printing a search result that contains characters outside cp1252 raises `UnicodeEncodeError`. The crash was first seen in a development probe script during Phase 3, not in a released CLI: the guard was added before the BM25 CLI was committed.
- **Resolution:** `sys.stdout.reconfigure(errors="replace")` in the BM25 search CLI (commit `704e581`), the evaluation CLI (`3e7e6f6`) and the dense search CLI (`5942160`).
- **Verified by:** `test_cli_module_entry_point_handles_non_console_characters` runs the BM25 search CLI as a subprocess on such text. A manual check during review confirmed that the same output without the guard crashes and with it does not. The evaluation and dense CLIs have the guard but no dedicated test.
- **Remaining:** The ingestion CLI has no guard (TD-006).

### TD-048 · A unit test attempted a real model download
- **Kind:** Confirmed (recorded during development, not reproducible from the repository) · **Priority:** Medium · **Status:** Resolved in Phase 4B
- **Evidence:** Registering the `dense` retriever made `test_unknown_retriever_is_rejected`, which used `"dense"` as its unknown name, construct a real `DenseRetriever`. In that development run the suite took about 100 seconds and the test failed with an `OSError` from the model download; nothing was downloaded.
- **Resolution:** Commit `5942160`. The test uses the name `"no-such-retriever"`, and the autouse fixture `no_model_downloads` in `tests/conftest.py` sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` for every test.
- **Verified by:** `pytest --setup-show` shows the fixture applied to an unrelated test, and the default suite now runs in about 3 seconds. No test asserts the offline environment directly.

## Maintenance policy

- **Update at the end of every phase.** Add what the phase revealed, with its evidence. Mark each new item Confirmed, Observed, Hypothesis, Opportunity or Risk.
- **Review before every commit.** Check whether the change resolves, worsens or adds an item, and update the file in the same commit.
- **Record outcomes.** When an item is fixed, set its status to Resolved, say in which phase or commit, and move it to the Resolved section. When it is set aside, set Deferred and give the reason.
- **Keep IDs stable.** Never renumber or reuse an ID. New items take the next number.
- **Evidence over opinion.** Do not add an item without a code reference, a reproduced behaviour, or a recorded observation. Do not claim a retrieval-quality improvement without benchmark results.
- **Registering is not fixing.** Fixes are made in their own changes, not while editing this file.
