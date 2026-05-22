import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from agent.logger import logger

OLLAMA_URL = "http://localhost:11434/api/generate"
TIMEOUT = 300
PRIMARY_MODEL = "qwen2.5-coder:7b"
FALLBACK_MODEL = "llama3.1:8b"


def query_llm(prompt, model=PRIMARY_MODEL, fallback=True):
    attempt_models = [model]
    if fallback and model == PRIMARY_MODEL:
        attempt_models.append(FALLBACK_MODEL)

    for m in attempt_models:
        try:
            # Strip image references that crash text-only models
            safe_prompt = re.sub(r'!\[.*?\]\(.*?\)', '', prompt)
            safe_prompt = re.sub(r'<img[^>]*>', '', safe_prompt)
            safe_prompt = re.sub(r'\[image:.*?\]', '', safe_prompt)
            payload = {"model": m, "prompt": safe_prompt, "stream": False}
            resp = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("response", "")
            if not response_text.strip():
                raise ValueError("Empty response from model")
            cleaned = re.sub(r"^```python\s*", "", response_text)
            cleaned = re.sub(r"^```\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()
            logger.log_decision(
                f"LLM response from {m}: {len(cleaned)} chars"
            )
            return cleaned
        except requests.exceptions.Timeout:
            logger.log_error(f"Timeout on model {m} after {TIMEOUT}s")
        except requests.exceptions.ConnectionError:
            logger.log_error(
                f"Connection refused to Ollama at {OLLAMA_URL}. Is Ollama running?"
            )
        except Exception as e:
            logger.log_error(f"Model {m} failed: {e}")

    raise RuntimeError(
        "All models failed. Check Ollama status and model availability."
    )
