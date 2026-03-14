#!/usr/bin/env python3
"""
Generate story JSON and epic JSON files.
Epic JSON is a living document updated as stories are added/moved/deferred.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def generate_story_yaml(story_data, output_path):
    """Generate a story JSON file from structured data.

    story_data keys:
        id, title, epic, goal, acceptance (list), complexity (int),
        type (optional), wireframe (optional), dependencies (list),
        outputs (list, optional), out_of_scope (list, optional),
        decisions (list of ADR ids), constraints (list of constraint ids),
        context (list of capsule names)
    """
    story = {
        "id": story_data["id"],
        "title": story_data["title"],
        "epic": story_data["epic"],
        "goal": story_data["goal"],
        "complexity": story_data["complexity"],
        "acceptance": story_data.get("acceptance", []),
        "dependencies": story_data.get("dependencies", []),
        "decisions": {
            "evaluated": True,
            "refs": story_data.get("decisions", [])
        },
        "constraints": {
            "evaluated": True,
            "refs": story_data.get("constraints", [])
        },
        "context": {
            "evaluated": True,
            "capsules": story_data.get("context", [])
        }
    }

    # Optional fields
    for field in ["type", "wireframe", "outputs", "out_of_scope"]:
        if field in story_data and story_data[field]:
            story[field] = story_data[field]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w") as f:
        json.dump(story, f, indent=2)

    return {"success": True, "path": str(out)}


def _normalize_story(s, root="."):
    """Normalize a story entry to a full dict.

    Accepts:
      - a plain string ID: "01.001"
      - a partial dict: {"id": "01.001", "complexity": 2}
      - a full dict: {"id": "01.001", "title": "...", "complexity": 2, "status": "backlog"}

    Missing title/complexity are filled from the story JSON file on disk when possible.
    """
    if isinstance(s, str):
        s = {"id": s}

    story = dict(s)

    # Try to fill missing fields from story JSON file on disk
    if not story.get("title") or story.get("complexity") is None:
        story_id = story.get("id", "")
        parts = story_id.split(".")
        if len(parts) == 2:
            epic_num = parts[0].lstrip("0") or "0"
            epic_id = f"epic-{int(epic_num):02d}"
            for status in ["backlog", "active", "done", "deferred"]:
                story_path = Path(root) / ".solution-factory" / "epics" / epic_id / "stories" / status / story_id / f"{story_id}.json"
                if story_path.exists():
                    with open(story_path) as f:
                        sdata = json.load(f)
                    story.setdefault("title", sdata.get("title", ""))
                    if story.get("complexity") is None:
                        story["complexity"] = sdata.get("complexity", 0)
                    break

    # Apply defaults for any still-missing fields
    story.setdefault("title", "")
    story.setdefault("complexity", 0)
    story.setdefault("status", "backlog")

    return story


def generate_epic_yaml(epic_num, title, description, stories, output_path, root="."):
    """Generate or update epic JSON file.

    stories: list of story entries — strings (IDs), partial dicts, or full dicts.
             Missing fields are resolved from story JSON files on disk.
    """
    normalized = [_normalize_story(s, root) for s in stories]

    epic = {
        "id": f"epic-{epic_num:02d}",
        "title": title,
        "description": description,
        "updated": datetime.utcnow().isoformat() + "Z",
        "story_count": len(normalized),
        "total_complexity": sum(s.get("complexity", 0) for s in normalized),
        "status_summary": {},
        "stories": []
    }

    # Calculate status summary
    status_counts = {}
    for s in normalized:
        st = s.get("status", "backlog")
        status_counts[st] = status_counts.get(st, 0) + 1
    epic["status_summary"] = status_counts

    # Story list
    for s in normalized:
        epic["stories"].append({
            "id": s["id"],
            "title": s["title"],
            "status": s.get("status", "backlog"),
            "complexity": s.get("complexity", 0)
        })

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w") as f:
        json.dump(epic, f, indent=2)

    return {"success": True, "path": str(out)}


def update_epic_yaml(epic_yaml_path, root="."):
    """Re-scan story folders and update the epic JSON to reflect current state."""
    epic_path = Path(epic_yaml_path)
    if not epic_path.exists():
        return {"error": f"Epic JSON not found: {epic_yaml_path}"}

    # Determine epic directory
    epic_dir = epic_path.parent
    stories_dir = epic_dir / "stories"

    if not stories_dir.exists():
        return {"error": f"Stories directory not found: {stories_dir}"}

    # Load existing epic JSON
    with open(epic_path, "r") as f:
        epic = json.load(f)

    # Scan all status folders
    stories = []
    for status in ["backlog", "active", "done", "deferred"]:
        status_dir = stories_dir / status
        if not status_dir.exists():
            continue
        for story_dir in sorted(status_dir.iterdir()):
            if not story_dir.is_dir():
                continue
            # Look for story JSON files
            story_files = list(story_dir.glob("*.json"))
            if story_files:
                story_file = story_files[0]
                with open(story_file, "r") as f:
                    sdata = json.load(f)
                stories.append({
                    "id": sdata.get("id", story_dir.name),
                    "title": sdata.get("title", ""),
                    "status": status,
                    "complexity": sdata.get("complexity", 0)
                })

    # Update epic fields
    epic["updated"] = datetime.utcnow().isoformat() + "Z"
    epic["story_count"] = len(stories)
    epic["total_complexity"] = sum(s.get("complexity", 0) for s in stories)
    status_counts = {}
    for s in stories:
        st = s["status"]
        status_counts[st] = status_counts.get(st, 0) + 1
    epic["status_summary"] = status_counts
    epic["stories"] = stories

    with open(epic_path, "w") as f:
        json.dump(epic, f, indent=2)

    return {"success": True, "path": str(epic_path), "story_count": len(stories)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate story/epic JSON")
    parser.add_argument("command", choices=["generate-yaml", "generate-epic-yaml", "update-epic-yaml"])
    parser.add_argument("--data", help="JSON string with story/epic data")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--epic-yaml", help="Path to existing epic JSON (for update)")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "generate-yaml":
        data = json.loads(args.data)
        result = generate_story_yaml(data, args.output)
    elif args.command == "generate-epic-yaml":
        data = json.loads(args.data)
        result = generate_epic_yaml(
            data["epic_num"], data["title"], data["description"],
            data["stories"], args.output, args.root
        )
    elif args.command == "update-epic-yaml":
        result = update_epic_yaml(args.epic_yaml, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
