"""Source status: what is known about the source of each evidence item, as separate statements.

    evidence_status(evidence, store) -> {evidence_id: SourceStatus as a dict}

Read-only: computed from the instrument registry (the version's kind, authenticity and
reference date) and the provision's review record in the provision store. It changes no
status, and it states nothing the metadata does not record.

Five distinctions, kept apart:
- source: an official publication, or an unofficial transcription (version kind "transcription"
  or authenticity "user_transcription"/"unofficial");
- extraction: "official_text_match" or "official_text_differs" only when the review ledger
  records an official-source check; otherwise "not_compared": the text was extracted
  automatically from the source file and anchored to it, but no comparison with an official
  text is recorded;
- human_review: "reviewed" when the ledger records a review, otherwise "pending";
- legal_currency: always "not_established": the system does not establish whether a provision
  is valid, in force or applicable at any date, and the version's own limits are stated;
- citable_in_verified_mode: the eligibility tier is "primary".
`category` combines the first two: official_extraction_checked,
official_extraction_not_checked or unofficial_transcription.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.evidence import EvidenceItem, EvidenceSet
from src.provisions import QUALIFICATIONS, REASONS, Provision, Version

CATEGORIES = {
    "official_extraction_checked": "Official source; text checked against an official text",
    "official_extraction_not_checked": "Official source; text not checked against an official "
                                       "text",
    "unofficial_transcription": "Unofficial transcription",
}
MATCHES = ("identical", "identical_after_normalisation")
# The version qualifications that bear on its currency (QUALIFICATIONS codes).
CURRENCY_CODES = ("original_publication_not_consolidated", "reference_date_unverified",
                  "source_marks_repealed")


@dataclass(frozen=True)
class SourceStatus:
    evidence_id: str
    provision_id: str
    category: str  # a CATEGORIES key
    source: str  # "official_publication" | "unofficial_transcription"
    extraction: str  # "official_text_match" | "official_text_differs" | "not_compared"
    human_review: str  # "reviewed" | "pending"
    legal_currency: str  # "not_established"
    citable_in_verified_mode: bool
    statements: tuple[str, ...]  # one plain sentence per point, written by this module


def status_of(item: EvidenceItem, provision: Provision, version: Version) -> SourceStatus:
    unofficial = (version.version_kind == "transcription"
                  or version.authenticity in ("user_transcription", "unofficial"))
    check = provision.review.official_check
    if check is None:
        extraction = "not_compared"
        extraction_statement = ("Text extracted automatically from the source file and anchored "
                                "to it; no comparison with an official text is recorded.")
    elif check.match_status in MATCHES:
        extraction = "official_text_match"
        extraction_statement = (f"Text compared with an official text ({check.source_type}, "
                                f"retrieved {check.retrieved_on}): "
                                f"{check.match_status.replace('_', ' ')}.")
    else:
        extraction = "official_text_differs"
        extraction_statement = (f"Text compared with an official text ({check.source_type}, "
                                f"retrieved {check.retrieved_on}): it differs.")
    reviewed = provision.review.status == "reviewed"
    if unofficial:
        category = "unofficial_transcription"
    elif extraction == "official_text_match":
        category = "official_extraction_checked"
    else:
        category = "official_extraction_not_checked"

    statements = [
        (f"Unofficial transcription: {version.description}" if unofficial
         else f"Official source: {version.description}")
        + ("" if unofficial or version.authenticity is not None
           else " The authenticity of this copy is not established."),
        extraction_statement,
        (f"Human review recorded ({provision.review.checked_on})." if reviewed else
         "Human review pending: no person has reviewed this provision's structure and text."),
        " ".join(["Version and legal currency not established."]
                 + [QUALIFICATIONS[code] for code in version.qualifications
                    if code in CURRENCY_CODES]
                 + [QUALIFICATIONS["legal_validity_not_established"]]),
        ("Citable in verified mode." if item.citable else
         "Not citable in verified mode: "
         + " ".join(REASONS.get(code, code) for code in item.reasons)),
    ]
    return SourceStatus(item.evidence_id, item.provision_id, category,
                        "unofficial_transcription" if unofficial else "official_publication",
                        extraction, "reviewed" if reviewed else "pending",
                        provision.legal_validity, item.citable, tuple(statements))


def evidence_status(evidence: EvidenceSet | None, store: Any) -> dict[str, dict[str, Any]]:
    """{evidence_id: status} for every item of `evidence`; `store` is a ProvisionStore."""
    if evidence is None:
        return {}
    out = {}
    for item in evidence.items:
        status = status_of(item, store.get(item.provision_id),
                           store.registry.version(item.version_id))
        data = asdict(status)
        data["statements"] = list(status.statements)
        out[item.evidence_id] = data
    return out
