import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.logger import logger
from agent.ollama_client import query_llm
from agent.prompts import get as get_prompt # type: ignore
from pathlib import Path


def read_spec():
    spec_path = Path(r"E:\42xNeedle_Hackathon-main\secret_spec\SECRET_SPEC.md")

    if not spec_path.exists():
        raise FileNotFoundError(f"Spec not found at: {spec_path}")

    return spec_path.read_text(encoding="utf-8")


def create_plan(spec_content):
    # Just send core requirements (first 4000 chars) to avoid model timeout
    spec_trimmed = spec_content[:4000]
    prompt = get_prompt("planning", spec_content=spec_trimmed)
    logger.log_prompt(prompt)
    plan = query_llm(prompt, model="qwen2.5-coder:7b")
    logger.log_decision(f"Plan generated ({len(plan)} chars)")
    return plan
