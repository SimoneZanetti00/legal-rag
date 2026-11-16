// Legal RAG web demo. Renders the server's answer: AnswerResult.to_dict() plus source_status.
// Every value from the server is written with textContent (never as HTML), and only fields the
// server provides are shown: no score, confidence or provenance is computed here. Variable
// names follow the backend objects: result, claim, quote, ref (SourceReference), item
// (EvidenceItem), anchor, status (source_status entry), gap (UnansweredIssue), rejected
// (RejectedClaim), dropped (DroppedCandidate), pre (CorpusPreflight), prov
// (GenerationProvenance), analysis, issue, suggestion, evidence, resolution, info (health).
"use strict";

// Labels for the backend's own codes (answer_generation, models.VerificationStatus).
const OUTCOMES = {
  answer: { tone: "ok", title: "Answer",
    text: "Every issue is addressed by statements quoted from the evidence." },
  answer_limited: { tone: "warn", title: "Partial answer",
    text: "Only part of the question is addressed by the evidence. See what could not be established." },
  abstain: { tone: "stop", title: "No answer",
    text: "The system abstained rather than answer without sufficient evidence." },
};
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
  updateCounter();
  updateStatus();
  const names = Object.values(info.instruments);
  $("#corpus").textContent = names.length ? `Corpus: ${names.join(" · ")}.` : "";
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
      showError(message);
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

function showError(message) {
  $("#state").replaceChildren(el("div", { class: "banner stop", role: "alert" },
    el("h2", {}, "Something went wrong"), el("p", { class: "detail" }, message)));
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

// --- Rendering ----------------------------------------------------------------------------------

function renderResult(result) {
  const statusById = result.source_status || {};
  const evidenceItems = result.evidence ? result.evidence.items : [];
  const itemById = Object.fromEntries(evidenceItems.map((item) => [item.evidence_id, item]));
  const issues = result.analysis ? result.analysis.issues : [];
  const issueText = Object.fromEntries(issues.map((issue) => [issue.id, issue.question]));
  const sections = [renderOutcome(result)];

  if (result.claims.length) {
    sections.push(card("Answer", el("div", { class: "answer" },
      result.claims.map((claim) => renderStatement(claim, statusById)))));
    sections.push(card("Supporting quotations", result.claims.map((claim) => renderClaim(claim, statusById, itemById))));
  }
  const gaps = renderGaps(result, issueText);
  if (gaps) sections.push(gaps);
  sections.push(renderCaveats(result));
  if (result.citations.length) {
    sections.push(card("Sources", el("p", { class: "muted" }, "The provisions the answer rests on, with what is known about each source."),
      result.citations.map((ref) => renderSource(ref, itemById[ref.evidence_id], statusById[ref.evidence_id]))));
  }
  sections.push(renderTransparency(result, statusById));
  $("#result").replaceChildren(...sections.filter(Boolean));
  $("#result").hidden = false;
  $("#reset").hidden = false;
  $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderOutcome(result) {
  const outcome = OUTCOMES[result.outcome] || { tone: "warn", title: result.outcome, text: "" };
  const research = result.mode === "research";
  const banner = el("div", { class: `banner ${outcome.tone}` },
    el("h2", {}, outcome.title, badge(research ? "warn" : "ok", MODE_LABELS[result.mode] || result.mode)),
    el("p", {}, outcome.text));
  if (research && result.citations.some((ref) => !ref.citable)) {
    banner.append(el("p", { class: "detail" },
      "This answer rests on sources pending human review. They are marked below and are not verified."));
  }
  if (result.outcome === "abstain") {
    banner.append(el("p", {}, el("strong", {}, explain(ABSTENTIONS, result.abstention_reason))));
    if (result.abstention_detail) banner.append(el("p", { class: "detail" }, result.abstention_detail));
    const analysis = result.analysis;
    if (analysis && analysis.clarification_question) {
      banner.append(el("p", { class: "detail" }, `Clarification needed: ${analysis.clarification_question}`));
    }
  }
  return banner;
}

function citeLink(evidenceId, status) {
  const unreviewed = pending(status);
  return el("a", { class: `cite ${unreviewed ? "unreviewed" : ""}`, href: `#source-${evidenceId}`,
    title: unreviewed ? "Source pending human review" : "Source" },
  evidenceId, unreviewed ? "· unreviewed" : null);
}

function renderStatement(claim, statusById) {
  return el("p", { class: "statement" },
    claim.kind === "inference" ? el("span", { class: "kind-tag" }, "Interpretation") : null,
    claim.text, " ",
    claim.evidence_ids.map((evidenceId) => citeLink(evidenceId, statusById[evidenceId])));
}

function renderClaim(claim, statusById, itemById) {
  const [tone, label] = VERIFICATION[claim.verification] || ["", claim.verification];
  return el("article", { class: "claim" },
    el("p", { class: "claim-text" }, claim.text),
    el("div", { class: "meta" },
      badge("", claim.claim_id), badge(claim.kind === "inference" ? "warn" : "", KINDS[claim.kind] || claim.kind),
      badge(tone, label), claim.issue_ids.length ? badge("", `Issue ${claim.issue_ids.join(", ")}`) : null),
    claim.quotes.map((quote) => {
      const status = statusById[quote.evidence_id];
      const item = itemById[quote.evidence_id];
      return el("blockquote", { class: pending(status) ? "unreviewed" : "" },
        `«${quote.text}» `, citeLink(quote.evidence_id, status),
        item ? el("span", { class: "muted" }, ` ${item.heading}`) : null);
    }));
}

function renderGaps(result, issueText) {
  const parts = [];
  if (result.unanswered_issues.length) {
    parts.push(list(result.unanswered_issues, (gap) =>
      [el("strong", {}, gap.issue_id), issueText[gap.issue_id] ? ` ${issueText[gap.issue_id]} — ` : " — ", gap.reason]));
  }
  if (result.model_notes.length) {
    parts.push(el("p", { class: "subhead" }, info.model_notes_label), list(result.model_notes, (note) => note));
  }
  if (result.rejected_claims.length) {
    parts.push(el("p", { class: "muted" },
      `${result.rejected_claims.length} statement(s) proposed by the model were removed by the checks; ` +
      "see Research transparency."));
  }
  return parts.length ? card("What could not be established", parts) : null;
}

function renderCaveats(result) {
  return card("Caveats and limitations",
    list(result.qualifications, (text) => (text.startsWith("RESEARCH DEMO MODE")
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
  const title = `${ref.evidence_id} · ${ref.heading}${ref.title ? ` — ${ref.title}` : ""}`;
  const node = el("article", { class: `source ${pending(status) ? "unreviewed" : ""}`, id: `source-${ref.evidence_id}` },
    el("p", { class: "source-title" }, title),
    renderStatus(status),
    el("dl", { class: "kv" },
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

// --- Research transparency ----------------------------------------------------------------------

function table(head, rows) {
  return el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, head.map((h) => el("th", {}, h)))),
    el("tbody", {}, rows.map((row) => el("tr", {}, row.map((cell) => el("td", {}, cell)))))));
}

function renderTransparency(result, statusById) {
  const blocks = [];
  const execution = [el("dt", {}, "Mode"), el("dd", {}, MODE_LABELS[result.mode] || result.mode)];
  for (const [name, prov] of [["Generation", result.generation], ["Support check", result.verification]]) {
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
  return el("section", { class: "card" }, el("details", {},
    el("summary", {}, "Research transparency: retrieval, exclusions, execution"), blocks));
}

// --- Wiring -------------------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
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
