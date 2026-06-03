#!/usr/bin/env python3
"""
Check if a Python virtual environment is active.
"""

import json
import os
import sys


def check_venv():
    """Return the active virtual environment type or a warning if none is active."""
    virtual_env = os.environ.get("VIRTUAL_ENV")
    conda_env = os.environ.get("CONDA_DEFAULT_ENV")

    if virtual_env:
        return {
            "active": True,
            "type": "virtualenv",
            "path": virtual_env,
        }

    if conda_env:
        return {
            "active": True,
            "type": "conda",
            "env": conda_env,
        }

    return {
        "active": False,
        "warning": "No virtual environment detected. Consider activating a venv or conda environment.",
    }


if __name__ == "__main__":
    result = check_venv()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("active") else 1)
