#!/usr/bin/env python3
"""
Lint an idea's plan.md Technical Approach section.

parse_technical_approach_section() is the single shared parser --
read_idea_plan.py imports it rather than keeping a second copy, so the two
can never drift out of sync. plan.md is freeform prose here (the technical
approach is a design writeup, not a parseable story list -- story sizing
happens later, in /create-stories), so the only things worth linting are:
the section exists, and it isn't empty.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import idea_store

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")


def _find_section(lines, name):
    """Return (start, end) line-index span of a level-2 heading's body, or None."""
    start = None
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line.strip())
        if m and m.group(1).strip().lower() == name.lower():
            start = i + 1
            break
    if start is None:
        return None

    end = len(lines)
    for i in range(start, len(lines)):
        if _HEADING_RE.match(lines[i].strip()):
            end = i
            break
    return start, end


def parse_technical_approach_section(text):
    """Parse the '## Technical Approach' section of a plan.md.

    Returns {"content": str, "warnings": [...]}. content is the section's
    raw text (stripped). A missing section is an error (mirrors the old
    Stories-section-missing case); an empty section is a warning, not an
    error, since the user may still be drafting it.
    """
    lines = text.splitlines()
    span = _find_section(lines, "Technical Approach")
    if span is None:
        return {
            "content": "",
            "warnings": [],
            "error": "No '## Technical Approach' section found",
        }

    start, end = span
    content = "\n".join(lines[start:end]).strip()
    warnings = []
    if not content:
        warnings.append(
            {
                "reason": "'## Technical Approach' section is present but empty",
            }
        )

    return {"content": content, "warnings": warnings}


def check_plan(idea_id, root="."):
    plan_path = idea_store._idea_dir(idea_id, root) / "plan.md"
    if not plan_path.exists():
        return {"error": f"No plan.md found for {idea_id}"}

    parsed = parse_technical_approach_section(plan_path.read_text())
    if "error" in parsed:
        return parsed

    return {
        "idea": idea_id,
        "technical_approach_present": bool(parsed["content"]),
        "warnings": parsed["warnings"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lint an idea's plan.md")
    parser.add_argument("command", choices=["plan-check"])
    parser.add_argument("idea_id", help="Idea ID (e.g., IDEA-001)")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "plan-check":
        result = check_plan(args.idea_id, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if "error" not in result else 1)
