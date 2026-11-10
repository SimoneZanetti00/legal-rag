"""Citation resolution (M2): legal references in text, resolved to provisions of the corpus.

Three separate steps, so that each can grow on its own:

1. Parsing (scan_text, extract_references): article references ("art. 33", "articoli 33 e 34",
   "Article 34(2)"), with the paragraphs, points and letters attached to them, plus recitals,
   numbered documents and act numbers. Pure text work, no corpus needed.
2. Instrument attribution: which act each article reference points to. The basis is recorded:
   - "explicit": the act is named next to the reference ("art. 33 GDPR", "articolo 2-bis del
     Codice privacy", "GDPR, art. 33"). An explicit name always wins over the context;
   - "context": the reference sits inside a known instrument (context_instrument) and names no
     act, or names it with a word that only that context defines ("del presente regolamento"
     inside the GDPR; "del regolamento" inside the Privacy Code, whose Art. 1 defines
     «Regolamento» as Regulation (EU) 2016/679);
   - "external": the reference is tied to an act outside the corpus (another decree, law,
     directive, treaty, or regulation), which this corpus cannot resolve;
   - "none": no act can be determined. An article number alone never identifies a provision.
3. Resolution (resolve_reference, resolve_references): the attributed reference looked up in a
   ProvisionStore, exactly as ProvisionStore.lookup matches labels (no fuzzy matching):
   - resolved: one article of the target instrument, and every paragraph, point or letter
     named is present in its text (paragraphs "N.", points "N)", letters "x)" at line start);
   - partially_resolved: the article is resolved, but a named part is not in its text or
     its text was not available to check;
   - ambiguous: the act is not determined (candidates are listed even if there is only one),
     or the label matches several articles of the instrument;
   - unresolved: the act is outside the corpus, or it has no such article.

Instruments are described in INSTRUMENTS (CitationInstrument). Adding a source later means:
registering and indexing it like the existing ones (instruments.json, an inventory, a recorded
build: a separate task), then adding one CitationInstrument entry with its names. Nothing in the
parser or the resolver changes. An act without an entry is "external", never a guessed match.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.provisions import normalise_label
from src.text_normalization import normalise

# --- Instruments -------------------------------------------------------------------------------


@dataclass(frozen=True)
class CitationInstrument:
    """How text names one corpus instrument. Patterns are regular expressions, matched without
    regard to case."""

    instrument_id: str
    names: tuple[str, ...]  # name it anywhere: explicit attribution
    self_names: tuple[str, ...] = ()  # name it only inside its own text: context attribution
    # Terms another instrument's text defines as this one: (defining instrument, pattern).
    defined_terms: tuple[tuple[str, str], ...] = ()
    # Names of other instruments that mean something else in this instrument's own text: a
    # name whose words are just one of these is ignored there (in the GDPR, a bare "codice" is
    # a code of conduct, never the Privacy Code; "Codice privacy" still names it).
    own_non_names: tuple[str, ...] = ()


GDPR = "eu-reg-2016-679"
PRIVACY_CODE = "it-dlgs-2003-196"
# "Codice" followed by a code's name ("civile", "del consumo", "delle comunicazioni
# elettroniche", "di procedura penale") is another code. "di cui" ("the code referred to in")
# names none.
_CODE_NAME = r"civile|penale|d(?:el|ello|ella|ei|egli|elle)\b|dell['’]|di\b(?!\s+cui\b)"

INSTRUMENTS: tuple[CitationInstrument, ...] = (
    CitationInstrument(
        GDPR,
        names=(r"\bGDPR\b", r"\bRGPD\b",
               r"\bregolamento\s*\(\s*UE\s*\)\s*(?:n\.\s*)?2016/679",
               r"\bregulation\s*\(\s*EU\s*\)\s*(?:no\.?\s*)?2016/679",
               r"\bregolamento\s+generale\s+sulla\s+protezione\s+dei\s+dati\b",
               r"\bgeneral\s+data\s+protection\s+regulation\b", r"(?<![\d/])2016/679\b"),
        self_names=(r"\bpresente\s+regolamento\b", r"\bthis\s+regulation\b",
                    r"\bregolamento\b(?!\s*\()", r"\bregulation\b(?!\s*\()"),
        defined_terms=((PRIVACY_CODE, r"\bregolamento\b(?!\s*\()"),
                       (PRIVACY_CODE, r"\bregulation\b(?!\s*\()")),
        own_non_names=(r"codic[ei]",),  # Arts. 40-41: "del codice da parte dei titolari"
    ),
    CitationInstrument(
        PRIVACY_CODE,
        names=(r"\bcodice\s+(?:della\s+|in\s+materia\s+di\s+)?privacy\b",
               r"\bcodice\s+(?:in\s+materia\s+di|della|di)\s+protezione\s+dei\s+dati\s+personali\b",
               r"\b(?:italian\s+)?(?:privacy|data\s+protection)\s+code\b",
               r"\b(?:d\.\s*lgs\.?|decreto\s+legislativo)\s*(?:30\s+giugno\s+2003\s*,?\s*)?"
               r"(?:n\.\s*)?196(?:/2003)?\b",
               r"(?<![\d/])196/2003\b",
               # A bare "Codice" / "the Code": the only code in the corpus. Not when a code's
               # name follows (another code: EXTERNAL_ACTS), and not codes of conduct
               # (NOT_INSTRUMENTS; a bare "codice" in the GDPR's own text: own_non_names).
               rf"(?<!presente\s)\bcodice\b(?!\s+(?:{_CODE_NAME}|deontologic))",
               r"\bthe\s+code\b"),
        self_names=(r"\bpresente\s+codice\b", r"\bthis\s+code\b"),
    ),
)

# Words that look like an act but are not one: never attributed (GDPR codes of conduct).
NOT_INSTRUMENTS = re.compile(r"\bcodic[ei]\s+di\s+condotta\b|\bcodes?\s+of\s+conduct\b", re.I)

# Acts outside the corpus. Checked after the corpus names, so "d.lgs. 196/2003" or
# "regolamento (UE) 2016/679" are never external.
EXTERNAL_ACTS = re.compile(
    r"\b(?:d\.\s*lgs\.?|decreto(?:\s+legislativo|\s*-\s*legge|\s+legge|\s+ministeriale)?|"
    r"d\.\s*l\.|d\.\s*p\.\s*r\.|legge\s+(?=n\.|\d)|l\.\s*(?=n\.|\d)|direttiva|directive|"
    r"trattato|treaty|tfue|carta\s+dei\s+diritti|charter\s+of\s+fundamental|"
    rf"codice\s+(?:{_CODE_NAME})|"
    r"regolamento\s*\(\s*(?:UE|CE|CEE)\s*\)|regulation\s*\(\s*(?:EU|EC|EEC)\s*\)|"
    r"regolamento\s+(?:delegato|di\s+esecuzione))", re.I)


# "This regulation", "il presente codice": the act whose text this is, whatever it is.
SELF_REFERENCE = re.compile(r"\bpresente\s+(?:codice|regolamento|decreto|legge|atto)\b|"
                            r"\bthis\s+(?:code|regulation|act|decree|law)\b", re.I)

# Words that name some act without saying which. When no rule above identifies them (a context
# that defines them, or the act's own text), the act stays undetermined: basis "none".
GENERIC_ACT_WORDS = re.compile(r"\bregolament[oi]\b(?!\s*\()|\bregulations?\b(?!\s*\()", re.I)


def _compile(patterns: Iterable[str]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I)


_NAMES = {i.instrument_id: _compile(i.names) for i in INSTRUMENTS}
_SELF_NAMES = {i.instrument_id: _compile(i.self_names) for i in INSTRUMENTS if i.self_names}
_OWN_NON_NAMES = {i.instrument_id: _compile(i.own_non_names) for i in INSTRUMENTS
                  if i.own_non_names}
_DEFINED = [(context, target.instrument_id, re.compile(p, re.I))
            for target in INSTRUMENTS for context, p in target.defined_terms]

# --- Parsing -----------------------------------------------------------------------------------

# Latin ordinal suffixes of inserted articles: bis, ter, ..., decies, undecies ... noviesdecies.
_LATIN = (r"bis|ter|quater|quinquies|sexies|septies|octies|novies|nonies|decies|vicies"
          r"|[a-z]+decies")
_SUFFIX = rf"(?:[-\s](?:{_LATIN})\b)"
_ARTICLE_LABEL = rf"\d{{1,4}}(?![\d/]){_SUFFIX}?"  # never the start of a longer number or act
_AND = r"\s*(?:,|\be\b|\bed\b|\band\b|\bor\b|\bo\b)\s*"  # joins the items of a list
_NUMBERS = rf"\d{{1,3}}(?:{_AND}\d{{1,3}})*(?![\d/])"
# One source reference. A paragraph, point, letter or bracketed number that follows an article
# with only spaces or commas in between belongs to that article.
_REFERENCE = re.compile(
    rf"(?P<article>\b(?:artt?\.|art\b|articol[oi]|articles?)\s*(?P<label>{_ARTICLE_LABEL})"
    rf"(?P<more>(?:{_AND}{_ARTICLE_LABEL})*))"
    rf"|(?P<bracket>\(\s*(?P<bracket_value>\d{{1,3}}|[a-z])\s*\))"
    rf"|(?P<paragraph>\b(?:paragraf[oi]|parr?\.|paragraphs?|paras?\.|comm[ai])\s*"
    rf"(?P<paragraphs>{_NUMBERS}))"
    rf"|(?P<point>\b(?:punt[oi]|points?)\s*(?P<points>{_NUMBERS}))"
    rf"|(?P<letter>\b(?:letter[ae]|lett\.|letters?|punt[oi]|points?)\s*"
    rf"(?P<letters>\(?[a-z]\)?(?![a-z])(?:{_AND}\(?[a-z]\))*))"
    rf"|(?P<number>\b(?:nn?\.|n[°º]|nr\.?|num\.)\s*(?P<number_value>\d{{1,7}})(?![\d/]))"
    rf"|(?P<docweb>\bdoc\.?\s*web\s*(?:n\.\s*)?(?P<docweb_value>\d{{4,9}}))"
    rf"|(?P<recital>\b(?:considerand[oi]|recitals?)\s*(?:n\.\s*)?(?P<recitals>{_NUMBERS}))"
    rf"|(?P<recital_before>\b(?P<recital_value>\d{{1,3}})\s*(?:°|º|th|st|nd|rd)?\s*"
    rf"(?:considerando|recital)\b)",
    re.IGNORECASE)
_ARTICLE_NUMBER = re.compile(_ARTICLE_LABEL, re.IGNORECASE)
_ACT_NUMBER = re.compile(r"(?<![\d/])\d{1,4}/\d{2,4}(?!\d)")  # "95/46/CE" gives "95/46"
_CHAIN = re.compile(r"[\s,]*")  # what may separate an article from the parts that follow it
# Where the words that belong to a reference stop: a sentence or clause end, or a blank line.
_CLAUSE_END = re.compile(r"[;?!]|\.(?=\s+[A-ZÀ-Ý]|\s*$)|\n\s*\n")
_TAIL_CHARS = 100  # at most this many characters after a reference may name its act
_HEAD = re.compile(r"[\s,:]*(?:(?:l|all|dell|nell|dall|sull)['’])?\s*$", re.I)
# How an article's own text numbers its parts: paragraphs "1.", points "12)", letters "a)".
MARKERS = (("paragraph", re.compile(r"(?m)^[ \t]*(\d{1,3})\.(?=\s|$)")),
           ("point", re.compile(r"(?m)^[ \t]*(\d{1,3})\)")),
           ("letter", re.compile(r"(?m)^[ \t]*\(?([a-z])\)")))
PART_WORDS = {"paragraph": "paragrafo", "point": "punto", "letter": "lettera"}


@dataclass(frozen=True)
class Part:
    """A paragraph, point or letter named in a reference."""

    article: str | None  # the article label it belongs to, when the text says so
    kind: str  # "paragraph", "point", "letter", or "number" (bracketed: paragraph or point)
    value: str


class Basis(StrEnum):
    EXPLICIT = "explicit"
    CONTEXT = "context"
    EXTERNAL = "external"
    NONE = "none"


@dataclass(frozen=True)
class Reference:
    """One article reference, as written and as attributed (not yet looked up)."""

    raw_text: str  # the article reference with its parts, as written
    start: int  # offsets of raw_text in the text that was scanned
    end: int
    article: str  # target label, normalised ("Art. 2 bis" -> "2-bis")
    parts: tuple[Part, ...]
    source_instrument: str | None  # the instrument whose text this is (the context), if known
    target_instrument: str | None  # the instrument it points to, if determined
    basis: Basis
    instrument_text: str | None  # the words that named the act, if any
    external_act: str | None = None  # for basis "external": the act as written


@dataclass(frozen=True)
class TextReferences:
    """Everything scan_text finds in one text."""

    references: tuple[Reference, ...]  # article references, attributed
    loose_parts: tuple[Part, ...]  # parts named without an article ("il paragrafo 3")
    recitals: tuple[str, ...]
    documents: tuple[str, ...]  # numbered documents: "n. 157", "doc. web 9876543"


def scan_text(text: str, *, context_instrument: str | None = None,
              own_text: bool = True) -> TextReferences:
    """Parse and attribute every reference in `text`. Offsets refer to `text` as given.

    `own_text`: `text` is part of `context_instrument` (an evidence item). False when it is
    only written about it (a claim citing its provisions): the instrument's own_non_names then
    do not apply, so "articolo 33 del Codice" stays the Privacy Code in a claim on the GDPR.
    """
    articles: list[tuple[re.Match[str], list[str]]] = []
    parts: dict[int, list[Part]] = {}  # article match index -> its parts
    chain_ends: dict[int, int] = {}
    loose: list[Part] = []
    recitals: list[str] = []
    documents: list[str] = []
    owner, chain_end = None, 0  # index of the article that following parts belong to
    for m in _REFERENCE.finditer(text):
        attached = owner if owner is not None and _CHAIN.fullmatch(text, chain_end, m.start()) \
            else None
        if m.group("article"):
            labels = [_label(m.group("label")),
                      *(_label(n) for n in _ARTICLE_NUMBER.findall(m.group("more")))]
            articles.append((m, labels))
            index = len(articles) - 1
            owner = index if len(labels) == 1 else None
            chain_end = chain_ends[index] = m.end()
            continue
        article = articles[attached][1][0] if attached is not None else None
        found: list[Part] = []
        if m.group("bracket"):
            if attached is not None:
                value = m.group("bracket_value").lower()
                found = [Part(article, "letter" if value.isalpha() else "number", value)]
        elif m.group("paragraph"):
            found = [Part(article, "paragraph", n)
                     for n in re.findall(r"\d+", m.group("paragraphs"))]
        elif m.group("point"):
            found = [Part(article, "point", n) for n in re.findall(r"\d+", m.group("points"))]
        elif m.group("letter"):
            found = [Part(article, "letter", x) for x in _letters(m.group("letters"))]
        elif m.group("number") and attached is not None:  # "art. 4, n. 12": point 12
            found = [Part(article, "point", m.group("number_value"))]
        elif m.group("number"):
            documents.append(m.group("number_value"))
        elif m.group("docweb"):
            documents.append(m.group("docweb_value"))
        elif m.group("recital"):
            recitals += re.findall(r"\d+", m.group("recitals"))
        else:
            recitals.append(m.group("recital_value"))
        if found and attached is not None:
            parts.setdefault(attached, []).extend(found)
            chain_end = chain_ends[attached] = m.end()
        else:
            loose += found
            owner = None

    references: list[Reference] = []
    for index, (m, labels) in enumerate(articles):
        end = chain_ends[index]
        next_start = articles[index + 1][0].start() if index + 1 < len(articles) else len(text)
        previous_end = chain_ends[index - 1] if index else 0
        target, basis, named, external = _attribute(text, m.start(), end, next_start,
                                                    previous_end, context_instrument, own_text)
        for label in labels:
            references.append(Reference(
                raw_text=text[m.start():end], start=m.start(), end=end, article=label,
                parts=tuple(dict.fromkeys(parts.get(index, []))) if len(labels) == 1 else (),
                source_instrument=context_instrument, target_instrument=target, basis=basis,
                instrument_text=named, external_act=external))
    return TextReferences(tuple(references), tuple(dict.fromkeys(loose)),
                          tuple(dict.fromkeys(recitals)), tuple(dict.fromkeys(documents)))


def extract_references(text: str, *, context_instrument: str | None = None,
                       own_text: bool = True) -> tuple[Reference, ...]:
    """The article references in `text`, each attributed to an instrument where possible."""
    return scan_text(text, context_instrument=context_instrument, own_text=own_text).references


def _attribute(text: str, start: int, end: int, next_start: int, previous_end: int,
               context: str | None,
               own_text: bool) -> tuple[str | None, Basis, str | None, str | None]:
    """(target instrument, basis, words that named it, external act) for one reference."""
    tail = text[end:min(next_start, end + _TAIL_CHARS)]
    stop = _CLAUSE_END.search(tail)
    tail = NOT_INSTRUMENTS.sub(lambda m: " " * len(m.group(0)), tail[:stop.start()] if stop
                               else tail)
    non_names = _OWN_NON_NAMES.get(context) if own_text else None
    best: tuple[int, str | None, Basis, str] | None = None  # (position, target, basis, words)

    def names_in(pattern: re.Pattern[str], where: str) -> Iterator[re.Match[str]]:
        """Matches of an instrument's names in `where`, less those that name nothing here."""
        return (m for m in pattern.finditer(where)
                if non_names is None or not non_names.fullmatch(m.group(0)))

    def consider(match: re.Match[str] | None, target: str | None, basis: Basis) -> None:
        nonlocal best
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), target, basis, match.group(0))

    for instrument_id, pattern in _NAMES.items():
        consider(next(names_in(pattern, tail), None), instrument_id, Basis.EXPLICIT)
    if context is not None:
        for context_id, target_id, pattern in _DEFINED:
            if context_id == context:
                consider(pattern.search(tail), target_id, Basis.CONTEXT)
        if context in _SELF_NAMES:
            consider(_SELF_NAMES[context].search(tail), context, Basis.CONTEXT)
    consider(SELF_REFERENCE.search(tail), context, Basis.CONTEXT if context else Basis.NONE)
    consider(GENERIC_ACT_WORDS.search(tail), None, Basis.NONE)  # last: loses ties
    external = EXTERNAL_ACTS.search(tail)
    if external and (best is None or external.start() < best[0]):
        return None, Basis.EXTERNAL, None, _act_words(tail[external.start():])
    if best is not None:
        _, target, basis, words = best
        if target is None:  # an act word no rule identifies: never fall back to the context
            return None, Basis.NONE, " ".join(words.split()), None
        return target, basis, " ".join(words.split()), None

    head = text[previous_end:start]
    for instrument_id, pattern in _NAMES.items():
        for match in names_in(pattern, head):
            if _HEAD.fullmatch(head, match.end()):
                return instrument_id, Basis.EXPLICIT, " ".join(match.group(0).split()), None
    if context is not None:
        return context, Basis.CONTEXT, None, None
    return None, Basis.NONE, None, None


def _act_words(text: str) -> str:
    """The external act as written, up to its number when it has one ("95/46", "n. 101")."""
    matches = [m for m in (re.match(r"[^;]{0,80}?\d{1,4}/\d{2,4}", text),
                           re.match(r"[^;]{0,80}?n\.\s*\d+(?![\d/])", text)) if m]
    shortest = min(matches, key=lambda m: m.end(), default=None)
    return " ".join((shortest.group(0) if shortest else text[:40]).split())


def article_label(text: str) -> str:
    """An article label in its comparison form: "Art. 2 bis" label "2 bis" -> "2-bis"."""
    return re.sub(r"[\s-]+", "-", text.strip().lower())


_label = article_label


def _letters(text: str) -> list[str]:
    """'b), c) e d)' -> b, c, d: the first letter, then each later one closed by ')'."""
    first = re.match(r"\(?([a-z])\)?", text, re.IGNORECASE)
    rest = re.findall(r"\(?([a-z])\)", text[first.end():], re.IGNORECASE)
    return [first.group(1).lower(), *(x.lower() for x in rest)]


def article_references(text: str) -> list[str]:
    """Article labels named in `text`, normalised ("Art. 2 bis" -> "2-bis"), in order."""
    return list(dict.fromkeys(r.article for r in extract_references(normalise(text))))


def act_numbers(text: str) -> list[str]:
    """Act numbers such as "2016/679" or "101/2018" named in `text`, in order."""
    return list(dict.fromkeys(_ACT_NUMBER.findall(normalise(text))))


def part_markers(text: str) -> set[tuple[str, str]]:
    """(kind, value) of the paragraphs, points and letters an article's text numbers."""
    return {(kind, value.lower()) for kind, marker in MARKERS for value in marker.findall(text)}


# --- Resolution --------------------------------------------------------------------------------


class Status(StrEnum):
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Resolution:
    reference: Reference
    status: Status
    reason: str  # a code: found, instrument_not_stated, label_ambiguous, no_such_article,
    #              instrument_not_in_corpus, part_not_found, parts_not_checked
    explanation: str
    provision_id: str | None = None  # the resolved provision, when the article is resolved
    candidates: tuple[str, ...] = field(default=())  # provision IDs, for ambiguous references
    point: str | None = None  # a numbered point "N)" to look up, when exactly one is named


ArticleText = Callable[[Any], str | None]  # Provision -> its article text, if available


def resolve_reference(reference: Reference, store: Any, *,
                      article_text: ArticleText | None = None) -> Resolution:
    """Look `reference` up in `store` (a ProvisionStore). Never guesses an instrument."""
    label = reference.article
    if reference.basis == Basis.EXTERNAL:
        return Resolution(reference, Status.UNRESOLVED, "instrument_not_in_corpus",
                          f"articolo {label} of {reference.external_act}, an act outside the "
                          "corpus")
    if reference.target_instrument is None:
        candidates = tuple(p.provision_id for p in _articles(store, None, label))
        if not candidates:
            return Resolution(reference, Status.UNRESOLVED, "no_such_article",
                              f"no article {label} in any corpus instrument")
        return Resolution(reference, Status.AMBIGUOUS, "instrument_not_stated",
                          f"the act of articolo {label} is not stated; {len(candidates)} "
                          "corpus article(s) have this number", candidates=candidates)
    if reference.target_instrument not in {i.instrument_id for i in store.registry.instruments}:
        return Resolution(reference, Status.UNRESOLVED, "instrument_not_in_corpus",
                          f"{reference.target_instrument} is not in the corpus")
    found = _articles(store, reference.target_instrument, label)
    if not found:
        return Resolution(reference, Status.UNRESOLVED, "no_such_article",
                          f"no article {label} in {reference.target_instrument}")
    if len(found) > 1:
        return Resolution(reference, Status.AMBIGUOUS, "label_ambiguous",
                          f"articolo {label} matches {len(found)} articles of "
                          f"{reference.target_instrument}",
                          candidates=tuple(p.provision_id for p in found))
    provision = found[0]
    if not reference.parts:
        return Resolution(reference, Status.RESOLVED, "found", f"{provision.provision_id}",
                          provision.provision_id)
    text = article_text(provision) if article_text else None
    if text is None:
        return Resolution(reference, Status.PARTIALLY_RESOLVED, "parts_not_checked",
                          "the article is resolved; its text was not available to check the "
                          "parts", provision.provision_id)
    present = part_markers(text)
    missing = [p for p in reference.parts if not _part_present(p, present)]
    if missing:
        return Resolution(reference, Status.PARTIALLY_RESOLVED, "part_not_found",
                          "the article is resolved; not in its text: "
                          + ", ".join(_part_words(p) for p in missing), provision.provision_id)
    points = [p.value for p in reference.parts
              if p.kind == "point" or (p.kind == "number" and ("point", p.value) in present
                                       and ("paragraph", p.value) not in present)]
    return Resolution(reference, Status.RESOLVED, "found", provision.provision_id,
                      provision.provision_id,
                      point=points[0] if len(points) == 1 and len(reference.parts) == 1 else None)


def resolve_references(text: str, store: Any, *, context_instrument: str | None = None,
                       article_text: ArticleText | None = None) -> tuple[Resolution, ...]:
    """Extract and resolve every article reference in `text`, in order."""
    return tuple(resolve_reference(r, store, article_text=article_text)
                 for r in extract_references(text, context_instrument=context_instrument))


def _articles(store: Any, instrument_id: str | None, label: str) -> list[Any]:
    """Articles matching `label` as ProvisionStore.lookup does: exactly as printed, otherwise
    after normalise_label; within one instrument, or in all of them."""
    candidates = [p for p in store.articles()
                  if instrument_id in (None, p.instrument_id)]
    exact = [p for p in candidates if p.label_as_printed == label]
    if exact:
        return exact
    return [p for p in candidates if p.normalised_label == normalise_label(label)]


def _part_present(part: Part, present: set[tuple[str, str]]) -> bool:
    kinds = ("paragraph", "point") if part.kind == "number" else (part.kind,)
    return any((kind, part.value) in present for kind in kinds)


def _part_words(part: Part) -> str:
    if part.kind == "number":
        return f"({part.value})"
    return f"{PART_WORDS[part.kind]} {part.value}"
