#!/usr/bin/env python3
"""
Lint an idea's plan.md Stories section.

parse_stories_section() is the single shared parser -- read_idea_plan.py
imports it rather than keeping a second copy, so the two can never drift
out of sync. A malformed story header (STORY_HINT matches, STORY_BULLET
doesn't) is surfaced as a warning instead of silently vanishing from the
parsed story list.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import idea_store

# Matches a well-formed story header exactly.
STORY_BULLET = re.compile(
    r"^-\s*(?P<seq>\d+)\s*-\s*(?P<title>.+?)\s*"
    r"\[\s*complexity\s+(?P<complexity>\d+)\s*,\s*deps:\s*(?P<deps>none|[\d,\s]+)"
    r"(?:\s*,\s*type:\s*(?P<type>[\w-]+))?\s*\]\s*$",
    re.IGNORECASE,
)

# Matches anything that *looks like* a story header, well-formed or not.
STORY_HINT = re.compile(r"^-\s*\d+\s*-\s*")

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


def parse_stories_section(text):
    """Parse the '## Stories' section of a plan.md.

    Returns {"stories": [...], "warnings": [...]}. A story dict has: seq
    (int, provisional and local to the idea), title, complexity,
    dependencies (list of seq ints), acceptance (list of str), and
    optional type.
    """
    lines = text.splitlines()
    span = _find_section(lines, "Stories")
    if span is None:
        return {"stories": [], "warnings": [], "error": "No '## Stories' section found"}

    start, end = span
    stories = []
    warnings = []
    current = None

    for lineno in range(start, end):
        raw_line = lines[lineno]
        line = raw_line.rstrip()
        if not line.strip():
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if indent == 0 and stripped.startswith("-"):
            m = STORY_BULLET.match(stripped)
            if m:
                deps_raw = m.group("deps").strip()
                deps = (
                    []
                    if deps_raw.lower() == "none"
                    else [int(d.strip()) for d in deps_raw.split(",") if d.strip()]
                )
                current = {
                    "seq": int(m.group("seq")),
                    "title": m.group("title").strip(),
                    "complexity": int(m.group("complexity")),
                    "dependencies": deps,
                    "acceptance": [],
                }
                if m.group("type"):
                    current["type"] = m.group("type")
                stories.append(current)
            elif STORY_HINT.match(stripped):
                warnings.append(
                    {
                        "line": lineno + 1,
                        "text": raw_line,
                        "reason": (
                            "looks like a story header but does not match the expected "
                            "'- <seq> - <title>  [complexity N, deps: seq,seq|none, "
                            "type: token]' format"
                        ),
                    }
                )
                current = None
            else:
                current = None
            continue

        if current is not None:
            if re.match(r"^Acceptance:\s*$", stripped, re.IGNORECASE):
                continue
            ac_m = re.match(r"^-\s+(.+)$", stripped)
            if ac_m:
                current["acceptance"].append(ac_m.group(1).strip())

    return {"stories": stories, "warnings": warnings}


def check_plan(idea_id, root="."):
    plan_path = idea_store._idea_dir(idea_id, root) / "plan.md"
    if not plan_path.exists():
        return {"error": f"No plan.md found for {idea_id}"}

    parsed = parse_stories_section(plan_path.read_text())
    if "error" in parsed:
        return parsed

    return {
        "idea": idea_id,
        "story_count": len(parsed["stories"]),
        "stories": parsed["stories"],
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
