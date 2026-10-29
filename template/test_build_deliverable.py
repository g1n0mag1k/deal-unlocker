#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for build_deliverable.py.

Covers input validation (fail-loud on malformed/missing review data — this
feeds a document a client sends to an enterprise security reviewer, so
silent guessing is worse than a crash with a clear message), domain
ordering, auto-generated priority callout, and an end-to-end HTML smoke
test against the shipped sample fixtures.

Run: python3 test_build_deliverable.py
"""

import csv
import datetime
import tempfile
import unittest
from pathlib import Path

import build_deliverable as mod


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


MINIMAL_CONFIG = {
    "company_name": "Acme Co.",
    "company_blurb": "A small company.",
    "product_scope": "The Acme platform.",
    "questionnaire_type": "SIG Lite",
    "posture_summary": "Generally solid.",
    "prepared_date": "2026-01-01",
}


class TestLoadQuestions(unittest.TestCase):
    def test_minimal_valid_row_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"domain": "Access Control", "question": "MFA enforced?", "answer": "Y", "note": "Ref: IAM Policy"}],
                      ["domain", "question", "answer", "note"])
            qs = mod.load_questions(p)
            self.assertEqual(len(qs), 1)
            self.assertEqual(qs[0]["answer"], "Y")
            self.assertIsNone(qs[0]["priority"])

    def test_missing_domain_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"question": "MFA enforced?", "answer": "Y", "note": "x"}],
                      ["question", "answer", "note"])
            with self.assertRaises(SystemExit):
                mod.load_questions(p)

    def test_invalid_answer_value_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"domain": "Access Control", "question": "MFA?", "answer": "maybe", "note": "x"}],
                      ["domain", "question", "answer", "note"])
            with self.assertRaises(SystemExit):
                mod.load_questions(p)

    def test_no_row_missing_priority_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"domain": "Access Control", "question": "MFA?", "answer": "N", "note": "x", "target_days": "30"}],
                      ["domain", "question", "answer", "note", "target_days"])
            with self.assertRaises(SystemExit):
                mod.load_questions(p)

    def test_no_row_missing_target_days_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"domain": "Access Control", "question": "MFA?", "answer": "N", "note": "x", "priority": "High"}],
                      ["domain", "question", "answer", "note", "priority"])
            with self.assertRaises(SystemExit):
                mod.load_questions(p)

    def test_no_row_bad_target_days_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"domain": "Access Control", "question": "MFA?", "answer": "N", "note": "x",
                           "priority": "High", "target_days": "soon"}],
                      ["domain", "question", "answer", "note", "priority", "target_days"])
            with self.assertRaises(SystemExit):
                mod.load_questions(p)

    def test_no_row_defaults_artifact_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"domain": "Access Control", "question": "MFA?", "answer": "N", "note": "x",
                           "priority": "High", "target_days": "30"}],
                      ["domain", "question", "answer", "note", "priority", "target_days"])
            qs = mod.load_questions(p)
            self.assertEqual(qs[0]["artifact_required"], "Remediation Evidence (TBD)")

    def test_engine_output_column_aliases_accepted(self):
        # Mirrors engine/answer_engine.py's answer_sheet.csv column names
        # (incoming_question, final_answer, final_note) extended with the
        # review columns a human adds after confirming the draft.
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"question_id": "Q001", "domain": "Access Control",
                           "incoming_question": "Is MFA enforced?", "final_answer": "N",
                           "final_note": "Not yet enforced for legacy VPN users.",
                           "priority": "High", "target_days": "30"}],
                      ["question_id", "domain", "incoming_question", "final_answer", "final_note", "priority", "target_days"])
            qs = mod.load_questions(p)
            self.assertEqual(qs[0]["id"], "Q001")
            self.assertEqual(qs[0]["question"], "Is MFA enforced?")
            self.assertEqual(qs[0]["answer"], "N")
            self.assertEqual(qs[0]["note"], "Not yet enforced for legacy VPN users.")

    def test_priority_alias_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.csv"
            write_csv(p, [{"domain": "Access Control", "question": "MFA?", "answer": "N", "note": "x",
                           "priority": "high", "target_days": "30"}],
                      ["domain", "question", "answer", "note", "priority", "target_days"])
            qs = mod.load_questions(p)
            self.assertEqual(qs[0]["priority"], "High")


class TestAssignIds(unittest.TestCase):
    def test_auto_numbers_with_prefix(self):
        qs = [{"id": None}, {"id": None}, {"id": "KEEP-ME"}]
        mod.assign_ids(qs, prefix="SIG")
        self.assertEqual(qs[0]["id"], "SIG-01")
        self.assertEqual(qs[1]["id"], "SIG-02")
        self.assertEqual(qs[2]["id"], "KEEP-ME")


class TestLoadConfig(unittest.TestCase):
    def test_missing_required_field_fails_loud(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            bad = dict(MINIMAL_CONFIG)
            del bad["posture_summary"]
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(SystemExit):
                mod.load_config(p)

    def test_defaults_applied(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            cfg = dict(MINIMAL_CONFIG)
            del cfg["prepared_date"]
            p.write_text(json.dumps(cfg), encoding="utf-8")
            config = mod.load_config(p)
            self.assertEqual(config["buyer_label"], "Enterprise Buyer Security Review Team")
            self.assertFalse(config["is_sample"])
            self.assertEqual(config["_prepared_date"], datetime.date.today())

    def test_explicit_prepared_date_parsed(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            p.write_text(json.dumps(MINIMAL_CONFIG), encoding="utf-8")
            config = mod.load_config(p)
            self.assertEqual(config["_prepared_date"], datetime.date(2026, 1, 1))


class TestDomainOrderingAndCallout(unittest.TestCase):
    def test_domains_ordered_by_first_appearance(self):
        questions = [
            {"domain": "Zebra Domain"}, {"domain": "Apple Domain"}, {"domain": "Zebra Domain"},
        ]
        self.assertEqual(mod.ordered_domains(questions), ["Zebra Domain", "Apple Domain"])

    def test_auto_priority_callout_picks_earliest_high_gaps(self):
        prepared = datetime.date(2026, 1, 1)
        gaps = [
            {"priority": "High", "target_days": 60, "artifact_required": "Late Item"},
            {"priority": "High", "target_days": 10, "artifact_required": "Early Item"},
            {"priority": "Medium", "target_days": 5, "artifact_required": "Ignored Medium"},
        ]
        callout = mod.auto_priority_callout(gaps, prepared)
        self.assertIn("Early Item", callout)
        self.assertIn("Late Item", callout)
        self.assertIn("Ignored Medium", "Ignored Medium")  # sanity
        self.assertNotIn("Ignored Medium", callout)
        # earlier item should appear before the later one
        self.assertLess(callout.index("Early Item"), callout.index("Late Item"))

    def test_auto_priority_callout_no_high_gaps(self):
        callout = mod.auto_priority_callout([], datetime.date(2026, 1, 1))
        self.assertIn("No high-priority gaps", callout)


class TestEndToEndHtml(unittest.TestCase):
    def setUp(self):
        self.fixture_dir = Path(__file__).parent
        self.questions_path = self.fixture_dir / "sample_questions.csv"
        self.config_path = self.fixture_dir / "sample_client_config.json"

    def test_shipped_sample_fixtures_produce_well_formed_html(self):
        config = mod.load_config(self.config_path)
        questions = mod.load_questions(self.questions_path)
        mod.assign_ids(questions, prefix=config["id_prefix"])
        html = mod.generate_html(questions, config)

        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Example Health, Inc.", html)
        self.assertIn("Reviewer Brief", html)
        self.assertIn("Gap Register", html)
        # 8 questions in the fixture, 4 "Y" and 4 "N"
        self.assertEqual(html.count('class="pill pill-no"'), 4)
        self.assertEqual(html.count('class="pill pill-yes"'), 4)
        # is_sample: true in the fixture config -> watermark present
        self.assertIn("SAMPLE", html)

    def test_is_sample_false_omits_watermark(self):
        config = mod.load_config(self.config_path)
        config["is_sample"] = False
        questions = mod.load_questions(self.questions_path)
        mod.assign_ids(questions, prefix=config["id_prefix"])
        html = mod.generate_html(questions, config)
        # The CSS always *defines* .sample-watermark (harmless, unused when
        # not rendered) — what matters is that the element itself is absent.
        self.assertNotIn('<div class="sample-watermark">', html)
        self.assertNotIn("Fictional sample for demonstration", html)

    def test_html_escaping_prevents_injection(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            qpath = Path(tmp) / "q.csv"
            write_csv(qpath, [{"domain": "Access <script>Control", "question": "MFA & <b>stuff</b>?",
                               "answer": "Y", "note": "Ref: <IAM> Policy"}],
                      ["domain", "question", "answer", "note"])
            cpath = Path(tmp) / "c.json"
            cpath.write_text(json.dumps(MINIMAL_CONFIG), encoding="utf-8")

            config = mod.load_config(cpath)
            questions = mod.load_questions(qpath)
            mod.assign_ids(questions, prefix="Q")
            html = mod.generate_html(questions, config)
            self.assertNotIn("<script>Control", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertIn("&lt;b&gt;stuff&lt;/b&gt;", html)


class TestCliEndToEnd(unittest.TestCase):
    def test_main_writes_output_file(self):
        import subprocess
        import sys as _sys
        fixture_dir = Path(__file__).parent
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.html"
            result = subprocess.run(
                [_sys.executable, str(fixture_dir / "build_deliverable.py"),
                 "--questions", str(fixture_dir / "sample_questions.csv"),
                 "--client-config", str(fixture_dir / "sample_client_config.json"),
                 "--output", str(out_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(out_path.exists())
            self.assertIn("Wrote", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
