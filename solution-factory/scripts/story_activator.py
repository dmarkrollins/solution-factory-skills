#!/usr/bin/env python3
"""
Activate a story: move from backlog to active, create local.md and summary.md.
Updates sequence.json status and moves the story folder.
"""

import json
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime


def activate_story(story_id, epic_id, root="."):
    """Move story from backlog to active, create working files."""
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories"
    backlog_dir = base / "backlog" / story_id
    active_dir = base / "active" / story_id

    if not backlog_dir.exists():
        # Check if already active
        if active_dir.exists():
            return {"success": True, "message": f"Story {story_id} already active", "already_active": True}
        return {"error": f"Story {story_id} not found in backlog for {epic_id}"}

    # Move folder
    active_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(backlog_dir), str(active_dir))

    # Create local.md (scratch pad for discoveries)
    local_md = active_dir / "local.md"
    if not local_md.exists():
        local_md.write_text(f"""# Story {story_id} — Local Discoveries

## Decisions Identified
<!-- Track new architectural decisions discovered during implementation -->

## Constraints Identified
<!-- Track new constraints discovered during implementation -->

## Notes
<!-- General implementation notes, blockers, observations -->

""")

    # Create summary.md (high-level for dependency loading)
    summary_md = active_dir / "summary.md"
    if not summary_md.exists():
        summary_md.write_text(f"""# Story {story_id} — Summary

## Objective
<!-- Filled during planning phase -->

## Key Decisions
<!-- Key technical decisions made during planning/implementation -->

## Dependencies Provided
<!-- What this story provides to downstream stories -->

""")

    return {
        "success": True,
        "story_id": story_id,
        "epic_id": epic_id,
        "active_path": str(active_dir),
        "files_created": ["local.md", "summary.md"]
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Activate a story")
    parser.add_argument("--story", required=True, help="Story ID (e.g., 01.001)")
    parser.add_argument("--epic", required=True, help="Epic ID (e.g., epic-01)")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    result = activate_story(args.story, args.epic, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
