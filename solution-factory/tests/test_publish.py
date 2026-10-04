"""
Tests for plugin/publish.py — the script that publishes Solution Factory to a
plugin marketplace folder.

Unit tests cover the text rewriting; the end-to-end tests publish the real
skills/agents/scripts/docs into a temp folder (never the real marketplace).
"""

import json
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugin"
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

import publish as pub  # noqa: E402

ROOT = "${CLAUDE_PLUGIN_ROOT}"


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

class TestRewritePaths:
    def test_script_call_is_rooted_and_quoted(self):
        src = "python3 ~/.claude/skills/solution-factory/scripts/get_status.py --root ."
        assert pub.rewrite_paths(src) == 'python3 "%s/scripts/get_status.py" --root .' % ROOT

    def test_ellipsis_form(self):
        src = "All `python3 ~/.claude/skills/solution-factory/scripts/...` invocations"
        assert pub.rewrite_paths(src) == 'All `python3 "%s/scripts/..."` invocations' % ROOT

    def test_doc_path(self):
        src = "Read `~/.claude/skills/solution-factory/docs/pipeline-help.md` using"
        assert pub.rewrite_paths(src) == "Read `%s/docs/pipeline-help.md` using" % ROOT

    def test_skill_file_is_renamed(self):
        src = "as written in `~/.claude/skills/solution/skill.md`, then STOP"
        assert pub.rewrite_paths(src) == "as written in `%s/skills/solution/SKILL.md`, then STOP" % ROOT

    def test_project_folder_untouched(self):
        src = "git add .solution-factory/ && ls .solution-factory/epics"
        assert pub.rewrite_paths(src) == src


# --------------------------------------------------------------------------
# Commands and agent names
# --------------------------------------------------------------------------

class TestRewriteNames:
    @pytest.mark.parametrize("src,expected", [
        ("Run `/solution next` now", "Run `/solution-factory:solution next` now"),
        ("/ideate → /create-stories", "/solution-factory:ideate → /solution-factory:create-stories"),
        ("run `/ideate`/`/bootstrap` first", "run `/solution-factory:ideate`/`/solution-factory:bootstrap` first"),
        ("then run /solution.", "then run /solution-factory:solution."),
        ("that is /create-stories's job", "that is /solution-factory:create-stories's job"),
        ("ask /guide", "ask /solution-factory:guide"),
    ])
    def test_commands_prefixed(self, src, expected):
        assert pub.rewrite_names(src) == expected

    @pytest.mark.parametrize("src", [
        "git add .solution-factory/",
        "under .solution-factory/ideas/ and writes",
        "see skills/solution/SKILL.md",
        "branch feature/solution-rework",
        "the /solution-factory:solution command",   # already prefixed
        "decisions/constraints and ideas/plans",
        "cd /solution-factory",
    ])
    def test_non_commands_untouched(self, src):
        assert pub.rewrite_names(src) == src

    @pytest.mark.parametrize("src,expected", [
        ("Spawn `code-reviewer` agent", "Spawn `solution-factory:code-reviewer` agent"),
        ("subagent_type=technical-architect", "subagent_type=solution-factory:technical-architect"),
        ("the **story-worker**", "the **solution-factory:story-worker**"),
        ("| infra | `devops-engineer` |", "| infra | `solution-factory:devops-engineer` |"),
    ])
    def test_agents_prefixed(self, src, expected):
        assert pub.rewrite_names(src) == expected

    @pytest.mark.parametrize("src", [
        "(`code-reviewer.md`, `security-engineer.md`)",   # agent definition files
        "name it `worker-[ID]`",
        "solution-factory:code-reviewer",                 # already prefixed
        "agents/story-worker",
    ])
    def test_non_agents_untouched(self, src):
        assert pub.rewrite_names(src) == src

    def test_continuation_lines_keep_column_alignment(self):
        src = "\n".join([
            "```",
            "  /solution stop     saves run state",
            "                     and commits it",
            "  /solution next     resumes",
            "```",
        ])
        lines = pub.rewrite_names(src).split("\n")
        assert lines[1].index("saves") == lines[2].index("and commits") == lines[3].index("resumes")

    def test_continuation_not_shifted_when_command_is_after_its_column(self):
        src = "\n".join([
            "```",
            "  plan       Requires a scaffold (run /ideate or",
            "             /bootstrap first).",
            "```",
        ])
        lines = pub.rewrite_names(src).split("\n")
        assert lines[2] == "             /solution-factory:bootstrap first)."

    def test_no_alignment_shift_outside_code_fences(self):
        src = "- Run `/solution next`\n        indented prose"
        assert pub.rewrite_names(src).split("\n")[1] == "        indented prose"

    def test_preformatted_doc_aligns_without_fences(self):
        src = "  /ideas     capture ideas, then\n             hand off"
        lines = pub.rewrite_names(src, preformatted=True).split("\n")
        assert lines[0].index("capture") == lines[1].index("hand off")


class TestTransform:
    def test_frontmatter_is_left_alone(self):
        src = "---\nname: story-worker\ndescription: runs /solution phases\n---\n\nUse story-worker with /solution.\n"
        out = pub.transform(src)
        assert out.startswith("---\nname: story-worker\ndescription: runs /solution phases\n---\n")
        assert "Use solution-factory:story-worker with /solution-factory:solution." in out

    def test_file_without_frontmatter(self):
        assert pub.transform("/ideate\n") == "/solution-factory:ideate\n"


# --------------------------------------------------------------------------
# Version
# --------------------------------------------------------------------------

class TestBumpVersion:
    @pytest.mark.parametrize("part,expected", [
        ("patch", "1.2.4"), ("minor", "1.3.0"), ("major", "2.0.0"),
    ])
    def test_bump(self, part, expected):
        assert pub.bump_version("1.2.3", part) == expected

    def test_bad_version(self):
        with pytest.raises(pub.PublishError):
            pub.bump_version("1.2", "patch")


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

class TestCheckOutput:
    def _plugin(self, tmp_path, name, text):
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
        return tmp_path

    def test_personal_path_is_reported(self, tmp_path):
        out = self._plugin(tmp_path, "skills/x/SKILL.md", "python3 ~/.claude/skills/other/thing.py\n")
        assert any("personal ~/.claude path" in p for p in pub.check_output(out))

    def test_absolute_home_path_is_reported(self, tmp_path):
        out = self._plugin(tmp_path, "scripts/x.py", 'P = "/Users/someone/x"\n')
        assert any("absolute home path" in p for p in pub.check_output(out))

    def test_missing_script_reference_is_reported(self, tmp_path):
        out = self._plugin(tmp_path, "skills/x/SKILL.md", 'python3 "%s/scripts/nope.py"\n' % ROOT)
        assert any("scripts/nope.py" in p for p in pub.check_output(out))

    def test_unknown_agent_reference_is_reported(self, tmp_path):
        out = self._plugin(tmp_path, "skills/x/SKILL.md", "Spawn `solution-factory:ghost-agent`\n")
        assert any("ghost-agent" in p for p in pub.check_output(out))

    def test_clean_output_has_no_problems(self, tmp_path):
        out = self._plugin(tmp_path, "skills/x/SKILL.md", "Run /solution-factory:solution\n")
        assert pub.check_output(out) == []


# --------------------------------------------------------------------------
# End to end, from the real sources into a temp marketplace
# --------------------------------------------------------------------------

@pytest.fixture
def source(tmp_path):
    """A throwaway copy of plugin/ so --bump never touches the real version file."""
    import shutil
    sf = tmp_path / "skills" / "solution-factory"
    shutil.copytree(pub.SF_DIR / "plugin", sf / "plugin", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(pub.SF_DIR / "scripts", sf / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(pub.SF_DIR / "docs", sf / "docs")
    return sf


def _publish(dest, source, **kwargs):
    log = []
    version = pub.publish(dest, validate=False, sf_dir=source, log=log.append, **kwargs)
    return version, log


class TestPublish:
    def test_layout(self, tmp_path, source):
        dest = tmp_path / "market"
        _publish(dest, source)
        plugin = dest / "plugins" / "solution-factory"

        assert (dest / ".claude-plugin" / "marketplace.json").is_file()
        assert (plugin / ".claude-plugin" / "plugin.json").is_file()
        for name in pub.SKILLS + pub.PLUGIN_ONLY_SKILLS:
            assert [p.name for p in (plugin / "skills" / name).iterdir() if p.suffix == ".md"] == ["SKILL.md"]
        assert sorted(p.stem for p in (plugin / "agents").glob("*.md")) == sorted(pub.AGENTS)
        assert sorted(p.name for p in (plugin / "scripts").iterdir()) == \
            sorted(p.name for p in (pub.SF_DIR / "scripts").glob("*.py"))
        assert sorted(p.name for p in (plugin / "docs").iterdir()) == sorted(pub.DOCS)
        for name in ("README.md", "LICENSE"):
            assert (plugin / name).is_file() and (dest / name).is_file()

    def test_nothing_private_is_published(self, tmp_path, source):
        dest = tmp_path / "market"
        _publish(dest, source)
        names = {p.name for p in dest.rglob("*")}
        assert not names & {"tests", ".venv", "__pycache__", ".pytest_cache", "publish.py",
                            "lane-processing-plan.md", "concurrent-slot-processing.md"}
        assert pub.check_output(dest / "plugins" / "solution-factory") == []

    def test_marketplace_entry(self, tmp_path, source):
        dest = tmp_path / "market"
        _publish(dest, source)
        market = json.loads((dest / ".claude-plugin" / "marketplace.json").read_text())
        assert market["name"] == "6thcents"
        assert [p["name"] for p in market["plugins"]] == ["solution-factory"]
        assert market["plugins"][0]["source"] == "./plugins/solution-factory"

    def test_agent_frontmatter_names_stay_unprefixed(self, tmp_path, source):
        dest = tmp_path / "market"
        _publish(dest, source)
        for name in pub.AGENTS:
            text = (dest / "plugins" / "solution-factory" / "agents" / (name + ".md")).read_text()
            assert "\nname: %s\n" % name in text

    def test_story_worker_gets_plugin_path_note(self, tmp_path, source):
        dest = tmp_path / "market"
        _publish(dest, source)
        text = (dest / "plugins" / "solution-factory" / "agents" / "story-worker.md").read_text()
        assert "## Plugin paths" in text and "installed at `%s`" % ROOT in text

    def test_republish_is_stable_and_keeps_other_plugins(self, tmp_path, source):
        dest = tmp_path / "market"
        _publish(dest, source)

        # Someone adds a second plugin and edits the marketplace README.
        other = dest / "plugins" / "other-plugin"
        other.mkdir()
        (other / "keep.txt").write_text("keep")
        market_path = dest / ".claude-plugin" / "marketplace.json"
        market = json.loads(market_path.read_text())
        market["plugins"].insert(0, {"name": "other-plugin", "source": "./plugins/other-plugin"})
        market_path.write_text(json.dumps(market))
        (dest / "README.md").write_text("custom readme")
        # ...and a stale file is left in our plugin folder.
        (dest / "plugins" / "solution-factory" / "stale.md").write_text("old")

        _, log = _publish(dest, source)

        assert (other / "keep.txt").read_text() == "keep"
        assert (dest / "README.md").read_text() == "custom readme"
        assert not (dest / "plugins" / "solution-factory" / "stale.md").exists()
        names = [p["name"] for p in json.loads(market_path.read_text())["plugins"]]
        assert names == ["other-plugin", "solution-factory"]
        assert any("0 added, 0 changed, 1 removed" in line for line in log)

    def test_dry_run_writes_nothing(self, tmp_path, source):
        dest = tmp_path / "market"
        before = json.loads((source / "plugin" / "plugin.json").read_text())["version"]
        version, _ = _publish(dest, source, dry_run=True, bump="minor")
        assert version == pub.bump_version(before, "minor")
        assert not dest.exists()
        assert json.loads((source / "plugin" / "plugin.json").read_text())["version"] == before

    def test_bump_updates_source_and_output(self, tmp_path, source):
        dest = tmp_path / "market"
        before = json.loads((source / "plugin" / "plugin.json").read_text())["version"]
        version, _ = _publish(dest, source, bump="patch")
        assert version == pub.bump_version(before, "patch")
        assert json.loads((source / "plugin" / "plugin.json").read_text())["version"] == version
        published = json.loads((dest / "plugins" / "solution-factory" / ".claude-plugin" / "plugin.json").read_text())
        assert published["version"] == version

    def test_refuses_to_replace_a_foreign_folder(self, tmp_path, source):
        dest = tmp_path / "market"
        foreign = dest / "plugins" / "solution-factory"
        foreign.mkdir(parents=True)
        (foreign / "important.txt").write_text("not ours")
        with pytest.raises(pub.PublishError, match="refusing to replace"):
            _publish(dest, source)
        assert (foreign / "important.txt").read_text() == "not ours"

    def test_leak_in_source_blocks_publish(self, tmp_path, source):
        dest = tmp_path / "market"
        (source / "docs" / "workflows.md").write_text("see ~/.claude/skills/private/notes.md\n")
        with pytest.raises(pub.PublishError, match="failed checks"):
            _publish(dest, source)
        assert not dest.exists()
