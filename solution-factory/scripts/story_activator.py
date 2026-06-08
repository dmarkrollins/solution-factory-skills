#!/usr/bin/env python3
"""
Activate a story: move from backlog to active, create local.md.
Updates sequence.json status and moves the story folder.
"""

import json
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime


def activate_story(story_id, epic_id, root="."):
    """Move story from backlog to active, sync its sequence.json status, and
    create working files -- all as one operation so the folder location and
    the sequence.json status field can never drift out of sync (there is no
    window where one has changed and the other hasn't)."""
    base = Path(root) / ".solution-factory" / "epics" / epic_id / "stories"
    backlog_dir = base / "backlog" / story_id
    active_dir = base / "active" / story_id

    sys.path.insert(0, str(Path(__file__).parent))
    from generate_sequence import update_status

    if not backlog_dir.exists():
        # Check if already active
        if active_dir.exists():
            # Self-heal: a prior run may have moved the folder without syncing
            # sequence.json (e.g. interrupted mid-activation). Ensure the
            # status reflects reality regardless of how we got here.
            seq_result = update_status(story_id, "active", root=root)
            if "error" in seq_result:
                return {"error": f"Story {story_id} folder is active but sequence.json sync failed: {seq_result['error']}"}
            return {"success": True, "message": f"Story {story_id} already active", "already_active": True}
        return {"error": f"Story {story_id} not found in backlog for {epic_id}"}

    # Move folder
    active_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(backlog_dir), str(active_dir))

    # Sync sequence.json status in the same call -- no orchestration gap for
    # an external observer (or an interruption) to catch the two halves apart.
    seq_result = update_status(story_id, "active", root=root)
    if "error" in seq_result:
        return {"error": f"Story {story_id} folder moved to active but sequence.json sync failed: {seq_result['error']}", "active_path": str(active_dir)}

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

    return {
        "success": True,
        "story_id": story_id,
        "epic_id": epic_id,
        "active_path": str(active_dir),
        "files_created": ["local.md"]
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
