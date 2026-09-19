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
        "automerge": True,
        "merge_branch": "main",
        "max_stories_per_epic": 10,
        "auto_accept_recommendations": True
    },
    "ux": {
        "wireframe_path": None,
        "default_stack": {
            "framework": "react",
            "bundler": "vite",
            "design_system": "chakra ui"
        }
    },
    # Autonomous /solution epic runs. max_concurrent > 1 lets file-disjoint
    # stories run at the same time in separate worktree slots; shared_paths are
    # coordination files every story touches (lockfiles, CLAUDE.md, ...) that
    # are excluded from the "do these stories share a file" check; and
    # worktree_setup is a shell command run once per new slot (installs,
    # .env copies) since a fresh worktree has none of that.
    "epic_run": {
        "max_concurrent": 3,
        "shared_paths": [".solution-factory/**"],
        "worktree_setup": None
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
