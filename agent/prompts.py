import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_CONFIG_CACHE = None


def _load():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    path = os.environ.get(
        "AGENT_PROMPTS",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts_config.json"),
    )

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Prompts config not found at {path}. "
            "Set AGENT_PROMPTS env var or ensure agent/prompts_config.json exists."
        )

    with open(path, "r", encoding="utf-8") as f:
        _CONFIG_CACHE = json.load(f)
    return _CONFIG_CACHE


def get(template_name, **kwargs):
    templates = _load()
    raw = templates.get(template_name)
    if not raw:
        raise KeyError(
            f"Prompt template '{template_name}' not found in prompts config. "
            f"Available keys: {list(templates.keys())}"
        )
    return raw.format(**kwargs)


def reload():
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
    return _load()
