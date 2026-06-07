#!/usr/bin/env python3
"""
Complete a story: validate, move from active to done, update epic JSON.
"""

import json
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime


def validate_completion(story_id, epic_id, root="."):
    """Check that a story is ready to be completed."""
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories"
    active_dir = base / "active" / story_id

    if not active_dir.exists():
        return {"valid": False, "error": f"Story {story_id} not found in active for {epic_id}"}

    errors = []

    # Check plan.md exists
    plan_md = active_dir / "plan.md"
    if not plan_md.exists():
        errors.append("plan.md not found — story was not properly planned")

    # Check plan.md has all checkboxes checked
    if plan_md.exists():
        content = plan_md.read_text()
        import re
        unchecked = re.findall(r'-\s+\[\s\]\s+(.+)', content)
        checked = re.findall(r'-\s+\[x\]\s+(.+)', content, re.IGNORECASE)
        if unchecked:
            errors.append(f"{len(unchecked)} unchecked criteria: {unchecked}")

    # Check story JSON file exists
    story_files = list(active_dir.glob("*.json"))
    if not story_files:
        errors.append("Story JSON file not found")

    if errors:
        return {"valid": False, "errors": errors}

    return {"valid": True, "story_id": story_id}


def complete_story(story_id, epic_id, root="."):
    """Move story from active to done, syncing its sequence.json status (and
    `completed` timestamp) in the same call -- mirrors story_activator's fix
    so the active->done transition can't drift between folder and status."""
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories"
    active_dir = base / "active" / story_id
    done_dir = base / "done" / story_id

    if not active_dir.exists():
        return {"error": f"Story {story_id} not found in active for {epic_id}"}

    # Move folder
    done_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(active_dir), str(done_dir))

    # Sync sequence.json status (and completed timestamp) in the same call
    sys.path.insert(0, str(Path(__file__).parent))
    from generate_sequence import update_status
    from story_templates import update_epic_yaml

    seq_result = update_status(story_id, "done", root=root)
    if "error" in seq_result:
        return {"error": f"Story {story_id} folder moved to done but sequence.json sync failed: {seq_result['error']}", "done_path": str(done_dir)}

    # Update epic JSON
    epic_json_path = Path(root) / ".solution-factory" / "epics" / epic_id / f"{epic_id}.json"
    if epic_json_path.exists():
        update_epic_yaml(str(epic_json_path), root)

    return {
        "success": True,
        "story_id": story_id,
        "epic_id": epic_id,
        "done_path": str(done_dir)
    }


def rollback_story(story_id, epic_id, root="."):
    """Move story from done back to active (reopen), syncing its sequence.json
    status in the same call -- mirrors story_activator's fix so the
    done->active transition can't drift between folder and status."""
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories"
    done_dir = base / "done" / story_id
    active_dir = base / "active" / story_id

    if not done_dir.exists():
        return {"error": f"Story {story_id} not found in done for {epic_id}"}

    active_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(done_dir), str(active_dir))

    # Sync sequence.json status in the same call
    sys.path.insert(0, str(Path(__file__).parent))
    from generate_sequence import update_status
    from story_templates import update_epic_yaml

    seq_result = update_status(story_id, "active", root=root)
    if "error" in seq_result:
        return {"error": f"Story {story_id} folder moved to active but sequence.json sync failed: {seq_result['error']}", "active_path": str(active_dir)}

    # Update epic JSON
    epic_json_path = Path(root) / ".solution-factory" / "epics" / epic_id / f"{epic_id}.json"
    if epic_json_path.exists():
        update_epic_yaml(str(epic_json_path), root)

    return {
        "success": True,
        "story_id": story_id,
        "status": "active",
        "active_path": str(active_dir)
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Complete or rollback a story")
    parser.add_argument("command", choices=["validate", "complete", "rollback"])
    parser.add_argument("--story", required=True, help="Story ID")
    parser.add_argument("--epic", required=True, help="Epic ID")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "validate":
        result = validate_completion(args.story, args.epic, args.root)
    elif args.command == "complete":
        result = complete_story(args.story, args.epic, args.root)
    elif args.command == "rollback":
        result = rollback_story(args.story, args.epic, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") or result.get("valid") else 1)
