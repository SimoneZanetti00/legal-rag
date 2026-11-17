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

Reading form (`reading_form`): evidence text laid out for a model to read, used only
in the prompts of answer generation and the support check. It undoes the PDF layout
and nothing else:

1. a soft hyphen and the whitespace after it are removed, so a word split at a line
   end is whole again (`precon\\xad\\n\\ntrattuali` becomes `precontrattuali`);
2. a line break is kept, as one line break, before a paragraph number or point label
   (`1.`, `2-bis.`, `(3)`, `a)`, `12)`, also after Normattiva's `((`), after a sentence
   end (`.` `;` `:` `!` `?`) unless the line is only a label, after an article
   heading line (`Articolo 6`, `Art. 2-bis`), and after the article's title when the
   caller passes it (`title=`, the inventory title);
3. every other line break or blank line, with the spaces around it, becomes one
   space; a label alone on its line is joined to the text that follows (`1. Il ...`).

Only whitespace and soft hyphens change, so `normalise(reading_form(t)) ==
normalise(t)`: a quotation copied from the reading form is checked, unchanged, against
the stored text in its normalised form. The reading form is never stored and never
used for anchoring, lookup or validation.
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


# --- Reading form ------------------------------------------------------------------------

# A paragraph number ("1.", "2-bis.", "(3)") or a point label ("a)", "12)", "a-bis)") at the
# start of a line, also after Normattiva's opening marker "((".
_LINE_LABEL = re.compile(
    r"(?:\(\(\s*)?(?:\d{1,3}(?:-[a-z]+)*[.)]|\(\d{1,3}\)|[a-z](?:-[a-z]+)*\))(?=\s|$)")
_ARTICLE_HEADING = re.compile(r"(?:Articolo|Art\.)\s+\S+")
_SENTENCE_END = re.compile(r"[.;:!?][\"'»”)\]]*$")


def reading_form(text: str, title: str | None = None) -> str:
    """`text` with its PDF layout undone, for a model to read (see the module docstring).

    `title`, the article's printed title as the inventory records it, keeps the line break
    after it: a line (or run of joined lines) equal to the title is never joined to the text
    that follows it.
    """
    pieces: list[str] = []
    previous: str | None = None
    current = ""  # the reading-form line being built
    for line in _SOFT_HYPHEN.sub("", text).split("\n"):
        line = line.strip()
        if not line:
            continue
        if previous is not None:
            keep = _keeps_break(previous, line) or (title is not None and current == title)
            pieces.append("\n" if keep else " ")
            current = "" if keep else current + " "
        pieces.append(line)
        current += line
        previous = line
    return "".join(pieces)


def _keeps_break(before: str, after: str) -> bool:
    if _LINE_LABEL.match(after):
        return True  # a paragraph or point starts here
    if _LINE_LABEL.fullmatch(before):
        return False  # a label alone on its line: its text follows on the same line
    return bool(_SENTENCE_END.search(before) or _ARTICLE_HEADING.fullmatch(before))
