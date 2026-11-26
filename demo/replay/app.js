// Legal RAG web demo. Renders the server's answer: AnswerResult.to_dict() plus source_status.
// Every value from the server is written with textContent (never as HTML), and only fields the
// server provides are shown: no score, confidence or provenance is computed here. Variable
// names follow the backend objects: result, claim, quote, ref (SourceReference), item
// (EvidenceItem), anchor, status (source_status entry), gap (UnansweredIssue), rejected
// (RejectedClaim), dropped (DroppedCandidate), pre (CorpusPreflight), prov
// (GenerationProvenance), analysis, issue, suggestion, evidence, resolution, info (health).
"use strict";

// Plain-language outcomes (answer_generation.Outcome) and abstention reasons, for the simple view.
const OUTCOMES = {
  answer: { tone: "ok", title: "Answer",
    text: "Every part of the question is answered by statements quoted from the law." },
  answer_limited: { tone: "warn", title: "Partial answer",
    text: "Part of the question is not answered by the provisions found: see what is missing below." },
  abstain: { tone: "stop", title: "No answer", text: "" },
};
const PLAIN_REASONS = {
  out_of_scope: "the question is outside the GDPR and the Italian Privacy Code",
  needs_clarification: "the question needs to be made clearer first",
  no_evidence: "no relevant provision was found",
  no_citable_evidence: "no provision that may be cited in this mode was found",
  analysis_failed: "the question could not be analysed",
  model_refused: "the model declined the request",
  generation_failed: "no answer could be generated",
  model_abstained: "the provisions found do not answer the question",
  no_supported_claims: "no statement passed the checks",
};
// The backend's own codes, for the detailed sections.
const ABSTENTIONS = {
  out_of_scope: "The question is outside the corpus",
  needs_clarification: "The question needs clarification",
  no_evidence: "No relevant provision was found",
  no_citable_evidence: "No usable evidence for this mode",
  analysis_failed: "The question could not be analysed",
  model_refused: "The model declined the request",
  generation_failed: "The answer could not be generated",
  model_abstained: "The model found the evidence insufficient",
  no_supported_claims: "No statement survived the checks",
};
const VERIFICATION = {
  SUPPORTED: ["ok", "Support confirmed by the model check"],
  PARTIALLY_SUPPORTED: ["warn", "Partially supported"],
  UNCERTAIN: ["warn", "Support uncertain"],
  NOT_VERIFIED: ["", "Support not checked"],
  UNSUPPORTED: ["stop", "Unsupported"],
  CONTRADICTED: ["stop", "Contradicted"],
};
const KINDS = { source_statement: "Provision text", inference: "Interpretation" };
// The direct answer to a yes/no or premise question (answer_generation.DirectAnswer).
const DIRECT_VALUES = { yes: "Yes", no: "No", partly: "Partly" };
const DIRECT_NOT_SHOWN = {  // as answer_generation.DIRECT_NOT_SHOWN
  missing: "the model gave no usable direct answer",
  cannot_establish: "the supplied provisions do not establish a yes or no",
  not_supported: "the statements it rests on were not all confirmed by the support check",
  unsupported_reference: "it named a provision outside the statements it rests on",
};
const QUESTION_TYPES = { yes_no: "asks for a yes or no", premise: "rests on a stated premise", open: "open question" };
// Short names for the provision chips (the registry's full names are in info.instruments).
const SHORT_NAMES = { "eu-reg-2016-679": "GDPR", "it-dlgs-2003-196": "Codice privacy" };
const HELD_CLAIMS_TITLE = "Partially supported or uncertain — not part of the answer";  // as answer_generation.HELD_CLAIMS_TITLE
const HELD_SOURCES_TITLE = "Sources of these statements only";  // as answer_generation.HELD_SOURCES_TITLE
// As answer_generation.SUPPORT_NOT_RUN_NOTICE / SUPPORT_FAILED_NOTICE and support_check_notice().
const SUPPORT_NOT_RUN_NOTICE = "The support check did not run: no statement in this answer has been checked against its evidence by the model check.";
const SUPPORT_FAILED_NOTICE = "The support check failed: no statement in this answer has been checked against its evidence by the model check.";
// The research-mode qualification starts with one of these (answer_generation.RESEARCH_QUALIFICATION and its Italian display text).
const RESEARCH_PREFIXES = ["RESEARCH DEMO MODE", "MODALITÀ DIMOSTRATIVA DI RICERCA"];
// answer_generation.DIGITAL_OMNIBUS_CAVEAT, added to answers that cite GDPR Art. 33, contains this.
const OMNIBUS_MARK = "Digital Omnibus";

function supportNotice(result) {
  if (!result.claims.length || result.verification) return null;
  const failed = result.warnings.some((w) => w.startsWith("support_verification_unavailable"));
  return el("div", { class: "banner warn" }, el("p", {}, failed ? SUPPORT_FAILED_NOTICE : SUPPORT_NOT_RUN_NOTICE));
}
const MODE_LABELS = { verified: "Verified mode", research: "Research demo mode" };

let info = { reasons: {}, qualifications: {}, instruments: {}, source_categories: {},
  max_question_chars: 2000, citable_articles: null, research_usable_articles: null,
  model_notes_label: "Model notes: unverified, not part of the legal answer" };
let busy = false;

const $ = (selector) => document.querySelector(selector);

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const badge = (tone, text) => el("span", { class: `badge ${tone || ""}` }, text);
const pages = (start, end) => (start === end ? `p. ${start}` : `pp. ${start}–${end}`);
const card = (title, ...body) => el("section", { class: "card" }, el("h3", {}, title), ...body);
// A section collapsed by default: the details below the simple view.
const fold = (title, ...body) => el("section", { class: "card fold" },
  el("details", {}, el("summary", {}, title), el("div", { class: "fold-body" }, ...body)));
const list = (values, render) => el("ul", { class: "plain" }, values.map((v) => el("li", {}, render(v))));
const explain = (table, code) => (table[code] ? `${table[code]} (${code})` : code);
const selectedMode = () => document.querySelector('input[name="mode"]:checked').value;
const pending = (status) => Boolean(status) && status.human_review === "pending";

// --- Status, mode and corpus -------------------------------------------------------------------

async function loadHealth() {
  const statusLine = $("#status");
  try {
    const response = await fetch("/api/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(String(response.status));
    info = { ...info, ...(await response.json()) };
  } catch {
    statusLine.textContent = "The local server is not answering. Start it with: python -m src.web_demo";
    statusLine.className = "status stop";
    return;
  }
  $("#question").maxLength = info.max_question_chars;
  if (info.public) applyPublicMode();
  updateCounter();
  updateStatus();
  const names = Object.values(info.instruments);
  $("#corpus").textContent = names.length ? `Corpus: ${names.join(" · ")}.` : "";
}

// The public live demo (web_demo --public, a Hugging Face Space): research mode only, short
// questions, limits per visitor and per day; the page says where questions go.
function applyPublicMode() {
  const limits = info.limits;
  $(".modes").hidden = true;
  document.querySelector('input[name="mode"][value="verified"]').disabled = true;
  document.querySelector('input[name="mode"][value="research"]').checked = true;
  $("#public-notice").hidden = false;
  $("#public-limits").textContent = `Each visitor may ask ${limits.per_visitor_hour} questions per hour and ` +
    `${limits.per_visitor_day} per day, in at most ${limits.max_question_chars} characters; the demo answers ` +
    `${limits.global_day} questions per day in total. When a limit is reached, the saved answers remain available:`;
  $("#public-replay").href = info.replay_url;
  $("#footer-note").textContent = "Prototype for research and demonstration. Not legal advice. Live demo: " +
    "questions and the provisions retrieved for them are sent to Anthropic's API for analysis, generation " +
    "and verification. Do not include personal data.";
  onModeChange();
}

function updateStatus() {
  const statusLine = $("#status");
  if (info.citable_articles === null) return;
  const research = selectedMode() === "research";
  const model = `model ${info.provider}/${info.model}`;
  if (research) {
    statusLine.textContent = `${model} · ${info.research_usable_articles} articles usable in research mode, ` +
      `of which ${info.citable_articles} have passed human review`;
    statusLine.className = "status warn";
  } else if (!info.citable_articles) {
    statusLine.textContent = `${model} · no article has passed human review yet, so verified questions ` +
      "abstain before any model call. Research demo mode can use provisions pending review.";
    statusLine.className = "status warn";
  } else {
    statusLine.textContent = `${model} · ${info.citable_articles} citable articles`;
    statusLine.className = "status";
  }
}

function onModeChange() {
  const research = selectedMode() === "research";
  const pill = $("#mode-pill");
  pill.textContent = MODE_LABELS[selectedMode()];
  pill.className = `mode-pill ${research ? "research" : "verified"}`;
  $("#research-warning").hidden = !research;
  $("#ack-row").hidden = !research;
  if (!research) $("#ack").checked = false;
  updateAskButton();
  updateStatus();
}

function updateAskButton() {
  $("#ask").disabled = busy || (selectedMode() === "research" && !$("#ack").checked);
}

// --- Asking -------------------------------------------------------------------------------------

async function ask(event) {
  event.preventDefault();
  if (busy) return;
  const question = $("#question").value.trim();
  const mode = selectedMode();
  if (!question) {
    showError("Write a question first.");
    $("#question").focus();
    return;
  }
  if (mode === "research" && !$("#ack").checked) {
    showError("Research demo mode needs your confirmation that answers may rest on unreviewed sources.");
    return;
  }
  setBusy(true);
  $("#result").hidden = true;
  $("#empty").hidden = true;
  const started = Date.now();
  const elapsed = el("span", { class: "muted" }, "0 s");
  const timer = setInterval(() => { elapsed.textContent = `${Math.round((Date.now() - started) / 1000)} s`; }, 1000);
  $("#state").replaceChildren(el("div", { class: "card loading", role: "status" },
    el("span", { class: "spinner", "aria-hidden": "true" }),
    el("span", {}, `Analysing the question, retrieving provisions and checking the answer (${MODE_LABELS[mode]}). `,
      "With model calls this can take a minute. "),
    elapsed));
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ question, mode }),
    });
    let payload = null;
    try { payload = await response.json(); } catch { payload = null; }
    if (!response.ok || !payload) {
      const message = payload && payload.error ? payload.error.message : `The server answered with HTTP ${response.status}.`;
      // A limit of the public demo (HTTP 429) points to the replay of saved answers.
      showError(message, payload && payload.error ? payload.error.replay_url : null);
      return;
    }
    $("#state").replaceChildren();
    renderResult(payload);
  } catch {
    showError("Could not reach the local server. Is it still running?");
  } finally {
    clearInterval(timer);
    setBusy(false);
  }
}

function setBusy(value) {
  busy = value;
  $("#question").readOnly = value;
  for (const control of document.querySelectorAll(".example, input[name=mode], #ack")) control.disabled = value;
  updateAskButton();
}

function showError(message, replayUrl) {
  $("#state").replaceChildren(el("div", { class: "banner stop", role: "alert" },
    el("h2", {}, replayUrl ? "Limit reached" : "Something went wrong"), el("p", { class: "detail" }, message),
    replayUrl ? el("p", {}, el("a", { href: replayUrl, target: "_blank", rel: "noopener" },
      "Open the replay of saved answers")) : null));
}

function reset() {
  $("#question").value = "";
  updateCounter();
  $("#state").replaceChildren();
  $("#result").replaceChildren();
  $("#result").hidden = true;
  $("#empty").hidden = false;
  $("#reset").hidden = true;
  $("#question").focus();
}

function updateCounter() {
  const textarea = $("#question");
  $("#counter").textContent = `${textarea.value.length} / ${textarea.maxLength}`;
}

// --- Rendering: the simple view ------------------------------------------------------------------
// On top: the question, a plain-language outcome, one-line notices, and the answer as sentences,
// each with a chip per provision that opens the exact quotation and page. Below, collapsed: the
// statements not confirmed, the sources and their status, how the answer was produced, the model
// notes and every caveat.

function renderResult(result) {
  const statusById = result.source_status || {};
  const evidenceItems = result.evidence ? result.evidence.items : [];
  const itemById = Object.fromEntries(evidenceItems.map((item) => [item.evidence_id, item]));
  const refById = Object.fromEntries(result.citations.map((ref) => [ref.evidence_id, ref]));
  const issues = result.analysis ? result.analysis.issues : [];
  const issueText = Object.fromEntries(issues.map((issue) => [issue.id, issue.question]));

  // The rule of answer_generation.in_answer(): a claim the support check rated other than
  // SUPPORTED is shown apart, below the answer, and is not part of it. Display only.
  const inAnswer = (claim) => claim.verification === "SUPPORTED" || claim.verification === "NOT_VERIFIED";
  const shown = result.claims.filter(inAnswer);
  const held = result.claims.filter((claim) => !inAnswer(claim));
  // The rule of answer_generation.answer_sources(): the Sources section lists the sources of the
  // claims in the answer; sources cited only by held-apart claims are listed with those claims.
  const shownIds = new Set(shown.flatMap((claim) => claim.evidence_ids));
  const heldIds = new Set(held.flatMap((claim) => claim.evidence_ids));
  const mainSources = result.citations.filter((ref) => shownIds.has(ref.evidence_id));
  const heldSources = result.citations.filter((ref) => heldIds.has(ref.evidence_id) && !shownIds.has(ref.evidence_id));
  const source = (ref) => renderSource(ref, itemById[ref.evidence_id], statusById[ref.evidence_id]);

  const sections = [renderOutcome(result), renderNotices(result)];
  // The statements a direct answer rests on, when the application shows it (answer_generation.
  // _direct_answer()); absent from results made before the direct answer existed.
  const direct = result.direct_answer;
  const basis = new Set(direct && direct.status === "shown" ? direct.claim_ids : []);
  if (result.claims.length) {
    // The summary is shown only when the application kept it (answer_generation._summary()).
    sections.push(card("What the provisions say", renderDirect(direct),
      result.summary ? el("p", { class: "summary" }, result.summary) : null,
      supportNotice(result),
      shown.length
        ? el("div", { class: "answer" }, shown.map((claim) => renderStatement(claim, refById, statusById, basis.has(claim.claim_id))))
        : el("p", { class: "muted" }, "No statement was confirmed by the support check: see the statements not confirmed below."),
      renderMissing(result, issueText)));
  }
  if (held.length) {
    sections.push(fold(`Statements not confirmed (${held.length})`,
      el("p", { class: "muted" }, `${HELD_CLAIMS_TITLE}. The support check did not confirm these statements; they are shown with their status and quotations.`),
      held.map((claim) => renderClaim(claim, statusById, itemById)),
      heldSources.length ? [el("p", { class: "subhead" }, HELD_SOURCES_TITLE), heldSources.map(source)] : null));
  }
  if (mainSources.length) {
    sections.push(fold(`Sources and their status (${mainSources.length})`,
      el("p", { class: "muted" }, "The provisions the answer rests on, with what is known about each source."),
      mainSources.map(source)));
  }
  sections.push(renderTransparency(result, statusById, itemById, shown));
  if (result.model_notes.length) {
    sections.push(fold(`Model notes (${result.model_notes.length})`,
      el("p", { class: "subhead" }, info.model_notes_label), list(result.model_notes, (note) => note)));
  }
  sections.push(renderCaveats(result));
  $("#result").replaceChildren(...sections.filter(Boolean));
  $("#result").hidden = false;
  $("#reset").hidden = false;
  $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderOutcome(result) {
  const outcome = OUTCOMES[result.outcome] || { tone: "warn", title: result.outcome, text: "" };
  const reason = result.outcome === "abstain" ? PLAIN_REASONS[result.abstention_reason] || result.abstention_reason : null;
  const banner = el("div", { class: `banner ${outcome.tone}` },
    el("p", { class: "question" }, result.question),
    el("h2", {}, reason ? `${outcome.title}: ${reason}` : outcome.title),
    outcome.text ? el("p", {}, outcome.text) : null);
  const analysis = result.analysis;
  if (result.outcome === "abstain" && analysis && analysis.clarification_question) {
    banner.append(el("p", { class: "detail" }, `Clarification needed: ${analysis.clarification_question}`));
  }
  return banner;
}

// The direct answer, at the top of the answer: shown only with the status "shown", as an
// interpretation of the statements marked below it; otherwise one line says why there is none.
// The value is the label ("Direct answer: No"); the model's sentence follows on its own line,
// unchanged, so a sentence that itself starts with "No" does not repeat it after the value.
function renderDirect(direct) {
  if (!direct) return null;
  if (direct.status !== "shown") {
    return el("p", { class: "direct-none" }, `No direct yes or no: ${DIRECT_NOT_SHOWN[direct.status] || direct.status}.`);
  }
  return el("div", { class: "direct" },
    el("p", { class: "direct-label" }, el("strong", {}, `Direct answer: ${DIRECT_VALUES[direct.value] || direct.value}`),
      " · an interpretation of the statements marked «basis» below"),
    el("p", { class: "direct-text" }, direct.text));
}

// Always visible, one line each: the mode, not legal advice, the as-of date, the Omnibus caveat.
function renderNotices(result) {
  const lines = [];
  if (result.mode === "research") {
    lines.push(el("li", { class: "caveat-research" }, result.citations.some((ref) => !ref.citable)
      ? "Research demo mode. This answer rests on sources pending human review. They are marked «pending review» and are not verified."
      : "Research demo mode: answers may rest on provisions that no person has reviewed yet."));
  }
  lines.push(el("li", {}, "Not legal advice: a research prototype. It does not establish whether a provision is valid or in force."));
  if (result.as_of) {
    lines.push(el("li", {}, `As of ${result.as_of}: the answer reflects the texts in the corpus on that date, not the law in force then or later.`));
  }
  // The Art. 33 caveat itself, as displayed (in Italian for an Italian question).
  const omnibus = (result.display_qualifications || result.qualifications).find((text) => text.includes(OMNIBUS_MARK));
  if (omnibus) lines.push(el("li", {}, omnibus));
  return el("ul", { class: "notices" }, lines);
}

// Display only: the Code's article titles carry the transcription's amendment markers, e.g.
// "(( (Autorità di controllo). ))", shown as "Autorità di controllo". Quoted text is never changed.
function displayTitle(title) {
  if (!title) return title;
  let text = title.replaceAll("((", " ").replaceAll("))", " ").replace(/\s+/g, " ").trim();
  const wrapped = text.match(/^\(([^()]*)\)\.?$/);
  if (wrapped) text = wrapped[1].trim();
  return text.replace(/\.$/, "");
}

function provisionName(ref) {
  const name = SHORT_NAMES[ref.instrument_id] || info.instruments[ref.instrument_id] || ref.instrument_id;
  return `${name} art. ${ref.label}${ref.point ? `, point ${ref.point}` : ""}`;
}

// A statement of the answer: its text, then a chip per provision it cites. A chip opens the exact
// quotation(s) from that provision and its page; «pending review» marks a source not yet reviewed.
function renderStatement(claim, refById, statusById, isBasis = false) {
  const panels = [];
  const chips = claim.evidence_ids.map((evidenceId) => {
    const ref = refById[evidenceId];
    const status = statusById[evidenceId];
    const panelId = `quote-${claim.claim_id}-${evidenceId}`;
    const panel = el("div", { class: "quote-panel", id: panelId, hidden: true },
      claim.quotes.filter((quote) => quote.evidence_id === evidenceId).map((quote) => el("blockquote", {}, `«${quote.text}»`,
        quote.widened_from ? el("span", { class: "widened-note" }, `Widened by the repair pass, within the same provision, from «${quote.widened_from}».`) : null)),
      ref ? el("p", { class: "muted" }, `${provisionName(ref)} — ${ref.heading}${ref.title ? ` (${displayTitle(ref.title)})` : ""}, ` +
        `${pages(ref.page_start, ref.page_end)} of the source PDF` + (pending(status) ? ". Human review pending: not verified." : ".")) : null);
    panels.push(panel);
    const chip = el("button", { type: "button", class: `chip-cite ${pending(status) ? "unreviewed" : ""}`,
      "aria-expanded": "false", "aria-controls": panelId, title: "Show the exact quotation" },
    ref ? provisionName(ref) : evidenceId, pending(status) ? el("span", { class: "pending-mark" }, "pending review") : null);
    chip.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      chip.setAttribute("aria-expanded", String(!panel.hidden));
    });
    return chip;
  });
  return el("div", { class: "statement" },
    el("p", {}, isBasis ? el("span", { class: "kind-tag basis-tag" }, "Basis") : null,
      claim.kind === "inference" ? el("span", { class: "kind-tag" }, "Interpretation") : null,
      claim.text, " ", chips),
    panels);
}

// What the answer leaves open: shown with the answer, in plain words, for a partial answer.
function renderMissing(result, issueText) {
  if (!result.unanswered_issues.length) return null;
  return el("div", { class: "missing" },
    el("p", { class: "subhead" }, "Not answered by the provisions found"),
    list(result.unanswered_issues, (gap) => issueText[gap.issue_id] || gap.issue_id));
}

function renderClaim(claim, statusById, itemById) {
  const [tone, label] = VERIFICATION[claim.verification] || ["", claim.verification];
  return el("article", { class: "claim" },
    el("p", { class: "claim-text" }, claim.text),
    el("div", { class: "meta" },
      badge("", claim.claim_id), badge(claim.kind === "inference" ? "warn" : "", KINDS[claim.kind] || claim.kind),
      badge(tone, label), claim.repaired_from ? badge("ok", "Repaired") : null,
      claim.issue_ids.length ? badge("", `Issue ${claim.issue_ids.join(", ")}`) : null),
    claim.repaired_from ? el("p", { class: "muted" }, "Rewritten by the repair pass from a wording the support check did not confirm: ",
      `«${claim.repaired_from}». The rewrite keeps quotations of that statement` +
      (claim.quotes.some((quote) => quote.widened_from) ? ", widened within the same provision where marked," : "") +
      " and was confirmed by the support check.") : null,
    claim.quotes.map((quote) => {
      const status = statusById[quote.evidence_id];
      const item = itemById[quote.evidence_id];
      return el("blockquote", { class: pending(status) ? "unreviewed" : "" },
        `«${quote.text}» `, el("span", { class: "muted" }, quote.evidence_id),
        item ? el("span", { class: "muted" }, ` ${item.heading}`) : null,
        quote.widened_from ? el("span", { class: "widened-note" }, `Widened by the repair pass, within the same provision, from «${quote.widened_from}».`) : null);
    }));
}

function renderCaveats(result) {
  return fold("All caveats and limitations",
    list(result.display_qualifications || result.qualifications, (text) => (RESEARCH_PREFIXES.some((p) => text.startsWith(p))
      ? el("span", { class: "caveat-research" }, text) : text)),
    result.warnings.length ? el("p", { class: "muted" }, `Warnings: ${result.warnings.join(", ")}`) : null);
}

function renderStatus(status) {
  if (!status) return null;
  const categoryTone = status.category === "official_extraction_checked" ? "ok" : "warn";
  return [
    el("div", { class: "meta" },
      badge(categoryTone, info.source_categories[status.category] || status.category),
      badge(status.human_review === "reviewed" ? "ok" : "warn",
        status.human_review === "reviewed" ? "Human review recorded" : "Human review pending"),
      badge("warn", "Legal currency not established"),
      badge(status.citable_in_verified_mode ? "ok" : "", status.citable_in_verified_mode
        ? "Citable in verified mode" : "Not citable in verified mode")),
    el("div", { class: "statements" }, list(status.statements, (text) => text)),
  ];
}

function renderSource(ref, item, status) {
  const extent = ref.whole_provision ? "whole provision" : ref.point ? `point ${ref.point} only` : "excerpt";
  const title = `${provisionName(ref)} · ${ref.heading}${ref.title ? ` — ${displayTitle(ref.title)}` : ""}`;
  const node = el("article", { class: `source ${pending(status) ? "unreviewed" : ""}`, id: `source-${ref.evidence_id}` },
    el("p", { class: "source-title" }, title),
    renderStatus(status),
    el("dl", { class: "kv" },
      el("dt", {}, "Evidence ID"), el("dd", {}, ref.evidence_id),
      el("dt", {}, "Instrument"), el("dd", {}, info.instruments[ref.instrument_id] || ref.instrument_id),
      el("dt", {}, "Location"), el("dd", {}, `${ref.path} · ${pages(ref.page_start, ref.page_end)} · ${extent}`),
      el("dt", {}, "Eligibility"), el("dd", {}, ref.citable ? `tier ${ref.tier}`
        : `tier ${ref.tier}: ${ref.reasons.map((code) => explain(info.reasons, code)).join(" ")}`),
      el("dt", {}, "Provision ID"), el("dd", { class: "mono" }, ref.provision_id),
      el("dt", {}, "Version"), el("dd", { class: "mono" }, ref.version_id)));
  if (item) {
    const anchors = item.anchors.map((anchor) => `characters ${anchor.char_start}–${anchor.char_end}, ${pages(anchor.page, anchor.page_end)}`);
    node.append(el("details", {},
      el("summary", {}, "Exact source text"),
      el("pre", { class: "source-text" }, item.text),
      el("dl", { class: "kv" },
        el("dt", {}, "Source anchors"), el("dd", {}, anchors.join("; ")),
        el("dt", {}, "Found by"), el("dd", {}, item.origins.map(origin).join("; ")))));
  }
  return node;
}

function origin(code) {
  if (code === "lookup") return "direct lookup";
  if (code.startsWith("query:")) return `search query ${code.slice(6)}`;
  if (code.startsWith("reference:")) return `reference in ${code.slice(10)}`;
  return code;
}

// --- How this answer was produced (collapsed) -----------------------------------------------------

function table(head, rows) {
  return el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, head.map((h) => el("th", {}, h)))),
    el("tbody", {}, rows.map((row) => el("tr", {}, row.map((cell) => el("td", {}, cell)))))));
}

function renderTransparency(result, statusById, itemById, shown) {
  const blocks = [];
  if (shown.length) {
    blocks.push(el("p", { class: "subhead" }, "Statements in the answer and their checks"),
      shown.map((claim) => renderClaim(claim, statusById, itemById)));
  }
  const execution = [el("dt", {}, "Mode"), el("dd", {}, MODE_LABELS[result.mode] || result.mode)];
  const direct = result.direct_answer;
  if (direct) {
    execution.push(el("dt", {}, "Direct answer"), el("dd", {}, direct.status === "shown"
      ? `${DIRECT_VALUES[direct.value] || direct.value}, resting on ${direct.claim_ids.join(", ")}; not support-checked itself`
      : `not shown: ${DIRECT_NOT_SHOWN[direct.status] || direct.status}` + (direct.value ? ` (model's value: ${direct.value})` : "")));
  }
  for (const [name, prov] of [["Generation", result.generation], ["Support check", result.verification],
    ["Repair", result.repair], ["Support check of the repairs", result.repair_verification]]) {
    if (prov) {
      execution.push(el("dt", {}, name), el("dd", {},
        `${prov.provider}/${prov.served_by}, ${prov.prompt_version}, ${prov.attempts} attempt${prov.attempts === 1 ? "" : "s"}` +
        (prov.fallback_used ? ", fallback model used" : "") +
        (prov.supplied_evidence_ids.length ? `; evidence supplied: ${prov.supplied_evidence_ids.join(", ")}` : "")));
    }
  }
  if (result.generation && !result.verification) execution.push(el("dt", {}, "Support check"), el("dd", {}, "not run"));
  const pre = result.preflight;
  if (pre) {
    const tiers = Object.entries(pre.article_tiers).map(([tier, count]) => `${count} ${tier}`).join(", ");
    execution.push(el("dt", {}, "Corpus check"), el("dd", {}, `build ${pre.build_id}: ${tiers}; ${pre.citable_articles} citable`));
  }
  blocks.push(el("p", { class: "subhead" }, "Execution"), el("dl", { class: "kv" }, execution));

  if (result.outcome === "abstain") {
    blocks.push(el("p", { class: "subhead" }, "Reason for abstaining"),
      el("p", {}, explain(ABSTENTIONS, result.abstention_reason), result.abstention_detail ? `: ${result.abstention_detail}` : ""));
  }
  if (result.unanswered_issues.length) {
    blocks.push(el("p", { class: "subhead" }, "Issues not fully answered"),
      list(result.unanswered_issues, (gap) => [el("strong", {}, gap.issue_id), ` — ${gap.reason}`]));
  }

  const evidence = result.evidence;
  if (evidence) {
    const cited = new Set(result.citations.map((ref) => ref.evidence_id));
    const refused = new Set(result.non_authoritative.map((ref) => ref.evidence_id));
    blocks.push(el("p", { class: "subhead" }, `Retrieved provisions (${evidence.items.length})`),
      el("p", { class: "muted" }, "BM25 rank is the best position among the search hits (1 is best); direct lookups have none. No relevance score is computed for evidence items."),
      table(["ID", "Provision", "Found by", "BM25 rank", "Tier", "Source", "In the answer"],
        evidence.items.map((item) => {
          const status = statusById[item.evidence_id];
          return [item.evidence_id, `${item.heading}${item.point ? ` (point ${item.point})` : ""}`,
            item.origins.map(origin).join("; "), item.best_rank === null ? "—" : String(item.best_rank),
            item.tier, status ? (info.source_categories[status.category] || status.category) + (pending(status) ? "; review pending" : "") : "",
            cited.has(item.evidence_id) ? "cited" : refused.has(item.evidence_id) ? "not allowed in this mode" : "not cited"];
        })),
      el("p", { class: "muted" }, `${evidence.total_tokens} of ${evidence.token_budget} estimated tokens; at most ${evidence.max_items} items.`));
    if (evidence.dropped.length) {
      blocks.push(el("p", { class: "subhead" }, "Excluded by the evidence limits"),
        list(evidence.dropped, (dropped) => `${dropped.label} (${dropped.provision_id}): ${dropped.reason}, found by ${dropped.origins.map(origin).join("; ")}`));
    }
  }
  if (result.non_authoritative.length) {
    blocks.push(el("p", { class: "subhead" }, "Retrieved but not allowed in this mode"),
      list(result.non_authoritative, (ref) => `${ref.evidence_id} ${ref.heading}: ${ref.reasons.map((code) => explain(info.reasons, code)).join(" ")}`));
  }
  if (result.rejected_claims.length) {
    blocks.push(el("p", { class: "subhead" }, "Statements removed by the checks"),
      list(result.rejected_claims, (rejected) => [rejected.text, el("span", { class: "muted" }, ` — ${rejected.reasons.join(", ")}`)]));
  }
  const analysis = result.analysis;
  if (analysis) {
    blocks.push(el("p", { class: "subhead" }, "Question analysis"),
      el("dl", { class: "kv" },
        el("dt", {}, "Language"), el("dd", {}, analysis.language),
        el("dt", {}, "In scope"), el("dd", {}, `${analysis.in_scope ? "yes" : "no"}: ${analysis.scope_reason}`),
        analysis.question_type ? [el("dt", {}, "Question type"), el("dd", {}, QUESTION_TYPES[analysis.question_type] || analysis.question_type)] : null,
        analysis.uncertainty ? [el("dt", {}, "Uncertainty"), el("dd", {}, analysis.uncertainty)] : null,
        analysis.search_queries_it.length ? [el("dt", {}, "Search queries"), el("dd", {}, analysis.search_queries_it.join("; "))] : null,
        analysis.suggested_provisions.length ? [el("dt", {}, "Suggested lookups"), el("dd", {},
          analysis.suggested_provisions.map((suggestion) => `${suggestion.instrument} art. ${suggestion.article}${suggestion.point ? ` point ${suggestion.point}` : ""}`).join("; "))] : null),
      analysis.issues.length ? list(analysis.issues, (issue) => [el("strong", {}, issue.id), ` ${issue.question}`]) : null);
  }
  if (result.question_references.length) {
    blocks.push(el("p", { class: "subhead" }, "Legal references in the question"),
      list(result.question_references, (resolution) => [`«${resolution.reference.raw_text}» `,
        badge("", resolution.status.replaceAll("_", " ")), ` ${resolution.explanation}`]));
  }
  return fold("How this answer was produced", blocks);
}

// --- Replay of saved answers (python -m src.web_replay) -------------------------------------------
// A static export sets data-replay on <html> to its file of saved answers. The page then sends
// nothing anywhere: it never calls /api/*, and a visitor chooses one of the saved questions, whose
// answer is rendered by renderResult() exactly as a live one.

const REPLAY_FILE = document.documentElement.dataset.replay || null;
let saved = null;  // the replay file: { replay, info, questions, featured, answers }

async function loadReplay() {
  const statusLine = $("#status");
  try {
    const response = await fetch(REPLAY_FILE, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(String(response.status));
    saved = await response.json();
  } catch {
    statusLine.textContent = "The saved answers could not be loaded.";
    statusLine.className = "status stop";
    return;
  }
  info = { ...info, ...saved.info };
  const replay = saved.replay;
  statusLine.textContent = replay.label;
  statusLine.className = "status warn";
  const research = replay.mode === "research";
  $("#mode-pill").textContent = MODE_LABELS[replay.mode] || replay.mode;
  $("#mode-pill").className = `mode-pill ${research ? "research" : "verified"}`;
  $("#research-warning").hidden = !research;
  const names = Object.values(info.instruments);
  $("#corpus").textContent = names.length ? `Corpus: ${names.join(" · ")}.` : "";

  const textOf = Object.fromEntries(saved.questions.map((question) => [question.id, question.question]));
  const featured = (saved.featured || []).filter((pick) => textOf[pick.id]);
  const featuredIds = new Set(featured.map((pick) => pick.id));
  const button = (id, note) => {
    const node = el("button", { type: "button", class: "pick", "data-id": id, "aria-pressed": "false" },
      el("span", { class: "pick-question" }, textOf[id]), note ? el("span", { class: "pick-note" }, note) : null);
    node.addEventListener("click", () => showSaved(id));
    return node;
  };
  const others = saved.questions.filter((question) => !featuredIds.has(question.id));
  $("#ask-form").after(el("section", { class: "card ask-card replay-card" },
    el("p", { class: "replay-label" }, replay.label),
    replay.live_url ? el("p", { class: "replay-live" },
      el("a", { href: replay.live_url, target: "_blank", rel: "noopener" }, "Ask your own question: live demo (limited)"),
      el("span", { class: "replay-live-note" }, "It runs on free hosting and may take about a minute to wake up. " +
        "Questions asked there are sent to Anthropic's API.")) : null,
    el("h2", { class: "picks-title" }, "Choose a question"),
    el("div", { class: "picks" }, featured.map((pick) => button(pick.id, pick.note))),
    others.length ? el("details", { class: "more-questions" },
      el("summary", {}, `More questions (${others.length})`),
      el("div", { class: "picks" }, others.map((question) => button(question.id, null)))) : null,
    el("p", { class: "muted" }, "Development questions of the project's benchmark. Each answer was generated once " +
      "and saved; choosing a question shows it again without calling any model.")));
  $("#empty").replaceChildren(el("h2", {}, "Choose a saved question"),
    el("p", { class: "muted" }, "The answer cites the provisions it rests on, quotes them exactly, shows how " +
      "reliable each source is, and lists what it could not establish."));
}

function showSaved(id) {
  $("#state").replaceChildren();
  for (const node of document.querySelectorAll(".pick")) node.setAttribute("aria-pressed", String(node.dataset.id === id));
  if (!id) {
    $("#result").replaceChildren();
    $("#result").hidden = true;
    $("#empty").hidden = false;
    return;
  }
  $("#empty").hidden = true;
  renderResult(saved.answers[id]);
}

// --- Wiring -------------------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  if (REPLAY_FILE) {
    $("#ask-form").hidden = true;  // a replay asks nothing
    loadReplay();
    return;
  }
  $("#ask-form").addEventListener("submit", ask);
  $("#reset").addEventListener("click", reset);
  $("#question").addEventListener("input", updateCounter);
  $("#question").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey || !event.shiftKey)) {
      event.preventDefault();
      $("#ask-form").requestSubmit();
    }
  });
  for (const radio of document.querySelectorAll("input[name=mode]")) radio.addEventListener("change", onModeChange);
  $("#ack").addEventListener("change", updateAskButton);
  for (const chip of document.querySelectorAll(".example")) {
    chip.addEventListener("click", () => {
      $("#question").value = chip.textContent;
      updateCounter();
      $("#question").focus();
    });
  }
  // Every page load starts in verified mode: research mode is never remembered.
  document.querySelector('input[name="mode"][value="verified"]').checked = true;
  onModeChange();
  loadHealth();
});
