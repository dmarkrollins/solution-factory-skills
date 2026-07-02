#!/usr/bin/env python3
"""
Manage the pre-epic idea backlog: .solution-factory/ideas/IDEA-NNN/.

Single writer of idea.md frontmatter. The state field drives everything
downstream: raw -> triaged -> planning -> planned -> promoted, with
discarded reachable from any non-promoted state. No other code path may
write idea.md frontmatter, so create-stories can trust state == "planned"
without re-validating anything.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

VALID_STATES = ["raw", "triaged", "planning", "planned", "promoted", "discarded"]

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
_IDEA_ID_RE = re.compile(r"^IDEA-(\d+)$")


def _ideas_dir(root="."):
    return Path(root) / ".solution-factory" / "ideas"


def _idea_dir(idea_id, root="."):
    return _ideas_dir(root) / idea_id


def _idea_path(idea_id, root="."):
    return _idea_dir(idea_id, root) / "idea.md"


def _parse_frontmatter(text):
    """Parse simple `key: value` frontmatter (no PyYAML dependency)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text, body = m.groups()
    fm = {}
    for line in fm_text.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm, body


def _render(frontmatter, body):
    lines = ["---"]
    for k, v in frontmatter.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body.strip("\n"))
    lines.append("")
    return "\n".join(lines)


def _read_idea(idea_id, root="."):
    path = _idea_path(idea_id, root)
    if not path.exists():
        return None
    fm, body = _parse_frontmatter(path.read_text())
    return {"frontmatter": fm, "body": body, "path": str(path)}


def get_next_idea_id(root="."):
    """Scan existing idea dirs for the max ID, zero-padded 3 digits, never reused."""
    d = _ideas_dir(root)
    if not d.exists():
        return "IDEA-001"

    existing = []
    for p in d.iterdir():
        if p.is_dir():
            m = _IDEA_ID_RE.match(p.name)
            if m:
                existing.append(int(m.group(1)))

    if not existing:
        return "IDEA-001"
    return f"IDEA-{max(existing) + 1:03d}"


def add(title, body="", root="."):
    """Allocate a new IDEA-NNN and write idea.md with state: raw.

    Auto-creates .solution-factory/ideas/ even if the rest of
    .solution-factory/ doesn't exist yet -- capture should never require a
    scaffolded project.
    """
    ideas_dir = _ideas_dir(root)
    ideas_dir.mkdir(parents=True, exist_ok=True)

    idea_id = get_next_idea_id(root)
    now = datetime.utcnow().isoformat() + "Z"
    frontmatter = {
        "id": idea_id,
        "title": title,
        "state": "raw",
        "created": now,
        "updated": now,
    }

    idea_dir = _idea_dir(idea_id, root)
    idea_dir.mkdir(parents=True, exist_ok=True)
    (idea_dir / "idea.md").write_text(_render(frontmatter, body))

    return {"success": True, "id": idea_id, "path": str(idea_dir / "idea.md")}


def list_ideas(root=".", state=None):
    d = _ideas_dir(root)
    if not d.exists():
        return {"ideas": []}

    ideas = []
    for p in sorted(d.iterdir()):
        if not p.is_dir():
            continue
        idea = _read_idea(p.name, root)
        if idea is None:
            continue
        fm = idea["frontmatter"]
        if state and fm.get("state") != state:
            continue
        ideas.append(
            {
                "id": fm.get("id", p.name),
                "title": fm.get("title", ""),
                "state": fm.get("state", ""),
                "updated": fm.get("updated", ""),
            }
        )

    return {"ideas": ideas}


def show(idea_id, root="."):
    idea = _read_idea(idea_id, root)
    if idea is None:
        return {"error": f"Idea not found: {idea_id}"}

    result = {"id": idea_id, "frontmatter": idea["frontmatter"], "body": idea["body"]}
    plan_path = _idea_dir(idea_id, root) / "plan.md"
    if plan_path.exists():
        result["plan"] = plan_path.read_text()
    return result


def set_state(idea_id, new_state, root="."):
    """The only function that writes idea.md frontmatter's state field."""
    if new_state not in VALID_STATES:
        return {"error": f"Invalid state: {new_state}. Must be one of {VALID_STATES}"}

    idea = _read_idea(idea_id, root)
    if idea is None:
        return {"error": f"Idea not found: {idea_id}"}

    fm = idea["frontmatter"]
    fm["state"] = new_state
    fm["updated"] = datetime.utcnow().isoformat() + "Z"
    Path(idea["path"]).write_text(_render(fm, idea["body"]))

    return {"success": True, "id": idea_id, "state": new_state}


def discard(idea_id, reason=None, root="."):
    idea = _read_idea(idea_id, root)
    if idea is None:
        return {"error": f"Idea not found: {idea_id}"}

    fm = idea["frontmatter"]
    if fm.get("state") == "promoted":
        return {"error": f"Cannot discard a promoted idea: {idea_id}"}

    fm["state"] = "discarded"
    fm["updated"] = datetime.utcnow().isoformat() + "Z"

    body = idea["body"]
    if reason:
        body = body.rstrip("\n") + f"\n\n## Discard reason\n{reason}\n"

    Path(idea["path"]).write_text(_render(fm, body))
    return {"success": True, "id": idea_id, "state": "discarded"}


def promote(idea_id, epic_num, root="."):
    """Terminal call from create-stories after its file-writing steps validate.

    Not called from within the ideas skill itself.
    """
    idea = _read_idea(idea_id, root)
    if idea is None:
        return {"error": f"Idea not found: {idea_id}"}

    fm = idea["frontmatter"]
    if fm.get("state") != "planned":
        return {
            "error": (
                f"Cannot promote idea {idea_id}: state is '{fm.get('state')}', "
                "expected 'planned'"
            )
        }

    epic_id = f"epic-{int(epic_num):02d}"
    fm["state"] = "promoted"
    fm["epic_num"] = epic_id
    fm["updated"] = datetime.utcnow().isoformat() + "Z"
    Path(idea["path"]).write_text(_render(fm, idea["body"]))

    return {"success": True, "id": idea_id, "state": "promoted", "epic": epic_id}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage the pre-epic idea backlog")
    parser.add_argument(
        "command", choices=["add", "list", "show", "discard", "set-state", "promote"]
    )
    parser.add_argument("idea_id", nargs="?", help="Idea ID (e.g., IDEA-001)")
    parser.add_argument("--title", help="Idea title (for add)")
    parser.add_argument("--body", default="", help="Idea body text (for add)")
    parser.add_argument("--state", help="New state (for list filter or set-state)")
    parser.add_argument("--reason", help="Discard reason (for discard)")
    parser.add_argument("--epic-num", type=int, help="Epic number (for promote)")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "add":
        if not args.title:
            result = {"error": "--title required for add"}
        else:
            result = add(args.title, args.body, args.root)
    elif args.command == "list":
        result = list_ideas(args.root, args.state)
    elif args.command == "show":
        if not args.idea_id:
            result = {"error": "idea_id required for show"}
        else:
            result = show(args.idea_id, args.root)
    elif args.command == "discard":
        if not args.idea_id:
            result = {"error": "idea_id required for discard"}
        else:
            result = discard(args.idea_id, args.reason, args.root)
    elif args.command == "set-state":
        if not args.idea_id or not args.state:
            result = {"error": "idea_id and --state required for set-state"}
        else:
            result = set_state(args.idea_id, args.state, args.root)
    elif args.command == "promote":
        if not args.idea_id or args.epic_num is None:
            result = {"error": "idea_id and --epic-num required for promote"}
        else:
            result = promote(args.idea_id, args.epic_num, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if "error" not in result else 1)
