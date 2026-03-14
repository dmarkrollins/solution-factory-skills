#!/usr/bin/env python3
"""
Generate project progress overview from sequence.json.
"""

import json
import sys
from pathlib import Path


def get_status(root="."):
    """Generate status report from sequence.json."""
    seq_path = Path(root) / ".solution-factory" / "sequence.json"

    if not seq_path.exists():
        return {"error": "sequence.json not found. Run /ideate to initialize."}

    with open(seq_path, "r") as f:
        sequence = json.load(f)

    epics = sequence.get("epics", [])
    total_stories = 0
    done_stories = 0
    active_stories = 0
    backlog_stories = 0
    deferred_stories = 0
    active_story = None
    active_epic = None

    epic_summaries = []

    for epic in epics:
        epic_total = len(epic["stories"])
        epic_done = sum(1 for s in epic["stories"] if s["status"] == "done")
        epic_active = sum(1 for s in epic["stories"] if s["status"] == "active")
        epic_backlog = sum(1 for s in epic["stories"] if s["status"] == "backlog")
        epic_deferred = sum(1 for s in epic["stories"] if s["status"] == "deferred")

        total_stories += epic_total
        done_stories += epic_done
        active_stories += epic_active
        backlog_stories += epic_backlog
        deferred_stories += epic_deferred

        # Find active story
        for s in epic["stories"]:
            if s["status"] == "active":
                active_story = s["id"]
                active_epic = epic["id"]

        epic_summaries.append({
            "id": epic["id"],
            "status": epic["status"],
            "total": epic_total,
            "done": epic_done,
            "active": epic_active,
            "backlog": epic_backlog,
            "deferred": epic_deferred
        })

    return {
        "total_stories": total_stories,
        "done": done_stories,
        "active": active_stories,
        "backlog": backlog_stories,
        "deferred": deferred_stories,
        "active_story": active_story,
        "active_epic": active_epic,
        "epics": epic_summaries,
        "total_epics": len(epics)
    }


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = get_status(root)
    print(json.dumps(result, indent=2))
