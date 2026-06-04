#!/usr/bin/env python3
"""
Validate story structure: numbering format, complexity within threshold,
valid dependencies (no cycles, no forward refs), required fields, no duplicates.
"""

import json
import sys
import argparse
from pathlib import Path


def load_config(root="."):
    """Load complexity threshold and per-epic story cap from config."""
    threshold = 3
    max_stories_per_epic = 10
    config_path = Path(root) / ".solution-factory" / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            cfg = json.load(f) or {}
        threshold = cfg.get("complexity", {}).get("threshold", 3)
        max_stories_per_epic = cfg.get("stories", {}).get("max_stories_per_epic", 10)
    return threshold, max_stories_per_epic


def validate(epic_id=None, root="."):
    """Validate all stories in sequence, or just one epic."""
    seq_path = Path(root) / ".solution-factory" / "sequence.json"
    if not seq_path.exists():
        return {"error": "sequence.json not found"}

    with open(seq_path, "r") as f:
        sequence = json.load(f)

    threshold, max_stories_per_epic = load_config(root)
    errors = []
    warnings = []
    seen_ids = set()

    epics = sequence.get("epics", [])
    if epic_id:
        epics = [e for e in epics if e["id"] == epic_id]
        if not epics:
            return {"error": f"Epic {epic_id} not found"}

    for epic in epics:
        story_ids_in_order = []

        # Per-epic story cap — forces large epics to be split into sequential epics
        story_count = len(epic.get("stories", []))
        if story_count > max_stories_per_epic:
            errors.append(
                f"Epic {epic['id']} has {story_count} stories, exceeds "
                f"max_stories_per_epic {max_stories_per_epic} — split into sequential epics"
            )

        for story in epic["stories"]:
            sid = story["id"]

            # Check duplicate IDs
            if sid in seen_ids:
                errors.append(f"Duplicate story ID: {sid}")
            seen_ids.add(sid)
            story_ids_in_order.append(sid)

            # Check ID format (NN.NNN)
            parts = sid.split(".")
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                errors.append(f"Invalid story ID format: {sid} (expected NN.NNN)")

            # Check no letter suffixes
            if any(c.isalpha() for c in sid):
                errors.append(f"Story ID contains letters: {sid} (numeric only)")

            # Load story JSON and validate fields
            base = Path(root) / ".solution-factory" / "epics" / epic["id"] / "stories"
            story_data = None
            for status in ["backlog", "active", "done", "deferred"]:
                story_dir = base / status / sid
                story_files = list(story_dir.glob("*.json")) if story_dir.exists() else []
                if story_files:
                    with open(story_files[0], "r") as f:
                        story_data = json.load(f)
                    break

            if story_data:
                # Required fields
                for field in ["id", "title", "epic", "goal", "acceptance", "complexity"]:
                    if field not in story_data:
                        errors.append(f"Story {sid} missing required field: {field}")

                # Complexity check
                complexity = story_data.get("complexity", 0)
                if complexity > threshold:
                    errors.append(
                        f"Story {sid} complexity {complexity} exceeds threshold {threshold}"
                    )

            # Dependency validation
            for dep in story.get("dependencies", []):
                if dep not in seen_ids:
                    # Check if it's in the full sequence (just later)
                    all_ids = [s["id"] for e in epics for s in e["stories"]]
                    if dep in all_ids:
                        errors.append(
                            f"Story {sid} depends on {dep} which appears later in sequence (forward reference)"
                        )
                    else:
                        errors.append(f"Story {sid} depends on unknown story: {dep}")

    # Cycle detection via topological sort
    all_stories = {s["id"]: s.get("dependencies", [])
                   for e in epics for s in e["stories"]}
    visited = set()
    in_stack = set()

    def has_cycle(node):
        if node in in_stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for dep in all_stories.get(node, []):
            if has_cycle(dep):
                return True
        in_stack.discard(node)
        return False

    for sid in all_stories:
        if has_cycle(sid):
            errors.append(f"Dependency cycle detected involving story: {sid}")
            break

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stories_checked": len(seen_ids),
        "complexity_threshold": threshold,
        "max_stories_per_epic": max_stories_per_epic
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate story structure")
    parser.add_argument("--epic", help="Validate specific epic only")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    result = validate(args.epic, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("valid") else 1)
