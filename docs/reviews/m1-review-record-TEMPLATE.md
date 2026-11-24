# M1 human review record: TEMPLATE

> **Blank template; do not fill in this file.** Copy it to `docs/reviews/m1-review-record-<YYYY-MM-DD>.md` and fill in the copy.
>
> - This record is separate from the generated review package, which must never be edited by hand.
> - Nothing here is pre-filled. Every decision is the human reviewer's.
> - Filling in a record changes neither the review ledger nor the inventories. Recording a review there is a separate step (package section 12).
> - Legal validity is not assessed and stays `not_established`.

## 1. Record identity

| Field | Value |
|---|---|
| Reviewer (full name) | |
| Review date (YYYY-MM-DD) | |
| Package reviewed | `docs/reviews/m1-human-review-package.md` |
| Package SHA-256 this record applies to | `2f90fe52723f91c63f4414404c4ce880e5a37bfc61de00f2e3ec45568665ce56` |
| Recorded build ID | `build-f76ff6031f2fc82c4852f0a2bde27807` |
| Code commit of the build | `e29a1b43033204338b0bdb4c013e67b88c3b4254` |
| Repository commit at the time of review | |
| Archived official sources | `data/raw/trial-2026-10-10/official-sources/`: `gdpr_consolidated_it.html` (`90d0710134489e08fc26f142c416028d2ee6f3cf049f83c084e772da3ac8d260`), `normattiva_2bis.html` (`f95c865efdc99dedd1993e993b343d1d31dbc902b72ae6992a5f3d4dcd4435ce`) |

**Checks before starting.** Run each command and tick the result. If the package hash differs from the one above, stop: this record does not apply to that package.

| Check | Command (from the repository root) | Result |
|---|---|---|
| Package hash | `Get-FileHash docs\reviews\m1-human-review-package.md -Algorithm SHA256` | ☐ matches ☐ differs |
| Package reproduced | `.\.venv\Scripts\python.exe -m tools.review_package.generate --check` | ☐ byte-identical ☐ differs |
| Official sources and extraction hashes | `.\.venv\Scripts\python.exe -m tools.review_package.official_texts` | ☐ all OK ☐ failed |

## 2. How to fill in this record

- **One worksheet per provision.** The five decision areas in each worksheet are independent: a decision in one never implies a decision in another.
- **One box per decision.** Give the reason in the same row. A reason is required for «correction needed», «cannot confirm» and «should not become primary», and recommended for the others.
- **Anomalies:** refer to the package's numbering (for example «package §6 B, anomaly 1») and add any you find yourself.
- **Qualifications:** statements that must accompany any use of the provision. Copy the ones that apply from the package (section A, «Qualifications») and add your own.
- **Primary-citation eligibility** is computed by the system from the recorded review. Your decision records your view and your reason.
- **Corrections:** list every inventory field you would change, with its value before and after (package section 12).

## 3. GDPR Article 4 (the demonstration uses point 12)

| Field | Value |
|---|---|
| Provision ID | `eu-reg-2016-679@oj-l119-2016-it/body/article:4` |
| Inventory entry | `gdpr-2016-679-oj-it:art:4` |
| Package section | 5 |
| Scope reviewed | ☐ the whole article (points 1–26) ☐ other (describe): |

| Decision area | Decision (tick one) | Reasons |
|---|---|---|
| 1. Structure | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 2. Extraction fidelity | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 3. Completeness | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 4. Source-status markers | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 5. Primary-citation eligibility | ☐ should become primary ☐ should not become primary | |

**Corrections**

| Field | Before | After | Reason |
|---|---|---|---|
| | | | |

**Anomalies**

| Package reference or new | What I found | Effect on the text |
|---|---|---|
| | | |

**Qualifications**

-

**Official-source check:** ☐ record it as computed in the package (section C) ☐ record it with my own extraction (SHA-256: ) ☐ do not record it

**Ledger outcome to record:** ☐ `confirmed` ☐ `corrected` ☐ no record yet

**Notes**

-

## 4. GDPR Article 33

| Field | Value |
|---|---|
| Provision ID | `eu-reg-2016-679@oj-l119-2016-it/body/article:33` |
| Inventory entry | `gdpr-2016-679-oj-it:art:33` |
| Package section | 6 |

| Decision area | Decision (tick one) | Reasons |
|---|---|---|
| 1. Structure | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 2. Extraction fidelity | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 3. Completeness | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 4. Source-status markers | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 5. Primary-citation eligibility | ☐ should become primary ☐ should not become primary | |

**Corrections**

| Field | Before | After | Reason |
|---|---|---|---|
| | | | |

**Anomalies**

| Package reference or new | What I found | Effect on the text |
|---|---|---|
| | | |

**Qualifications**

-

**Official-source check:** ☐ record it as computed in the package (section C) ☐ record it with my own extraction (SHA-256: ) ☐ do not record it

**Ledger outcome to record:** ☐ `confirmed` ☐ `corrected` ☐ no record yet

**Notes**

-

## 5. GDPR Article 34

| Field | Value |
|---|---|
| Provision ID | `eu-reg-2016-679@oj-l119-2016-it/body/article:34` |
| Inventory entry | `gdpr-2016-679-oj-it:art:34` |
| Package section | 7 |

| Decision area | Decision (tick one) | Reasons |
|---|---|---|
| 1. Structure | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 2. Extraction fidelity | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 3. Completeness | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 4. Source-status markers | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 5. Primary-citation eligibility | ☐ should become primary ☐ should not become primary | |

**Corrections**

| Field | Before | After | Reason |
|---|---|---|---|
| | | | |

**Anomalies**

| Package reference or new | What I found | Effect on the text |
|---|---|---|
| | | |

**Qualifications**

-

**Official-source check:** ☐ record it as computed in the package (section C) ☐ record it with my own extraction (SHA-256: ) ☐ do not record it

**Ledger outcome to record:** ☐ `confirmed` ☐ `corrected` ☐ no record yet

**Notes**

-

## 6. GDPR Article 55

| Field | Value |
|---|---|
| Provision ID | `eu-reg-2016-679@oj-l119-2016-it/body/article:55` |
| Inventory entry | `gdpr-2016-679-oj-it:art:55` |
| Package section | 8 |

| Decision area | Decision (tick one) | Reasons |
|---|---|---|
| 1. Structure | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 2. Extraction fidelity | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 3. Completeness | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 4. Source-status markers | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 5. Primary-citation eligibility | ☐ should become primary ☐ should not become primary | |

**Corrections**

| Field | Before | After | Reason |
|---|---|---|---|
| | | | |

**Anomalies**

| Package reference or new | What I found | Effect on the text |
|---|---|---|
| | | |

**Qualifications**

-

**Official-source check:** ☐ record it as computed in the package (section C) ☐ record it with my own extraction (SHA-256: ) ☐ do not record it

**Ledger outcome to record:** ☐ `confirmed` ☐ `corrected` ☐ no record yet

**Notes**

-

## 7. Italian Privacy Code Article 2-bis

| Field | Value |
|---|---|
| Provision ID | `it-dlgs-2003-196@transcription-vigente-2026-11-05/body/article:2-bis` |
| Inventory entry | `dlgs-196-2003-transcription:body:art:2-bis` |
| Package section | 9 |

| Decision area | Decision (tick one) | Reasons |
|---|---|---|
| 1. Structure | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 2. Extraction fidelity | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 3. Completeness | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 4. Source-status markers | ☐ confirmed ☐ correction needed ☐ cannot confirm | |
| 5. Primary-citation eligibility | ☐ should become primary ☐ should not become primary | |

**Corrections**

| Field | Before | After | Reason |
|---|---|---|---|
| | | | |

**Anomalies**

| Package reference or new | What I found | Effect on the text |
|---|---|---|
| | | |

**Qualifications**

-

**Official-source check:** ☐ record it as computed in the package (section C) ☐ record it with my own extraction (SHA-256: ) ☐ do not record it

**Ledger outcome to record:** ☐ `confirmed` ☐ `corrected` ☐ no record yet

**Notes**

-

## 8. Sign-off

I reviewed the provisions above against the source PDFs and against the package whose SHA-256 is given in section 1. This record covers structure, extraction fidelity, completeness, source-status markers and my view on primary-citation eligibility. It does not establish that any provision is legally valid or in force.

| Field | Value |
|---|---|
| Reviewer (full name) | |
| Date (YYYY-MM-DD) | |
| Ledger and inventory changes recorded in commit | |
