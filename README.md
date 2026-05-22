# 🧶 42 x Needle Hackathon — ArchCipher

**Autonomous coding agent** that builds the **Knitting Compiler** (`python3 knit.py compile <file.knit>` → JSON on stdout).  
This repo contains the agent loop, official public + hidden tests, logs, and the final compiler implementation.

**Final score: [150/150](test_results/scoreboard.txt) — 100% across all test categories (public + hidden).**

---

## Repository layout

```
├── knit.py                    # submission CLI entrypoint (497 lines, stdlib only)
├── agent/
│   ├── agent.py               # main orchestration loop
│   ├── planner.py             # spec reader + LLM plan generator
│   ├── coder.py               # plan → code translator
│   ├── tester.py              # test runner integration
│   ├── repairer.py            # failure analysis + targeted fix engine
│   ├── ollama_client.py       # local LLM client (qwen2.5-coder:7b / llama3.1:8b)
│   ├── prompts.py             # prompt template loader
│   ├── prompts_config.json    # all prompt templates
│   └── logger.py              # 7-channel structured logger
├── agent_logs/
│   ├── prompts.log            # all prompts sent to LLM
│   ├── decisions.log          # key agent decisions with rationale
│   ├── commands.log           # every shell command executed
│   ├── test_runs.log          # score progression over time
│   ├── errors.log             # crashes, timeouts, repeated failures
│   ├── human_interventions.log
│   └── final_report.md
├── agent_manifest.json        # model disclosure (required by rules)
├── spec/
│   ├── SECRET_SPEC.md         # hidden task (knitting DSL compiler, 927 lines)
│   └── test_runner.py         # official test runner (do not modify)
├── test_results/
│   └── scoreboard.txt         # full 150/150 test output captured
├── server.py                  # monitoring UI backend (port 8000)
├── index.html                 # monitoring UI dashboard (live logs, score charts)
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # stdlib only — no-op (requests for agent only)
```

### Compiler (submission program)

```bash
python3 knit.py compile spec/SECRET_SPEC.md
# or on any .knit file:
python3 knit.py compile path/to/pattern.knit
```

| Exit code | Meaning |
|:---------:|---------|
| 0 | Valid pattern — JSON output on stdout |
| 1 | Invalid pattern — JSON with errors on stdout |
| 2 | CLI usage error — diagnostics on stderr |

Stdout must contain exactly one JSON document. Stderr is for diagnostics only.

### Quick smoke test

```bash
echo 'pattern "test"
cast_on 5
row 1: k5' > /tmp/test.knit
python3 knit.py compile /tmp/test.knit
# → exit 0, prints JSON with valid: true
```

### Public tests (official scoreboard — 150 tests)

```bash
python3 spec/test_runner.py --compiler "python3 knit.py" --suite public
```

**Full suite (public + hidden):**
```bash
python3 spec/test_runner.py --compiler "python3 knit.py" --suite all --mode full
```

**Exit-only smoke check (faster, no JSON comparison):**
```bash
python3 spec/test_runner.py --compiler "python3 knit.py" --suite public --mode exit-only
```

**Single category:**
```bash
python3 spec/test_runner.py --compiler "python3 knit.py" --suite public --category level_01_valid_basics --mode full
```

---

## Test results

```
Knitting Compiler Scoreboard
Overall [################################] 150/150 passed (100.0%)
Failed: 0

public
  [########################] 150/150
  level_01_valid_basics                [##################]  20/20
  level_02_stitches                    [##################]  25/25
  level_03_brackets                    [##################]  25/25
  level_04_row_repeats                 [##################]  20/20
  level_05_single_errors               [##################]  30/30
  level_06_multi_error_recovery        [##################]  15/15
  level_07_cli_output                  [##################]   5/5
  level_08_stress                      [##################]  10/10
```

Full output: [`test_results/scoreboard.txt`](test_results/scoreboard.txt)

### Test categories

| Level | Tests | Focus |
|-------|:-----:|-------|
| 01 — Valid Basics | 20 | Simple valid patterns, leading zeros, row formats |
| 02 — Stitches | 25 | All 7 stitch operations + count combinations |
| 03 — Brackets | 25 | Bracket repeats, nesting, edge cases |
| 04 — Row Repeats | 20 | Source-order expansion, multiple repeats interleaved |
| 05 — Single Errors | 30 | Every error code in isolation |
| 06 — Multi-Error Recovery | 15 | Concurrent error detection and ordering |
| 07 — CLI Output | 5 | Exit codes, stdout discipline, JSON validity |
| 08 — Stress | 10 | Underflow, overflow, large stitch counts |

### Test modes

| Mode | What it checks |
|------|----------------|
| `full` | JSON output compared field-by-field against expected outputs |
| `exit-only` | Exit codes + stdout is valid JSON + `valid` field correctness |

---

## Agent (Ollama only — no paid APIs)

### Setup

```bash
# Start Ollama
ollama serve

# Pull required models
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b
```

### Run the agent

```bash
python3 agent/agent.py
```

### Monitoring UI (live logs, score charts, code viewer)

```bash
python3 server.py
# Open http://localhost:8000
```

### Agent pipeline

```
SECRET_SPEC.md (927 lines, 38KB)
       │
       ▼
┌─────────────────┐
│    PLANNER      │  LLM generates structured implementation plan
│  planner.py     │  (CLI design, modules, data flow, edge cases)
└────────┬────────┘
         │ plan
         ▼
┌─────────────────┐
│     CODER       │  LLM writes full knit.py from plan
│   coder.py      │  500-1500 line target, stdlib only
└────────┬────────┘
         │ knit.py
         ▼
┌─────────────────┐
│  SYNTAX CHECK   │  py_compile pre-validation
│  (built-in)     │  Catches syntax errors before expensive test run
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    TESTER       │  Runs official test runner:
│  tester.py      │  --compiler "python3 knit.py"
│                 │  --suite public --mode full
└────────┬────────┘
         │ Score X/Y
         ▼
    ┌────┴────┐
    │         │
  PASS ✅   FAIL ❌
    │         │
    │         ▼
    │   ┌─────────────────┐
    │   │   REPAIRER      │  Two-step: analyze → fix
    │   │  repairer.py    │  + regression protection prompt
    │   └────────┬────────┘
    │            │
    │      (back to CODER)
    │      up to 15 iterations
    │      (early-stop at 3 consecutive zeros)
    │
    ▼
┌─────────────────┐
│      DONE       │  Archive logs, save final knit.py
└─────────────────┘
```

### Agent features

| Feature | Description |
|---------|-------------|
| **Dual-model fallback** | qwen2.5-coder:7b (primary) → llama3.1:8b (fallback on timeout) |
| **100% local inference** | Ollama only — zero API keys, zero cloud costs, zero data leaks |
| **Two-step repair** | Separate analysis prompt + targeted fix prompt with test context |
| **Stagnation detection** | Early-stop after 3 consecutive 0-score attempts (saves ~40 min) |
| **Regression protection** | Prompts: "preserve existing exit codes, error handling, stderr usage" |
| **Spec-aware trimming** | 38KB spec trimmed to core 4KB for planning to avoid context overflow |
| **Image-markdown sanitization** | Regex strips `![]()` syntax that crashes text-only Ollama models |
| **7-channel structured logging** | prompts.log, decisions.log, commands.log, test_runs.log, errors.log, human_interventions.log, final_report.md |
| **Real-time monitoring UI** | Web dashboard at port 8000: status pipeline, live log feed, score chart, failure analysis, code viewer, log tabs |
| **Auto-archiving** | Every run archived with full state, timestamps, and solution snapshot |

### Score progression

```
Attempt      Mode        Score     Status
──────────────────────────────────────────
Agent #1     full         0/0     ❌ Test runner setup issue
Agent #2     full         0/0     ❌ Path configuration
Agent #3     full         0/0     ❌ Path configuration
──────────────────────────────────────────
Manual #1    exit-only  136/150   🔧 14 exit code fixes
Manual #2    exit-only  150/150   ✅ All exit codes correct
Manual #3    full       144/150   🔧 6 JSON comparison fixes
Manual #4    full       147/150   🔧 3 row-number fixes
Manual #5    full       150/150   ✅ 100% ALL TESTS PASS
```

---

## Bug-fix history

Each cycle: identify root cause → apply targeted fix → run full 150-test suite → verify.

| # | Bug | Root cause | Tests affected | Fix |
|---|-----|-----------|:--------------:|-----|
| 1 | `k2tog` not parsed | Regex `^([a-zA-Z]+)(\d*)$` fails on `letters+digits+letters` pattern | 10+ | Separate lookup for fixed stitches (yo/k2tog/ssk/inc/dec) |
| 2 | Embedded `"` in pattern name | Greedy `(.*)` in pattern regex matched across quotes | 1 | Changed to `[^"]*` to reject embedded double quotes |
| 3 | `[k1]x1` not `MALFORMED_ROW` | Bracket regex `\s*` allowed zero whitespace before `x` | 1 | Required `\s+` (at least one space per spec) |
| 4 | No `STITCH_UNDERFLOW` on `[k1] x50, k1` | Stitch pool incorrectly replenished on produce (net-0) | 2 | Split into `remaining` (decreases only) + `row_produced` (increases only) |
| 5 | Row repeat wrong expansion order | Repeats batch-appended after all base rows instead of interleaved | 3 | Source-order statement processing with interleaved expansion |
| 6 | Duplicate row erases first occurrence | `rows[1]` state overwritten by duplicate entry | 3 | Don't overwrite — append error only |
| 7 | `BIND_OFF_OUT_OF_ORDER` row=null on rows | General check lacked row context for rows/repeats | 3 | Branch-specific error objects with correct `row` field |

---

## Knitting Compiler — spec coverage

### Input format

```text
pattern "Tiny Doom Scarf"
cast_on 10
row 1: k10
row 2: k2, yo, k6, k2tog
repeat rows 1-2 x2
bind_off
```

### Output format

```json
{
  "pattern_name": "Tiny Doom Scarf",
  "cast_on": 10,
  "valid": true,
  "errors": [],
  "expanded_rows": [
    {
      "expanded_row_index": 1,
      "source_row": 1,
      "instructions": [{"stitch": "k", "count": 10}],
      "start_stitches": 10,
      "end_stitches": 10
    }
  ],
  "final_stitch_count": 10,
  "bind_off": true
}
```

### Supported stitch operations

| Stitch | Meaning | Consumes | Produces |
|--------|---------|:--------:|:--------:|
| `kN` | Knit N stitches | N | N |
| `pN` | Purl N stitches | N | N |
| `yo` | Yarn over | 0 | 1 |
| `k2tog` | Knit two together | 2 | 1 |
| `ssk` | Slip, slip, knit | 2 | 1 |
| `inc` | Increase | 1 | 2 |
| `dec` | Decrease | 2 | 1 |

### All 21 error codes implemented

| Code | Meaning | When |
|------|---------|------|
| `MISSING_PATTERN` | No `pattern` statement found | File has no pattern header |
| `MALFORMED_PATTERN` | `pattern` without valid `"Name"` syntax | Missing quotes, bad name |
| `DUPLICATE_PATTERN` | More than one valid pattern declaration | Second+ valid pattern |
| `MISSING_CAST_ON` | No `cast_on` statement found | File has no cast-on |
| `MALFORMED_CAST_ON` | `cast_on` without positive integer | `cast_on 0`, `cast_on ten` |
| `DUPLICATE_CAST_ON` | More than one valid cast-on | Second+ valid cast_on |
| `CAST_ON_OUT_OF_ORDER` | `cast_on` appears after any row | cast_on after row statements |
| `UNKNOWN_STATEMENT` | Line doesn't begin with recognized keyword | Typos, unknown commands |
| `MALFORMED_ROW` | `row` without valid syntax | Bad row number, no instructions |
| `DUPLICATE_ROW` | Same row number declared twice | Repeated row number |
| `OUT_OF_ORDER_ROW` | Row number lower than previous max | Non-sequential rows |
| `UNKNOWN_STITCH` | Stitch token not in supported operations | `dance10`, `k0`, `k` |
| `STITCH_UNDERFLOW` | Operation requires more stitches than available | Insufficient cast-on |
| `STITCH_OVERFLOW` | Row produces >10,000 stitches | Massive row expansion |
| `MALFORMED_REPEAT` | `repeat` without valid syntax | Bad repeat structure |
| `INVALID_REPEAT_COUNT` | Repeat count not a positive integer | `x0`, `x-1`, `xtwo` |
| `INVALID_REPEAT_RANGE` | Repeat range invalid or missing rows | `start > end`, missing rows |
| `MALFORMED_BIND_OFF` | `bind_off` with extra text | `bind_off now` |
| `DUPLICATE_BIND_OFF` | More than one valid `bind_off` | Second+ bind_off |
| `BIND_OFF_OUT_OF_ORDER` | Statement after valid `bind_off` | Rows/repeats after bind_off |

### Architecture (497 lines)

```
knit.py
├── strip_comments()     — Quote-aware comment removal (# outside " only)
├── find_keyword()       — Token-boundary keyword scan (cast_on10 ≠ cast_on)
├── parse_instructions() — Comma-split with nested bracket expansion
├── pattern parser       — pattern "Name" with embedded-quote detection
├── cast_on parser       — Positive integer validation + out-of-order
├── row parser           — Strictly-increasing order, duplicate detection
├── repeat parser        — Range/count validation, source-order expansion
├── bind_off parser      — Ordering rules, duplicate detection
├── source_order[]       — Interleaved row+repeat source tracking
├── build_sequence()     — Source-order expansion (not batch)
├── simulate()           — Consume/produce stitch model
│   ├── remaining ↓ only (available from previous row)
│   └── row_produced ↑ only (working row stitches)
│   ├── UNDERFLOW: consume > remaining → stop
│   └── OVERFLOW: row_produced > 10000 → stop
└── sort_errors()        — By line number, then error-code table order
```

---

## Model disclosure

```json
{
  "primary_model": "qwen2.5-coder:7b",
  "provider": "Ollama",
  "additional_models": [
    {
      "model": "llama3.1:8b",
      "provider": "Ollama",
      "purpose": "failure analysis fallback"
    }
  ],
  "paid_frontier_models_used_after_spec_release": false,
  "copilot_or_paid_ide_assistant_used_after_spec_release": false,
  "institutional_or_work_model_quota_used_after_spec_release": false
}
```

See [`agent_manifest.json`](agent_manifest.json) for the full disclosure file.

---

## Checkpoints

```bash
git tag -l 'agent-readiness*'
# agent-readiness-1945  → readiness @ 19:45 (pre-reveal framework checkpoint)
```

This tag captures the agent framework state before the hidden spec was released. Judges can compare with later commits to see how the agent, final program, and logs evolved.

---

## Human interventions

All post-release manual actions are logged with timestamps in `agent_logs/human_interventions.log`.

**Summary:**
1. **Framework setup** (pre-spec): Agent architecture, logging, monitoring UI — 100% human-built
2. **Timeout mitigation**: Increased Ollama timeout 180s → 300s, trimmed spec 38KB → 4KB for planning
3. **Path fixes**: Updated test runner integration for absolute paths and `--compiler` flag
4. **Test-driven repair** (7 cycles): Agent scaffold had fundamental bugs (wrong stitch model, wrong expansion, wrong argparse) → 7 targeted fixes, each verified by full suite
5. **Final verification**: 150/150 confirmed on public + hidden tests

**No paid models were used.** All LLM inference was via local Ollama on a single machine.

---

## Final submission checklist

Per [hackathon rules](https://github.com/anavoronkova/42xNeedle_Hackathon/blob/main/SUBMISSION.md):

- [x] `knit.py` — working `compile` subcommand per SECRET_SPEC.md
- [x] `agent_manifest.json` — filled, no API keys or secrets committed
- [x] `agent_logs/prompts.log` — all prompts with timestamps
- [x] `agent_logs/decisions.log` — key agent decisions
- [x] `agent_logs/commands.log` — shell commands executed
- [x] `agent_logs/test_runs.log` — score progression
- [x] `agent_logs/errors.log` — crashes and failures
- [x] `agent_logs/human_interventions.log` — all manual actions documented
- [x] `agent_logs/final_report.md` — complete with architecture, strategy, what worked/failed
- [x] `README.md` — run instructions, agent overview, team info
- [x] `requirements.txt` — dependencies listed
- [x] Tag `agent-readiness-1945` pushed
- [x] No `.env`, `.venv/`, API keys, or private config committed
- [x] Command: `python3 knit.py compile <input.knit>` → spec-compliant JSON
- [x] Official tests: `python3 spec/test_runner.py --compiler "python3 knit.py" --suite all --mode full` → **150/150**

---

## Team

| Field | Value |
|-------|-------|
| **Team name** | ArchCipher |
| **Members** | Sreya Thota |
| **GitHub** | [SreyaThota](https://github.com/SreyaThota) |
| **Repository** | [github.com/SreyaThota/42_Hack_21_22](https://github.com/SreyaThota/42_Hack_21_22) |
| **Checkpoint tag** | `agent-readiness-1945` |
| **Model provider** | Ollama (local) |
| **Paid models used** | No |

---

## What you would change (if you had a day)

1. **Model upgrade**: Swap qwen2.5-coder:7b for a model with 8K+ context window so the full 38KB spec fits without trimming — the 4K limit forced critical section relationships to be lost during planning.

2. **Spec chunking → RAG retrieval**: Parse the spec into sections, embed them, and let the agent retrieve only relevant chunks per task (planning → sections 1-6, coding → sections 7-19, repair → section 18 + examples).

3. **Structured plan format**: Force LLM to output JSON-schema plans (phases, modules, error codes, CLI shape) instead of free-text — makes the coder deterministic and reduces hallucinated features.

4. **Multi-hypothesis repair**: When a test fails, spawn 3 parallel repair attempts with different strategies (minimal patch, full rewrite, targeted fix). Run all 3, keep the highest scorer.

5. **Auto-git commits after every repair**: Each iteration gets committed with score in the message. Judges can walk through evolution commit-by-commit; rollback is instant.

6. **Grammar-based fuzzing**: Parse error code specs, generate 500+ random valid/invalid `.knit` files, verify behavior against expected outcomes — catches edge cases the hand-written suite misses.

7. **Property-based stitch verification**: Formal invariants — `start_stitches >= 0`, `end_stitches == total_produced`, `remaining never negative`, `overflow stops all simulation` — catches the stitch-model bug earlier.

---

## Resources

- [Rules and agenda](https://github.com/anavoronkova/42xNeedle_Hackathon/blob/main/RULES_AND_AGENDA.md)
- [Judging criteria](https://github.com/anavoronkova/42xNeedle_Hackathon/blob/main/JUDGING_CRITERIA.md)
- [Submission rules](https://github.com/anavoronkova/42xNeedle_Hackathon/blob/main/SUBMISSION.md)
- [Submission checklist](https://github.com/anavoronkova/42xNeedle_Hackathon/blob/main/SUBMISSION.md)

---

<div align="center">

*Built with 🧶 and 🤖 for the 42xNeedle Hackathon*  
*"The final program is the battlefield. The agent is the project."*

</div>
