#!/usr/bin/env python3
"""
Lint an idea's plan.md Technical Approach section.

parse_technical_approach_section() is the single shared parser --
read_idea_plan.py imports it rather than keeping a second copy, so the two
can never drift out of sync. plan.md is freeform prose here (the technical
approach is a design writeup, not a parseable story list -- story sizing
happens later, in /create-stories), so the only things worth linting are:
the section exists, it isn't empty, and it doesn't slip into delivery
planning (phases, size estimates, ship order) -- splitting work into
deliverables is /create-stories's job alone.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import idea_store

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")

# Delivery-planning language that does not belong in a technical approach.
# Deliberately NOT flagged: a bare mention of "story sizing" -- deferring a
# question to that later pass is legitimate. These patterns catch the work
# itself being split, sized, or ordered here.
_DELIVERY_PLANNING_PATTERNS = [
    (re.compile(r"\bphase\s+(\d+|[ivx]+|one|two|three)\b", re.I), "phase label"),
    (re.compile(r"\b(milestone|sprint|tranche)s?\b", re.I), "milestone/sprint/tranche"),
    (re.compile(r"\bepic[- ]sized\b|\bstory[- ]sized\b|\bsizing note\b", re.I), "size estimate"),
    (re.compile(r"\bships?\s+(first|last|with|in)\b", re.I), "ship order"),
    (re.compile(r"^#{1,6}\s*stories\b", re.I | re.M), "story list"),
    (re.compile(r"\bcomplexity\s+(score|total)s?\b", re.I), "complexity score"),
]


def find_delivery_planning_language(text):
    """Return warnings for phasing / sizing / ship-order language in text.

    Lint only (never blocks promotion by itself): the caller decides. One
    warning per pattern, quoting the first match so it is easy to find.
    """
    warnings = []
    for pattern, label in _DELIVERY_PLANNING_PATTERNS:
        m = pattern.search(text)
        if m:
            warnings.append(
                {
                    "reason": (
                        f"delivery-planning language ({label}): '{m.group(0)}' -- "
                        "describe one technical design by component; splitting "
                        "into phases/stories and sizing is /create-stories's job"
                    ),
                }
            )
    return warnings


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
        "warnings": parsed["warnings"]
        + find_delivery_planning_language(parsed["content"]),
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
