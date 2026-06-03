#!/usr/bin/env python3
"""
Manage the run block on an epic JSON for stop/resume support.

run block schema:
  {
    "status":        "active" | "stopped" | "complete",
    "review_merges": bool,
    "started_at":    ISO timestamp,
    "stopped_at":    ISO timestamp | null,
    "current_story": story_id | null
  }
"""

import json
import glob
import argparse
from pathlib import Path
from datetime import datetime, timezone


def _epic_path(epic_id, root):
    return Path(root) / ".solution-factory" / "epics" / epic_id / f"{epic_id}.json"


def _load(epic_id, root):
    p = _epic_path(epic_id, root)
    if not p.exists():
        return None, p
    return json.loads(p.read_text()), p


def _save(data, path):
    path.write_text(json.dumps(data, indent=2))


def _now():
    return datetime.now(timezone.utc).isoformat()


def start_run(epic_id, review_merges, root="."):
    data, path = _load(epic_id, root)
    if data is None:
        return {"error": f"Epic JSON not found: {epic_id}"}
    data["run"] = {
        "status": "active",
        "review_merges": bool(review_merges),
        "started_at": _now(),
        "stopped_at": None,
        "current_story": None,
    }
    _save(data, path)
    return {"success": True, "epic_id": epic_id, "run": data["run"]}


def stop_run(epic_id, root="."):
    data, path = _load(epic_id, root)
    if data is None:
        return {"error": f"Epic JSON not found: {epic_id}"}
    if "run" not in data:
        return {"error": f"No active run found for {epic_id}"}
    data["run"]["status"] = "stopped"
    data["run"]["stopped_at"] = _now()
    _save(data, path)
    return {"success": True, "epic_id": epic_id, "run": data["run"]}


def complete_run(epic_id, root="."):
    data, path = _load(epic_id, root)
    if data is None:
        return {"error": f"Epic JSON not found: {epic_id}"}
    if "run" not in data:
        return {"error": f"No run block found for {epic_id}"}
    data["run"]["status"] = "complete"
    data["run"]["current_story"] = None
    _save(data, path)
    return {"success": True, "epic_id": epic_id, "run": data["run"]}


def update_current_story(epic_id, story_id, root="."):
    data, path = _load(epic_id, root)
    if data is None:
        return {"error": f"Epic JSON not found: {epic_id}"}
    if "run" not in data:
        return {"error": f"No run block found for {epic_id}"}
    data["run"]["current_story"] = story_id
    _save(data, path)
    return {"success": True, "epic_id": epic_id, "current_story": story_id}


def find_active_run(root="."):
    pattern = str(Path(root) / ".solution-factory" / "epics" / "*" / "epic-*.json")
    for f in sorted(glob.glob(pattern)):
        try:
            data = json.loads(Path(f).read_text())
        except (json.JSONDecodeError, OSError):
            continue
        run = data.get("run", {})
        if run.get("status") in ("active", "stopped"):
            return {
                "found": True,
                "epic_id": data["id"],
                "title": data.get("title", ""),
                "run": run,
            }
    return {"found": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage epic run state")
    parser.add_argument("command", choices=["start", "stop", "complete", "update", "find"])
    parser.add_argument("--epic", help="Epic ID (e.g. epic-02)")
    parser.add_argument("--story", help="Current story ID (for update)")
    parser.add_argument("--review-merges", action="store_true", default=False)
    parser.add_argument("--root", default=".", help="Project root")
    args = parser.parse_args()

    if args.command == "start":
        result = start_run(args.epic, args.review_merges, args.root)
    elif args.command == "stop":
        result = stop_run(args.epic, args.root)
    elif args.command == "complete":
        result = complete_run(args.epic, args.root)
    elif args.command == "update":
        result = update_current_story(args.epic, args.story, args.root)
    elif args.command == "find":
        result = find_active_run(args.root)

    print(json.dumps(result, indent=2))
