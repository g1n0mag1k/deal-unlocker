#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
answer_engine.py
================

The Answer Library Engine — Deal Unlocker's core automation.

Takes an incoming client security questionnaire (any CSV with a column of
question text — extracted from a SIG Lite, CAIQ, or custom PDF/Excel
questionnaire) and fuzzy-matches each question against
answer-library/answer_library_master.csv, producing a draft answer sheet:
the matched canonical answer, with client-specific {{PLACEHOLDER}} values
filled in from a client config file, a confidence score, and a clear flag
for anything that needs a human to actually look at it before it goes out
the door.

This does NOT auto-submit anything. Every answer_sheet.csv row still needs
a human pass per the engagement's own guardrail ("client approves every
questionnaire answer before submission") — this script exists to make that
human pass fast (reviewing and tweaking 80-150 pre-drafted answers) instead
of slow (writing 80-150 answers from scratch under a 72-hour clock).

=============================================================================
HOW MATCHING WORKS
=============================================================================
For each incoming question, every library row is scored on:

  1. Text similarity (difflib) against the row's canonical_question AND
     each of its question_variants — the best of these counts.
  2. Keyword overlap — how many of the row's comma-separated keywords
     appear as substrings in the incoming question text. This catches
     cases where the incoming question is phrased very differently from
     the canonical question/variants but uses the same domain vocabulary
     (e.g. "What's your approach to least-privilege access?" vs. the
     library's canonical "Is access to production systems granted based
     on least privilege / role-based access control (RBAC)?").

The final score is a weighted blend (SIMILARITY_WEIGHT / KEYWORD_WEIGHT,
tunable via CLI flags). Matches are bucketed:

  - HIGH   (>= --high-threshold, default 0.55): auto-filled, still flagged
            "review before sending" like everything else, but the engine's
            own confidence is high.
  - MEDIUM (>= --medium-threshold, default 0.32): best-guess match filled
            in, flagged NEEDS_REVIEW — treat as a draft, not an answer.
  - NONE   (below medium threshold): no confident match. The row is left
            blank with flag NO_MATCH_MANUAL_ANSWER_REQUIRED, and the
            question is listed in the run summary as a candidate to add to
            the library once it's been answered for the first time.

  Scores are an IDF-weighted Dice coefficient over stemmed tokens, not a
  0-100% "confidence" in the statistical sense — thresholds above were
  tuned empirically against a 25-question realistic sample, not derived
  analytically, and deliberately favor precision over recall: a real but
  low-scoring match (e.g. the right library row phrased very differently)
  is more likely to fall to NO_MATCH than to be mis-surfaced as a wrong
  high-confidence draft. A human writing one more answer from scratch is a
  cheaper mistake than a human approving the wrong drafted one.

An optional --framework filter (SIG Lite / CAIQ / Custom) restricts
matching to library rows tagged for that framework, which improves
precision when you know which questionnaire type you're working.

=============================================================================
CLIENT CONFIG / PLACEHOLDER SUBSTITUTION
=============================================================================
Library answer_template strings contain {{PLACEHOLDER}} tokens (e.g.
{{COMPANY}}, {{ASSET_INVENTORY_DOC}}, {{FREQUENCY}}). Pass a JSON file via
--client-config mapping placeholder names to values for a specific client
engagement; this script substitutes every placeholder it has a value for
and leaves the rest as-is but flags the row so a human knows exactly what
still needs filling in by hand (rather than silently shipping literal
"{{ASSET_INVENTORY_DOC}}" text in a sent answer sheet).

=============================================================================
USAGE
=============================================================================
  python3 answer_engine.py \\
      --questionnaire incoming_questions.csv --question-column question \\
      --library ../answer-library/answer_library_master.csv \\
      --client-config client_config_clearpath.json \\
      --framework "SIG Lite" \\
      --output clearpath_answer_sheet.csv
"""

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_/,.\s-]+?)\}\}")
PUNCT_RE = re.compile(r"[^a-z0-9\s]")

DEFAULT_SIMILARITY_WEIGHT = 0.55
DEFAULT_KEYWORD_WEIGHT = 0.45
DEFAULT_HIGH_THRESHOLD = 0.55
DEFAULT_MEDIUM_THRESHOLD = 0.32

# Common words stripped before token-overlap scoring. Short on purpose —
# this is a precision/recall tuning point, not an attempt at real NLP.
# Compliance-domain words that happen to be common English words (e.g.
# "access", "data", "policy") are deliberately NOT in this list, since they
# carry real signal here even though a general-purpose stopword list would
# usually keep them.
STOPWORDS = {
    "the", "a", "an", "is", "are", "do", "does", "did", "you", "your",
    "of", "to", "for", "and", "or", "in", "on", "at", "by", "with", "as",
    "it", "its", "this", "that", "if", "any", "all", "be", "have", "has",
    "had", "was", "were", "will", "would", "can", "could", "should",
    "please", "describe", "what", "how", "when", "where", "who", "which",
    "there", "being", "into", "from", "about", "such", "etc", "e", "g",
    "while", "only", "anyone", "within", "upon", "per",
}


def normalize(s: str) -> str:
    """Lowercase, collapse whitespace, and turn punctuation (hyphens,
    slashes, parens, commas) into spaces so that e.g. "least-privilege"
    and "least privilege" compare equal. This matters a lot: without it,
    keyword substring checks silently fail on any hyphenated phrase."""
    s = s.lower()
    s = PUNCT_RE.sub(" ", s)
    return " ".join(s.split())


# Small hand-maintained equivalence map for word pairs the suffix-stripping
# stemmer can't unify on its own (different root spellings for the same
# concept — "revoke"/"revoking" vs "revocation", not a simple suffix).
# Add to this as real engagements surface more missed matches; it's a
# tuning knob, not meant to be exhaustive.
STEM_EQUIVALENTS = {
    "revok": "revoke", "revocat": "revoke",
    "lockout": "lock",
    "notif": "notify", "notificat": "notify",
    "authoriz": "authorize", "authoris": "authorize",
    "terminat": "terminate",
    "assessment": "assess", "assesst": "assess",
    "recertif": "recertify", "recertificat": "recertify",
    "disclos": "disclose", "disclosure": "disclose",
}


def stem(word: str) -> str:
    """Crude suffix-stripping stemmer — not linguistically rigorous, but
    enough to collapse common compliance-vocabulary variants (encrypt /
    encrypted / encryption, monitor / monitored / monitoring, access /
    accessing / accessed, database / databases) onto the same token so
    token-overlap scoring isn't defeated by ordinary verb/plural forms.
    Order matters: sibilant plurals (churches, breaches) before the
    generic single-s plural (databases -> database, not "databas"),
    then verb-form suffixes, then the manual equivalence map for pairs
    no suffix rule can unify."""
    if len(word) > 5 and word.endswith(("ches", "shes", "xes", "zes")):
        word = word[:-2]
    elif len(word) > 6 and word.endswith("sses"):
        word = word[:-2]
    elif len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]

    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 5 and word.endswith("ion"):
        word = word[:-3]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]

    return STEM_EQUIVALENTS.get(word, word)


def tokenize(s: str) -> set:
    return {stem(w) for w in normalize(s).split() if w not in STOPWORDS and len(w) > 1}


def build_idf(library: list):
    """
    Computes an inverse-document-frequency weight per stemmed token across
    the library, so that generic words appearing in dozens of questions
    ("access", "process", "system", "policy") count for much less than
    distinctive words appearing in only a handful ("offboard", "break",
    "glass", "encrypt"). Without this, two questions that share only
    common words can out-score a question that shares the one or two words
    that actually identify the right control — which is exactly the
    failure mode plain bag-of-words matching falls into on a compliance
    questionnaire, where most sentences share heavy scaffolding ("Does the
    organization maintain a documented process for...").

    Returns (idf, default_idf). `default_idf` is used for any token not
    seen in the library at all (treated as maximally rare/distinctive,
    which is the safe assumption for an out-of-vocabulary word).
    """
    df = {}
    n = len(library)
    for row in library:
        doc_tokens = set(tokenize(row["canonical_question"]))
        for v in row["_variants"]:
            doc_tokens |= tokenize(v)
        for t in doc_tokens:
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    default_idf = math.log(n + 1) + 1.0
    return idf, default_idf


def token_overlap_score(a_tokens: set, b_tokens: set, idf: dict, default_idf: float) -> float:
    """IDF-weighted Dice coefficient: 2*w(A∩B) / (w(A) + w(B)), where w(S)
    sums each token's idf weight. Falls back gracefully to an unweighted
    Dice coefficient if idf is empty (e.g. a caller not using build_idf)."""
    if not a_tokens or not b_tokens:
        return 0.0
    if not idf:
        return 2 * len(a_tokens & b_tokens) / (len(a_tokens) + len(b_tokens))
    w = lambda tokens: sum(idf.get(t, default_idf) for t in tokens)
    inter_w = w(a_tokens & b_tokens)
    denom = w(a_tokens) + w(b_tokens)
    return 2 * inter_w / denom if denom else 0.0


def load_library(path: Path, framework_filter: str = None):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if framework_filter:
                frameworks = [f.strip() for f in row.get("frameworks", "").split(",")]
                if framework_filter not in frameworks:
                    continue
            row["_variants"] = [v.strip() for v in row.get("question_variants", "").split("|") if v.strip()]
            row["_keywords"] = [k.strip().lower() for k in row.get("keywords", "").split(",") if k.strip()]
            rows.append(row)
    return rows


def load_client_config(path: Path):
    if path is None:
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def best_text_score(incoming_tokens: set, row: dict, idf: dict, default_idf: float) -> float:
    """Best token-overlap score of the incoming question against this row's
    canonical question OR any of its listed variants (best of all wins)."""
    best = token_overlap_score(incoming_tokens, tokenize(row["canonical_question"]), idf, default_idf)
    for variant in row["_variants"]:
        best = max(best, token_overlap_score(incoming_tokens, tokenize(variant), idf, default_idf))
    return best


def keyword_score(incoming_tokens: set, row: dict, idf: dict, default_idf: float) -> float:
    """IDF-weighted overlap between the incoming question's tokens and the
    UNION of all tokens across this row's keyword phrases. Pooling into one
    set (rather than scoring each keyword phrase separately and averaging)
    avoids a distortion where a row with few, short keyword phrases that
    all happen to share one common word (e.g. "access") scores an inflated
    average just from that one word recurring, while a row with a genuinely
    strong match plus one unrelated keyword gets dragged down by it. IDF
    weighting on top of that means the shared common word still doesn't
    dominate the result the way it would under plain overlap counting."""
    kw_tokens = set()
    for kw in row["_keywords"]:
        kw_tokens |= tokenize(kw)
    if not kw_tokens:
        return 0.0
    return token_overlap_score(incoming_tokens, kw_tokens, idf, default_idf)


def score_row(incoming_tokens: set, row: dict, sim_weight: float, kw_weight: float,
              idf: dict, default_idf: float) -> float:
    sim = best_text_score(incoming_tokens, row, idf, default_idf)
    kw = keyword_score(incoming_tokens, row, idf, default_idf)
    return sim_weight * sim + kw_weight * kw


def match_question(incoming_text: str, library: list, sim_weight: float, kw_weight: float,
                    idf: dict, default_idf: float):
    """Returns (score, row) for the best match, or (0.0, None) if the library is empty."""
    if not library:
        return 0.0, None
    incoming_tokens = tokenize(incoming_text)
    scored = [(score_row(incoming_tokens, row, sim_weight, kw_weight, idf, default_idf), row)
              for row in library]
    scored.sort(key=lambda x: -x[0])
    return scored[0]


def fill_placeholders(template: str, client_config: dict):
    """
    Substitutes every {{PLACEHOLDER}} in `template` with a value from
    `client_config` when present (case-sensitive key match, stripped).
    Returns (filled_text, list_of_unresolved_placeholder_names).
    Handles compound placeholders with inline guidance, e.g.
    {{AND/OR complexity rules}} or {{N, e.g., Okta}} — these are treated as
    always-unresolved free-text notes for the human to write, not simple
    key lookups, since they aren't single config keys.
    """
    unresolved = []

    def replace(m):
        token = m.group(1).strip()
        # A "simple" placeholder is a single UPPER_SNAKE-ish token with no
        # commentary; anything with a space, comma, or lowercase prose is a
        # free-text instruction to the human, not a config lookup key.
        is_simple_key = bool(re.fullmatch(r"[A-Z0-9_]+(/[A-Z0-9_]+)?", token))
        if is_simple_key and token in client_config:
            return str(client_config[token])
        unresolved.append(token)
        return "{{" + token + "}}"

    filled = PLACEHOLDER_RE.sub(replace, template)
    return filled, unresolved


def process_questionnaire(questionnaire_path: Path, question_col: str, id_col: str,
                           library: list, client_config: dict,
                           sim_weight: float, kw_weight: float,
                           high_threshold: float, medium_threshold: float,
                           idf: dict = None, default_idf: float = 0.0):
    if idf is None:
        idf, default_idf = build_idf(library)

    results = []
    no_match_questions = []

    with open(questionnaire_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if question_col not in reader.fieldnames:
            sys.exit(
                f"Column '{question_col}' not found in {questionnaire_path}. "
                f"Available columns: {', '.join(reader.fieldnames)}"
            )
        for i, row in enumerate(reader, 1):
            q_text = (row.get(question_col) or "").strip()
            if not q_text:
                continue
            q_id = (row.get(id_col) or f"Q{i:03d}") if id_col else f"Q{i:03d}"

            score, match = match_question(q_text, library, sim_weight, kw_weight, idf, default_idf)

            if match is None or score < medium_threshold:
                no_match_questions.append(q_text)
                results.append({
                    "question_id": q_id,
                    "incoming_question": q_text,
                    "match_status": "NO_MATCH_MANUAL_ANSWER_REQUIRED",
                    "confidence": f"{score * 100:.0f}%",
                    "matched_library_id": "",
                    "domain": "",
                    "default_answer": "",
                    "draft_answer": "",
                    "unresolved_placeholders": "",
                    "artifact_type": "",
                    "verification_guidance": "No library match above the medium-confidence threshold. "
                                              "Answer this manually, then consider adding it to "
                                              "answer_library_master.csv for future reuse.",
                })
                continue

            status = "HIGH_CONFIDENCE" if score >= high_threshold else "NEEDS_REVIEW_MEDIUM_CONFIDENCE"
            filled, unresolved = fill_placeholders(match["answer_template"], client_config)

            results.append({
                "question_id": q_id,
                "incoming_question": q_text,
                "match_status": status,
                "confidence": f"{score * 100:.0f}%",
                "matched_library_id": match["id"],
                "domain": match["domain"],
                "default_answer": match["default_answer"],
                "draft_answer": filled,
                "unresolved_placeholders": "; ".join(unresolved),
                "artifact_type": match["artifact_type"],
                "verification_guidance": match["verification_guidance"],
            })

    return results, no_match_questions


def write_output(results: list, output_path: Path):
    fields = ["question_id", "incoming_question", "match_status", "confidence",
              "matched_library_id", "domain", "default_answer", "draft_answer",
              "unresolved_placeholders", "artifact_type", "verification_guidance"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in results:
            w.writerow(r)


def print_summary(results: list, no_match_questions: list):
    total = len(results)
    high = sum(1 for r in results if r["match_status"] == "HIGH_CONFIDENCE")
    medium = sum(1 for r in results if r["match_status"] == "NEEDS_REVIEW_MEDIUM_CONFIDENCE")
    no_match = len(no_match_questions)
    unresolved_ph = sum(1 for r in results if r["unresolved_placeholders"])

    print("\n=== Answer Engine Summary ===")
    print(f"Total questions processed  : {total}")
    print(f"  High confidence match    : {high}")
    print(f"  Medium confidence (review): {medium}")
    print(f"  No match (manual answer) : {no_match}")
    print(f"Rows with unresolved {{{{placeholders}}}} needing manual completion: {unresolved_ph}")

    if no_match_questions:
        print(f"\nQuestions with no library match ({len(no_match_questions)}):")
        for q in no_match_questions[:20]:
            print(f"  - {q}")
        if len(no_match_questions) > 20:
            print(f"  ... and {len(no_match_questions) - 20} more (see output CSV)")

    if total:
        pct_actionable = (high + medium) / total * 100
        print(f"\n{pct_actionable:.0f}% of questions got a draft answer from the library "
              f"(before human review). The remaining {100 - pct_actionable:.0f}% need a "
              f"first-time manual answer.")


def main():
    parser = argparse.ArgumentParser(
        description="Fuzzy-match an incoming client questionnaire against answer_library_master.csv "
                    "to produce a draft answer sheet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--questionnaire", required=True,
                         help="CSV of incoming questions (one row per question).")
    parser.add_argument("--question-column", default="question",
                         help="Column name in --questionnaire containing question text (default: 'question').")
    parser.add_argument("--id-column", default=None,
                         help="Optional column with a question ID/number to preserve in the output.")
    parser.add_argument("--library", default="answer_library_master.csv",
                         help="Path to the master answer library CSV.")
    parser.add_argument("--client-config", default=None,
                         help="Optional JSON file mapping {{PLACEHOLDER}} names to client-specific values.")
    parser.add_argument("--framework", default=None, choices=["SIG Lite", "CAIQ", "Custom"],
                         help="Restrict matching to library rows tagged for this framework (improves precision).")
    parser.add_argument("--output", default="answer_sheet.csv",
                         help="Output CSV path.")
    parser.add_argument("--sim-weight", type=float, default=DEFAULT_SIMILARITY_WEIGHT,
                         help=f"Weight for text-similarity score (default {DEFAULT_SIMILARITY_WEIGHT}).")
    parser.add_argument("--kw-weight", type=float, default=DEFAULT_KEYWORD_WEIGHT,
                         help=f"Weight for keyword-overlap score (default {DEFAULT_KEYWORD_WEIGHT}).")
    parser.add_argument("--high-threshold", type=float, default=DEFAULT_HIGH_THRESHOLD,
                         help=f"Score at/above which a match is HIGH_CONFIDENCE (default {DEFAULT_HIGH_THRESHOLD}).")
    parser.add_argument("--medium-threshold", type=float, default=DEFAULT_MEDIUM_THRESHOLD,
                         help=f"Score at/above which a match is kept at all, below HIGH (default {DEFAULT_MEDIUM_THRESHOLD}).")
    args = parser.parse_args()

    questionnaire_path = Path(args.questionnaire)
    if not questionnaire_path.exists():
        sys.exit(f"Questionnaire file not found: {questionnaire_path}")

    library_path = Path(args.library)
    if not library_path.exists():
        sys.exit(f"Library file not found: {library_path}")

    client_config_path = Path(args.client_config) if args.client_config else None
    if client_config_path and not client_config_path.exists():
        sys.exit(f"Client config file not found: {client_config_path}")

    library = load_library(library_path, framework_filter=args.framework)
    print(f"Loaded {len(library)} library row(s)"
          f"{f' (filtered to framework={args.framework!r})' if args.framework else ''} from {library_path}")

    client_config = load_client_config(client_config_path)
    if client_config:
        print(f"Loaded {len(client_config)} client config value(s) from {client_config_path}")

    results, no_match_questions = process_questionnaire(
        questionnaire_path, args.question_column, args.id_column,
        library, client_config,
        args.sim_weight, args.kw_weight,
        args.high_threshold, args.medium_threshold,
    )

    output_path = Path(args.output)
    write_output(results, output_path)
    print(f"\nWrote {output_path} ({len(results)} rows)")

    print_summary(results, no_match_questions)

    print(
        "\nReminder: every row here is a DRAFT. Per engagement guardrails, the client approves "
        "every questionnaire answer before submission — this output speeds up the human review "
        "pass, it does not replace it."
    )


if __name__ == "__main__":
    main()
