#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_deliverable.py
=====================

Deal Unlocker — Standalone Reusable Gap Register / Reviewer Brief Generator
Sui-Generis LLC

Produces the client-facing deliverable: a single print-ready HTML document
combining the Reviewer Brief (one-pager summary), the full Answer Set, and
the Gap Register. This is the same design built for the ClearPath Health
sample (samples/clearpath-health/), decoupled from ClearPath's hardcoded
content so it can be driven by real per-client data instead of edited by
hand for every engagement.

Packaging note: the product spec lists the Reviewer Brief as a distinct
deliverable from the Gap Register. In practice they ship as one document —
the Brief is the one-pager the enterprise buyer's security reviewer reads
first, with the full Answer Set and Gap Register as the backing detail in
the same file they can keep scrolling into. That's what this script
produces. If a client engagement specifically needs the Brief split out as
its own standalone page, pass --brief-only to emit just that section.

=============================================================================
PIPELINE
=============================================================================
1. (Optional) Run engine/answer_engine.py against the incoming questionnaire
   to get a draft answer_sheet.csv.
2. Human review pass (REQUIRED per engagement guardrail — the client
   approves every answer before submission): open the draft in a
   spreadsheet, confirm or correct each answer, and fill in the few extra
   columns this script needs (see INPUT CSV below). Save as a plain CSV.
3. Run this script against the reviewed CSV + a client config JSON to
   produce the final polished HTML.

=============================================================================
INPUT CSV
=============================================================================
One row per question. Column names are flexible — this script accepts
either a hand-built CSV or the engine's answer_sheet.csv extended with a
few review columns, matched in this priority order per field:

  id              : "id" | "question_id"                      (optional — auto-numbered if absent)
  domain          : "domain"                                   (required)
  question        : "question" | "incoming_question"           (required)
  answer          : "answer" | "final_answer"                  (required — "Y" or "N")
  note            : "note" | "final_note" | "draft_answer"      (required — citation if Y, finding if N)
  priority        : "priority"                                 (required if answer is "N" — High/Medium/Low)
  target_days     : "target_days"                               (required if answer is "N" — integer days
                                                                   from --prepared-date to the remediation
                                                                   target date)
  artifact_required : "artifact_required"                      (optional — defaults to
                                                                   "Remediation Evidence (TBD)")

Domains are grouped and ordered by first appearance in the CSV — there is
no hardcoded domain list, so this works for SIG Lite, CAIQ, or a fully
custom questionnaire without code changes.

=============================================================================
CLIENT CONFIG (JSON)
=============================================================================
See client_config_example.json for a filled-in example. Fields:

  company_name        (required) e.g. "ClearPath Health, Inc."
  company_blurb        (required) one or two sentences for the Brief's "Company" field
  product_scope         (required) one or two sentences for the Brief's "Product in scope" field
  questionnaire_type    (required) "SIG Lite" | "CAIQ" | "Custom"
  posture_summary        (required) one or two sentences for the Brief's overall posture summary
  buyer_label             (optional, default "Enterprise Buyer Security Review Team")
  prepared_date            (optional, default: today, ISO format YYYY-MM-DD)
  priority_callout          (optional) override the auto-generated "fastest-closing high-priority
                              items" line in the Brief. If omitted, this script generates it from
                              the highest-priority gaps sorted by target date.
  is_sample                  (optional, default false) — true adds the "SAMPLE — FICTIONAL DATA"
                              watermark and footer language. ALWAYS false for a real client
                              engagement; this flag exists so this same script also builds
                              fictional sales-asset samples like ClearPath Health.
  firm_name                   (optional, default "Sui-Generis LLC")
  firm_location                 (optional, default "Knoxville, TN")
  id_prefix                      (optional, default "Q") — short prefix for auto-numbered
                                   question IDs, e.g. "SIG" -> "SIG-01".

=============================================================================
USAGE
=============================================================================
  python3 build_deliverable.py \\
      --questions reviewed_answers.csv \\
      --client-config client_config.json \\
      --output deliverable.html

  python3 build_deliverable.py --questions sample_questions.csv \\
      --client-config sample_client_config.json --output /tmp/demo.html
"""

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path

PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}
PRIORITY_ALIASES = {"high": "High", "medium": "Medium", "med": "Medium", "low": "Low"}


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def _first_present(row: dict, *keys):
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


def load_questions(path: Path):
    """
    Loads and validates the reviewed-answers CSV into a normalized list of
    dicts: id, domain, question, answer ("Y"/"N"), note, priority
    (None for "Y" rows), target_days (int, None for "Y" rows),
    artifact_required. Raises SystemExit with a clear row-level error
    message on anything malformed — this feeds a client-facing document,
    so fail loudly rather than silently guess.
    """
    questions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            question = _first_present(row, "question", "incoming_question")
            if not question:
                sys.exit(f"Row {i}: missing required 'question' (or 'incoming_question') value.")

            domain = _first_present(row, "domain")
            if not domain:
                sys.exit(f"Row {i} ({question[:60]!r}): missing required 'domain' value.")

            answer_raw = _first_present(row, "answer", "final_answer")
            if not answer_raw or answer_raw.strip().upper() not in ("Y", "N"):
                sys.exit(
                    f"Row {i} ({question[:60]!r}): 'answer' (or 'final_answer') must be "
                    f"'Y' or 'N', got {answer_raw!r}. Every row needs a human-confirmed "
                    f"determination — this script does not infer Yes/No from draft text."
                )
            answer = answer_raw.strip().upper()

            note = _first_present(row, "note", "final_note", "draft_answer")
            if not note:
                sys.exit(f"Row {i} ({question[:60]!r}): missing required 'note' (citation or finding) value.")

            priority = None
            target_days = None
            artifact_required = None
            if answer == "N":
                priority_raw = _first_present(row, "priority")
                if not priority_raw or priority_raw.strip().lower() not in PRIORITY_ALIASES:
                    sys.exit(
                        f"Row {i} ({question[:60]!r}): answer is 'N', so 'priority' is required "
                        f"and must be High/Medium/Low, got {priority_raw!r}."
                    )
                priority = PRIORITY_ALIASES[priority_raw.strip().lower()]

                target_days_raw = _first_present(row, "target_days")
                if target_days_raw is None:
                    sys.exit(f"Row {i} ({question[:60]!r}): answer is 'N', so 'target_days' is required.")
                try:
                    target_days = int(target_days_raw)
                except ValueError:
                    sys.exit(f"Row {i} ({question[:60]!r}): 'target_days' must be an integer, got {target_days_raw!r}.")

                artifact_required = _first_present(row, "artifact_required") or "Remediation Evidence (TBD)"

            qid = _first_present(row, "id", "question_id")
            questions.append({
                "id": qid,  # filled in by assign_ids() if None
                "domain": domain,
                "question": question,
                "answer": answer,
                "note": note,
                "priority": priority,
                "target_days": target_days,
                "artifact_required": artifact_required,
            })

    if not questions:
        sys.exit(f"No rows found in {path}.")
    return questions


def assign_ids(questions, prefix="Q"):
    for i, q in enumerate(questions, 1):
        if not q["id"]:
            q["id"] = f"{prefix}-{i:02d}"
    return questions


# ---------------------------------------------------------------------------
# Client config
# ---------------------------------------------------------------------------

REQUIRED_CONFIG_FIELDS = [
    "company_name", "company_blurb", "product_scope",
    "questionnaire_type", "posture_summary",
]


def load_config(path: Path):
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    missing = [f for f in REQUIRED_CONFIG_FIELDS if not config.get(f)]
    if missing:
        sys.exit(f"Client config {path} is missing required field(s): {', '.join(missing)}")

    config.setdefault("buyer_label", "Enterprise Buyer Security Review Team")
    config.setdefault("is_sample", False)
    config.setdefault("firm_name", "Sui-Generis LLC")
    config.setdefault("firm_location", "Knoxville, TN")
    config.setdefault("id_prefix", "Q")
    config.setdefault("priority_callout", None)

    if config.get("prepared_date"):
        try:
            config["_prepared_date"] = datetime.date.fromisoformat(config["prepared_date"])
        except ValueError:
            sys.exit(f"client config 'prepared_date' must be YYYY-MM-DD, got {config['prepared_date']!r}")
    else:
        config["_prepared_date"] = datetime.date.today()

    return config


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dplus(prepared_date, days):
    return (prepared_date + datetime.timedelta(days=days)).strftime("%B %-d, %Y")


def pill(ans):
    return '<span class="pill pill-yes">YES</span>' if ans == "Y" else '<span class="pill pill-no">NO</span>'


def priority_pill(p):
    cls = {"High": "pr-high", "Medium": "pr-med", "Low": "pr-low"}[p]
    return f'<span class="pr-pill {cls}">{p}</span>'


def domain_anchor(d):
    return "dom-" + d.lower().replace(" ", "-").replace("/", "-")


def ordered_domains(questions):
    """Domains in order of first appearance in the input — no hardcoded list."""
    seen = []
    for q in questions:
        if q["domain"] not in seen:
            seen.append(q["domain"])
    return seen


def auto_priority_callout(gaps, prepared_date, max_items=5):
    high_gaps = [g for g in gaps if g["priority"] == "High"]
    if not high_gaps:
        return "No high-priority gaps were identified in this response."
    high_gaps_sorted = sorted(high_gaps, key=lambda g: g["target_days"])[:max_items]
    items = ", ".join(
        f"{g['artifact_required']} ({dplus(prepared_date, g['target_days'])})"
        for g in high_gaps_sorted
    )
    return f"Fastest-closing high-priority items: {items}. Full remediation timeline and artifact requirements follow in the Gap Register below."


def build_qa_sections(questions, domains, prepared_date):
    rows_by_domain = {}
    for q in questions:
        rows_by_domain.setdefault(q["domain"], []).append(q)

    sections = []
    for d in domains:
        items = rows_by_domain[d]
        gap_n = sum(1 for q in items if q["answer"] == "N")
        tot_n = len(items)
        rows_html = []
        for q in items:
            if q["answer"] == "Y":
                note_html = f'<span class="citation">{esc(q["note"])}</span>'
            else:
                note_html = (
                    f'<span class="finding">{esc(q["note"])}</span> '
                    f'<span class="see-gap">— see Gap Register, target {dplus(prepared_date, q["target_days"])}</span>'
                )
            rows_html.append(f"""
        <tr>
          <td class="qid">{esc(q['id'])}</td>
          <td class="qtext">{esc(q['question'])}</td>
          <td class="qans">{pill(q['answer'])}</td>
          <td class="qnote">{note_html}</td>
        </tr>""")
        sections.append(f"""
    <section class="domain-section" id="{domain_anchor(d)}">
      <h3>{esc(d)} <span class="domain-tally">{tot_n - gap_n}/{tot_n} satisfied</span></h3>
      <table class="qa-table">
        <thead>
          <tr><th class="col-id">ID</th><th class="col-q">Question</th><th class="col-ans">Answer</th><th class="col-note">Artifact / Finding</th></tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </section>""")
    return "\n".join(sections)


def build_gap_register(gaps, domains, prepared_date):
    gaps_sorted = sorted(gaps, key=lambda g: (PRIORITY_RANK[g["priority"]], domains.index(g["domain"])))
    rows = []
    for g in gaps_sorted:
        rows.append(f"""
        <tr>
          <td>{priority_pill(g['priority'])}</td>
          <td class="gap-domain">{esc(g['domain'])}</td>
          <td class="gap-control">{esc(g['question'])}</td>
          <td class="gap-finding">{esc(g['note'])}</td>
          <td class="gap-date">{dplus(prepared_date, g['target_days'])}</td>
          <td class="gap-artifact">{esc(g['artifact_required'])}</td>
        </tr>""")
    return "\n".join(rows)


CSS = """
  :root {
    --navy: #0f2a4a; --navy-light: #1d4273; --accent: #1a73a3; --accent-light: #e8f1f6;
    --ink: #1c242e; --muted: #5b6672; --border: #d7dde3; --bg-soft: #f6f8fa;
    --yes: #1b7a43; --yes-bg: #e5f5ea; --no: #b23b2e; --no-bg: #fbeae7;
    --high: #b23b2e; --high-bg: #fbeae7; --med: #a4700a; --med-bg: #fbf1de;
    --low: #4c5a68; --low-bg: #eef1f4;
  }
  * { box-sizing: border-box; }
  body {
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    color: var(--ink); margin: 0; background: #fff; font-size: 13.5px; line-height: 1.5;
  }
  .page { max-width: 980px; margin: 0 auto; padding: 40px 48px 64px; }
  .masthead {
    display: flex; justify-content: space-between; align-items: flex-start;
    border-bottom: 3px solid var(--navy); padding-bottom: 18px; margin-bottom: 28px;
  }
  .masthead h1 { font-size: 22px; margin: 0 0 4px; color: var(--navy); letter-spacing: -0.2px; }
  .masthead .sub { color: var(--muted); font-size: 13px; }
  .masthead .meta { text-align: right; font-size: 12px; color: var(--muted); line-height: 1.7; }
  .masthead .meta strong { color: var(--ink); }
  .doc-tag {
    display: inline-block; background: var(--navy); color: #fff; font-size: 10.5px;
    font-weight: 600; letter-spacing: 0.06em; padding: 3px 9px; border-radius: 3px;
    text-transform: uppercase; margin-bottom: 8px;
  }
  .brief {
    background: var(--bg-soft); border: 1px solid var(--border); border-left: 5px solid var(--navy);
    border-radius: 6px; padding: 22px 26px; margin-bottom: 34px; page-break-inside: avoid;
  }
  .brief h2 { margin: 0 0 14px; font-size: 16.5px; color: var(--navy); }
  .brief-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; margin-bottom: 16px; }
  .brief-grid .label { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 2px; }
  .brief-grid .value { font-size: 13.5px; }
  .stat-row { display: flex; gap: 14px; margin: 14px 0 16px; flex-wrap: wrap; }
  .stat-box { background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 10px 16px; min-width: 108px; text-align: center; }
  .stat-box .num { font-size: 22px; font-weight: 700; color: var(--navy); line-height: 1.1; }
  .stat-box.alert .num { color: var(--high); }
  .stat-box .lbl { font-size: 10.5px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }
  .brief p { margin: 8px 0; }
  .brief .priority-line { font-size: 12.5px; color: var(--muted); }
  .brief .priority-line b { color: var(--ink); }
  .toc { margin-bottom: 30px; }
  .toc h3 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 8px; }
  .toc ul { list-style: none; margin: 0; padding: 0; columns: 2; column-gap: 32px; }
  .toc li { margin-bottom: 6px; break-inside: avoid; }
  .toc a { color: var(--accent); text-decoration: none; font-size: 12.5px; }
  .toc-count { color: var(--muted); font-size: 11px; }
  h2.section-title {
    font-size: 16px; color: var(--navy); border-bottom: 2px solid var(--border);
    padding-bottom: 6px; margin: 38px 0 18px;
  }
  .domain-section { margin-bottom: 26px; page-break-inside: avoid; }
  .domain-section h3 {
    font-size: 13.5px; color: var(--navy-light); background: var(--accent-light);
    padding: 7px 12px; border-radius: 4px; margin: 0 0 8px; display: flex;
    justify-content: space-between; align-items: center;
  }
  .domain-tally { font-size: 11px; font-weight: 500; color: var(--navy); }
  table.qa-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  table.qa-table th {
    text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--muted); border-bottom: 1px solid var(--border); padding: 5px 8px;
  }
  table.qa-table td { padding: 7px 8px; border-bottom: 1px solid #ecf0f3; vertical-align: top; }
  .col-id { width: 7%; } .col-q { width: 40%; } .col-ans { width: 8%; } .col-note { width: 45%; }
  .qid { font-family: "SFMono-Regular", Consolas, monospace; font-size: 10.5px; color: var(--muted); }
  .pill { display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; letter-spacing: 0.03em; }
  .pill-yes { background: var(--yes-bg); color: var(--yes); }
  .pill-no { background: var(--no-bg); color: var(--no); }
  .citation { color: var(--muted); font-style: italic; }
  .finding { color: var(--no); }
  .see-gap { color: var(--muted); font-size: 11px; }
  table.gap-table { width: 100%; border-collapse: collapse; font-size: 11.8px; margin-top: 6px; }
  table.gap-table th {
    text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
    color: #fff; background: var(--navy); padding: 8px; position: sticky; top: 0;
  }
  table.gap-table td { padding: 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
  table.gap-table tr:nth-child(even) td { background: #fafbfc; }
  .gap-control { font-weight: 600; width: 22%; }
  .gap-finding { color: var(--muted); width: 26%; }
  .gap-date { white-space: nowrap; font-weight: 600; color: var(--navy); }
  .gap-domain { color: var(--muted); font-size: 11px; white-space: nowrap; }
  .gap-artifact { width: 20%; }
  .pr-pill { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
  .pr-high { background: var(--high-bg); color: var(--high); }
  .pr-med { background: var(--med-bg); color: var(--med); }
  .pr-low { background: var(--low-bg); color: var(--low); }
  .footer {
    margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border);
    font-size: 10.5px; color: var(--muted); display: flex; justify-content: space-between;
  }
  .sample-watermark {
    position: fixed; top: 46%; left: 50%; transform: translate(-50%,-50%) rotate(-28deg);
    font-size: 86px; font-weight: 800; color: rgba(15,42,74,0.06); z-index: -1;
    letter-spacing: 0.05em; pointer-events: none; white-space: nowrap;
  }
  @media print {
    .page { padding: 0.3in 0.5in; }
    .domain-section { break-inside: avoid; }
    table.gap-table { break-inside: auto; }
    table.gap-table tr { break-inside: avoid; }
    a { color: inherit; text-decoration: none; }
  }
  @page { margin: 0.5in; size: letter; }
"""


def generate_html(questions, config):
    prepared_date = config["_prepared_date"]
    domains = ordered_domains(questions)
    gaps = [q for q in questions if q["answer"] == "N"]
    yes_count = len(questions) - len(gaps)
    high_gaps = [g for g in gaps if g["priority"] == "High"]
    med_gaps = [g for g in gaps if g["priority"] == "Medium"]
    low_gaps = [g for g in gaps if g["priority"] == "Low"]

    domain_totals = {d: sum(1 for q in questions if q["domain"] == d) for d in domains}
    domain_gap_counts = {d: sum(1 for g in gaps if g["domain"] == d) for d in domains}

    qa_html = build_qa_sections(questions, domains, prepared_date)
    gap_register_html = build_gap_register(gaps, domains, prepared_date)
    priority_callout = config.get("priority_callout") or auto_priority_callout(gaps, prepared_date)

    toc_items = "".join(
        f'<li><a href="#{domain_anchor(d)}">{esc(d)} <span class="toc-count">({domain_totals[d]} questions, {domain_gap_counts[d]} open)</span></a></li>'
        for d in domains
    )

    doc_tag = f"{config['questionnaire_type']} Response &amp; Gap Register"
    watermark = '<div class="sample-watermark">SAMPLE — FICTIONAL DATA</div>' if config["is_sample"] else ""
    sample_note = " Fictional sample for demonstration purposes only." if config["is_sample"] else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{esc(config['company_name'])} — {esc(config['questionnaire_type'])} Response &amp; Gap Register</title>
<style>{CSS}</style>
</head>
<body>
{watermark}
<div class="page">

  <div class="masthead">
    <div>
      <div class="doc-tag">{doc_tag}</div>
      <h1>{esc(config['company_name'])}</h1>
      <div class="sub">{esc(config['questionnaire_type'])} &mdash; Security Questionnaire Response</div>
    </div>
    <div class="meta">
      <div><strong>Prepared for:</strong> {esc(config['buyer_label'])}</div>
      <div><strong>Prepared:</strong> {prepared_date.strftime('%B %-d, %Y')}</div>
      <div><strong>Document support:</strong> {esc(config['firm_name'])} &mdash; Deal Unlocker</div>
    </div>
  </div>

  <div class="brief">
    <h2>Reviewer Brief</h2>
    <div class="brief-grid">
      <div>
        <div class="label">Company</div>
        <div class="value">{esc(config['company_blurb'])}</div>
      </div>
      <div>
        <div class="label">Product in scope</div>
        <div class="value">{esc(config['product_scope'])}</div>
      </div>
      <div>
        <div class="label">Questionnaire</div>
        <div class="value">{esc(config['questionnaire_type'])}, {len(questions)} questions, standard domains.</div>
      </div>
      <div>
        <div class="label">Overall posture summary</div>
        <div class="value">{esc(config['posture_summary'])}</div>
      </div>
    </div>
    <div class="stat-row">
      <div class="stat-box"><div class="num">{len(questions)}</div><div class="lbl">Questions</div></div>
      <div class="stat-box"><div class="num">{yes_count}</div><div class="lbl">Satisfied</div></div>
      <div class="stat-box alert"><div class="num">{len(gaps)}</div><div class="lbl">Open gaps</div></div>
      <div class="stat-box alert"><div class="num">{len(high_gaps)}</div><div class="lbl">High priority</div></div>
      <div class="stat-box"><div class="num">{len(med_gaps)}</div><div class="lbl">Medium priority</div></div>
      <div class="stat-box"><div class="num">{len(low_gaps)}</div><div class="lbl">Low priority</div></div>
    </div>
    <p class="priority-line"><b>{esc(priority_callout)}</b></p>
    <p class="priority-line">This brief and the attached answer set are intended to give your security review team a complete, source-cited picture of {esc(config['company_name'])}'s control environment in a single pass, with named artifacts available for follow-up evidence requests. No statement in this document should be read as a legal compliance or certification conclusion.</p>
  </div>

  <div class="toc">
    <h3>Domains in this response</h3>
    <ul>{toc_items}</ul>
  </div>

  <h2 class="section-title">Part 1 &mdash; {esc(config['questionnaire_type'])} Answer Set ({len(questions)} Questions)</h2>
  {qa_html}

  <h2 class="section-title">Part 2 &mdash; Gap Register</h2>
  <p style="color:var(--muted); font-size:12.5px; margin-bottom:14px;">
    Every "No" response above is tracked here as a dated remediation item. Target dates reflect priority:
    High-priority items are scheduled soonest, Medium and Low items further out, measured from the
    date of this assessment ({prepared_date.strftime('%B %-d, %Y')}). This register is the forward plan
    {esc(config['company_name'])}'s accountable owner is responsible for; it is not a representation
    that the organization is "compliant" with any specific regulation or framework.
  </p>
  <table class="gap-table">
    <thead>
      <tr><th style="width:8%">Priority</th><th style="width:11%">Domain</th><th>Control</th><th>Finding</th><th style="width:10%">Target Date</th><th>Artifact Required</th></tr>
    </thead>
    <tbody>
      {gap_register_html}
    </tbody>
  </table>

  <div class="footer">
    <div>{esc(config['company_name'])} &mdash; {esc(config['questionnaire_type'])} Response &amp; Gap Register.{sample_note}</div>
    <div>Prepared with Deal Unlocker by {esc(config['firm_name'])} &mdash; {esc(config['firm_location'])}</div>
  </div>

</div>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build the client-facing Reviewer Brief / Answer Set / Gap Register deliverable "
                    "from a reviewed answers CSV and a client config JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--questions", required=True, help="Reviewed answers CSV (see module docstring for columns).")
    parser.add_argument("--client-config", required=True, help="Client config JSON (see module docstring for fields).")
    parser.add_argument("--output", required=True, help="Output HTML path.")
    args = parser.parse_args()

    questions_path = Path(args.questions)
    if not questions_path.exists():
        sys.exit(f"Questions file not found: {questions_path}")
    config_path = Path(args.client_config)
    if not config_path.exists():
        sys.exit(f"Client config file not found: {config_path}")

    config = load_config(config_path)
    questions = load_questions(questions_path)
    assign_ids(questions, prefix=config["id_prefix"])

    html = generate_html(questions, config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    gaps = sum(1 for q in questions if q["answer"] == "N")
    print(f"Wrote {output_path} — {len(questions)} questions, {gaps} gap(s).")
    if config["is_sample"]:
        print("NOTE: is_sample=true — this build carries the SAMPLE watermark. "
              "Set is_sample=false in the client config for a real engagement deliverable.")


if __name__ == "__main__":
    main()
