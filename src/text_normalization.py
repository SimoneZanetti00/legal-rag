"""Comparison normalisation for legal text: profile `ws-markers-softhyphen-v1`.

One shared, deterministic definition of "the same text, apart from formatting", for
comparing two renderings of a provision: our anchored text against an official
source (the review ledger's `official_check`), and, later, a quoted passage against
its evidence (the M3 citation validator).

The normalised form exists only for comparing. It is never stored, never shown as
the text of a provision and never written back: the original strings are not
changed, and anchoring and lookup stay exact (no normalised matching there).

Permitted transformations, applied in this order and nothing else:

1. EUR-Lex consolidation markers become a space: `▼` or `►` immediately followed by
   a label (`B`, or `M`, `A` or `C` with a number, e.g. `▼B`, `▼C2`, `►M1`) that
   is not itself followed by a letter or digit, and every `◄`. A marker glued to
   a word (`►C2Il`) or an unknown label is left as it is and shows up as a
   difference.
2. A soft hyphen (U+00AD) is removed together with any whitespace after it, line
   breaks included: `approssi\\xad\\n\\nmativo` becomes `approssimativo`. An ordinary
   hyphen (`-`) is never removed or joined.
3. The typographic apostrophe U+2019 (’) becomes the ASCII apostrophe ('). No other
   quotation mark is changed: «», "" and ‘ stay as they are.
4. Every run of Unicode whitespace (spaces, tabs, line breaks, no-break spaces;
   anything `str.isspace` accepts) becomes one space; leading and trailing
   whitespace is removed.
5. A space before `,` `;` `:` `.` `?` `!` `)` `]`, or after `(` `[`, is removed.
   This also closes up the spaces inside Normattiva's markers: `(( (Autorità` and
   `). ))` become `(((Autorità` and `).))`; the brackets themselves are kept.

Everything else counts: letters and their case, accents, digits, all other
punctuation, quotation marks, hyphens, Normattiva's amendment markers `((` `))`,
and the order of words. No Unicode normalisation (NFC/NFKC) is applied.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

PROFILE = "ws-markers-softhyphen-v1"
PROFILES = (PROFILE,)

# Outcomes of compare_texts, also the `match_status` values of an official check.
IDENTICAL = "identical"  # the two strings are equal as they are
IDENTICAL_AFTER_NORMALISATION = "identical_after_normalisation"
DIFFERS = "differs"
MATCH_STATUSES = (IDENTICAL, IDENTICAL_AFTER_NORMALISATION, DIFFERS)

_MARKER = re.compile(r"[▼►](?:B|[MAC][0-9]+)(?!\w)|◄")
_SOFT_HYPHEN = re.compile(r"\u00ad\s*")
_WHITESPACE = re.compile(r"\s+")
_SPACE_BEFORE = re.compile(r" (?=[,;:.?!)\]])")
_SPACE_AFTER = re.compile(r"(?<=[(\[]) ")


def normalise(text: str, profile: str = PROFILE) -> str:
    """`text` in its comparison form under `profile` (see the module docstring)."""
    if profile != PROFILE:
        raise ValueError(f"unknown normalisation profile {profile!r}")
    text = _MARKER.sub(" ", text)
    text = _SOFT_HYPHEN.sub("", text)
    text = text.replace("\u2019", "'")
    text = _WHITESPACE.sub(" ", text).strip()
    text = _SPACE_BEFORE.sub("", text)
    return _SPACE_AFTER.sub("", text)


@dataclass(frozen=True)
class TextDifference:
    """One place where two texts differ, as normalised words ("" = nothing there)."""

    ours: str
    theirs: str


@dataclass(frozen=True)
class TextComparison:
    status: str  # one of MATCH_STATUSES
    differences: tuple[TextDifference, ...]  # empty unless status is DIFFERS


def compare_texts(ours: str, theirs: str, profile: str = PROFILE) -> TextComparison:
    """Compare two renderings of the same text; differences are listed word by word."""
    if ours == theirs:
        normalise("", profile)  # still reject an unknown profile
        return TextComparison(IDENTICAL, ())
    a, b = normalise(ours, profile), normalise(theirs, profile)
    if a == b:
        return TextComparison(IDENTICAL_AFTER_NORMALISATION, ())
    a_words, b_words = a.split(" ") if a else [], b.split(" ") if b else []
    matcher = difflib.SequenceMatcher(None, a_words, b_words, autojunk=False)
    differences = tuple(
        TextDifference(" ".join(a_words[i1:i2]), " ".join(b_words[j1:j2]))
        for op, i1, i2, j1, j2 in matcher.get_opcodes() if op != "equal"
    )
    return TextComparison(DIFFERS, differences)
