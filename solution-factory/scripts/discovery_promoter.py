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
import re
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


def list_existing(root="."):
    """List existing decisions/constraints as {id, type, title, path} for dedup checks."""
    base = Path(root) / ".solution-factory"
    out = []
    for type_name, dirname, prefix in (("decision", "decisions", "adr"), ("constraint", "constraints", "const")):
        d = base / dirname
        if not d.exists():
            continue
        for f in sorted(d.glob(f"{prefix}-*.md")):
            content = f.read_text()
            title_match = re.search(r'^#\s+[\w-]+:\s*(.+)', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f.stem
            out.append({"id": f.stem, "type": type_name, "title": title, "path": str(f)})
    return {"success": True, "items": out}


def resolve_target_path(base, target_id):
    """Resolve a target_id like 'const-060' or 'adr-003' to its file path, or None."""
    if target_id.startswith("adr-"):
        p = base / "decisions" / f"{target_id}.md"
    elif target_id.startswith("const-"):
        p = base / "constraints" / f"{target_id}.md"
    else:
        return None
    return p if p.exists() else None


SECTION_RE = re.compile(r'^##[ \t]+(.+?)[ \t]*$', re.MULTILINE)
META_RE = re.compile(r'^\*\*(?P<key>[^:*]+):\*\*[ \t]*(?P<val>.*)$')


def split_sections(text):
    """Split markdown into (preamble, [(heading, body), ...]) on '## ' headings."""
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return text, []
    preamble = text[:matches[0].start()]
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1), text[m.end():end]))
    return preamble, sections


def apply_metadata(lines, updates):
    """Update '**Key:** value' lines in place; append any key that was absent.

    Keys not named in `updates` (Status, Type, and any project-specific ones)
    are left exactly as found.
    """
    seen = set()
    last_meta = None
    for i, line in enumerate(lines):
        m = META_RE.match(line)
        if not m:
            continue
        key = m.group("key").strip()
        last_meta = i
        if key in updates:
            lines[i] = f"**{key}:** {updates[key]}"
            seen.add(key)
    missing = [f"**{k}:** {v}" for k, v in updates.items() if k not in seen]
    if missing:
        at = last_meta + 1 if last_meta is not None else len(lines)
        lines[at:at] = missing
    return lines


def amend_existing(file_path, disc, score):
    """Update an existing decision/constraint in place, PRESERVING its body.

    An amend refines one finding; it is not a regeneration of the file. The
    target may hold hundreds of lines of hand-maintained detail this discovery
    knows nothing about, so only three things are rewritten:

      * the header title (the ID stays stable),
      * the amend-tracking metadata (Date / Source / Relevance Score),
      * the primary content section.

    Every other section keeps its text verbatim. Section naming follows the
    same Status/Context/Decision/Consequences convention that new files use --
    for constraints as well as decisions -- so amending never reshapes a file
    into a different structure than the one promote_discoveries created.
    """
    old = file_path.read_text()
    preamble, sections = split_sections(old)

    lines = preamble.rstrip("\n").splitlines()
    header = f"# {file_path.stem}: {disc['title']}"
    if lines and lines[0].lstrip().startswith("#"):
        lines[0] = header
    else:
        lines.insert(0, header)

    lines = apply_metadata(lines, {
        "Date": datetime.utcnow().strftime('%Y-%m-%d'),
        "Source": f"Story {disc['source_story']} (amended)",
        "Relevance Score": str(score),
    })

    # Primary content section is 'Context' by the current convention. Files
    # amended by an earlier version of this script may carry 'Constraint'
    # instead -- update that one in place rather than leaving a stale section
    # beside a new one.
    names = [n for n, _ in sections]
    target = "Context" if "Context" in names else (
        "Constraint" if "Constraint" in names else None
    )
    if target is None:
        sections.insert(0, ("Context", disc["content"]))
    else:
        sections = [
            (n, disc["content"] if n == target else b) for n, b in sections
        ]

    out = ["\n".join(lines).rstrip(), ""]
    for name, body in sections:
        out.append(f"## {name}")
        out.append(body.strip("\n"))
        out.append("")
    file_path.write_text("\n".join(out).rstrip() + "\n")


def promote_discoveries(discoveries, root="."):
    """Process scored discoveries.

    discoveries: list of dicts:
        {
            "title": str,
            "content": str,
            "type": "decision" | "constraint",
            "relevance": int (1-10),
            "source_story": str,
            "action": "new" | "amend"   (optional, default "new"),
            "target_id": "const-060"    (required when action == "amend")
        }

    When action == "amend" and target_id resolves to an existing file, the
    discovery updates that file in place instead of creating a new one — this
    is how repeated findings about the same topic stay consolidated instead of
    spawning near-duplicate files.
    """
    base = Path(root) / ".solution-factory"
    thresholds = load_thresholds(root)

    promoted = []
    amended = []
    needs_confirmation = []
    discarded = []

    for disc in discoveries:
        score = disc["relevance"]
        disc_type = disc["type"]
        action = disc.get("action", "new")
        target_id = disc.get("target_id")

        if score >= thresholds["auto_create"]:
            if action == "amend" and target_id:
                target_path = resolve_target_path(base, target_id)
                if target_path:
                    amend_existing(target_path, disc, score)
                    amended.append({
                        "id": target_id,
                        "title": disc["title"],
                        "type": disc_type,
                        "score": score,
                        "path": str(target_path)
                    })
                    continue
                # target_id didn't resolve — fall through and create new instead

            # Auto-promote (new file)
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
<!-- Describe the decision made and the rationale here -->

## Consequences
<!-- Positive and negative consequences of this decision -->
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
                "source_story": disc["source_story"],
                "action": action,
                "target_id": target_id
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
        "amended": amended,
        "needs_confirmation": needs_confirmation,
        "discarded": discarded,
        "thresholds": thresholds
    }


def confirm_and_promote(discoveries, root="."):
    """Promote all confirmed discoveries (list or single dict), forcing auto-promote."""
    if isinstance(discoveries, dict):
        discoveries = [discoveries]
    for discovery in discoveries:
        discovery["relevance"] = 10  # Force auto-promote
    result = promote_discoveries(discoveries, root)
    return result


def merge_into(sources, target_id, merged_content, root="."):
    """Consolidate multiple existing decisions/constraints into one target file.

    `target_id` may be an existing ID (its content is replaced with
    `merged_content`) or a fresh ID of the same type as the sources (created
    with `merged_content`). Every other file in `sources` is reduced to a
    short stub pointing at the target — old IDs still resolve for any story
    that references them, but the content lives in one place.
    """
    base = Path(root) / ".solution-factory"
    source_paths = []
    for sid in sources:
        p = resolve_target_path(base, sid)
        if not p:
            return {"success": False, "error": f"source id not found: {sid}"}
        source_paths.append((sid, p))

    target_path = resolve_target_path(base, target_id)
    if not target_path:
        is_decision = target_id.startswith("adr-")
        target_path = base / ("decisions" if is_decision else "constraints") / f"{target_id}.md"

    target_path.write_text(merged_content)

    date = datetime.utcnow().strftime('%Y-%m-%d')
    stubbed = []
    for sid, p in source_paths:
        if p == target_path:
            continue
        old = p.read_text()
        header_match = re.match(r'(#\s+[\w-]+:\s*.+?\n)', old)
        header = header_match.group(1) if header_match else f"# {sid}\n"
        p.write_text(f"{header}\n**Superseded by:** {target_id} (consolidated {date})\n")
        stubbed.append(sid)

    return {
        "success": True,
        "target_id": target_id,
        "target_path": str(target_path),
        "stubbed": stubbed
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote discoveries")
    parser.add_argument("command", choices=["auto", "confirm", "list", "merge"])
    parser.add_argument("--discoveries", help="JSON array of discoveries (auto/confirm)")
    parser.add_argument("--sources", help="JSON array of source IDs to merge (merge)")
    parser.add_argument("--target", help="Target ID to merge into (merge)")
    parser.add_argument("--content", help="Merged markdown content for the target (merge)")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()

    if args.command == "auto":
        result = promote_discoveries(json.loads(args.discoveries), args.root)
    elif args.command == "confirm":
        result = confirm_and_promote(json.loads(args.discoveries), args.root)
    elif args.command == "list":
        result = list_existing(args.root)
    elif args.command == "merge":
        result = merge_into(json.loads(args.sources), args.target, args.content, args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
