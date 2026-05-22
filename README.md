# 🧶 Knitting Compiler — 42xNeedle Hackathon

<div align="center">

```
  ╔══════════════════════════════════════════════════╗
  ║     150/150 · 100% · 21 Error Codes · 8 Levels  ║
  ╚══════════════════════════════════════════════════╝
```

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-Local-000?logo=ollama)](https://ollama.com)
[![Tests](https://img.shields.io/badge/Tests-150%2F150-2ea44f?logo=github)](test_results/scoreboard.txt)
[![License](https://img.shields.io/badge/License-MIT-f39f37)](LICENSE)

**A DSL compiler + autonomous coding agent — built entirely with local LLMs**

</div>

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [The Knitting Compiler](#-the-knitting-compiler)
- [The SPRK Agent](#-the-sprk-agent)
- [Repository Structure](#-repository-structure)
- [Test Results](#-test-results)
- [Score Progression](#-score-progression)
- [Agent Readiness Checkpoint](#-agent-readiness-checkpoint)
- [How to Reproduce](#-how-to-reproduce)
- [What Makes This Stand Out](#-what-makes-this-stand-out)
- [License](#-license)

---

## 🚀 Quick Start

```bash
# 1. Run the compiler
python knit.py compile examples/scarf.knit

# 2. Run the full test suite
python spec/test_runner.py --compiler "python knit.py" --suite all --mode full

# 3. Or just check exit codes (faster)
python spec/test_runner.py --compiler "python knit.py" --suite public --mode exit-only
```

**Python version:** 3.11+  
**Dependencies:** None — pure Python stdlib (`argparse`, `json`, `re`, `sys`)  
**Exit codes:** `0` = valid, `1` = invalid, `2` = CLI error

### To Run the Agent

```bash
# Requires Ollama with models:
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b

# Start monitoring UI
python server.py
# Open http://localhost:8000

# Run agent
python agent/agent.py
```

---

## 🧶 The Knitting Compiler

A command-line tool that parses knitting pattern files (`.knit` DSL), validates them, performs full error recovery, expands repeats, and simulates stitch counts — outputting structured JSON.

### Input Format

```text
pattern "Tiny Doom Scarf"
cast_on 10
row 1: k10
row 2: k2, yo, k6, k2tog
repeat rows 1-2 x2
bind_off
```

### Output Format

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

### Supported Stitch Operations

| Stitch | Meaning | Consumes | Produces |
|--------|---------|:--------:|:--------:|
| `kN` | Knit N stitches | N | N |
| `pN` | Purl N stitches | N | N |
| `yo` | Yarn over | 0 | 1 |
| `k2tog` | Knit two together | 2 | 1 |
| `ssk` | Slip, slip, knit | 2 | 1 |
| `inc` | Increase | 1 | 2 |
| `dec` | Decrease | 2 | 1 |

### All 21 Error Codes

| Code | Meaning |
|------|---------|
| `MISSING_PATTERN`, `MALFORMED_PATTERN`, `DUPLICATE_PATTERN` | Pattern header |
| `MISSING_CAST_ON`, `MALFORMED_CAST_ON`, `DUPLICATE_CAST_ON`, `CAST_ON_OUT_OF_ORDER` | Cast-on |
| `MALFORMED_ROW`, `DUPLICATE_ROW`, `OUT_OF_ORDER_ROW` | Row validation |
| `UNKNOWN_STITCH` | Invalid stitch |
| `STITCH_UNDERFLOW`, `STITCH_OVERFLOW` | Simulation errors |
| `MALFORMED_REPEAT`, `INVALID_REPEAT_COUNT`, `INVALID_REPEAT_RANGE` | Repeats |
| `MALFORMED_BIND_OFF`, `DUPLICATE_BIND_OFF`, `BIND_OFF_OUT_OF_ORDER` | Bind-off |
| `UNKNOWN_STATEMENT` | Unrecognized keyword |

### Architecture

```
knit.py (497 lines)
├── strip_comments()     — Quote-aware comment removal (# outside " only")
├── find_keyword()       — Token-boundary keyword scan (cast_on10 ≠ cast_on)
├── parse_instructions() — Comma-split with bracket expansion (nested supported)
├── Statement parsers    — pattern, cast_on, row, repeat, bind_off
├── source_order[]       — Interleaved row+repeat source order tracking
├── build_sequence()     — Source-order expansion (not batch)
├── simulate()           — Accurate consume/produce stitch model
│   ├── remaining ↓ only (available from previous row)
│   └── row_produced ↑ only (working row stitches)
├── sort_errors()        — By line number, then error-code table order
└── main()               — argparse subcommand "compile"
```

---

## 🤖 The SPRK Agent

### What is SPRK?

**SPRK** (Systematic Problem Resolution through Knowledge) is an autonomous coding agent that:

1. **Reads** a technical specification it hasn't seen before
2. **Plans** an implementation strategy
3. **Writes** code
4. **Runs** the official test suite
5. **Inspects** failures
6. **Repairs** mistakes
7. **Reruns** tests
8. **Logs** everything with timestamps

### Agent Pipeline

```
SECRET_SPEC.md           The hidden specification (927 lines, 38KB)
       │
       ▼
┌─────────────────┐
│    PLANNER      │  LLM generates structured implementation plan
│  planner.py     │  with CLI design, data flow, edge cases
└────────┬────────┘
         │ plan
         ▼
┌─────────────────┐
│     CODER       │  LLM writes knit.py from plan
│   coder.py      │  500-1500 line target, stdlib only
└────────┬────────┘
         │ knit.py
         ▼
┌─────────────────┐
│  SYNTAX CHECK   │  py_compile pre-validation
│  (built-in)     │  Catches syntax errors before test run
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    TESTER       │  Runs official test runner:
│  tester.py      │  --compiler "python knit.py"
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
    │   │  repairer.py    │  With regression protection
    │   └────────┬────────┘
    │            │ fixed code
    │            ▼
    │     (back to TESTER)
    │     up to 15 iterations
    │
    ▼
┌─────────────────┐
│      DONE       │  Archive logs, save final knit.py
└─────────────────┘
```

### Key Agent Features

| Feature | Description |
|---------|-------------|
| **Dual-model fallback** | qwen2.5-coder:7b → llama3.1:8b on timeout |
| **100% local** | Ollama only — no API keys, no cloud costs |
| **Smart repair** | Separate analysis + fix prompts with test context |
| **Stagnation detection** | Early-stop after 3 zero-score attempts |
| **Regression protection** | Prompts: "preserve existing exit codes, error handling" |
| **7-channel logging** | prompts.log, decisions.log, commands.log, test_runs.log, errors.log, human_interventions.log, final_report.md |
| **Real-time UI** | Web dashboard at port 8000 with live logs, score charts |
| **Auto-archive** | Each run archived with full state for reproducibility |

### Model Disclosure

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

See [`agent_manifest.json`](agent_manifest.json) for full disclosure.

---

## 📁 Repository Structure

```
📦 42_Hack_21_22
├── 📄 README.md                    ← This file
├── 📄 knit.py                      ← The compiler (497 lines, stdlib only)
├── 📄 agent_manifest.json          ← Model disclosure
├── 📄 requirements.txt             ← Dependencies (none required)
├── 📄 server.py                    ← Monitoring UI server
├── 📄 index.html                   ← Monitoring UI dashboard
│
├── 📁 agent/                       ← SPRK agent framework
│   ├── 📄 agent.py                 ← Main orchestration loop
│   ├── 📄 planner.py               ← Spec reader + plan generator
│   ├── 📄 coder.py                 ← Plan→code translator
│   ├── 📄 tester.py                ← Test runner integration
│   ├── 📄 repairer.py              ← Failure analysis + fix engine
│   ├── 📄 ollama_client.py         ← Local LLM client (qwen/llama)
│   ├── 📄 prompts.py               ← Prompt template loader
│   ├── 📄 prompts_config.json      ← All prompt templates
│   └── 📄 logger.py               ← 7-channel structured logger
│
├── 📁 agent_logs/                  ← Required by hackathon rules
│   ├── 📄 prompts.log              ← All prompts sent to LLM
│   ├── 📄 decisions.log            ← Key agent decisions
│   ├── 📄 commands.log             ← Shell commands executed
│   ├── 📄 test_runs.log            ← Score progression
│   ├── 📄 errors.log               ← Crashes and failures
│   ├── 📄 human_interventions.log  ← All manual actions logged
│   └── 📄 final_report.md          ← This report
│
├── 📁 spec/                        ← Hackathon materials
│   ├── 📄 SECRET_SPEC.md           ← Hidden specification
│   └── 📄 test_runner.py           ← Official test runner
│
├── 📁 test_results/                ← Evidence
│   └── 📄 scoreboard.txt           ← Full 150/150 test output
│
└── 📁 archives/                    ← Agent run snapshots
```

---

## 📊 Test Results

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

### Test Categories

| Level | Tests | Focus |
|-------|:-----:|-------|
| 01 — Valid Basics | 20 | Simple valid patterns, leading zeros, row formats |
| 02 — Stitches | 25 | All 7 stitch operations + count combinations |
| 03 — Brackets | 25 | Bracket repeats, nesting, edge cases |
| 04 — Row Repeats | 20 | Source-order expansion, multiple repeats |
| 05 — Single Errors | 30 | Each error code in isolation |
| 06 — Multi-Error Recovery | 15 | Detecting multiple errors concurrently |
| 07 — CLI Output | 5 | Exit codes, stdout discipline, JSON validity |
| 08 — Stress | 10 | Underflow, overflow, large patterns |

---

## 📈 Score Progression

```
Attempt      Mode        Score     Status
──────────────────────────────────────────
Agent #1     full         0/0     ❌ Test runner setup
Agent #2     full         0/0     ❌ Test runner setup
Agent #3     full         0/0     ❌ Test runner setup
──────────────────────────────────────────
Manual #1    exit-only  136/150   🔧 14 exit code fixes
Manual #2    exit-only  150/150   ✅ All exit codes correct
Manual #3    full       144/150   🔧 6 JSON comparison fixes
Manual #4    full       147/150   🔧 3 row-number fixes
Manual #5    full       150/150   ✅ 100% ALL TESTS PASS
```

Each manual fix was test-driven: one bug identified → one fix applied → full suite ran.

---

## 🏷 Agent Readiness Checkpoint

**Tag:** `agent-readiness-1945`

The SPRK agent framework was committed and tagged at 19:45 on May 21, before the hidden task release.

```bash
git tag agent-readiness-1945
```

This checkpoint captures the pre-reveal agent setup:
- Read-plan-code-test-repair pipeline
- Ollama integration with dual-model fallback
- 7-channel logging infrastructure
- Monitoring UI
- Self-test generation

---

## 🔬 Bug-Fix History

| # | Bug | Root Cause | Fix | Tests |
|---|-----|-----------|-----|-------|
| 1 | `k2tog` not parsed | Regex `^([a-zA-Z]+)(\d*)$` fails on `letters-digits-letters` | Fixed-stitch lookup table | 10+ |
| 2 | Embedded `"` in pattern name | Greedy `(.*)` matched across quotes | `[^"]*` regex | 1 |
| 3 | `[k1]x1` not MALFORMED | Bracket regex allowed `\s*` before `x` | Required `\s+` (at least one space) | 1 |
| 4 | No underflow on `[k1]x50,k1` | Stitch pool replenished on produce (net-0) | Split: `remaining` decr. + `row_produced` incr. | 2 |
| 5 | Row repeat wrong order | Repeats batch-appended after all rows | Source-order interleaved expansion | 3 |
| 6 | Duplicate row erases first | `rows[1]` overwritten by duplicate | Don't overwrite — just add error | 3 |
| 7 | BIND_OFF row=null on rows | General check lacked row context | Branch-specific error with row number | 3 |

---

## 🎯 How to Reproduce

```bash
# 1. Clone
git clone https://github.com/SreyaThota/42_Hack_21_22.git
cd 42_Hack_21_22

# 2. Run the compiler
python knit.py compile spec/SECRET_SPEC.md  # (not a real .knit file — see examples below)

# 3. Test a valid pattern
echo 'pattern "test"
cast_on 5
row 1: k5' > test.knit
python knit.py compile test.knit
# → exit 0, valid JSON

# 4. Test an invalid pattern
echo 'pattern test' > bad.knit
python knit.py compile bad.knit
# → exit 1, JSON with errors

# 5. Run the official test suite
python spec/test_runner.py --compiler "python knit.py" --suite all --mode full
```

### Running the Agent

```bash
# Requires Ollama with models:
ollama serve
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b

# Run agent:
python agent/agent.py

# Monitor at http://localhost:8000
python server.py
```


## 📜 License

MIT — Use freely, learn from it, improve upon it.

---

<div align="center">

```
  ╔══════════════════════════════════════════════════════════╗
  ║  Built with 🧶 and 🤖 for the 42xNeedle Hackathon       ║
  ║  "The final program is the battlefield.                 ║
  ║   The agent is the project."                            ║
  ╚══════════════════════════════════════════════════════════╝
```

**Team:** SreyaThota · **Repository:** [github.com/SreyaThota/42_Hack_21_22](https://github.com/SreyaThota/42_Hack_21_22)

</div>
