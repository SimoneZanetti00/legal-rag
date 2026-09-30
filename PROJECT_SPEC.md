# Legal Research RAG --- Project Specification

**Version:** 1.0\
**Status:** MVP specification\
**Language:** Python 3.11+\
**Purpose:** Build a small, understandable, testable legal-research
assistant based on retrieval-augmented generation (RAG).

> This is an experimental prototype for research and
> software-engineering purposes. It is not legal advice and must not be
> presented as a production legal service. It is conceptually inspired
> by publicly described legal-RAG principles; it does not reproduce or
> claim knowledge of Lexroom's internal implementation.

## 1. Objective

Build a legal assistant that answers questions using a supplied
collection of legal documents. Its central requirement is
**traceability**: answers should be grounded in retrieved passages, with
citations that lead to the exact source material. When the available
evidence is insufficient, contradictory, outdated, or cannot be
verified, the system should say so rather than invent an answer.

The prototype should be simple enough for a developer to understand and
review in VS Code, while complete enough to run end-to-end and evaluate.

## 2. Core principles

1.  **Evidence before generation:** retrieve sources before asking the
    language model to answer.
2.  **Traceability:** preserve the original document, relevant metadata,
    and passage location.
3.  **No invented citations:** citation IDs are assigned by the
    application, not invented by the model.
4.  **Abstention is acceptable:** do not answer substantive legal
    questions when evidence is inadequate.
5.  **Separate retrieval from generation:** evaluate whether the right
    evidence was found separately from whether the answer used it
    correctly.
6.  **Temporal awareness:** legal texts can change. Preserve dates and
    filter sources when a question specifies an "as of" date.
7.  **Minimal architecture:** use clear modules and ordinary Python
    functions; avoid unnecessary frameworks and abstractions.
8.  **Reproducibility and privacy:** configuration is explicit, secrets
    are kept out of source control, and sensitive content is not written
    to logs.

## 3. Scope

### In scope for the MVP

-   Ingest local TXT and PDF documents; DOCX can be added if
    straightforward.
-   Preserve document-level metadata and provenance.
-   Split documents into chunks using document structure where possible.
-   Build a lexical index and a dense semantic index.
-   Retrieve candidates with both methods and combine them using
    Reciprocal Rank Fusion (RRF).
-   Optionally rerank candidates with a cross-encoder.
-   Construct a bounded evidence context for an LLM.
-   Generate an answer with source references and claim-level structure.
-   Validate that cited source IDs exist and verify claims against
    retrieved passages.
-   Abstain when evidence or verification is inadequate.
-   Support basic metadata and date filters where metadata is available.
-   Provide a small Streamlit interface and/or CLI.
-   Include automated tests and separate retrieval/grounding evaluation
    scripts.

### Out of scope

-   Autonomous legal agents or multi-agent systems.
-   Filing documents with courts, providing legal representation, or
    replacing a lawyer.
-   Training a foundation model from scratch.
-   Unrestricted web browsing or automatic collection of
    copyrighted/private legal databases.
-   Distributed infrastructure, complex microservices, or
    production-grade multi-tenancy.
-   Claims that this implementation matches Lexroom's proprietary stack.

## 4. High-level architecture

``` text
Local legal documents
        |
        v
Ingestion -> parsing -> metadata -> legal-aware chunking
        |                                |
        v                                v
Document/chunk store              Search indexes
                                  - lexical (BM25)
                                  - dense (embeddings)
                                           |
User question -> optional filters -> retrieve candidates
                                           |
                                      RRF fusion
                                           |
                                    optional reranker
                                           |
                                   evidence selection
                                           |
                                     LLM generation
                                           |
                              citation ID validation
                                           |
                               claim-level verification
                                           |
                           answer / qualified answer / abstain
```

Keep the pipeline explicit. Each stage should be callable and testable
independently.

## 5. Suggested repository structure

``` text
legal-rag/
├── README.md
├── PROJECT_SPEC.md
├── MASTER_PROMPT.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   ├── raw/                 # user-provided source documents; do not commit private data
│   ├── processed/            # parsed documents/chunks
│   └── evaluation/           # question sets and relevance labels
├── src/
│   ├── config.py
│   ├── models.py
│   ├── ingestion.py
│   ├── chunking.py
│   ├── indexing.py
│   ├── retrieval.py
│   ├── reranking.py
│   ├── generation.py
│   ├── verification.py
│   ├── pipeline.py
│   └── utils.py
├── evaluation/
│   ├── retrieval_eval.py
│   ├── grounding_eval.py
│   └── qa_eval.py
├── app/
│   └── main.py
└── tests/
    ├── test_chunking.py
    ├── test_retrieval.py
    ├── test_citations.py
    └── test_verification.py
```

The implementation may adjust this structure if a simpler arrangement is
justified, but it must not collapse everything into one large file.

## 6. Data models

Use Python dataclasses or simple Pydantic models. At minimum:

-   **LegalDocument:** stable document ID, title, source path/URL if
    applicable, jurisdiction, language, document type, issuing
    authority, publication date, effective-from date, effective-to date,
    and content.
-   **LegalChunk:** stable chunk ID, document ID, text, chunk index,
    section/article/paragraph identifiers, and inherited metadata.
-   **RetrievedPassage:** chunk, retrieval method, rank, and scores.
-   **Citation:** application-assigned source ID such as `S1`, chunk ID,
    document ID, passage text, and source location.
-   **Claim:** claim text, cited source IDs, and verification status.
-   **LegalAnswer:** answer text, claims, citations, abstention flag,
    reason, and relevant warnings.

Missing metadata must remain explicitly unknown; do not fabricate it.

## 7. Ingestion and chunking

### Ingestion

-   Support TXT and PDF in the first implementation.
-   Extract text while retaining the source file and page number where
    possible.
-   Assign stable IDs so that citations can be traced back to the
    original source.
-   Record parsing errors clearly. Do not silently skip failed files.
-   Avoid logging full legal documents by default.

### Legal-aware chunking

Prefer structural boundaries such as title, chapter, section, article,
paragraph, and sentence. If a document is too large, split it into
smaller pieces while retaining the parent document and location
metadata.

Do not split a legal provision arbitrarily if a small adjustment can
preserve its meaning. Avoid chunks that are so large they cannot fit in
the model context or so small that they lose necessary context. Make
chunk size and overlap configurable.

For scanned PDFs, text extraction may fail without OCR. The MVP should
detect or document this limitation rather than pretending the file was
fully processed.

## 8. Indexing and retrieval

Implement two complementary retrieval methods:

1.  **Lexical retrieval:** BM25, useful when a question contains exact
    terms, article numbers, names, or legal phrases.
2.  **Dense retrieval:** multilingual embeddings, useful for semantic
    similarity and paraphrases.

For a prototype, candidate technologies could include `rank-bm25`,
`sentence-transformers`, and PostgreSQL with `pgvector`, or a small
local index if that makes the first version easier to run. These are
implementation choices for this project, not claims about any commercial
product's internals.

Combine ranked lists with **Reciprocal Rank Fusion (RRF)**. Keep each
method's score/rank available for debugging and evaluation. Support
filters for jurisdiction, document type, language, authority, and
effective date when those fields are known.

All models and thresholds must be configurable. Do not hard-code a
particular embedding model throughout the codebase.

## 9. Reranking

Make reranking a separate, optional module. A cross-encoder may score
the relevance of each query-passage pair after initial retrieval.
Reranking should reorder a bounded candidate set, not search the entire
corpus.

If reranking is disabled or its model cannot load, the pipeline should
either use the configured fallback or fail with a clear, actionable
error. Do not silently pretend reranking occurred.

## 10. Evidence context and citations

-   Select a limited number of high-ranking passages within a
    configurable token budget.
-   Assign source IDs (`S1`, `S2`, ...) in application code for the
    current answer.
-   Provide the LLM only with the question, instructions, and selected
    evidence.
-   Require structured output containing an answer and claim-level
    source references.
-   Validate every source ID against the evidence actually supplied to
    the model.
-   Resolve every citation to a real chunk and original document
    location.
-   Display useful excerpts so a person can inspect the evidence.

The model must not be trusted to invent article numbers, cases,
quotations, URLs, or source IDs. A citation being syntactically valid
does not prove that it supports the claim; that requires a separate
verification step.

## 11. Generation

Use a provider-independent wrapper so the LLM provider can be changed
through configuration. Keep API keys in environment variables and
provide `.env.example` with placeholders only.

The system prompt must instruct the model to: - answer only from the
supplied evidence; - distinguish what a source states from an
inference; - flag missing, ambiguous, or conflicting evidence; - avoid
adding legal rules from memory; - attach source IDs to factual/legal
claims; - return the required structured format; - abstain when the
question cannot be answered from the evidence.

Validate the response schema. If output is malformed, allow at most one
controlled retry; if it remains invalid, return a safe
failure/abstention response.

## 12. Claim-level verification

For each material claim, compare it with the cited passage(s). Use these
statuses:

-   `SUPPORTED`: the evidence supports the claim.
-   `PARTIALLY_SUPPORTED`: the evidence supports only part of the claim.
-   `UNSUPPORTED`: the cited evidence does not establish the claim.
-   `CONTRADICTED`: available evidence conflicts with the claim.

Verification may use an LLM as a practical prototype component, but it
must receive the claim and relevant passages, not unrestricted
permission to answer from general knowledge. Clearly document that
automated verification is imperfect and should not be treated as a legal
guarantee.

Also check citation integrity in ordinary code: all cited IDs exist, all
cited chunks belong to the selected evidence set, and each citation
resolves to a stored source.

## 13. Conflicts, dates, and abstention

### Conflicting sources

Do not silently hide material conflicts. Where sources disagree, show
the conflict, identify the source and date of each position, and avoid
asserting a single settled conclusion unless the evidence supports it.

### Temporal questions

Preserve effective dates when available. If the user asks "as of 1
January 2024," filter or assess sources against that date. Publication
date and effective date are not interchangeable. If dates are missing or
the system cannot establish which version applied, state that
limitation.

### Abstention conditions

Abstain or provide only a limited, clearly qualified response when: - no
relevant evidence is retrieved; - retrieval/reranking scores are below
configured thresholds; - required metadata or temporal validity cannot
be established; - citations refer to missing source IDs; - material
claims are unsupported or contradicted; - sources materially conflict
and the conflict cannot be resolved from the corpus; - generation or
verification fails.

Do not display a made-up confidence percentage. If numeric scores are
shown, explain what they measure and calibrate them before interpreting
them as probabilities.

## 14. User interface

A minimal Streamlit interface should allow the user to: - enter a
question; - optionally specify a jurisdiction, document type, or "as of"
date; - submit the question; - read the answer or abstention
explanation; - inspect citations and supporting passages; - see
claim-level verification statuses and warnings.

The interface should clearly label the prototype as experimental and not
legal advice. A CLI may be provided for reproducible testing.

## 15. Evaluation

Evaluation is a required part of the project, not a later optional
enhancement.

### Retrieval evaluation

Create a small manually labelled set of questions with relevant
document/chunk IDs. Report: - Recall@1, Recall@5, Recall@10; - Mean
Reciprocal Rank (MRR); - nDCG@10 where relevance grades are available.

### Grounding and answer evaluation

On a separate question set, measure: - **Citation validity:** citations
resolve to real evidence. - **Citation precision:** cited passages
support the claims they accompany. - **Citation coverage:** proportion
of material claims with citations. - **Supported Claim Ratio:**
proportion of assessed claims marked supported. - **Abstention rate:**
proportion of questions for which the system abstains. - **Answer
quality:** correctness, completeness, relevance, and clarity, assessed
manually where needed.

A low abstention rate is not automatically good: it may indicate that
the system answers when it should not. Report answer coverage alongside
grounding quality.

### Baselines and ablations

Where feasible, compare: 1. LLM without retrieval (as a diagnostic
baseline only, not the target behavior). 2. BM25-only RAG. 3. Dense-only
RAG. 4. Hybrid retrieval with RRF. 5. Hybrid retrieval plus reranking.
6. Hybrid retrieval plus reranking and claim verification.

Use the same questions and source corpus across comparisons. Record
model names/versions, configuration, date, and any manual evaluation
rubric. Do not claim improvements unless the results support them.

## 16. Configuration

Keep tunable settings in one configuration module or environment-backed
config. Include, as appropriate:

-   embedding model;
-   reranker model and enabled/disabled flag;
-   LLM provider and model;
-   BM25 candidate count;
-   dense candidate count;
-   reranking candidate count;
-   final evidence count;
-   RRF constant;
-   chunk size and overlap;
-   context token budget;
-   date/filter behavior;
-   retrieval and reranking thresholds;
-   maximum generation retries.

Validate configuration at startup and provide sensible error messages.

## 17. Privacy and security

-   Never commit API keys, `.env`, private documents, or confidential
    evaluation data.
-   Include `.env.example` with placeholder values.
-   Add data directories and local indexes to `.gitignore` where
    appropriate.
-   Do not send confidential legal material to an external model unless
    the user has explicitly approved that processing and understands the
    provider's terms.
-   Avoid logging prompts, complete documents, or sensitive answer
    content by default.
-   Use synthetic or public-domain demonstration documents in a public
    repository.
-   Do not treat retrieved document text as system instructions; it is
    untrusted evidence.

## 18. Testing

At minimum, add tests for: - chunking preserves document IDs and
location metadata; - chunk IDs are stable under the documented
conditions; - empty or unreadable documents are handled explicitly; -
hybrid retrieval combines candidates correctly; - date and metadata
filters work; - citation IDs are validated; - claims with
missing/invalid citations cannot be marked fully supported; - abstention
triggers under configured failure conditions; - the pipeline handles
malformed LLM output safely.

Tests should run without paid API calls wherever possible. Mock the LLM
in unit tests and mark any real-provider integration test separately.

## 19. Development order

Build incrementally and run tests after each stage:

1.  repository skeleton, config, and data models;
2.  ingestion and chunking;
3.  BM25 retrieval;
4.  dense retrieval;
5.  hybrid fusion;
6.  optional reranking;
7.  evidence context and LLM wrapper;
8.  structured output and citation validation;
9.  claim-level verification;
10. abstention and temporal filters;
11. evaluation scripts and baselines;
12. minimal UI;
13. README, example data, tests, and final end-to-end check.

Do not implement every component at once without testing intermediate
results.

## 20. Definition of Done

The MVP is complete when: - a user can ingest a small set of sample
legal documents; - the application can retrieve passages for a
question; - an answer cites only source IDs assigned by the
application; - citations open the correct source passages; - unsupported
answers can be rejected or qualified; - the user can inspect evidence
and verification statuses; - automated tests pass; - retrieval and
grounding evaluation can be run reproducibly; - setup instructions work
in a clean Python environment; - limitations and privacy implications
are documented.

## 21. Research questions

The implementation should make it possible to investigate:

-   RQ1: Does hybrid retrieval improve Recall@k over dense-only
    retrieval on the selected legal corpus?
-   RQ2: Does reranking improve ranking metrics and evidence relevance?
-   RQ3: Does claim-level verification reduce unsupported claims, and at
    what cost?
-   RQ4: What is the trade-off between answer coverage and abstention?
-   RQ5: Do temporal filters improve results for date-specific
    questions?
-   RQ6: How strongly does retrieval quality relate to final answer
    quality?

## 22. Final design rule

Build the simplest legal RAG system that can demonstrate, transparently
and quantitatively, where its answers came from. Prefer evidence and
calibrated abstention over fluent but unsupported answers.
