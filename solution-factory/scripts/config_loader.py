#!/usr/bin/env python3
"""
Load and validate .solution-factory/config.json with sensible defaults.
Used by all other scripts to get configuration values.
"""

import json
import sys
from pathlib import Path


DEFAULTS = {
    "complexity": {
        "threshold": 3
    },
    "relevance": {
        "auto_create": 8,
        "prompt": 5,
        "auto_discard": 4
    },
    "stories": {
        "require_tests": True,
        "generate_demo_scripts": False,
        "automerge": True
    },
    "ux": {
        "wireframe_path": None,
        "default_stack": {
            "framework": "react",
            "bundler": "vite",
            "design_system": "chakra ui"
        }
    }
}


def deep_merge(base, override):
    """Merge override dict into base dict recursively."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(root="."):
    """Load config.json from .solution-factory/, merged with defaults."""
    config_path = Path(root) / ".solution-factory" / "config.json"

    if not config_path.exists():
        return {"config": DEFAULTS, "source": "defaults"}

    with open(config_path, "r") as f:
        user_config = json.load(f) or {}

    merged = deep_merge(DEFAULTS, user_config)
    return {"config": merged, "source": str(config_path)}


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = load_config(root)
    print(json.dumps(result, indent=2))
    sys.exit(0 if "error" not in result else 1)
