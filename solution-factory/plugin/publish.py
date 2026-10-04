#!/usr/bin/env python3
"""
Publish Solution Factory from ~/.claude into a Claude Code plugin marketplace.

Reads the working copies of the skills, agents, scripts and docs, rewrites the
parts that only work on the author's machine, and writes a marketplace folder
in the standard layout:

    <dest>/
      .claude-plugin/marketplace.json
      README.md  LICENSE
      plugins/solution-factory/
        .claude-plugin/plugin.json
        skills/<name>/SKILL.md
        agents/<name>.md
        scripts/*.py
        docs/*.md
        README.md  LICENSE

What gets rewritten on the way out:
  - ~/.claude/skills/solution-factory/...  ->  ${CLAUDE_PLUGIN_ROOT}/...
  - /solution, /ideate, ...                ->  /solution-factory:solution, ...
  - agent names (code-reviewer, ...)       ->  solution-factory:code-reviewer, ...
  - skill.md                               ->  SKILL.md

Files only: this script never runs git. Review the output, then commit and
push the marketplace yourself.

Usage:
    publish.py                 publish at the current version
    publish.py --bump patch    raise the version first (patch | minor | major)
    publish.py --dry-run       build and check, but change nothing
    publish.py --dest PATH     marketplace folder (default ~/code/marketplaces/6thcents)
"""

import argparse
import filecmp
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_NAME = "solution-factory"
DEFAULT_DEST = "~/code/marketplaces/6thcents"

PLUGIN_SRC = Path(__file__).resolve().parent      # .../skills/solution-factory/plugin
SF_DIR = PLUGIN_SRC.parent                        # .../skills/solution-factory
SKILLS_DIR = SF_DIR.parent                        # .../skills
AGENTS_DIR = SKILLS_DIR.parent / "agents"         # .../agents

# Everything published is listed here by name. Anything else sitting in the
# skills/agents/docs folders stays private until it is added to a list.
SKILLS = ["ideate", "bootstrap", "ideas", "create-stories", "solution"]
PLUGIN_ONLY_SKILLS = ["guide"]                    # live in plugin/skills/
AGENTS = [
    "backend-developer", "code-reviewer", "database-engineer", "devops-engineer",
    "documentation-writer", "frontend-developer", "security-engineer",
    "story-worker", "technical-architect", "test-engineer",
]
DOCS = [
    "pipeline-help.md", "getting-started.md", "workflows.md", "configuration.md",
    "commands.md", "agents.md", "project-layout.md", "troubleshooting.md",
]
# Docs printed verbatim as column-aligned text (not inside a code fence).
PREFORMATTED_DOCS = {"pipeline-help.md"}

PREFIX = PLUGIN_NAME + ":"
ROOT_VAR = "${CLAUDE_PLUGIN_ROOT}"

_SKILL_ALT = "|".join(sorted((re.escape(s) for s in SKILLS + PLUGIN_ONLY_SKILLS), key=len, reverse=True))
_AGENT_ALT = "|".join(sorted((re.escape(a) for a in AGENTS), key=len, reverse=True))

SF_PATH_RE = re.compile(r"~/\.claude/skills/solution-factory/")
SKILL_FILE_RE = re.compile(r"~/\.claude/skills/(%s)/skill\.md" % _SKILL_ALT)
PYTHON_CALL_RE = re.compile(r"python3 " + re.escape(ROOT_VAR) + r"/scripts/([\w.]+)")
# A slash command: "/solution", not ".solution-factory/", "skills/solution/x" or "/solution-factory".
COMMAND_RE = re.compile(r"(?<![\w./~:-])/(%s)(?![\w/:-]|\.\w)" % _SKILL_ALT)
# An agent name: "code-reviewer", not "code-reviewer.md" or an already prefixed one.
AGENT_RE = re.compile(r"(?<![\w:/.-])(%s)(?![\w-]|\.md)" % _AGENT_ALT)
FENCE_RE = re.compile(r"^\s*(```|~~~)")

# Appended to the story-worker agent. Claude Code fills in the plugin root in
# skill and agent text it loads itself, but the worker reads the solution skill
# straight from disk, where the placeholder is still unresolved, and the
# variable is not set in the shell either.
WORKER_PATH_NOTE = """
## Plugin paths

Solution Factory is installed at `%s`.

When you read the solution skill file from disk, its commands contain an
unresolved plugin-root placeholder (the name `CLAUDE_PLUGIN_ROOT` wrapped in a
dollar sign and curly braces). That variable is **not** set in your shell.
Replace the placeholder with the absolute path above in every command you run.
""" % ROOT_VAR

# Text that must never reach a public repo.
LEAK_PATTERNS = [
    (re.compile(r"~/\.claude/(skills|agents)"), "personal ~/.claude path"),
    (re.compile(r"/Users/|/home/[a-z]"), "absolute home path"),
    (re.compile(re.escape(Path.home().name)), "local user name"),
]
TEXT_SUFFIXES = {".md", ".py", ".json", ".txt", ""}


class PublishError(Exception):
    pass


# --------------------------------------------------------------------------
# Text rewriting
# --------------------------------------------------------------------------

def split_frontmatter(text):
    """Return (frontmatter, body). Frontmatter keeps its --- lines; '' if none."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[: end + 5], text[end + 5:]
    return "", text


def rewrite_paths(text):
    text = SKILL_FILE_RE.sub(lambda m: "%s/skills/%s/SKILL.md" % (ROOT_VAR, m.group(1)), text)
    text = SF_PATH_RE.sub(lambda m: ROOT_VAR + "/", text)
    # Quote script paths so an install location with spaces still works.
    return PYTHON_CALL_RE.sub(lambda m: 'python3 "%s/scripts/%s"' % (ROOT_VAR, m.group(1)), text)


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def rewrite_names(text, preformatted=False):
    """Prefix slash commands and agent names with the plugin name.

    Inside code fences (or everywhere, for preformatted docs) the help text is
    column-aligned, and a line that got longer pushes its description column
    right. Wrapped continuation lines are indented by the same amount so the
    columns still line up.
    """
    out = []
    block = []          # (indent, [original columns of command matches]) for the current fence
    in_fence = False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            block = []
            out.append(line)
            continue
        cols = [m.start() for m in COMMAND_RE.finditer(line)]
        new = COMMAND_RE.sub(lambda m: "/%s%s" % (PREFIX, m.group(1)), line)
        new = AGENT_RE.sub(lambda m: PREFIX + m.group(1), new)
        if (in_fence or preformatted) and line.strip():
            indent = _indent(line)
            for head_indent, head_cols in reversed(block):
                if head_indent < indent:
                    shift = len(PREFIX) * sum(1 for c in head_cols if c < indent)
                    new = " " * shift + new
                    break
            block.append((indent, cols))
        out.append(new)
    return "\n".join(out)


def transform(text, preformatted=False):
    """Rewrite one markdown file for the plugin. Frontmatter is left untouched."""
    front, body = split_frontmatter(text)
    return front + rewrite_names(rewrite_paths(body), preformatted)


# --------------------------------------------------------------------------
# Version
# --------------------------------------------------------------------------

def bump_version(version, part):
    try:
        major, minor, patch = (int(x) for x in version.split("."))
    except ValueError:
        raise PublishError("version %r is not in major.minor.patch form" % version)
    if part == "major":
        return "%d.0.0" % (major + 1)
    if part == "minor":
        return "%d.%d.0" % (major, minor + 1)
    return "%d.%d.%d" % (major, minor, patch + 1)


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def _read(path):
    if not path.is_file():
        raise PublishError("missing source file: %s" % path)
    return path.read_text(encoding="utf-8")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_plugin(out, manifest, skills_dir=SKILLS_DIR, agents_dir=AGENTS_DIR, sf_dir=SF_DIR):
    """Write the complete plugin folder into `out` (which must not exist yet)."""
    plugin_src = sf_dir / "plugin"

    _write(out / ".claude-plugin" / "plugin.json", json.dumps(manifest, indent=2) + "\n")

    for name in SKILLS:
        _write(out / "skills" / name / "SKILL.md", transform(_read(skills_dir / name / "skill.md")))

    for name in PLUGIN_ONLY_SKILLS:
        src = plugin_src / "skills" / name
        if not (src / "SKILL.md").is_file():
            raise PublishError("missing source file: %s" % (src / "SKILL.md"))
        for f in sorted(p for p in src.rglob("*") if p.is_file() and p.name != ".DS_Store"):
            rel = f.relative_to(src)
            if f.suffix == ".md":
                _write(out / "skills" / name / rel, transform(_read(f)))
            else:
                (out / "skills" / name / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, out / "skills" / name / rel)

    for name in AGENTS:
        text = transform(_read(agents_dir / (name + ".md")))
        if name == "story-worker":
            text = text.rstrip("\n") + "\n" + WORKER_PATH_NOTE
        _write(out / "agents" / (name + ".md"), text)

    scripts = sorted((sf_dir / "scripts").glob("*.py"))
    if not scripts:
        raise PublishError("no scripts found in %s" % (sf_dir / "scripts"))
    for f in scripts:
        _write(out / "scripts" / f.name, _read(f))

    for name in DOCS:
        _write(out / "docs" / name, transform(_read(sf_dir / "docs" / name), name in PREFORMATTED_DOCS))

    _write(out / "README.md", transform(_read(plugin_src / "README.md")))
    _write(out / "LICENSE", _read(plugin_src / "LICENSE"))


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_output(out):
    """Return a list of problems found in the built plugin folder."""
    problems = []
    script_ref = re.compile(re.escape(ROOT_VAR) + r"/((?:scripts|docs|skills)/[\w./-]*\w)")
    agent_ref = re.compile(re.escape(PREFIX) + r"([a-z][a-z-]*[a-z])")
    known = set(SKILLS + PLUGIN_ONLY_SKILLS + AGENTS)

    for f in sorted(p for p in out.rglob("*") if p.is_file()):
        if f.suffix not in TEXT_SUFFIXES:
            continue
        rel = f.relative_to(out)
        text = f.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.split("\n"), 1):
            for pattern, label in LEAK_PATTERNS:
                if pattern.search(line):
                    problems.append("%s:%d: %s: %s" % (rel, lineno, label, line.strip()[:100]))
        for ref in set(script_ref.findall(text)):
            if not (out / ref).exists():
                problems.append("%s: points at %s/%s, which is not in the plugin" % (rel, ROOT_VAR, ref))
        if f.suffix == ".md":
            for ref in set(agent_ref.findall(text)):
                if ref not in known:
                    problems.append("%s: mentions %s%s, which is not in the plugin" % (rel, PREFIX, ref))
    return problems


def run_validator(path):
    """Run `claude plugin validate`. Returns (ok, output); ok is None if claude is not installed."""
    exe = shutil.which("claude")
    if not exe:
        return None, "claude CLI not found - skipped"
    proc = subprocess.run([exe, "plugin", "validate", str(path)],
                          capture_output=True, text=True, timeout=120)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


# --------------------------------------------------------------------------
# Marketplace
# --------------------------------------------------------------------------

def marketplace_entry(manifest):
    return {
        "name": manifest["name"],
        "source": "./plugins/" + manifest["name"],
        "description": manifest["description"],
        "category": "development",
        "keywords": manifest.get("keywords", []),
    }


def merged_marketplace(dest, template, manifest):
    """The marketplace.json to write: the existing one with our entry updated, or a new one."""
    path = dest / ".claude-plugin" / "marketplace.json"
    market = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else dict(template)
    entry = marketplace_entry(manifest)
    plugins = [p for p in market.get("plugins", []) if p.get("name") != entry["name"]]
    market["plugins"] = plugins + [entry]
    return market


def diff_trees(new, old):
    """Compare two folders. Returns (added, changed, removed) lists of relative paths."""
    new_files = {p.relative_to(new) for p in new.rglob("*") if p.is_file()}
    old_files = {p.relative_to(old) for p in old.rglob("*") if p.is_file()} if old.is_dir() else set()
    added = sorted(str(p) for p in new_files - old_files)
    removed = sorted(str(p) for p in old_files - new_files)
    changed = sorted(str(p) for p in new_files & old_files
                     if not filecmp.cmp(new / p, old / p, shallow=False))
    return added, changed, removed


def is_our_plugin(path):
    """True if `path` is a previous publish of this plugin (so it is safe to replace)."""
    manifest = path / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("name") == PLUGIN_NAME
    except (OSError, ValueError):
        return False


# --------------------------------------------------------------------------
# Publish
# --------------------------------------------------------------------------

def publish(dest, bump=None, dry_run=False, validate=True,
            skills_dir=SKILLS_DIR, agents_dir=AGENTS_DIR, sf_dir=SF_DIR, log=print):
    plugin_src = sf_dir / "plugin"
    manifest_path = plugin_src / "plugin.json"
    manifest = json.loads(_read(manifest_path))
    if manifest.get("name") != PLUGIN_NAME:
        raise PublishError("%s must have name %r" % (manifest_path, PLUGIN_NAME))

    old_version = manifest["version"]
    if bump:
        manifest["version"] = bump_version(old_version, bump)

    target = dest / "plugins" / PLUGIN_NAME
    if target.exists() and not is_our_plugin(target):
        raise PublishError("%s exists but is not a %s plugin - refusing to replace it"
                           % (target, PLUGIN_NAME))

    with tempfile.TemporaryDirectory(prefix="sf-publish-") as tmp:
        staged = Path(tmp) / PLUGIN_NAME
        build_plugin(staged, manifest, skills_dir, agents_dir, sf_dir)

        problems = check_output(staged)
        if problems:
            raise PublishError("output failed checks, nothing was written:\n  " + "\n  ".join(problems))

        if validate:
            ok, output = run_validator(staged)
            if ok is False:
                raise PublishError("claude plugin validate failed, nothing was written:\n" + output)
            log("Plugin validator: " + (output.splitlines()[-1] if output else "ok"))

        added, changed, removed = diff_trees(staged, target)
        market = merged_marketplace(dest, json.loads(_read(plugin_src / "marketplace.json")), manifest)

        version_note = manifest["version"] if not bump else "%s -> %s" % (old_version, manifest["version"])
        log("%s %s  (%s)" % (PLUGIN_NAME, version_note, "dry run" if dry_run else "publishing"))
        log("  destination: %s" % dest)
        log("  files: %d added, %d changed, %d removed, %d total"
            % (len(added), len(changed), len(removed), sum(1 for p in staged.rglob("*") if p.is_file())))
        for label, names in (("+", added), ("~", changed), ("-", removed)):
            for name in names:
                log("    %s %s" % (label, name))

        if dry_run:
            log("Dry run: nothing was written.")
            return manifest["version"]

        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, target)

    _write(dest / ".claude-plugin" / "marketplace.json", json.dumps(market, indent=2) + "\n")

    # Marketplace-level files are seeded once and then left alone, so edits
    # made in the marketplace (other plugins, a custom README) survive.
    for name in ("README.md", "LICENSE", ".gitignore"):
        src = plugin_src / "marketplace" / name
        if src.is_file() and not (dest / name).exists():
            shutil.copy2(src, dest / name)
            log("  seeded %s" % name)

    if bump:
        _write(manifest_path, json.dumps(manifest, indent=2) + "\n")

    if validate:
        ok, output = run_validator(dest)
        log("Marketplace validator: " + (output.splitlines()[-1] if output else "ok"))
        if ok is False:
            raise PublishError("claude plugin validate failed on the marketplace:\n" + output)

    log("Published. Review the changes in %s, then commit and push." % dest)
    return manifest["version"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Publish Solution Factory to a plugin marketplace folder.")
    parser.add_argument("--dest", default=DEFAULT_DEST, help="marketplace folder (default: %(default)s)")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], help="raise the version before publishing")
    parser.add_argument("--dry-run", action="store_true", help="build and check, but change nothing")
    parser.add_argument("--no-validate", action="store_true", help="skip `claude plugin validate`")
    args = parser.parse_args(argv)
    try:
        publish(Path(args.dest).expanduser(), bump=args.bump, dry_run=args.dry_run,
                validate=not args.no_validate)
    except PublishError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
