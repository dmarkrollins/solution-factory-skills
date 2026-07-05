#!/usr/bin/env python3
"""
Read an approved idea's plan.md into the context shape create-stories needs
to run its own Plan-agent story-drafting step (4a) with the idea's technical
approach as grounding, instead of drafting from a bare idea title/body.

Hard-fails if the idea isn't in the 'planned' state, has no plan.md, or its
'## Technical Approach' section is missing/empty -- create-stories should
never silently draft stories against an idea nobody finished designing.

Story sizing itself (vertical slicing, complexity scoring, dependency
sequencing) is NOT done here -- that's create-stories's own step 4a, run
against the context this returns. This script's only job is handing over
what /ideas plan produced: the idea's title, raw body, and technical
approach writeup.
"""

import argparse
import json
import sys

import idea_store
from idea_plan_check import parse_technical_approach_section


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

    parsed = parse_technical_approach_section(plan_path.read_text())
    if "error" in parsed:
        return parsed

    if parsed["warnings"] or not parsed["content"]:
        return {
            "error": (
                f"plan.md for {idea_id} has no usable '## Technical Approach' "
                "content -- run /ideas plan-check and fix before promoting."
            ),
            "warnings": parsed["warnings"],
        }

    return {
        "success": True,
        "idea": idea_id,
        "title": idea["frontmatter"].get("title", ""),
        "body": idea["body"].strip(),
        "technical_approach": parsed["content"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read an idea's approved plan")
    parser.add_argument("idea_id", help="Idea ID (e.g., IDEA-001)")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    result = read_idea_plan(args.idea_id, args.root)
    print(json.dumps(result, indent=2))
    sys.exit(0 if "error" not in result else 1)
