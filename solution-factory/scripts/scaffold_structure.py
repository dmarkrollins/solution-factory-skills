#!/usr/bin/env python3
"""
Scaffold .solution-factory/ directory structure.
Supports: init (full scaffold), epic (add epic), story (add story to epic).
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def init_structure(root="."):
    """Create the full .solution-factory/ directory tree."""
    base = Path(root) / ".solution-factory"

    dirs = [
        base / "docs",
        base / "constraints",
        base / "decisions",
        base / "context" / "capsules",
        base / "epics",
        base / "tests",
    ]

    created = []
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        created.append(str(d.relative_to(root)))

    # Create empty sequence.json if not exists
    seq_path = base / "sequence.json"
    if not seq_path.exists():
        seq_data = {
            "schema_version": "1.0",
            "project_root": ".",
            "created": datetime.utcnow().isoformat() + "Z",
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "epics": []
        }
        with open(seq_path, "w") as f:
            json.dump(seq_data, f, indent=2)
        created.append("sequence.json")

    return {"success": True, "created": created}


def create_epic(epic_num, root="."):
    """Create directory structure for a new epic."""
    base = Path(root) / ".solution-factory" / "epics" / f"epic-{epic_num:02d}"

    dirs = [
        base / "stories" / "active",
        base / "stories" / "backlog",
        base / "stories" / "done",
        base / "stories" / "deferred",
    ]

    created = []
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        created.append(str(d))

    return {"success": True, "epic": epic_num, "created": created}


def create_story(epic_num, story_num, status="backlog", root="."):
    """Create directory for a story within an epic."""
    story_id = f"{epic_num:02d}.{story_num:03d}"
    base = (Path(root) / ".solution-factory" / "epics" / f"epic-{epic_num:02d}"
            / "stories" / status / story_id)

    base.mkdir(parents=True, exist_ok=True)

    return {"success": True, "story_id": story_id, "path": str(base)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scaffold .solution-factory structure")
    parser.add_argument("command", choices=["init", "epic", "story"])
    parser.add_argument("--epic", type=int, help="Epic number")
    parser.add_argument("--story", type=int, help="Story number within epic")
    parser.add_argument("--status", default="backlog", choices=["backlog", "active", "done", "deferred"])
    parser.add_argument("--root", default=".", help="Project root directory")

    args = parser.parse_args()

    if args.command == "init":
        result = init_structure(args.root)
    elif args.command == "epic":
        if not args.epic:
            result = {"error": "--epic required for epic command"}
        else:
            result = create_epic(args.epic, args.root)
    elif args.command == "story":
        if not args.epic or not args.story:
            result = {"error": "--epic and --story required for story command"}
        else:
            result = create_story(args.epic, args.story, args.status, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
