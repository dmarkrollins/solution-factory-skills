#!/usr/bin/env python3
"""
Check if a Python virtual environment is active.
"""

import json
import os
import sys


def check_venv():
    """Check for active Python virtual environment."""
    venv = os.environ.get("VIRTUAL_ENV")
    conda = os.environ.get("CONDA_DEFAULT_ENV")

    if venv:
        return {"active": True, "type": "virtualenv", "path": venv}
    elif conda:
        return {"active": True, "type": "conda", "env": conda}
    else:
        return {
            "active": False,
            "warning": "No Python virtual environment detected.",
            "fix": "Run: source ~/.claude/skills/solution-factory/.venv/bin/activate"
        }


if __name__ == "__main__":
    result = check_venv()
    print(json.dumps(result, indent=2))
