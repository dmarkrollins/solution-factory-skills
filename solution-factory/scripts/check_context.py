#!/usr/bin/env python3
"""
Check if the shell context has been recently cleared.
"""

import json
import sys
from pathlib import Path


def check_context():
    """Check shell history files for evidence of a recent 'clear' command."""
    home = Path.home()

    history_paths = [
        home / ".bash_history",
        home / ".zsh_history",
        home / ".local" / "share" / "fish" / "fish_history",
        home / ".history",
    ]

    found_any = False
    for history_path in history_paths:
        if history_path.exists():
            found_any = True
            try:
                content = history_path.read_text(errors="ignore")
                if "clear" in content:
                    return {"clean": True}
            except Exception:
                continue

    if not found_any:
        return {
            "clean": False,
            "warning": "No shell history files found. Cannot verify context has been cleared.",
        }

    return {
        "clean": False,
        "warning": "No 'clear' command found in shell history. Context may not have been cleared.",
    }


if __name__ == "__main__":
    result = check_context()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("clean") else 1)
