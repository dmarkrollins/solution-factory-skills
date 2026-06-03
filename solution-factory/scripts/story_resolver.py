#!/usr/bin/env python3
"""
Find the next ready story from sequence.json.
A story is ready when: status=backlog AND all dependencies are status=done.
Order is determined by array position in sequence.json, NOT by numerical sort.
"""

import json
import sys
import argparse
from pathlib import Path


def load_story_yaml(story_id, epic_id, root="."):
    """Load story JSON from its folder."""
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories"
    for status in ["backlog", "active", "done", "deferred"]:
        story_dir = base / status / story_id
        if story_dir.exists():
            story_files = list(story_dir.glob("*.json"))
            if story_files:
                with open(story_files[0], "r") as f:
                    return json.load(f), status
    return None, None


def resolve_next(root=".", epic_filter=None):
    """Find the next story to work on.

    Dependency status is always evaluated globally (a story may depend on
    stories in another epic). When epic_filter is set, only stories belonging
    to that epic are eligible to be returned, but their cross-epic dependencies
    are still honored.
    """
    seq_path = Path(root) / ".solution-factory" / "sequence.json"
    if not seq_path.exists():
        return {"error": "sequence.json not found"}

    with open(seq_path, "r") as f:
        sequence = json.load(f)

    epics = sequence.get("epics", [])
    if epic_filter and not any(e["id"] == epic_filter for e in epics):
        return {"error": f"epic '{epic_filter}' not found in sequence.json"}

    # Build a lookup of all story statuses (global — deps can cross epics)
    status_map = {}
    for epic in epics:
        for story in epic["stories"]:
            status_map[story["id"]] = story["status"]

    # Check for active story first (scoped to epic_filter when set)
    for epic in epics:
        if epic_filter and epic["id"] != epic_filter:
            continue
        for story in epic["stories"]:
            if story["status"] == "active":
                story_data, _ = load_story_yaml(story["id"], epic["id"], root)
                return {
                    "status": "active",
                    "story_id": story["id"],
                    "epic_id": epic["id"],
                    "story_data": story_data,
                    "message": f"Story {story['id']} is in progress"
                }

    # Find next ready story (array order; scoped to epic_filter when set)
    for epic in epics:
        if epic_filter and epic["id"] != epic_filter:
            continue
        for story in epic["stories"]:
            if story["status"] != "backlog":
                continue
            # Check all dependencies are done
            deps_met = all(
                status_map.get(dep) == "done"
                for dep in story.get("dependencies", [])
            )
            if deps_met:
                story_data, _ = load_story_yaml(story["id"], epic["id"], root)
                return {
                    "status": "ready",
                    "story_id": story["id"],
                    "epic_id": epic["id"],
                    "story_data": story_data,
                    "dependencies": story.get("dependencies", [])
                }

    # No ready stories
    scope = f" in {epic_filter}" if epic_filter else ""
    return {"status": "complete", "message": f"All stories{scope} completed or blocked"}


def list_stories(status_filter=None, root=".", epic_filter=None):
    """List all stories, optionally filtered by status and/or epic."""
    seq_path = Path(root) / ".solution-factory" / "sequence.json"
    if not seq_path.exists():
        return {"error": "sequence.json not found"}

    with open(seq_path, "r") as f:
        sequence = json.load(f)

    stories = []
    for epic in sequence.get("epics", []):
        if epic_filter and epic["id"] != epic_filter:
            continue
        for story in epic["stories"]:
            if status_filter and story["status"] != status_filter:
                continue
            stories.append({
                "id": story["id"],
                "epic": epic["id"],
                "status": story["status"],
                "dependencies": story.get("dependencies", []),
                "completed": story.get("completed")
            })

    return {"stories": stories, "count": len(stories)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resolve next story from sequence")
    parser.add_argument("command", choices=["next", "list"])
    parser.add_argument("--status", help="Filter by status (for list)")
    parser.add_argument("--epic", help="Scope to a single epic id (e.g. epic-03)")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "next":
        result = resolve_next(args.root, epic_filter=args.epic)
    elif args.command == "list":
        result = list_stories(args.status, args.root, epic_filter=args.epic)

    print(json.dumps(result, indent=2))
