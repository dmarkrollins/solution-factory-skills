#!/usr/bin/env python3
"""
Check if /clear was run recently by inspecting shell history.
Returns JSON indicating whether context is considered clean.
"""

import json
import os
import sys
from pathlib import Path


def check_context():
    """Check command history for recent /clear."""
    # Check fish history
    fish_history = Path.home() / ".local" / "share" / "fish" / "fish_history"

    # Also check bash/zsh history as fallbacks
    histories = [
        fish_history,
        Path.home() / ".bash_history",
        Path.home() / ".zsh_history",
    ]

    for hist_path in histories:
        if hist_path.exists():
            try:
                with open(hist_path, "r", errors="ignore") as f:
                    lines = f.readlines()

                # Check last 5 entries for /clear
                recent = lines[-10:] if len(lines) >= 10 else lines
                for line in recent:
                    if "/clear" in line:
                        return {"clean": True, "source": str(hist_path)}
            except Exception:
                continue

    return {
        "clean": False,
        "warning": "No recent /clear detected. Consider running /clear before starting a new story for a clean context."
    }


if __name__ == "__main__":
    result = check_context()
    print(json.dumps(result, indent=2))
