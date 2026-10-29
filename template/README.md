# Standalone Gap Register / Reviewer Brief Template

`build_deliverable.py` — the reusable generator behind the ClearPath Health
sample (`../samples/clearpath-health/`), decoupled from ClearPath's
hardcoded content so it runs against any real client's reviewed answers.

It produces one print-ready HTML document combining the Reviewer Brief
(one-pager summary), the full Answer Set, and the Gap Register — the Brief
is the exec summary an enterprise buyer's security reviewer reads first,
with the full answer set and gap register as backing detail in the same
file.

## Quick start

```bash
python3 build_deliverable.py \
    --questions sample_questions.csv \
    --client-config sample_client_config.json \
    --output /tmp/demo.html
```

Run the tests before trusting any change:

```bash
python3 test_build_deliverable.py -v
```

## Real engagement usage

1. Run `../engine/answer_engine.py` against the incoming questionnaire →
   draft `answer_sheet.csv`.
2. **Human review pass (required per engagement guardrail — the client
   approves every answer before submission).** Open the draft in a
   spreadsheet. For every row, confirm or correct the Y/N answer, finalize
   the citation/finding text, and — for every "No" — add `priority`
   (High/Medium/Low) and `target_days` (int, days out from the assessment
   date). This script accepts either hand-built column names
   (`domain,question,answer,note,priority,target_days,artifact_required`)
   or the engine's own output columns (`domain,incoming_question,
   final_answer,final_note,...`) — see the full column list in
   `build_deliverable.py`'s module docstring.
3. Write a client config JSON (`sample_client_config.json` is a filled-in
   example) — company name/blurb, product scope, questionnaire type,
   posture summary. **Set `"is_sample": false`** — this is the field that
   keeps the real deliverable from carrying ClearPath's "SAMPLE —
   FICTIONAL DATA" watermark.
4. Run `build_deliverable.py` → the final HTML. Print to PDF for delivery.

## What's parameterized vs. fixed

Parameterized per client: company/product text, questionnaire type,
question set, domains (ordered by first appearance — no hardcoded domain
list, so this works for SIG Lite, CAIQ, or a fully custom questionnaire),
gap priorities/dates, and the "fastest-closing high-priority items" Brief
callout (auto-generated from the actual gap data, or override via config).

Fixed regardless of client: the visual design (same CSS as the ClearPath
sample — this is deliberately not re-themed per client, it's Sui-Generis
LLC's document brand), and the compliance-conclusion disclaimer language
("No statement in this document should be read as a legal compliance or
certification conclusion") — never remove that line; it's what keeps this
tool inside the "never say compliant" guardrail.
