import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.logger import logger
from agent.ollama_client import query_llm
from agent.prompts import get as get_prompt


def write_solution(plan, additional_instructions=None):
    prompt = get_prompt("coding", plan=plan)
    if additional_instructions:
        prompt += f"\n\nAdditional instructions:\n{additional_instructions}"

    logger.log_prompt(prompt)
    code = query_llm(prompt, model="qwen2.5-coder:7b")

    code = _strip_fences(code)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    solution_path = os.path.join(project_root, "knit.py")
    with open(solution_path, "w", encoding="utf-8") as f:
        f.write(code)
    logger.log_decision(f"Written knit.py ({len(code)} chars)")
    return code


def _strip_fences(code):
    code = re.sub(r"^```python\s*", "", code, flags=re.MULTILINE)
    code = re.sub(r"^```\s*", "", code, flags=re.MULTILINE)
    code = re.sub(r"\s*```$", "", code, flags=re.MULTILINE)
    code = code.strip()
    return code
