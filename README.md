# deal-unlocker
72-hour security questionnaire completion service — SIG Lite, CAIQ, and custom formats. Answer library, Gap Register, and Reviewer Brief generation.

Productized by Sui-Generis LLC.

## Layout

- **`answer-library/`** — the master SIG Lite answer library (`answer_library_master.csv`, 152 rows across 14 domains) plus its generator script (`build_answer_library.py`). Edit the script and regenerate, don't hand-edit the CSV.
- **`engine/`** — the Answer Library Engine (`answer_engine.py`): fuzzy-matches an incoming client questionnaire against the answer library and drafts an answer sheet with confidence scoring and client-placeholder substitution. See `engine/README.md` for how matching works and its tuning knobs. Run `python3 -m pytest engine/test_answer_engine.py` before trusting any change to the matching logic or library content.
- **`samples/clearpath-health/`** — a complete fictional sample deliverable (15-person healthtech SaaS startup) used as a sales asset: 80-question SIG Lite answer set, Gap Register, and Reviewer Brief, as a print-ready HTML file, plus the generator script.
- **`gap-register/`**, **`reviewer-brief/`** — standalone templates (currently the ClearPath sample's generator script is the de facto template for both; a reusable Jinja-style template is a planned follow-up).

## Pipeline (current state)

1. Client sends a questionnaire (PDF/Excel/portal export) → extract question text into a CSV.
2. Run `engine/answer_engine.py` against `answer-library/answer_library_master.csv` with a client-specific config → draft answer sheet.
3. Human review pass: approve/edit every row (per engagement guardrail — the client approves every answer before submission).
4. Every "No" becomes a dated Gap Register item; package the signed answer set + Gap Register + Reviewer Brief per the `samples/clearpath-health/` pattern.
5. Feed real near-misses from the engagement back into the answer library as new variants/keywords.

Still open: a standalone reusable Gap Register / Reviewer Brief HTML template (decoupled from the ClearPath sample generator), and a questionnaire-text-extraction helper for PDF/Excel inputs (currently manual).
