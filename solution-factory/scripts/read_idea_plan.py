#!/usr/bin/env python3
"""
Translate an approved idea's plan.md into the story-dict list create-stories
already knows how to consume (same shape the Plan agent drafts in its own
step 4a). Hard-fails if the idea isn't in the 'planned' state, and if the
plan has any unresolved parse warnings -- a translation bug here would
otherwise silently produce a story with no dependents blocking it.

seq numbers stay provisional (local to the idea) here; create-stories itself
does seq -> EPIC_NUM.NNN translation and dependency remapping, since that's
epic-numbering logic that belongs to create-stories's own workflow.
"""

import argparse
import json
import sys

import idea_store
from idea_plan_check import parse_stories_section


def read_idea_plan(idea_id, root="."):
    idea = idea_store._read_idea(idea_id, root)
    if idea is None:
        return {"error": f"Idea not found: {idea_id}"}

    state = idea["frontmatter"].get("state")
    if state != "planned":
        return {
            "error": (
                f"Idea {idea_id} is not ready for promotion: state is "
                f"'{state}', expected 'planned'. Run /ideas plan first."
            )
        }

    plan_path = idea_store._idea_dir(idea_id, root) / "plan.md"
    if not plan_path.exists():
        return {"error": f"Idea {idea_id} has no plan.md"}

    parsed = parse_stories_section(plan_path.read_text())
    if "error" in parsed:
        return parsed

    if parsed["warnings"]:
        return {
            "error": (
                f"plan.md for {idea_id} has {len(parsed['warnings'])} malformed "
                "story header(s) -- run /ideas plan-check and fix before promoting."
            ),
            "warnings": parsed["warnings"],
        }

    if not parsed["stories"]:
        return {"error": f"plan.md for {idea_id} has no stories in its '## Stories' section"}

    return {
        "success": True,
        "idea": idea_id,
        "title": idea["frontmatter"].get("title", ""),
        "stories": parsed["stories"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read an idea's approved plan")
    parser.add_argument("idea_id", help="Idea ID (e.g., IDEA-001)")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    result = read_idea_plan(args.idea_id, args.root)
    print(json.dumps(result, indent=2))
    sys.exit(0 if "error" not in result else 1)
