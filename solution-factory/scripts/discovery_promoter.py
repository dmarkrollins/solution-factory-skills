#!/usr/bin/env python3
"""
Process discoveries from a story's local.md.
Claude assigns relevance scores. This script handles the file operations:
- Auto-promote (score >= auto_create threshold) → create ADR/constraint file
- Prompt range (between prompt and auto_create) → flag for user confirmation
- Auto-discard (score <= auto_discard threshold) → skip

Input: JSON array of discoveries with scores and types.
Output: files created, items needing user confirmation.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def load_thresholds(root="."):
    """Load relevance thresholds from config.json."""
    config_path = Path(root) / ".solution-factory" / "config.json"
    defaults = {"auto_create": 8, "prompt": 5, "auto_discard": 4}

    if config_path.exists():
        with open(config_path, "r") as f:
            cfg = json.load(f) or {}
        return cfg.get("relevance", defaults)
    return defaults


def get_next_id(directory, prefix):
    """Get next sequential ID for ADRs or constraints."""
    d = Path(directory)
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        return f"{prefix}-001"

    existing = sorted(d.glob(f"{prefix}-*.md"))
    if not existing:
        return f"{prefix}-001"

    last = existing[-1].stem  # e.g., "adr-003"
    num = int(last.split("-")[1]) + 1
    return f"{prefix}-{num:03d}"


def promote_discoveries(discoveries, root="."):
    """Process scored discoveries.

    discoveries: list of dicts:
        {
            "title": str,
            "content": str,
            "type": "decision" | "constraint",
            "relevance": int (1-10),
            "source_story": str
        }
    """
    base = Path(root) / ".solution-factory"
    thresholds = load_thresholds(root)

    promoted = []
    needs_confirmation = []
    discarded = []

    for disc in discoveries:
        score = disc["relevance"]
        disc_type = disc["type"]

        if score >= thresholds["auto_create"]:
            # Auto-promote
            if disc_type == "decision":
                new_id = get_next_id(base / "decisions", "adr")
                file_path = base / "decisions" / f"{new_id}.md"
            else:
                new_id = get_next_id(base / "constraints", "const")
                file_path = base / "constraints" / f"{new_id}.md"

            content = f"""# {new_id}: {disc['title']}

**Status:** Accepted
**Date:** {datetime.utcnow().strftime('%Y-%m-%d')}
**Source:** Story {disc['source_story']}
**Relevance Score:** {score}

## Context
{disc['content']}

## Decision
{disc['content']}
"""
            file_path.write_text(content)
            promoted.append({
                "id": new_id,
                "title": disc["title"],
                "type": disc_type,
                "score": score,
                "path": str(file_path)
            })

        elif score >= thresholds["prompt"]:
            # Needs user confirmation
            needs_confirmation.append({
                "title": disc["title"],
                "type": disc_type,
                "score": score,
                "content": disc["content"],
                "source_story": disc["source_story"]
            })

        else:
            # Discard
            discarded.append({
                "title": disc["title"],
                "type": disc_type,
                "score": score
            })

    return {
        "success": True,
        "promoted": promoted,
        "needs_confirmation": needs_confirmation,
        "discarded": discarded,
        "thresholds": thresholds
    }


def confirm_and_promote(discovery, root="."):
    """Promote a single discovery that was confirmed by user."""
    # Wrap in list and promote with overridden high score
    discovery["relevance"] = 10  # Force auto-promote
    result = promote_discoveries([discovery], root)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote discoveries")
    parser.add_argument("command", choices=["auto", "confirm"])
    parser.add_argument("--discoveries", required=True, help="JSON array of discoveries")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    discoveries = json.loads(args.discoveries)

    if args.command == "auto":
        result = promote_discoveries(discoveries, args.root)
    elif args.command == "confirm":
        result = confirm_and_promote(discoveries[0] if isinstance(discoveries, list) else discoveries, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
