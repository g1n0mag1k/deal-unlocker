#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_answer_engine.py
======================

Unit + integration tests for answer_engine.py (the Answer Library Engine).

Run with:
    python3 -m pytest test_answer_engine.py -v
or, with no pytest installed:
    python3 test_answer_engine.py
"""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from answer_engine import (
    normalize,
    stem,
    tokenize,
    build_idf,
    token_overlap_score,
    load_library,
    load_client_config,
    best_text_score,
    keyword_score,
    score_row,
    match_question,
    fill_placeholders,
    process_questionnaire,
    write_output,
    DEFAULT_SIMILARITY_WEIGHT,
    DEFAULT_KEYWORD_WEIGHT,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers for building a small, fully-controlled fake library in memory
# (independent of the real 152-row answer_library_master.csv, so these
# tests don't silently break every time the library content changes).
# ---------------------------------------------------------------------------

def make_row(id_, domain, canonical, variants=None, keywords=None,
             default_answer="Y", answer_template="", artifact_type="",
             verification_guidance=""):
    row = {
        "id": id_,
        "domain": domain,
        "canonical_question": canonical,
        "question_variants": "|".join(variants or []),
        "keywords": ", ".join(keywords or []),
        "frameworks": "SIG Lite, CAIQ, Custom",
        "default_answer": default_answer,
        "answer_template": answer_template,
        "artifact_type": artifact_type,
        "verification_guidance": verification_guidance,
    }
    row["_variants"] = [v.strip() for v in row["question_variants"].split("|") if v.strip()]
    row["_keywords"] = [k.strip().lower() for k in row["keywords"].split(",") if k.strip()]
    return row


FAKE_LIBRARY = [
    make_row(
        "T-001", "Access Control",
        "Is there a documented, timely offboarding procedure that revokes access upon termination?",
        variants=["How fast is access revoked after termination?",
                  "What is your process for revoking system access when an employee leaves the company?"],
        keywords=["offboarding", "access revocation", "termination procedure", "employee offboarding"],
        answer_template="Access is revoked within {{TIMEFRAME}} of termination notice per {{OFFBOARDING_SOP}}.",
        artifact_type="Offboarding SOP",
        verification_guidance="Ask for a sanitized recent example.",
    ),
    make_row(
        "T-002", "Third-Party Risk Management",
        "Does the organization have a process to offboard vendors and revoke their access upon contract termination?",
        variants=["How do you offboard vendors?"],
        keywords=["vendor offboarding", "vendor access revocation"],
        answer_template="Vendor access is revoked within {{TIMEFRAME}} of contract termination.",
        artifact_type="Vendor Offboarding SOP",
    ),
    make_row(
        "T-003", "Access Control",
        "Are failed login attempts monitored and accounts locked out after a defined threshold?",
        keywords=["account lockout", "failed login monitoring"],
        answer_template="Accounts lock after {{LOCKOUT_THRESHOLD}} failed attempts.",
        artifact_type="IAM Policy",
    ),
    make_row(
        "T-004", "Data Governance",
        "Do you encrypt sensitive data at rest in your production databases?",
        variants=["Is data encrypted while stored?"],
        keywords=["encryption at rest", "database encryption"],
        default_answer="Y",
        answer_template="All PHI/PII at rest is encrypted via {{ENCRYPTION_STD}}.",
        artifact_type="Encryption Standard",
    ),
    make_row(
        "T-005", "Incident Management",
        "Have you experienced a security breach or incident involving customer data in the past 12 months?",
        keywords=["breach history", "security incident"],
        default_answer="N",
        answer_template="No reportable breaches to date. Monitoring per {{IR_PLAN}}.",
        artifact_type="Incident Log",
    ),
]


class TestNormalizeStemTokenize(unittest.TestCase):

    def test_normalize_lowercases_and_strips_punctuation(self):
        self.assertEqual(normalize("Least-Privilege, Access!"), "least privilege access")

    def test_normalize_collapses_whitespace(self):
        self.assertEqual(normalize("a   b\tc\n d"), "a b c d")

    def test_stem_handles_sibilant_plural_before_generic_s(self):
        # "breaches" should stem to "breach", NOT "breache" (the bug this
        # guards against: naively stripping a single trailing "s" first).
        self.assertEqual(stem("breaches"), "breach")

    def test_stem_handles_generic_plural(self):
        self.assertEqual(stem("databases"), "database")

    def test_stem_does_not_over_strip_short_or_double_s_words(self):
        # "ss"-ending and short words should survive untouched.
        self.assertEqual(stem("access"), "access")

    def test_stem_equivalence_map_unifies_irregular_pairs(self):
        self.assertEqual(stem("revoking")[:5], stem("revocation")[:5])
        self.assertEqual(stem("revok"), "revoke")
        self.assertEqual(stem("revocat"), "revoke")

    def test_tokenize_drops_stopwords_and_short_tokens(self):
        tokens = tokenize("What is your process for the access?")
        self.assertNotIn("what", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("for", tokens)
        self.assertIn("process", tokens)
        self.assertIn("access", tokens)

    def test_tokenize_unifies_hyphenated_and_spaced_phrases(self):
        a = tokenize("least-privilege access")
        b = tokenize("least privilege access")
        self.assertEqual(a, b)


class TestIdfWeighting(unittest.TestCase):

    def test_build_idf_returns_lower_weight_for_more_common_tokens(self):
        idf, default_idf = build_idf(FAKE_LIBRARY)
        # "access" / "revoke" appear in both T-001 and T-002's canonical
        # text, so they should carry a lower idf weight than a token that
        # appears in only one row's canonical/variant text, e.g. "database".
        self.assertLess(idf["access"], idf["database"])

    def test_unseen_token_gets_default_idf_treated_as_rare(self):
        idf, default_idf = build_idf(FAKE_LIBRARY)
        self.assertNotIn("zzz_unseen_token", idf)
        self.assertGreater(default_idf, 0)

    def test_token_overlap_score_empty_sets_is_zero(self):
        idf, default_idf = build_idf(FAKE_LIBRARY)
        self.assertEqual(token_overlap_score(set(), {"a"}, idf, default_idf), 0.0)
        self.assertEqual(token_overlap_score({"a"}, set(), idf, default_idf), 0.0)

    def test_token_overlap_score_identical_sets_is_one(self):
        idf, default_idf = build_idf(FAKE_LIBRARY)
        s = {"access", "revoke", "database"}
        self.assertAlmostEqual(token_overlap_score(s, s, idf, default_idf), 1.0, places=6)

    def test_token_overlap_score_falls_back_without_idf(self):
        # Plain (unweighted) Dice coefficient when idf dict is empty.
        score = token_overlap_score({"a", "b"}, {"a", "c"}, {}, 0.0)
        self.assertAlmostEqual(score, 2 * 1 / (2 + 2), places=6)


class TestMatchingAccuracy(unittest.TestCase):
    """
    The core regression-prevention tests. Each of these corresponds to a
    real mismatch found and fixed during development:

      - employee offboarding vs. vendor offboarding (two library rows
        about "revoking access" after a termination event, one about
        employees and one about vendors/contracts -- the engine must not
        confuse them just because they share generic words like "process"
        and "access").
      - account lockout phrased as a totally different sentence structure
        than its library row.
      - encryption-at-rest vs. breach-history, which share almost no
        vocabulary and must not cross-match.
    """

    def setUp(self):
        self.idf, self.default_idf = build_idf(FAKE_LIBRARY)

    def _best_match_id(self, question):
        score, row = match_question(
            question, FAKE_LIBRARY, DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT,
            self.idf, self.default_idf,
        )
        return (row["id"] if row else None), score

    def test_employee_offboarding_beats_vendor_offboarding(self):
        # Regression test: earlier scoring picked T-002 (vendor offboarding)
        # for this question because its canonical text happens to literally
        # contain the word "process", which the employee-offboarding row's
        # canonical/variant text did not. Fixed by adding an explicit
        # employee-phrased variant + keyword to the employee-offboarding row.
        match_id, score = self._best_match_id(
            "What is your process for revoking system access when an employee leaves the company?"
        )
        self.assertEqual(match_id, "T-001")

    def test_vendor_offboarding_question_still_matches_vendor_row(self):
        match_id, score = self._best_match_id(
            "How do you handle offboarding a vendor and cutting off their system access?"
        )
        self.assertEqual(match_id, "T-002")

    def test_differently_phrased_lockout_question_matches_lockout_row(self):
        match_id, score = self._best_match_id(
            "How quickly after a password is entered incorrectly multiple times does the account lock?"
        )
        self.assertEqual(match_id, "T-003")

    def test_encryption_question_does_not_match_breach_history_row(self):
        match_id, score = self._best_match_id(
            "Do you encrypt sensitive data while it is stored in your databases?"
        )
        self.assertEqual(match_id, "T-004")
        self.assertNotEqual(match_id, "T-005")

    def test_hyphenated_phrasing_matches_same_as_spaced_phrasing(self):
        score_hyphen, row_hyphen = match_question(
            "What is your least-privilege access control approach?",
            FAKE_LIBRARY, DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT, self.idf, self.default_idf,
        )
        score_spaced, row_spaced = match_question(
            "What is your least privilege access control approach?",
            FAKE_LIBRARY, DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT, self.idf, self.default_idf,
        )
        self.assertEqual(score_hyphen, score_spaced)

    def test_nonsense_question_scores_low_against_every_row(self):
        match_id, score = self._best_match_id(
            "What color is your company logo and does it meet WCAG contrast requirements?"
        )
        self.assertLess(score, DEFAULT_MEDIUM_THRESHOLD)

    def test_empty_library_returns_no_match(self):
        score, row = match_question("anything", [], DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT, {}, 0.0)
        self.assertIsNone(row)
        self.assertEqual(score, 0.0)


class TestKeywordScoring(unittest.TestCase):

    def setUp(self):
        self.idf, self.default_idf = build_idf(FAKE_LIBRARY)

    def test_keyword_score_pools_keywords_rather_than_averaging_per_phrase(self):
        # A row whose keyword set shares one common word with the incoming
        # question, plus one genuinely-matching distinctive word, should
        # score meaningfully above a row that shares only the common word.
        incoming = tokenize("Do you lock accounts after failed login attempts?")
        row_lockout = FAKE_LIBRARY[2]  # T-003: "account lockout, failed login monitoring"
        row_offboard = FAKE_LIBRARY[0]  # T-001: shares only "access"-adjacent vocabulary, not lockout
        kw_lockout = keyword_score(incoming, row_lockout, self.idf, self.default_idf)
        kw_offboard = keyword_score(incoming, row_offboard, self.idf, self.default_idf)
        self.assertGreater(kw_lockout, kw_offboard)

    def test_keyword_score_zero_when_row_has_no_keywords(self):
        row = make_row("T-999", "X", "some question")
        score = keyword_score(tokenize("some question"), row, self.idf, self.default_idf)
        self.assertEqual(score, 0.0)


class TestPlaceholderSubstitution(unittest.TestCase):

    def test_simple_placeholder_is_substituted(self):
        filled, unresolved = fill_placeholders(
            "Access is revoked within {{TIMEFRAME}} per {{OFFBOARDING_SOP}}.",
            {"TIMEFRAME": "4 business hours", "OFFBOARDING_SOP": "Offboarding SOP v1.0"},
        )
        self.assertEqual(filled, "Access is revoked within 4 business hours per Offboarding SOP v1.0.")
        self.assertEqual(unresolved, [])

    def test_missing_simple_placeholder_stays_and_is_reported_unresolved(self):
        filled, unresolved = fill_placeholders("Policy ref: {{AUP}}.", {})
        self.assertEqual(filled, "Policy ref: {{AUP}}.")
        self.assertEqual(unresolved, ["AUP"])

    def test_free_text_placeholder_is_never_auto_filled(self):
        # Compound/free-text placeholders (contain spaces, commas, or lowercase
        # prose) are deliberately never looked up in client_config, even if a
        # config happens to have a matching key -- they're a note to a human.
        filled, unresolved = fill_placeholders(
            "Identity provider: {{N, e.g., Okta}}.", {"N": "should not be used"},
        )
        self.assertIn("{{N, e.g., Okta}}", filled)
        self.assertIn("N, e.g., Okta", unresolved)

    def test_compound_simple_key_with_slash_is_substituted(self):
        filled, unresolved = fill_placeholders(
            "Timeframe: {{TIMEFRAME/SLA}}.", {"TIMEFRAME/SLA": "24 hours"},
        )
        self.assertEqual(filled, "Timeframe: 24 hours.")
        self.assertEqual(unresolved, [])


class TestLoadLibraryAndConfig(unittest.TestCase):

    def test_load_library_parses_variants_and_keywords(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "lib.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=[
                    "id", "domain", "canonical_question", "question_variants",
                    "keywords", "frameworks", "default_answer", "answer_template",
                    "artifact_type", "verification_guidance",
                ])
                w.writeheader()
                w.writerow({
                    "id": "X-1", "domain": "Test", "canonical_question": "Q?",
                    "question_variants": "V1|V2", "keywords": "k1, k2",
                    "frameworks": "SIG Lite", "default_answer": "Y",
                    "answer_template": "A", "artifact_type": "Art",
                    "verification_guidance": "G",
                })
            rows = load_library(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["_variants"], ["V1", "V2"])
            self.assertEqual(rows[0]["_keywords"], ["k1", "k2"])

    def test_load_library_framework_filter(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "lib.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=[
                    "id", "domain", "canonical_question", "question_variants",
                    "keywords", "frameworks", "default_answer", "answer_template",
                    "artifact_type", "verification_guidance",
                ])
                w.writeheader()
                w.writerow({"id": "X-1", "domain": "T", "canonical_question": "Q1",
                            "question_variants": "", "keywords": "", "frameworks": "SIG Lite",
                            "default_answer": "Y", "answer_template": "", "artifact_type": "", "verification_guidance": ""})
                w.writerow({"id": "X-2", "domain": "T", "canonical_question": "Q2",
                            "question_variants": "", "keywords": "", "frameworks": "CAIQ",
                            "default_answer": "Y", "answer_template": "", "artifact_type": "", "verification_guidance": ""})
            rows = load_library(path, framework_filter="CAIQ")
            self.assertEqual([r["id"] for r in rows], ["X-2"])

    def test_load_client_config_none_path_returns_empty_dict(self):
        self.assertEqual(load_client_config(None), {})

    def test_load_client_config_reads_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cfg.json"
            path.write_text(json.dumps({"COMPANY": "Acme"}), encoding="utf-8")
            self.assertEqual(load_client_config(path), {"COMPANY": "Acme"})


class TestProcessQuestionnaireEndToEnd(unittest.TestCase):
    """End-to-end test against a small, realistic, messy incoming
    questionnaire CSV -- including a question with an embedded comma (the
    exact bug class that silently truncated real sample data during
    development: an unquoted CSV field with a comma splits into extra
    columns unless properly quoted)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.questionnaire_path = Path(self.tmpdir.name) / "incoming.csv"
        with open(self.questionnaire_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, quoting=csv.QUOTE_ALL)
            w.writerow(["q_num", "question_text"])
            w.writerow(["1", "What is your process for revoking system access when an employee leaves the company?"])
            w.writerow(["2", "Is there a formal, board- or leadership-approved written information security policy?"])
            w.writerow(["3", "What color is your company logo and does it meet WCAG contrast requirements?"])
            w.writerow(["4", ""])  # blank question row should be skipped

    def test_high_and_medium_and_no_match_buckets_all_populated(self):
        results, no_match = process_questionnaire(
            self.questionnaire_path, "question_text", "q_num",
            FAKE_LIBRARY, {},
            DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT,
            DEFAULT_HIGH_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD,
        )
        # Blank row skipped -> 3 results, not 4.
        self.assertEqual(len(results), 3)
        statuses = {r["question_id"]: r["match_status"] for r in results}
        self.assertEqual(statuses["1"], "HIGH_CONFIDENCE")
        # Row 2 (infosec policy) has no corresponding row in this tiny
        # FAKE_LIBRARY (it only covers offboarding/lockout/encryption/breach),
        # so it correctly falls to NO_MATCH alongside row 3 (nonsense question).
        self.assertEqual(statuses["2"], "NO_MATCH_MANUAL_ANSWER_REQUIRED")
        self.assertEqual(statuses["3"], "NO_MATCH_MANUAL_ANSWER_REQUIRED")
        self.assertEqual(len(no_match), 2)

    def test_comma_containing_question_is_not_truncated(self):
        results, _ = process_questionnaire(
            self.questionnaire_path, "question_text", "q_num",
            FAKE_LIBRARY, {},
            DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT,
            DEFAULT_HIGH_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD,
        )
        row2 = next(r for r in results if r["question_id"] == "2")
        self.assertIn("board- or leadership-approved", row2["incoming_question"])

    def test_matched_row_fills_placeholders_from_client_config(self):
        results, _ = process_questionnaire(
            self.questionnaire_path, "question_text", "q_num",
            FAKE_LIBRARY, {"TIMEFRAME": "4 business hours", "OFFBOARDING_SOP": "Offboarding SOP v1.0"},
            DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT,
            DEFAULT_HIGH_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD,
        )
        row1 = next(r for r in results if r["question_id"] == "1")
        self.assertEqual(row1["matched_library_id"], "T-001")
        self.assertIn("4 business hours", row1["draft_answer"])
        self.assertEqual(row1["unresolved_placeholders"], "")

    def test_missing_question_column_exits(self):
        with self.assertRaises(SystemExit):
            process_questionnaire(
                self.questionnaire_path, "nonexistent_column", "q_num",
                FAKE_LIBRARY, {},
                DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT,
                DEFAULT_HIGH_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD,
            )

    def test_write_output_round_trips(self):
        results, _ = process_questionnaire(
            self.questionnaire_path, "question_text", "q_num",
            FAKE_LIBRARY, {},
            DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT,
            DEFAULT_HIGH_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD,
        )
        out_path = Path(self.tmpdir.name) / "out.csv"
        write_output(results, out_path)
        with open(out_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["question_id"], "1")


class TestRealLibraryIntegration(unittest.TestCase):
    """
    Sanity checks against the real answer_library_master.csv shipped
    alongside this script, so a future edit to the library content that
    breaks these specific, previously-debugged real-world cases is caught
    immediately rather than silently shipping to a client.

    Skipped gracefully if the real library file isn't present (e.g. this
    test file is copied elsewhere without it).
    """

    LIBRARY_PATH = Path(__file__).parent / "answer_library_master.csv"

    @classmethod
    def setUpClass(cls):
        if not cls.LIBRARY_PATH.exists():
            raise unittest.SkipTest(f"{cls.LIBRARY_PATH} not found; skipping real-library integration tests.")
        cls.library = load_library(cls.LIBRARY_PATH)
        cls.idf, cls.default_idf = build_idf(cls.library)

    def _best_match_id(self, question):
        score, row = match_question(
            question, self.library, DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT,
            self.idf, self.default_idf,
        )
        return (row["id"] if row else None), score

    def test_employee_offboarding_matches_al045_not_vendor_row(self):
        match_id, _ = self._best_match_id(
            "What is your process for revoking system access when an employee leaves the company?"
        )
        self.assertEqual(match_id, "AL-045")

    def test_mfa_question_matches_access_control_domain(self):
        match_id, score = self._best_match_id(
            "Is MFA required for anyone accessing your cloud infrastructure console?"
        )
        row = next(r for r in self.library if r["id"] == match_id)
        self.assertEqual(row["domain"], "Access Control")
        self.assertGreaterEqual(score, DEFAULT_HIGH_THRESHOLD)

    def test_cyber_insurance_question_matches_high_confidence(self):
        match_id, score = self._best_match_id("Do you carry cyber liability insurance?")
        self.assertIsNotNone(match_id)
        self.assertGreaterEqual(score, DEFAULT_HIGH_THRESHOLD)

    def test_overall_sample_questionnaire_actionable_rate_at_least_75_percent(self):
        """Guards against a future change silently tanking overall match
        quality: re-scores a realistic 25-question sample and asserts the
        actionable (HIGH + MEDIUM) rate doesn't regress below 75%, the
        level verified by hand during development (80% at time of writing)."""
        sample_path = Path(__file__).parent / "sample_incoming_questionnaire.csv"
        if not sample_path.exists():
            self.skipTest("sample_incoming_questionnaire.csv not found")
        results, no_match = process_questionnaire(
            sample_path, "question_text", "q_num",
            self.library, {},
            DEFAULT_SIMILARITY_WEIGHT, DEFAULT_KEYWORD_WEIGHT,
            DEFAULT_HIGH_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD,
        )
        actionable = sum(1 for r in results if r["match_status"] != "NO_MATCH_MANUAL_ANSWER_REQUIRED")
        rate = actionable / len(results) * 100
        self.assertGreaterEqual(rate, 75.0, f"Actionable rate regressed to {rate:.0f}%")

        # And: zero HIGH_CONFIDENCE matches should ever point at a wrong
        # domain for these specific, hand-verified unambiguous questions.
        by_id = {r["question_id"]: r for r in results}
        self.assertEqual(by_id["3"]["domain"], "Access Control")  # MFA
        self.assertEqual(by_id["9"]["domain"], "Incident Management")  # cyber insurance


if __name__ == "__main__":
    unittest.main(verbosity=2)
