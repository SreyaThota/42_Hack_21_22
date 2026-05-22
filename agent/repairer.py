import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.logger import logger
from agent.ollama_client import query_llm
from agent.prompts import get as get_prompt

ANALYSIS_PROMPT = """You are debugging a Python CLI program. Analyze these failures and identify the root cause.

TEST OUTPUT:
{test_failures}

TEST COMMAND:
The tests invoke your program as: {test_command}

CURRENT CODE:
{current_code}

Identify what is broken. Be specific about:
1. Which function/logic is wrong
2. What the expected behavior should be
3. What the actual behavior is
4. If ALL tests fail (0/X), the CLI interface likely does NOT match what the tests expect
5. Which working code MUST be preserved — do NOT suggest removing exit codes, error handling, or validation that already passes tests

Output ONLY the analysis, no code."""


def analyze_and_fix(test_output, current_code, test_command="python3 knit.py [args]"):
    analysis_prompt = ANALYSIS_PROMPT.format(
        test_failures=test_output, current_code=current_code, test_command=test_command
    )
    logger.log_prompt(analysis_prompt)

    try:
        analysis = query_llm(analysis_prompt, model="qwen2.5-coder:7b")
    except RuntimeError:
        analysis = "Analysis failed, proceeding directly to fix."

    logger.log_decision(f"Failure analysis: {analysis[:300].replace(chr(10), ' ')}...")

    fix_prompt = get_prompt(
        "repair",
        test_failures=test_output,
        current_code=current_code,
        test_command=test_command,
    )
    fix_prompt += f"\n\nAnalysis of what is wrong:\n{analysis}\n\nFix the issues identified above."

    logger.log_prompt(fix_prompt)

    try:
        fixed_code = query_llm(fix_prompt, model="qwen2.5-coder:7b")
    except RuntimeError:
        logger.log_error("Primary model failed for repair, trying fallback")
        try:
            fixed_code = query_llm(fix_prompt, model="llama3.1:8b", fallback=False)
        except RuntimeError as e:
            logger.log_error(f"Fallback model also failed: {e}")
            raise

    fixed_code = re.sub(r"^```python\s*", "", fixed_code, flags=re.MULTILINE)
    fixed_code = re.sub(r"^```\s*", "", fixed_code, flags=re.MULTILINE)
    fixed_code = re.sub(r"\s*```$", "", fixed_code, flags=re.MULTILINE)
    fixed_code = fixed_code.strip()

    return fixed_code
