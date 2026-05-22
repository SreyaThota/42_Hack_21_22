# Final Report — SPRK Agent

**Team:** SreyaThota  
**Generated:** 2026-05-22 10:30  
**Repository:** github.com/SreyaThota/42_Hack_21_22

---

## Models Used

| Model | Provider | Purpose |
|-------|----------|---------|
| qwen2.5-coder:7b | Ollama (local) | Primary — code generation, planning |
| llama3.1:8b | Ollama (local) | Fallback — failure analysis, test review |

**Paid frontier models used after spec release:** No  
**Copilot or paid IDE assistant used:** No  
**Institutional/work model quota used:** No

---

## Tools Available to the Agent

- Ollama local API (http://localhost:11434)
- Python 3.11+
- subprocess, requests, json, re, argparse (stdlib)
- py_compile syntax pre-validation
- Self-test generation via LLM
- Real-time monitoring UI at port 8000
- 7-channel structured logging (prompts, decisions, commands, test runs, errors, interventions, final report)

---

## Agent Architecture

SPRK (Systematic Problem Resolution through Knowledge) is a read-plan-code-test-repair loop:

### Pipeline

```
┌──────────────────────────────────────────────────┐
│ 1. READ SPEC                                     │
│    └─ Parses SECRET_SPEC.md (927 lines, 38KB)    │
├──────────────────────────────────────────────────┤
│ 2. PLAN                                          │
│    └─ LLM generates structured implementation    │
│       strategy with CLI design, data flow,       │
│       edge cases                                 │
├──────────────────────────────────────────────────┤
│ 3. CODE                                          │
│    └─ LLM writes knit.py from plan               │
│       (500-1500 line target, stdlib only)        │
├──────────────────────────────────────────────────┤
│ 4. VALIDATE SYNTAX                               │
│    └─ py_compile pre-check before test run       │
├──────────────────────────────────────────────────┤
│ 5. TEST                                          │
│    └─ Runs official test runner:                 │
│       python spec/test_runner.py                 │
│       --compiler "python knit.py"                │
│       --suite public --mode full                 │
├──────────────────────────────────────────────────┤
│ 6. ANALYZE FAILURES                              │
│    └─ Extracts failure patterns from test output │
│       Determines root cause category             │
├──────────────────────────────────────────────────┤
│ 7. REPAIR                                        │
│    └─ Two-step: analysis prompt → fix prompt     │
│       Test command context included              │
│       Regression prevention in prompt            │
├──────────────────────────────────────────────────┤
│ 8. REPEAT 3-7 (up to 15 iterations)             │
│    └─ Early-stop after 3 consecutive zeros       │
│       Stagnation-based rewrite after 3 no-       │
│       progress repairs                           │
└──────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Dual-model fallback**: qwen2.5-coder:7b for generation, llama3.1:8b for review/fallback. If primary times out (180s→300s), fallback activates automatically.

2. **Spec trimming**: 38KB spec caused model timeouts. Planner trimmed to core requirements (first 4KB) for initial planning. Full spec available for coding step.

3. **Image-markdown sanitization**: Text-only Ollama models crash on `![](...)` or `<img>` syntax — regex stripping applied to all prompts.

4. **Two-step repair**: Separate analysis prompt extracts root cause, then fix prompt applies targeted correction — prevents context-window overload.

5. **Regression protection**: Repair prompts explicitly say "do NOT remove existing exit codes, error handling, stderr usage, input validation that already works."

6. **Stagnation detection**: 3 consecutive 0-score attempts → stop early (saves ~40 min). 3 repairs without score improvement → rewrite from original plan.

---

## Prompting Strategy

### Planning Prompt
Structured request for: requirements summary → CLI design → execution flow → edge cases → assumptions. No code output.

### Coding Prompt
Direct translation: plan → implementation. Constraints: stdlib only, subcommand-based CLI, JSON output, exact exit codes. Raw Python output — no markdown, no backticks.

### Repair Prompt
Input: test failures + current code + test command. Instruction: fix specific failure without rewriting working code. Regression prevention included.

### Self-Test Prompt
Generates edge-case tests beyond public suite to catch regressions and uncover subtle bugs.

---

## Test Strategy

### Test Suite
- **150 total tests** (public + hidden)
- **8 levels**: basics, stitches, brackets, row repeats, single errors, multi-error recovery, CLI output, stress
- **Two modes**: exit-only (smoke check) and full (JSON field-by-field comparison)

### Bug-Fix Cycles

| Cycle | Issue | Tests Affected | Method |
|-------|-------|----------------|--------|
| 1 | k2tog/ssk regex failed on letters-digits-letters | 10+ | Separate fixed-stitch lookup |
| 2 | Pattern name allowed embedded `"` | 1 | Changed to `[^"]*` |
| 3 | `[k1]x1` not MALFORMED (missing space) | 1 | `\s+` instead of `\s*` |
| 4 | Wrong stitch simulation model | 2 | Split tracking into remaining + produced |
| 5 | Row repeat batch expansion | 3 | Source-order interleaved processing |
| 6 | Duplicate row overwrote first occurrence | 3 | Don't overwrite state |
| 7 | BIND_OFF_OUT_OF_ORDER row=null on rows | 3 | Branch-specific row context |

### Score Progression

```
Agent iteration 1: 0/0  (test runner setup issue)
Agent iteration 2: 0/0  (test runner setup issue)
Agent iteration 3: 0/0  (test runner setup issue)
Manual fix cycle 1: 136/150 exit-only (14 exit-code failures)
Manual fix cycle 2: 150/150 exit-only (all exit codes correct)
Manual fix cycle 3: 144/150 full     (6 JSON comparison failures)
Manual fix cycle 4: 147/150 full     (3 row-number failures)
Manual fix cycle 5: 150/150 full     (100% - all tests pass)
```

---

## Human Interventions

See `human_interventions.log` for full details.

**Summary:**
1. Agent framework setup (pre-spec): 100% human
2. Timeout/truncation fixes: increased timeout, trimmed spec
3. Test runner path fixes: --compiler flag, absolute paths
4. Manual implementation of knit.py after agent scaffold proved insufficient
5. 7 test-driven bug-fix cycles to reach 150/150
6. Final verification and repo preparation

**No paid models were used.** All LLM inference was via local Ollama.

---

## What Worked

- **Agent framework**: The SPRK pipeline structure (read → plan → code → test → repair) was sound and caught basic issues
- **Syntax pre-validation**: Prevented wasted test runs on broken code
- **Self-test generation**: Produced additional coverage for edge cases
- **Truncation strategy**: Reducing spec size from 38KB → 4KB made planning feasible
- **Test-driven approach**: Running the official test suite after every change caught regressions immediately
- **Source-order expansion**: Correctly handles interleaved row declarations and repeat statements

## What Failed

- **LLM capability ceiling**: qwen2.5-coder:7b could not correctly implement the stitch simulation model (consume/produce semantics)
- **Spec comprehension**: 38KB spec overwhelmed the model's context window — key section relationships (like simulation depending on cast_on validity) were missed
- **Error recovery complexity**: The model produced correct error codes for simple cases but missed ordering, deduplication, and edge-case interactions
- **Bracket nesting**: LLM code for nested bracket repeats had off-by-one and scope errors
- **Model timeout on large prompts**: Even 300s timeout was insufficient for full-spec planning

## What Would Be Improved

1. **Model**: Use a model with larger context window (8K+ tokens minimum for this spec size)
2. **Spec chunking**: Instead of trimming, use a hierarchical approach — extract keywords first, then parse relevant sections
3. **Structured output**: Require LLM to produce JSON-structured plans for more reliable parsing
4. **Parallel repair hypotheses**: Test multiple repair strategies simultaneously and select best
5. **Commit-based history**: Auto-commit after each repair for full rollback capability
6. **Multi-file output**: Separate compiler into modules for maintainability (already single-file for submission)
7. **PBT (Property-Based Testing)**: Generate random valid/invalid .knit files to find edge cases beyond the test suite

---

## Final Solution

- **File**: `knit.py` (497 lines)
- **CLI**: `python knit.py compile <input_file>`
- **Pass rate**: 150/150 (100%) — all public and hidden tests
- **Dependencies**: None (Python stdlib only: argparse, json, re, sys)
- **Python version**: 3.11+
