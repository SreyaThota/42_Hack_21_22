import sys
import os
import subprocess
import json
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.logger import logger
from agent.planner import read_spec, create_plan
from agent.coder import write_solution
from agent.tester import run_tests
from agent.repairer import analyze_and_fix

MAX_ITERATIONS = 15
ITERATION_TIMEOUT = 600


def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git_init():
    try:
        project_root = get_project_root()
        subprocess.run(["git", "init"], cwd=project_root, capture_output=True, timeout=10)
        subprocess.run(["git", "config", "user.email", "agent@sprk.ai"], cwd=project_root, capture_output=True, timeout=10)
        subprocess.run(["git", "config", "user.name", "SPRK Agent"], cwd=project_root, capture_output=True, timeout=10)
        logger.log_decision("Git repository initialized")
    except Exception as e:
        logger.log_decision(f"Git init skipped: {e}")


def git_commit(score_str, attempt):
    try:
        project_root = get_project_root()
        subprocess.run(["git", "add", "knit.py", "agent_logs/"], cwd=project_root, capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m", f"Auto-commit: score {score_str} after attempt {attempt}", "--allow-empty"], cwd=project_root, capture_output=True, timeout=10)
    except Exception:
        pass


def check_ollama():
    logger.log_decision("Checking Ollama connectivity and models...")
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        needed = ["qwen2.5-coder:7b", "llama3.1:8b"]
        found = [m for m in needed if m in models]
        logger.log_decision(f"Ollama available. Models found: {found}")
        if "qwen2.5-coder:7b" not in models:
            logger.log_error("qwen2.5-coder:7b not pulled. Run: ollama pull qwen2.5-coder:7b")
            print("WARNING: qwen2.5-coder:7b not found. Run 'ollama pull qwen2.5-coder:7b'")
        return True
    except Exception as e:
        logger.log_error(f"Ollama check failed: {e}")
        print(f"WARNING: Cannot reach Ollama at localhost:11434 — {e}")
        return False


def validate_syntax(solution_path):
    if not os.path.exists(solution_path):
        return False, "knit.py not found"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", solution_path],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr or result.stdout
    except Exception as e:
        return False, str(e)


def get_last_archive_path():
    logs_dir = os.path.join(get_project_root(), "agent_logs")
    last_archive_file = os.path.join(logs_dir, ".last_archive")
    if os.path.exists(last_archive_file):
        with open(last_archive_file, "r") as f:
            return f.read().strip()
    return None


def generate_self_tests(spec_content, current_code):
    logger.log_decision("Attempting to generate self-tests...")
    from agent.ollama_client import query_llm
    prompt = (
        "You are a test engineer. Given this specification and code, write additional pytest test cases "
        "that test edge cases NOT covered by a basic happy path.\n"
        f"SPECIFICATION:\n{spec_content[:2000]}\n\n"
        f"CODE:\n{current_code[:3000]}\n\n"
        "Output ONLY Python test functions (def test_*): no markdown, no backticks, no explanation."
    )
    try:
        tests = query_llm(prompt, model="qwen2.5-coder:7b")
        tests = tests.replace("```python", "").replace("```", "").strip()
        if tests:
            project_root = get_project_root()
            test_path = os.path.join(project_root, "agent_logs", "self_tests.py")
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(tests)
            logger.log_decision(f"Self-tests generated ({len(tests)} chars) → agent_logs/self_tests.py")
    except Exception as e:
        logger.log_error(f"Self-test generation skipped: {e}")


def write_final_report(scores, iterations_used):
    project_root = get_project_root()
    report_path = os.path.join(project_root, "agent_logs", "final_report.md")

    lines = [
        "# Final Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Models Used",
        "- Primary: qwen2.5-coder:7b (Ollama)",
        "- Fallback: llama3.1:8b (Ollama)",
        "",
        "## Tools Available",
        "- Ollama local API (http://localhost:11434)",
        "- Python 3.11+",
        "- subprocess, requests",
        "- py_compile syntax validation",
        "- Self-test generation",
        "",
        "## Agent Architecture",
        "The agent uses a read-plan-code-test-repair loop with syntax pre-validation and self-test generation.",
        "It reads the spec, generates an implementation plan via LLM, writes knit.py, ",
        "validates syntax before running the public test suite, and repairs failures in up to 15 iterations.",
        "",
        "## Prompting Strategy",
        "- **Planning**: Structured prompt for CLI interface, inputs/outputs, edge cases, data structures",
        "- **Coding**: Direct implementation with strict output format (raw Python only)",
        "- **Repair**: Failure-context prompt with current code, test output, and structured analysis",
        "- **Self-test**: Prompt to generate additional edge-case tests beyond the public suite",
        "",
        "## Test Score Progression",
    ]
    for i, s in enumerate(scores, 1):
        status = "PASS" if s.get("all_passed") else "FAIL"
        lines.append(f"  - Attempt {i}: {s['passed']}/{s['total']} [{status}]")
    lines.append("")

    lines.append("## Self-Tests Generated")
    st_path = os.path.join(project_root, "agent_logs", "self_tests.py")
    if os.path.exists(st_path):
        with open(st_path) as f:
            content = f.read().strip()
        lines.append(f"- Yes ({len(content)} chars, {content.count('def test_')} test functions)")
    else:
        lines.append("- No self-tests generated")
    lines.append("")

    all_passed = scores and scores[-1].get("all_passed")
    lines.append("## Human Interventions")
    hi_path = os.path.join(project_root, "agent_logs", "human_interventions.log")
    if os.path.exists(hi_path):
        with open(hi_path) as f:
            hi_content = f.read().strip()
        if hi_content:
            for line in hi_content.split("\n"):
                lines.append(f"- {line.strip()}")
        else:
            lines.append("- None recorded")
    else:
        lines.append("- None recorded")
    lines.append("")

    if all_passed:
        lines.append("## What Worked")
        lines.append("- All tests passed successfully")
        lines.append("- Syntax validation caught errors before test runs")
        lines.append("- Agent completed autonomously without human intervention")
        lines.append("")
        lines.append("## What Failed")
        lines.append("- Nothing - all tests passing")
    else:
        lines.append("## What Worked")
        lines.append(f"- Agent completed {iterations_used} iterations autonomously")
        lines.append("- Syntax pre-validation prevented wasted test runs on broken code")
        lines.append("")
        lines.append("## What Failed")
        lines.append(f"- Agent exhausted {MAX_ITERATIONS} iterations without passing all tests")
        lines.append(f"- Final score: {scores[-1]['passed']}/{scores[-1]['total']}")
        lines.append("")
        lines.append("## What Would Be Improved")
        lines.append("- Better model selection for complex logic")
        lines.append("- More specific repair prompts with targeted error debugging")
        lines.append("- Parallel hypothesis testing during repair phase")
        lines.append("- Adding self-test execution to the repair loop")

    archive_path = get_last_archive_path()
    if archive_path:
        lines.append("")
        lines.append("## Solution Artifacts")
        lines.append(f"- Archive: `{archive_path}`")
        lines.append(f"- Solution: `{archive_path}/knit.py`")
        lines.append(f"- Report: `{archive_path}/final_report.md`")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.log_decision("Final report written to agent_logs/final_report.md")


def archive_and_clear():
    project_root = get_project_root()
    logs_dir = os.path.join(project_root, "agent_logs")
    archive_dir = os.path.join(logs_dir, "archives", datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    os.makedirs(archive_dir, exist_ok=True)

    log_files = ["prompts.log", "decisions.log", "commands.log", "test_runs.log", "errors.log", "human_interventions.log", "final_report.md"]
    for fname in log_files:
        src = os.path.join(logs_dir, fname)
        if os.path.exists(src) and os.path.getsize(src) > 0:
            with open(src, "r", encoding="utf-8") as f:
                content = f.read()
            dst = os.path.join(archive_dir, fname)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(content)
            open(src, "w").close()

    for extra in ["knit.py", "self_tests.py"]:
        src = os.path.join(project_root if extra == "knit.py" else logs_dir, extra)
        if os.path.exists(src):
            with open(src, "r", encoding="utf-8") as f:
                content = f.read()
            dst = os.path.join(archive_dir, extra)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(content)

    marker = os.path.join(archive_dir, ".archive")
    with open(marker, "w") as f:
        f.write(f"Archived at {datetime.now().isoformat()}")
    last_archive = os.path.join(logs_dir, ".last_archive")
    with open(last_archive, "w", encoding="utf-8") as f:
        f.write(archive_dir)
    latest_link = os.path.join(logs_dir, "archives", "latest")
    try:
        if os.path.exists(latest_link):
            os.remove(latest_link)
        os.symlink(os.path.basename(archive_dir), latest_link, target_is_directory=True)
    except Exception:
        with open(latest_link + ".txt", "w") as f:
            f.write(archive_dir)
    print(f"Logs archived to agent_logs/archives/{os.path.basename(archive_dir)}/")
    print(f"Solution saved to agent_logs/archives/{os.path.basename(archive_dir)}/knit.py")


def main():
    project_root = get_project_root()
    os.chdir(project_root)

    print("SPRK Agent starting...")
    logger.log_decision("=== SPRK Agent Run Started ===")

    old_solution = os.path.join(project_root, "knit.py")
    if os.path.exists(old_solution):
        os.remove(old_solution)
        logger.log_decision("Removed stale knit.py from previous run")

    git_init()
    check_ollama()

    user_prompt_path = os.path.join(project_root, "agent_logs", "user_prompt.txt")
    spec_content = None

    if os.path.exists(user_prompt_path):
        print("Reading user prompt...")
        with open(user_prompt_path, "r", encoding="utf-8") as f:
            user_text = f.read().strip()
        logger.log_human_intervention(f"User submitted prompt: {user_text[:200]}")
        logger.log_decision(f"Using user prompt as spec ({len(user_text)} chars)")
        os.remove(user_prompt_path)
        spec_content = user_text
        print("Using your request as the specification.")
        logger.log_decision(f"Spec source: user prompt (agent_logs/user_prompt.txt)")

    if spec_content is None:
        print("Reading spec...")
        try:
            spec_content = read_spec()
            logger.log_decision(f"Spec source: secret_spec/spec.md")
        except FileNotFoundError as e:
            logger.log_error(f"Spec not found: {e}")
            print("ERROR: Spec file not found. Submit a prompt via the UI or place secret_spec/spec.md.")
            sys.exit(1)

    logger.log_decision(f"Spec read successfully ({len(spec_content)} chars)")
    logger.log_decision(f"Spec excerpt: {spec_content[:300].replace(chr(10), ' | ')}...")

    print("Planning implementation...")
    plan = create_plan(spec_content)
    logger.log_decision(f"Plan created ({len(plan)} chars)")
    logger.log_decision(f"Plan summary: {plan[:400].replace(chr(10), ' ')}...")

    scores = []
    self_tests_generated = False
    zero_streak = 0
    best_score = 0
    stagnation_count = 0
    MAX_ZERO_STREAK = 3
    MAX_STAGNATION = 3

    for attempt in range(1, MAX_ITERATIONS + 1):
        iter_start = datetime.now()
        print(f"Writing solution...")
        logger.log_decision(f"=== Attempt {attempt} ===")

        try:
            if attempt == 1:
                try:
                    write_solution(plan)
                except RuntimeError:
                    logger.log_error("Initial coding failed, retrying with simplified prompt")
                    print("Coding timed out. Retrying with minimal CLI prompt...")
                    from agent.prompts import get as get_prompt
                    mini_prompt = get_prompt("mini_coding", spec_summary=spec_content[:500])
                    from agent.ollama_client import query_llm
                    mini_code = query_llm(mini_prompt, model="qwen2.5-coder:7b")
                    import re as _re
                    mini_code = _re.sub(r"^```python\s*", "", mini_code)
                    mini_code = _re.sub(r"^```\s*", "", mini_code)
                    mini_code = _re.sub(r"\s*```$", "", mini_code)
                    mini_code = mini_code.strip()
                    sp = os.path.join(project_root, "knit.py")
                    with open(sp, "w", encoding="utf-8") as f:
                        f.write(mini_code)
                    logger.log_decision(f"Mini fallback code written ({len(mini_code)} chars)")
            else:
                current_code_path = os.path.join(project_root, "knit.py")
                if os.path.exists(current_code_path):
                    with open(current_code_path, "r", encoding="utf-8") as f:
                        current_code = f.read()
                else:
                    current_code = ""

                last_output = scores[-1]["output"] if scores else ""
                last_test_command = scores[-1].get("test_command", "python3 knit.py [args]") if scores else "python3 knit.py [args]"

                # Fix 3: After MAX_STAGNATION repairs without improvement, rewrite from plan
                if attempt > 3 and stagnation_count >= MAX_STAGNATION:
                    logger.log_decision(f"Stagnation detected ({stagnation_count} attempts without improvement). Rewriting from plan...")
                    print(f"No improvement in {stagnation_count} attempts. Rewriting from scratch...")
                    try:
                        write_solution(plan)
                        logger.log_decision("Rewrite from plan completed")
                    except RuntimeError:
                        logger.log_error("Rewrite also timed out, falling back to repair")
                        fixed_code = analyze_and_fix(last_output, current_code, last_test_command)
                        solution_path = os.path.join(project_root, "knit.py")
                        with open(solution_path, "w", encoding="utf-8") as f:
                            f.write(fixed_code)
                    stagnation_count = 0
                else:
                    logger.log_decision(f"Repair input: {len(current_code)} chars code, {len(last_output)} chars test output")
                    fixed_code = analyze_and_fix(last_output, current_code, last_test_command)

                    solution_path = os.path.join(project_root, "knit.py")
                    with open(solution_path, "w", encoding="utf-8") as f:
                        f.write(fixed_code)
                    logger.log_decision(f"Fixed code written ({len(fixed_code)} chars)")
        except RuntimeError as e:
            logger.log_error(f"Code generation failed: {e}")
            print(f"ERROR: Code generation failed - {e}")
            if attempt < MAX_ITERATIONS:
                print("Retrying...")
                continue
            else:
                print("Max attempts reached. Exiting.")
                write_final_report(scores, attempt)
                archive_and_clear()
                return

        solution_path = os.path.join(project_root, "knit.py")
        valid, error_msg = validate_syntax(solution_path)
        if not valid:
            logger.log_error(f"Syntax validation failed on attempt {attempt}: {error_msg[:200]}")
            print(f"Syntax error detected. Sending to repair...")
            with open(solution_path, "r") as f:
                current_code = f.read()
            last_test_command = scores[-1].get("test_command", "python3 knit.py [args]") if scores else "python3 knit.py [args]"
            fixed_code = analyze_and_fix(
                f"SYNTAX ERROR:\n{error_msg[:1000]}",
                current_code,
                last_test_command,
            )
            with open(solution_path, "w", encoding="utf-8") as f:
                f.write(fixed_code)
            logger.log_decision(f"Syntax repair applied on attempt {attempt}")

        print("Running tests...")
        result = run_tests()

        score_str = f"{result['passed']}/{result['total']}"
        logger.log_test_run(score_str)
        print(f"Attempt {attempt}: Score: {score_str}")

        elapsed = (datetime.now() - iter_start).total_seconds()
        logger.log_decision(f"Attempt {attempt} took {elapsed:.0f}s. Score: {score_str}")
        if result.get("parse_error"):
            logger.log_error(f"Could not parse test output. Raw: {result['output'][:300]}")

        scores.append(result)

        # Fix 1: Early stop on 3 consecutive zero-score attempts
        if result["passed"] == 0:
            zero_streak += 1
            logger.log_decision(f"Zero-streak: {zero_streak}/{MAX_ZERO_STREAK}")
            if zero_streak >= MAX_ZERO_STREAK:
                logger.log_decision(f"Early stop: {zero_streak} consecutive zero-score attempts. Stopping.")
                print(f"No progress after {zero_streak} attempts. Stopping early.")
                write_final_report(scores, attempt)
                archive_and_clear()
                return
        else:
            zero_streak = 0

        # Track stagnation for rewrite trigger
        if result["passed"] > best_score:
            best_score = result["passed"]
            stagnation_count = 0
        else:
            stagnation_count += 1

        if not self_tests_generated and result["passed"] > 0:
            with open(solution_path, "r") as f:
                current_code = f.read()
            generate_self_tests(spec_content, current_code)
            self_tests_generated = True

        if result["passed"] > 0:
            git_commit(score_str, attempt)

        if result.get("all_passed"):
            print(f"Done! Final score: {score_str}")
            logger.log_decision(f"All tests passed on attempt {attempt}. Score: {score_str}")
            write_final_report(scores, attempt)
            archive_and_clear()
            print("Final report written to agent_logs/final_report.md")
            return

        if elapsed > ITERATION_TIMEOUT:
            logger.log_error(f"Attempt {attempt} exceeded {ITERATION_TIMEOUT}s timeout")
            print(f"Attempt {attempt} timed out. Moving on.")

        if attempt < MAX_ITERATIONS:
            print(f"Fixing failures, attempt {attempt + 1}...")
            logger.log_decision(f"Attempt {attempt} failed ({score_str}). Moving to repair. Failures: {result.get('output', '')[:200]}")

    print(f"Done! Final score: {scores[-1]['passed']}/{scores[-1]['total']}")
    logger.log_decision(f"Agent finished after {MAX_ITERATIONS} attempts. Final score: {scores[-1]['passed']}/{scores[-1]['total']}")
    write_final_report(scores, MAX_ITERATIONS)
    archive_and_clear()
    print("Final report written to agent_logs/final_report.md")


if __name__ == "__main__":
    main()
