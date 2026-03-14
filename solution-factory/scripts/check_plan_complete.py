#!/usr/bin/env python3
"""
Check if all checkboxes in a story's plan.md are marked complete.
"""

import json
import sys
import argparse
import re
from pathlib import Path


def check_plan_complete(story_id, epic_id, root="."):
    """Check plan.md completion status."""
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories"

    # Find plan.md in active folder
    plan_path = base / "active" / story_id / "plan.md"
    if not plan_path.exists():
        # Also check done
        plan_path = base / "done" / story_id / "plan.md"
    if not plan_path.exists():
        return {"error": f"plan.md not found for story {story_id}"}

    content = plan_path.read_text()

    checked = re.findall(r'-\s+\[x\]\s+(.+)', content, re.IGNORECASE)
    unchecked = re.findall(r'-\s+\[\s\]\s+(.+)', content)

    if unchecked:
        return {
            "complete": False,
            "incomplete": unchecked,
            "checked": len(checked),
            "total": len(checked) + len(unchecked)
        }

    return {
        "complete": True,
        "total": len(checked)
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check plan completion")
    parser.add_argument("--story", required=True, help="Story ID")
    parser.add_argument("--epic", required=True, help="Epic ID")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    result = check_plan_complete(args.story, args.epic, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("complete", False) else 1)
