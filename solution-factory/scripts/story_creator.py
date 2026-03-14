#!/usr/bin/env python3
"""
Create new stories from discoveries found during implementation.
Adds stories to backlog and updates sequence.json.
"""

import json
import sys
import argparse
from pathlib import Path


def create_from_discovery(epic_id, story_data, insert_before=None, root="."):
    """Create a new story from a discovery and add to sequence.

    story_data: dict with id, title, epic, goal, acceptance, complexity, dependencies
    """
    # Create story directory in backlog
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories" / "backlog" / story_data["id"]
    base.mkdir(parents=True, exist_ok=True)

    # Write story JSON
    sys.path.insert(0, str(Path(__file__).parent))
    from story_templates import generate_story_yaml
    json_path = base / f"{story_data['id']}.json"
    generate_story_yaml(story_data, str(json_path))

    # Update sequence.json
    from generate_sequence import add_story
    seq_result = add_story(
        epic_id, story_data["id"],
        dependencies=story_data.get("dependencies", []),
        insert_before=insert_before,
        root=root
    )

    if not seq_result.get("success"):
        return seq_result

    # Update epic JSON
    epic_json_path = Path(root) / ".solution-factory" / "epics" / epic_id / f"{epic_id}.json"
    if epic_json_path.exists():
        from story_templates import update_epic_yaml
        update_epic_yaml(str(epic_json_path), root)

    return {
        "success": True,
        "story_id": story_data["id"],
        "epic_id": epic_id,
        "path": str(base),
        "inserted_before": insert_before
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create story from discovery")
    parser.add_argument("--epic", required=True, help="Epic ID")
    parser.add_argument("--data", required=True, help="JSON string with story data")
    parser.add_argument("--insert-before", help="Insert before this story ID")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    story_data = json.loads(args.data)
    result = create_from_discovery(args.epic, story_data, args.insert_before, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
