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


def resolve_next(root="."):
    """Find the next story to work on."""
    seq_path = Path(root) / ".solution-factory" / "sequence.json"
    if not seq_path.exists():
        return {"error": "sequence.json not found"}

    with open(seq_path, "r") as f:
        sequence = json.load(f)

    # Build a lookup of all story statuses
    status_map = {}
    for epic in sequence.get("epics", []):
        for story in epic["stories"]:
            status_map[story["id"]] = story["status"]

    # Check for active story first
    for epic in sequence.get("epics", []):
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

    # Find next ready story (array order)
    for epic in sequence.get("epics", []):
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
    return {"status": "complete", "message": "All stories completed or blocked"}


def list_stories(status_filter=None, root="."):
    """List all stories, optionally filtered by status."""
    seq_path = Path(root) / ".solution-factory" / "sequence.json"
    if not seq_path.exists():
        return {"error": "sequence.json not found"}

    with open(seq_path, "r") as f:
        sequence = json.load(f)

    stories = []
    for epic in sequence.get("epics", []):
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
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "next":
        result = resolve_next(args.root)
    elif args.command == "list":
        result = list_stories(args.status, args.root)

    print(json.dumps(result, indent=2))
