# ArchCipher — autonomous coding agent (42 × Needle hackathon)

A hackathon project: a plan → code → test → repair loop that runs on **local LLMs only** (Ollama: `qwen2.5-coder:7b`, with `llama3.1:8b` for failure analysis) and was pointed at a hidden task, a compiler for a small knitting DSL (`python3 knit.py compile <file.knit>` → JSON).

**Team:** 3 people (team SPARK). **My part:** the isolated compiler v2 pipeline, merged into the team repository ([PR](https://github.com/ArchCipher/42xNeedle_Hackathon/pull/1)). This repository holds the agent framework, logs and the final compiler.

## What is in this repo

| Path | What it is |
|---|---|
| `agent/` | The agent loop: planner, coder, tester, repairer, Ollama client, prompt templates, structured logger |
| `knit.py` | The compiler entry point (stdlib only, ~500 lines) |
| `agent_logs/` | Prompts, decisions, commands, test-run history, errors, human interventions, final report |
| `agent_manifest.json` | Model disclosure required by the hackathon rules |
| `server.py`, `index.html` | Small local dashboard for live logs and score history |
| `spec/` | **Organizers' material** (task spec and test runner), kept for context. Not my work |

## Results — what can and cannot be verified from this repo

- The score reported during the event was **150/150 on the organizers' public test suite**. The test cases and the saved scoreboard are **not included in this repository**, so that number **cannot be reproduced from this repo alone**. The hidden-test result was reported by the organizers' runner and is not documented here.
- The agent's own end-to-end runs did **not** produce a passing compiler. The final `knit.py` was reached through seven manual, test-driven repair cycles; the full history is in `agent_logs/human_interventions.log` and `agent_logs/final_report.md`. Treat this as a framework that supported the work, not as an agent that solved the task on its own.

## Run the agent

```bash
ollama pull qwen2.5-coder:7b && ollama pull llama3.1:8b
pip install -r requirements.txt
python3 agent/agent.py          # needs the organizers' spec and test runner in spec/
python3 server.py               # dashboard at http://localhost:8000
```

## Design notes

- Local inference only (no paid APIs), with a fallback model on timeout.
- Spec trimming for the planning prompt, because the full spec exceeded the small models' context.
- Stagnation detection: stop after three consecutive zero-score attempts.
- Separate analysis and fix prompts in the repair step.

## Limitations

- Small local models struggled with a long specification; most of the progress came from human-guided repair.
- The task spec and test runner belong to the hackathon organizers and have no licence; they are included only as hackathon context.
