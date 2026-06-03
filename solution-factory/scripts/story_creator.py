#!/usr/bin/env python3
"""
Create a new story from discovery data.
Writes the story JSON to the backlog directory and updates sequence.json.
"""

import json
import sys
from pathlib import Path

import generate_sequence


def create_from_discovery(epic_id, story_data, insert_before=None, root="."):
    """Create a story from discovery data: write JSON to backlog dir and add to sequence."""
    story_id = story_data["id"]

    story_dir = (
        Path(root)
        / ".solution-factory"
        / "epics"
        / epic_id
        / "stories"
        / "backlog"
        / story_id
    )
    story_dir.mkdir(parents=True, exist_ok=True)

    json_file = story_dir / f"{story_id}.json"
    with open(json_file, "w") as f:
        json.dump(story_data, f, indent=2)

    deps = story_data.get("dependencies", [])
    result = generate_sequence.add_story(
        epic_id, story_id, dependencies=deps, insert_before=insert_before, root=root
    )

    if "error" in result:
        return result

    return {"success": True, "story": story_id, "epic": epic_id}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create a story from discovery data")
    parser.add_argument("epic_id", help="Epic ID (e.g., epic-01)")
    parser.add_argument("story_json", help="Path to story JSON file")
    parser.add_argument("--insert-before", help="Insert story before this story ID")
    parser.add_argument("--root", default=".", help="Project root")
    args = parser.parse_args()

    with open(args.story_json) as f:
        story_data = json.load(f)

    result = create_from_discovery(
        args.epic_id, story_data, insert_before=args.insert_before, root=args.root
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
