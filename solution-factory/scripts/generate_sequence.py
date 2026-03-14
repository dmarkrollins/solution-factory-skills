#!/usr/bin/env python3
"""
Create or update sequence.json.
Supports adding stories, updating statuses, and inserting stories before others.
Story execution order is determined by array position, NOT numerical sort.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def load_sequence(root="."):
    """Load sequence.json."""
    seq_path = Path(root) / ".solution-factory" / "sequence.json"
    if not seq_path.exists():
        return None, seq_path
    with open(seq_path, "r") as f:
        return json.load(f), seq_path


def save_sequence(data, seq_path):
    """Save sequence.json with updated timestamp."""
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    with open(seq_path, "w") as f:
        json.dump(data, f, indent=2)


def find_epic(data, epic_id):
    """Find an epic in the sequence by id."""
    for epic in data.get("epics", []):
        if epic["id"] == epic_id:
            return epic
    return None


def add_epic(epic_id, root="."):
    """Add a new epic to the sequence."""
    data, seq_path = load_sequence(root)
    if data is None:
        return {"error": "sequence.json not found"}

    if find_epic(data, epic_id):
        return {"error": f"Epic {epic_id} already exists"}

    epic = {
        "id": epic_id,
        "status": "pending",
        "dependencies": [],
        "stories": []
    }
    data["epics"].append(epic)
    save_sequence(data, seq_path)
    return {"success": True, "action": "add_epic", "epic": epic_id}


def add_story(epic_id, story_id, dependencies=None, insert_before=None, root="."):
    """Add a story to an epic. Optionally insert before another story."""
    data, seq_path = load_sequence(root)
    if data is None:
        return {"error": "sequence.json not found"}

    epic = find_epic(data, epic_id)
    if epic is None:
        return {"error": f"Epic {epic_id} not found"}

    # Check for duplicate
    for s in epic["stories"]:
        if s["id"] == story_id:
            return {"error": f"Story {story_id} already exists in epic {epic_id}"}

    story_entry = {
        "id": story_id,
        "status": "backlog",
        "dependencies": dependencies or [],
        "completed": None
    }

    if insert_before:
        # Find position of insert_before story
        idx = None
        for i, s in enumerate(epic["stories"]):
            if s["id"] == insert_before:
                idx = i
                break
        if idx is None:
            return {"error": f"Story {insert_before} not found for --insert-before"}

        # Insert at position, rewire downstream deps
        epic["stories"].insert(idx, story_entry)

        # Any story that depended on insert_before should also depend on new story
        for s in epic["stories"][idx + 1:]:
            if insert_before in s["dependencies"] and story_id not in s["dependencies"]:
                s["dependencies"].append(story_id)
    else:
        epic["stories"].append(story_entry)

    save_sequence(data, seq_path)
    return {"success": True, "action": "add_story", "story": story_id, "epic": epic_id}


def update_status(story_id, new_status, root="."):
    """Update a story's status in the sequence."""
    data, seq_path = load_sequence(root)
    if data is None:
        return {"error": "sequence.json not found"}

    for epic in data.get("epics", []):
        for story in epic["stories"]:
            if story["id"] == story_id:
                story["status"] = new_status
                if new_status == "done":
                    story["completed"] = datetime.utcnow().isoformat() + "Z"
                save_sequence(data, seq_path)
                return {"success": True, "story": story_id, "status": new_status}

    return {"error": f"Story {story_id} not found in any epic"}


def update_epic_status(epic_id, new_status, root="."):
    """Update an epic's status."""
    data, seq_path = load_sequence(root)
    if data is None:
        return {"error": "sequence.json not found"}

    epic = find_epic(data, epic_id)
    if epic is None:
        return {"error": f"Epic {epic_id} not found"}

    epic["status"] = new_status
    save_sequence(data, seq_path)
    return {"success": True, "epic": epic_id, "status": new_status}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage sequence.json")
    parser.add_argument("command", choices=["add-epic", "add-story", "update-status", "update-epic-status"])
    parser.add_argument("--epic", help="Epic ID (e.g., epic-01)")
    parser.add_argument("--story", help="Story ID (e.g., 01.001)")
    parser.add_argument("--status", help="New status")
    parser.add_argument("--dependencies", nargs="*", default=[], help="Dependency story IDs")
    parser.add_argument("--insert-before", help="Insert story before this story ID")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "add-epic":
        result = add_epic(args.epic, args.root)
    elif args.command == "add-story":
        result = add_story(args.epic, args.story, args.dependencies, args.insert_before, args.root)
    elif args.command == "update-status":
        result = update_status(args.story, args.status, args.root)
    elif args.command == "update-epic-status":
        result = update_epic_status(args.epic, args.status, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
