#!/usr/bin/env python3
"""
Validate story structure: numbering format, complexity from 1 to threshold,
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


def _check_outputs_shape(sid, outputs):
    """Return error strings for a malformed `outputs` block.

    Valid: {"create": [paths], "modify": [paths]} (either key may be absent),
    every path a non-empty, repo-relative string with no `..` segments.
    """
    if not isinstance(outputs, dict):
        return [f"Story {sid} outputs must be an object with 'create'/'modify' lists"]
    errors = []
    unknown = set(outputs) - {"create", "modify"}
    if unknown:
        errors.append(f"Story {sid} outputs has unknown keys: {sorted(unknown)}")
    for key in ("create", "modify"):
        paths = outputs.get(key, [])
        if not isinstance(paths, list):
            errors.append(f"Story {sid} outputs.{key} must be a list")
            continue
        for p in paths:
            if not isinstance(p, str) or not p.strip():
                errors.append(f"Story {sid} outputs.{key} contains a non-string or empty path")
            elif p.startswith("/") or ".." in Path(p).parts:
                errors.append(f"Story {sid} outputs.{key} path must be repo-relative: {p}")
    return errors


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

    all_epics = sequence.get("epics", [])

    # Execution order is array position in sequence.json — across epics first,
    # then within each epic. Build a global position index BEFORE applying any
    # --epic filter, so a dependency living in another epic still resolves when
    # validating a single epic in isolation.
    global_order = {}
    for e in all_epics:
        for s in e.get("stories", []):
            if s["id"] not in global_order:
                global_order[s["id"]] = len(global_order)

    epics = all_epics
    if epic_id:
        epics = [e for e in epics if e["id"] == epic_id]
        if not epics:
            return {"error": f"Epic {epic_id} not found"}

    for epic in epics:
        story_ids_in_order = []
        # Declared-outputs bookkeeping for this epic: which stories declared
        # nothing (they'll run alone in a concurrent /solution epic run) and
        # which files several stories intend to modify (those stories can
        # never run concurrently, whatever the scheduler does).
        missing_outputs = []
        modify_owners = {}

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

                # Complexity check. The scale is 1-based: complexity is
                # 1 + dimension points, a whole number from 1 to threshold.
                # Done stories written before the 1-based scale may still
                # carry a 0, so the lower bound applies to open stories only.
                complexity = story_data.get("complexity", 0)
                if not isinstance(complexity, int) or isinstance(complexity, bool):
                    errors.append(
                        f"Story {sid} complexity {complexity!r} must be a whole number "
                        f"from 1 to {threshold}"
                    )
                elif complexity > threshold:
                    errors.append(
                        f"Story {sid} complexity {complexity} exceeds threshold {threshold}"
                    )
                elif complexity < 1 and status != "done":
                    errors.append(
                        f"Story {sid} complexity {complexity} is below the minimum of 1 "
                        f"(complexity is 1 + dimension points, from 1 to {threshold})"
                    )

                # Declared outputs — optional, but when present the shape must
                # be exactly what the concurrent scheduler reads.
                outputs = story_data.get("outputs")
                if outputs is None:
                    if story["status"] in ("backlog", "active"):
                        missing_outputs.append(sid)
                else:
                    errors.extend(_check_outputs_shape(sid, outputs))
                    if isinstance(outputs, dict):
                        for path in outputs.get("modify", []) or []:
                            if isinstance(path, str):
                                modify_owners.setdefault(path, []).append(sid)

            # Dependency validation — resolved against the GLOBAL story order,
            # never just the epic under validation. Cross-epic dependencies are
            # sanctioned by design (/create-stories: "Cross-epic dependencies are
            # fine: a story in epic-NN+1 may depend on a story in epic-NN
            # (dependencies are global story IDs; epics run sequentially)"), and
            # are produced routinely whenever an epic is split at the story cap.
            # Comparing positions rather than "have I seen it yet" also means a
            # dependency on an EARLIER epic is accepted while one on a LATER epic
            # is still correctly reported as a forward reference.
            for dep in story.get("dependencies", []):
                if dep not in global_order:
                    errors.append(f"Story {sid} depends on unknown story: {dep}")
                elif sid in global_order and global_order[dep] >= global_order[sid]:
                    errors.append(
                        f"Story {sid} depends on {dep} which appears later in sequence (forward reference)"
                    )

        if missing_outputs:
            warnings.append(
                f"Epic {epic['id']}: {len(missing_outputs)} open stories declare no outputs "
                f"and will run one at a time in a concurrent epic run: {', '.join(missing_outputs)}"
            )
        for path, owners in sorted(modify_owners.items()):
            if len(owners) > 1:
                warnings.append(
                    f"Epic {epic['id']}: hot file {path} is modified by {len(owners)} stories "
                    f"({', '.join(owners)}) — they will never run concurrently; "
                    f"consider splitting by file"
                )

    # Cycle detection via topological sort. Build the graph from ALL epics so a
    # cycle that spans an epic boundary is actually traversable when validating
    # one epic — but only report cycles reachable from the stories in scope, so
    # a --epic run doesn't surface problems belonging to a different epic.
    all_stories = {s["id"]: s.get("dependencies", [])
                   for e in all_epics for s in e["stories"]}
    in_scope_ids = [s["id"] for e in epics for s in e["stories"]]
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

    for sid in in_scope_ids:
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
