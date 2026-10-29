# Answer Library Engine

The core automation behind Deal Unlocker's 72-hour turnaround: fuzzy-matches an
incoming client security questionnaire (SIG Lite, CAIQ, or custom) against
[`answer-library/answer_library_master.csv`](../answer-library/answer_library_master.csv),
and produces a draft answer sheet — matched canonical answer, client-specific
`{{PLACEHOLDER}}` values filled in, a confidence score, and a clear flag for
anything that needs a human to actually look at it before it goes out the door.

**This does not auto-submit anything.** Every row still needs a human pass per
the engagement guardrail ("client approves every questionnaire answer before
submission"). This tool exists to make that human pass fast — reviewing and
tweaking 80–150 pre-drafted answers — instead of slow — writing 80–150 answers
from scratch under a 72-hour clock.

## Quick start

```bash
pip install -r requirements.txt   # stdlib only; no third-party deps required to run
python3 answer_engine.py \
    --questionnaire incoming_questions.csv --question-column question \
    --library ../answer-library/answer_library_master.csv \
    --client-config client_config_clearpath.json \
    --output clearpath_answer_sheet.csv
```

Run the test suite before trusting any change to the matching logic or the
library content:

```bash
python3 -m pytest test_answer_engine.py -v
```

## How matching works

For each incoming question, every library row is scored on two signals,
blended by weight:

1. **Text similarity** — an IDF-weighted token-overlap (Dice coefficient)
   score against the row's `canonical_question` and each of its
   `question_variants`; the best of these wins.
2. **Keyword overlap** — the same IDF-weighted overlap, but against the
   pooled token set of all of the row's comma-separated `keywords`. This
   catches cases where the incoming question is phrased very differently
   from the canonical question but uses the same domain vocabulary.

**Why IDF weighting matters here specifically:** compliance questionnaire
sentences share heavy scaffolding ("Does the organization maintain a
documented process for…"). Plain bag-of-words / character-diff matching lets
two topically unrelated questions that merely share common scaffolding words
outscore the genuinely correct match, which usually shares only one or two
rare, distinctive words ("offboard," "break-glass," "recertify"). IDF weights
each token by how rare it is across the whole library, so distinctive words
carry the match and generic scaffolding doesn't dominate it.

Tokens are lowercased, stripped of punctuation (so `least-privilege` ==
`least privilege`), and run through a small hand-tuned stemmer (so
`encrypt`/`encrypted`/`encryption` and `database`/`databases` collapse to the
same token) plus a manual equivalence map for irregular pairs the stemmer
can't unify on its own (`revoke`/`revocation`, `lockout`/`lock`, etc.) — see
`STEM_EQUIVALENTS` in `answer_engine.py`.

### Confidence buckets

| Status | Threshold | Meaning |
|---|---|---|
| `HIGH_CONFIDENCE` | score ≥ `--high-threshold` (default **0.55**) | Confident match. Still flagged for review like everything else, but the engine's own confidence is high. |
| `NEEDS_REVIEW_MEDIUM_CONFIDENCE` | score ≥ `--medium-threshold` (default **0.32**) | Best-guess match filled in. Treat as a starting draft, not an answer. |
| `NO_MATCH_MANUAL_ANSWER_REQUIRED` | below medium threshold | No confident match. Row left blank; question listed in the run summary as a candidate to add to the library once answered for the first time. |

Scores are an IDF-weighted Dice coefficient over stemmed tokens, not a
calibrated statistical probability — these thresholds were tuned empirically
against a 25-question realistic sample questionnaire (`sample_incoming_questionnaire.csv`),
not derived analytically. **They deliberately favor precision over recall**:
a real-but-oddly-phrased match is more likely to fall through to `NO_MATCH`
than to get mis-surfaced as a wrong high-confidence draft. A human writing one
answer from scratch is a cheaper mistake than a human approving a wrong
drafted one in a document going to an enterprise security reviewer.

On the 25-question sample, this currently resolves **80%** of questions to a
draft (36% high-confidence, 44% medium-confidence review), with the remaining
20% split between genuinely out-of-library questions and borderline near-misses
that fell just under threshold.

### Tuning knobs

All exposed as CLI flags, with the defaults above:

```
--sim-weight          weight for text-similarity score      (default 0.55)
--kw-weight           weight for keyword-overlap score       (default 0.45)
--high-threshold      score at/above which match is HIGH     (default 0.55)
--medium-threshold    score at/above which match is kept at all, below HIGH (default 0.32)
--framework           restrict matching to rows tagged for this framework
                       ("SIG Lite" / "CAIQ" / "Custom") — improves precision
                       when you know the questionnaire type.
```

## Placeholder substitution

`answer_template` strings in the library contain `{{PLACEHOLDER}}` tokens
(e.g. `{{COMPANY}}`, `{{ASSET_INVENTORY_DOC}}`, `{{FREQUENCY}}`). Pass a JSON
file via `--client-config` mapping placeholder names to client-specific
values (see `client_config_example.json`); the engine substitutes every
placeholder it has a value for.

Two kinds of placeholder are handled differently:

- **Simple keys** — a single `UPPER_SNAKE` token, optionally with a `/`
  (`{{TIMEFRAME}}`, `{{CLOUD_PROVIDER/REGION}}`) — are looked up directly in
  the client config.
- **Free-text notes** — anything containing a space, comma, or lowercase
  prose (`{{N, e.g., Okta}}`, `{{AND/OR complexity rules}}`) — are never
  auto-filled, even if a config happens to have a matching key. These are
  treated as a note to the human reviewer, not a config lookup, and always
  appear in the output's `unresolved_placeholders` column.

This means the output never silently ships literal `{{...}}` text in an
answer sent to a client's enterprise reviewer — anything left unresolved is
explicitly surfaced in its own column.

## Output columns

`question_id, incoming_question, match_status, confidence, matched_library_id,
domain, default_answer, draft_answer, unresolved_placeholders, artifact_type,
verification_guidance`

`verification_guidance` is carried straight through from the matched library
row — it's the "what to actually check before you say yes to this" note a
human reviewer needs, not boilerplate.

## Known limitations

- **Stdlib-only, no ML/embeddings.** This is deliberate: the tool needs to be
  maintainable and extendable by a non-ML-specialist (via Cursor), and the
  library is small enough (152 rows) that a well-tuned lexical approach beats
  the complexity cost of an embedding dependency. If the library grows into
  the thousands of rows or starts seeing far more paraphrase variety, revisit
  this.
- **Borderline near-misses fall to NO_MATCH rather than low-confidence MEDIUM.**
  A couple of real library matches score just under the medium threshold on
  oddly-phrased incoming questions (see `test_overall_sample_questionnaire_actionable_rate_at_least_75_percent`
  in the test suite for the current measured rate). This is the intended
  fail-closed behavior, not a bug — see the confidence-bucket note above.
- **Library content gaps show up as matching bugs.** A real regression found
  during development: the employee-offboarding library row didn't contain the
  word "employee" anywhere in its canonical question, variants, or keywords,
  so a differently-phrased employee-offboarding question nearly matched the
  *vendor*-offboarding row instead (they share "process," "revoke," "access").
  The fix was adding an employee-phrased variant and keyword to the library
  row, not changing the scoring algorithm. **When a real engagement surfaces
  a wrong match, check the library row's variant/keyword coverage before
  touching `answer_engine.py` itself.**
- **No synonym/abbreviation expansion beyond the manual `STEM_EQUIVALENTS`
  map.** Acronyms the incoming questionnaire might use instead of the
  library's spelled-out term (e.g. "PoLP" for "principle of least privilege")
  won't match unless added as a keyword or variant.

## Files in this folder

- `answer_engine.py` — the engine (CLI + importable functions).
- `test_answer_engine.py` — unit tests (tokenization, IDF weighting, keyword
  pooling, placeholder substitution) plus regression tests tied to specific
  real matching bugs found during development, plus an integration test
  against the real shipped `answer_library_master.csv`.
- `client_config_example.json` — example client config, modeled on ClearPath
  Health.
- `sample_incoming_questionnaire.csv` — a 25-question realistic sample
  questionnaire (22 real rephrasings across most domains + 3 deliberately
  nonsensical questions) used to tune thresholds and as a regression fixture.
- `answer_library_master.csv` — a copy of the master library for local
  testing; the canonical source lives in `../answer-library/`.

## Suggested next steps

- Feed real client-engagement near-misses back into the library as new
  `question_variants` / `keywords` — this is the main lever for improving
  match quality over time, not algorithm tuning.
- A small `--explain` flag that prints the top-3 candidate scores (not just
  the winner) would speed up debugging a wrong match during a live
  engagement — currently that requires an ad hoc debug script (see the
  pattern in the regression tests).
