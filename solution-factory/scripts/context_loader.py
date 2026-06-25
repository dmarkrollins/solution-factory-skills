#!/usr/bin/env python3
"""
Load referenced ADRs, constraints, and capsules for a story.
Reads story JSON to find references, then loads their content.
Returns structured context for the LLM to consume with minimal tokens.
"""

import json
import sys
import argparse
from pathlib import Path


def load_file_content(file_path):
    """Load markdown file content."""
    p = Path(file_path)
    if p.exists():
        return p.read_text()
    return None


def load_context(story_id, epic_id, root="."):
    """Load all context referenced by a story."""
    base = Path(root) / ".solution-factory"

    # Find story JSON
    stories_base = base / "epics" / epic_id / "stories"
    story_data = None
    story_status = None

    for status in ["active", "backlog"]:
        story_dir = stories_base / status / story_id
        story_files = list(story_dir.glob("*.json")) if story_dir.exists() else []
        if story_files:
            with open(story_files[0], "r") as f:
                story_data = json.load(f)
            story_status = status
            break

    if not story_data:
        return {"error": f"Story {story_id} not found in {epic_id}"}

    context = {
        "story_id": story_id,
        "epic_id": epic_id,
        "decisions": [],
        "constraints": [],
        "capsules": []
    }

    # Load referenced ADRs
    decision_refs = story_data.get("decisions", {}).get("refs", [])
    for ref in decision_refs:
        content = load_file_content(base / "decisions" / f"{ref}.md")
        if content:
            context["decisions"].append({"id": ref, "content": content})

    # Load referenced constraints
    constraint_refs = story_data.get("constraints", {}).get("refs", [])
    for ref in constraint_refs:
        content = load_file_content(base / "constraints" / f"{ref}.md")
        if content:
            context["constraints"].append({"id": ref, "content": content})

    # Load referenced capsules
    capsule_refs = story_data.get("context", {}).get("capsules", [])
    for ref in capsule_refs:
        content = load_file_content(base / "context" / "capsules" / f"{ref}.md")
        if content:
            context["capsules"].append({"name": ref, "content": content})

    return context


def load_full_context(story_id, epic_id, root="."):
    """Load context plus story data — full payload for planning phase."""
    context = load_context(story_id, epic_id, root)
    if "error" in context:
        return context

    # Also include the story data itself
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories"
    for status in ["active", "backlog"]:
        story_dir = base / status / story_id
        story_files = list(story_dir.glob("*.json")) if story_dir.exists() else []
        if story_files:
            with open(story_files[0], "r") as f:
                context["story_data"] = json.load(f)
            break

    return context


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load story context")
    parser.add_argument("command", choices=["load", "full"])
    parser.add_argument("--story", required=True, help="Story ID")
    parser.add_argument("--epic", required=True, help="Epic ID")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "load":
        result = load_context(args.story, args.epic, args.root)
    elif args.command == "full":
        result = load_full_context(args.story, args.epic, args.root)

    print(json.dumps(result, indent=2))
