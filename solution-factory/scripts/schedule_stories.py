#!/usr/bin/env python3
"""
Decide which stories a concurrent /solution epic run may start right now.

A story is startable when it is ready (status backlog, every dependency done —
the same rule story_resolver uses), no free-slot limit is hit, and its
scheduling files don't overlap any in-flight story's files or any story picked
earlier in this same call. Scheduling files are the story's declared
outputs (create ∪ modify) minus epic_run.shared_paths. A story that declares
no outputs is treated as touching every file: it starts only when nothing is
in flight, and nothing else starts alongside it.

Ready stories are considered in sequence.json order, so the result is
deterministic for a given ledger + in-flight set. Held stories carry the
reason they were held so the orchestrator can print it.
"""

import json
import sys
import argparse
from fnmatch import fnmatchcase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
from story_resolver import load_story_yaml

# Sentinel for "declares no outputs, so may touch anything".
EVERYTHING = None


def _is_shared(path, shared_paths):
    return any(fnmatchcase(path, pat) for pat in shared_paths)


def scheduling_files(story_data, shared_paths):
    """Return the set of files used for the overlap check, or EVERYTHING."""
    outputs = (story_data or {}).get("outputs")
    if not isinstance(outputs, dict):
        return EVERYTHING
    files = set()
    for key in ("create", "modify"):
        for p in outputs.get(key, []) or []:
            if isinstance(p, str) and p and not _is_shared(p, shared_paths):
                files.add(p)
    return files if files else EVERYTHING


def _overlap(a, b):
    """First shared file between two scheduling sets, or "*" when either is
    EVERYTHING. None when disjoint."""
    if a is EVERYTHING or b is EVERYTHING:
        return "*"
    common = a & b
    return sorted(common)[0] if common else None


def schedule(epic_id, root=".", in_flight=None):
    """Compute startable/held stories for one epic.

    in_flight: story ids currently running. Defaults to the epic's `active`
    stories, which is also what a resume needs.
    """
    seq_path = Path(root) / ".solution-factory" / "sequence.json"
    if not seq_path.exists():
        return {"error": "sequence.json not found"}
    with open(seq_path) as f:
        sequence = json.load(f)

    epic = next((e for e in sequence.get("epics", []) if e["id"] == epic_id), None)
    if epic is None:
        return {"error": f"Epic {epic_id} not found"}

    cfg = load_config(root)["config"]["epic_run"]
    max_concurrent = max(1, int(cfg.get("max_concurrent", 1) or 1))
    shared_paths = cfg.get("shared_paths") or []

    # Dependency status is global: a story may depend on another epic.
    status_map = {s["id"]: s["status"]
                  for e in sequence.get("epics", []) for s in e["stories"]}

    if in_flight is None:
        in_flight = [s["id"] for s in epic["stories"] if s["status"] == "active"]
    in_flight = list(dict.fromkeys(in_flight))

    def files_for(story_id):
        data, _ = load_story_yaml(story_id, epic_id, root)
        return files_for_data(data)

    def files_for_data(data):
        return scheduling_files(data, shared_paths)

    def render(files):
        return sorted(files) if files is not EVERYTHING else None

    running = []
    for sid in in_flight:
        running.append({"id": sid, "files": files_for(sid)})

    free_slots = max_concurrent - len(running)
    startable, held, open_stories = [], [], []
    claimed = [(r["id"], r["files"]) for r in running]

    for story in epic["stories"]:
        sid = story["id"]
        if story["status"] not in ("backlog", "active"):
            continue
        data, _ = load_story_yaml(sid, epic_id, root)
        files = files_for_data(data)
        pending = [d for d in story.get("dependencies", []) if status_map.get(d) != "done"]
        open_stories.append({
            "id": sid,
            "title": (data or {}).get("title", ""),
            "status": story["status"],
            "files": render(files),
            "declared": files is not EVERYTHING,
            "deps_pending": pending,
        })
        if story["status"] != "backlog" or sid in in_flight:
            continue
        if pending:
            held.append({"id": sid, "reason": f"waits for {', '.join(pending)}"})
            continue
        if free_slots <= 0:
            held.append({"id": sid, "reason": "no free slot"})
            continue
        clash = None
        for other_id, other_files in claimed:
            hit = _overlap(files, other_files)
            if hit:
                if hit == "*" and files is EVERYTHING:
                    clash = f"declares no outputs; waits until nothing is in flight ({other_id})"
                elif hit == "*":
                    clash = f"{other_id} declares no outputs and runs alone"
                else:
                    clash = f"shares {hit} with {other_id}"
                break
        if clash:
            held.append({"id": sid, "reason": clash})
            continue
        startable.append({"id": sid, "title": (data or {}).get("title", ""), "files": render(files)})
        claimed.append((sid, files))
        free_slots -= 1

    return {
        "epic_id": epic_id,
        "mode": "concurrent" if max_concurrent > 1 else "sequential",
        "max_concurrent": max_concurrent,
        "shared_paths": shared_paths,
        "in_flight": [{"id": r["id"], "files": render(r["files"])} for r in running],
        "free_slots": max(0, free_slots),
        "startable": startable,
        "held": held,
        "open_stories": open_stories,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schedule stories for a concurrent epic run")
    parser.add_argument("--epic", required=True, help="Epic ID (e.g. epic-03)")
    parser.add_argument("--in-flight", nargs="*", default=None,
                        help="Story IDs currently running (default: the epic's active stories)")
    parser.add_argument("--root", default=".", help="Project root")
    args = parser.parse_args()

    result = schedule(args.epic, args.root, args.in_flight)
    print(json.dumps(result, indent=2))
    sys.exit(0 if "error" not in result else 1)
