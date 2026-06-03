"""
Comprehensive test suite for the solution-factory scripts.

Covers the full lifecycle pipeline:
    init -> create epic -> add stories -> validate -> activate ->
    complete -> promote discoveries -> generate capsules

PyYAML is not assumed to be installed; the JSON fallback path is exercised
throughout.  If PyYAML IS installed the tests still pass because the scripts
choose the YAML path automatically — and both paths produce the same logical
structure (dicts / files on disk).

All tests use a temp-directory fixture that acts as the project root so that
no test touches the real filesystem outside of /tmp.
"""

import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — add the scripts directory to sys.path once so every import
# inside the scripts themselves also resolves correctly.
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path("/Users/davidrollins/.claude/skills/solution-factory/scripts")


def _load(module_name: str):
    """Import a script module by name from SCRIPTS_DIR."""
    spec = importlib.util.spec_from_file_location(
        module_name, SCRIPTS_DIR / f"{module_name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Make the module findable so cross-script imports work
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load all modules once so cross-module imports are satisfied
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_modules = {}
_script_names = [
    "config_loader",
    "scaffold_structure",
    "generate_sequence",
    "story_templates",
    "story_resolver",
    "validate_stories",
    "story_activator",
    "story_completer",
    "story_creator",
    "context_loader",
    "discovery_promoter",
    "capsule_generator",
    "read_docs",
    "get_status",
    "check_plan_complete",
    "check_context",
    "check_venv",
    "wireframe_linker",
    "epic_run_manager",
]
for _name in _script_names:
    try:
        _modules[_name] = _load(_name)
    except FileNotFoundError:
        pass  # script not yet implemented; tests for it will fail with KeyError


# ---------------------------------------------------------------------------
# Shared fixture: a fully scaffolded .solution-factory/ temp directory
# ---------------------------------------------------------------------------


@pytest.fixture()
def proj(tmp_path):
    """Return a temp project root with .solution-factory/ initialised."""
    scaffold = _modules["scaffold_structure"]
    result = scaffold.init_structure(root=str(tmp_path))
    assert result["success"] is True
    return tmp_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def seq_path(proj):
    return proj / ".solution-factory" / "sequence.json"


def read_seq(proj):
    with open(seq_path(proj)) as f:
        return json.load(f)


def make_minimal_story_data(story_id, epic_id, complexity=1):
    return {
        "id": story_id,
        "title": f"Story {story_id}",
        "epic": epic_id,
        "goal": "Do the thing",
        "acceptance": ["It works"],
        "complexity": complexity,
        "dependencies": [],
        "decisions": [],
        "constraints": [],
        "context": [],
    }


def _normalise_story_data(story_data):
    """
    Ensure decisions/constraints/context are in the nested-dict form that
    generate_story_yaml writes and context_loader reads:
        {"evaluated": True, "refs": [...]}   for decisions/constraints
        {"evaluated": True, "capsules": [...]} for context

    Plain lists are promoted to the correct shape.  Already-correct dicts are
    passed through unchanged.
    """
    result = dict(story_data)
    for field in ("decisions", "constraints"):
        val = result.get(field, [])
        if isinstance(val, list):
            result[field] = {"evaluated": True, "refs": val}
    context_val = result.get("context", [])
    if isinstance(context_val, list):
        result["context"] = {"evaluated": True, "capsules": context_val}
    return result


def write_story_yaml(proj, epic_id, story_id, status, story_data=None):
    """Write a story JSON file into the given status folder.

    The decisions/constraints/context fields are normalised to the dict form
    that context_loader expects.
    """
    if story_data is None:
        story_data = make_minimal_story_data(story_id, epic_id)
    normalised = _normalise_story_data(story_data)
    story_dir = (
        proj
        / ".solution-factory"
        / "epics"
        / epic_id
        / "stories"
        / status
        / story_id
    )
    story_dir.mkdir(parents=True, exist_ok=True)
    json_file = story_dir / f"{story_id}.json"
    with open(json_file, "w") as f:
        json.dump(normalised, f, indent=2)
    return story_dir


# ---------------------------------------------------------------------------
# 1. config_loader
# ---------------------------------------------------------------------------


class TestConfigLoader:
    def test_defaults_when_no_config_file(self, proj):
        loader = _modules["config_loader"]
        result = loader.load_config(root=str(proj))
        assert result["source"] == "defaults"
        assert result["config"]["complexity"]["threshold"] == 3
        assert result["config"]["relevance"]["auto_create"] == 8

    def test_returns_defaults_structure_keys(self, proj):
        loader = _modules["config_loader"]
        result = loader.load_config(root=str(proj))
        cfg = result["config"]
        assert "complexity" in cfg
        assert "relevance" in cfg
        assert "stories" in cfg
        assert "ux" in cfg

    def test_deep_merge_override(self):
        loader = _modules["config_loader"]
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99}, "c": 4}
        merged = loader.deep_merge(base, override)
        assert merged["a"]["x"] == 1   # kept from base
        assert merged["a"]["y"] == 99  # overridden
        assert merged["b"] == 3        # kept
        assert merged["c"] == 4        # added

    def test_deep_merge_scalar_override(self):
        loader = _modules["config_loader"]
        base = {"a": {"nested": 1}}
        override = {"a": 42}  # scalar overwrites dict
        merged = loader.deep_merge(base, override)
        assert merged["a"] == 42


# ---------------------------------------------------------------------------
# 2. scaffold_structure
# ---------------------------------------------------------------------------


class TestScaffoldStructure:
    def test_init_creates_dirs(self, tmp_path):
        scaffold = _modules["scaffold_structure"]
        result = scaffold.init_structure(root=str(tmp_path))
        assert result["success"] is True
        base = tmp_path / ".solution-factory"
        for sub in ["docs", "constraints", "decisions", "epics", "tests"]:
            assert (base / sub).exists()
        assert (base / "context" / "capsules").exists()

    def test_init_creates_sequence_json(self, tmp_path):
        scaffold = _modules["scaffold_structure"]
        scaffold.init_structure(root=str(tmp_path))
        seq = tmp_path / ".solution-factory" / "sequence.json"
        assert seq.exists()
        data = json.loads(seq.read_text())
        assert data["schema_version"] == "1.0"
        assert data["epics"] == []

    def test_init_idempotent(self, tmp_path):
        scaffold = _modules["scaffold_structure"]
        scaffold.init_structure(root=str(tmp_path))
        result2 = scaffold.init_structure(root=str(tmp_path))
        # Second call must not raise and sequence.json must still be valid
        assert result2["success"] is True
        data = json.loads((tmp_path / ".solution-factory" / "sequence.json").read_text())
        assert data["epics"] == []

    def test_create_epic(self, proj):
        scaffold = _modules["scaffold_structure"]
        result = scaffold.create_epic(1, root=str(proj))
        assert result["success"] is True
        assert result["epic"] == 1
        epic_base = proj / ".solution-factory" / "epics" / "epic-01" / "stories"
        for status in ["active", "backlog", "done", "deferred"]:
            assert (epic_base / status).exists()

    def test_create_story(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        result = scaffold.create_story(1, 1, status="backlog", root=str(proj))
        assert result["success"] is True
        assert result["story_id"] == "01.001"
        assert Path(result["path"]).exists()

    def test_create_story_zero_padded_ids(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(3, root=str(proj))
        result = scaffold.create_story(3, 7, root=str(proj))
        assert result["story_id"] == "03.007"


# ---------------------------------------------------------------------------
# 3. generate_sequence
# ---------------------------------------------------------------------------


class TestGenerateSequence:
    def test_add_epic(self, proj):
        gs = _modules["generate_sequence"]
        result = gs.add_epic("epic-01", root=str(proj))
        assert result["success"] is True
        data = read_seq(proj)
        assert any(e["id"] == "epic-01" for e in data["epics"])

    def test_add_duplicate_epic_errors(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        result = gs.add_epic("epic-01", root=str(proj))
        assert "error" in result

    def test_add_story(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        result = gs.add_story("epic-01", "01.001", root=str(proj))
        assert result["success"] is True
        data = read_seq(proj)
        epic = next(e for e in data["epics"] if e["id"] == "epic-01")
        assert any(s["id"] == "01.001" for s in epic["stories"])

    def test_add_duplicate_story_errors(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        result = gs.add_story("epic-01", "01.001", root=str(proj))
        assert "error" in result

    def test_add_story_to_missing_epic_errors(self, proj):
        gs = _modules["generate_sequence"]
        result = gs.add_story("epic-99", "99.001", root=str(proj))
        assert "error" in result

    def test_update_status(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        result = gs.update_status("01.001", "active", root=str(proj))
        assert result["success"] is True
        data = read_seq(proj)
        story = data["epics"][0]["stories"][0]
        assert story["status"] == "active"

    def test_update_status_done_sets_completed_timestamp(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        gs.update_status("01.001", "done", root=str(proj))
        data = read_seq(proj)
        story = data["epics"][0]["stories"][0]
        assert story["completed"] is not None

    def test_update_status_missing_story_errors(self, proj):
        gs = _modules["generate_sequence"]
        result = gs.update_status("99.999", "done", root=str(proj))
        assert "error" in result

    def test_update_epic_status(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        result = gs.update_epic_status("epic-01", "active", root=str(proj))
        assert result["success"] is True
        data = read_seq(proj)
        assert data["epics"][0]["status"] == "active"

    def test_insert_before(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        gs.add_story("epic-01", "01.002", dependencies=["01.001"], root=str(proj))
        # Insert 01.001b before 01.002
        result = gs.add_story(
            "epic-01", "01.001b", insert_before="01.002", root=str(proj)
        )
        # insert_before still succeeds (story is placed at correct index)
        assert result["success"] is True
        data = read_seq(proj)
        stories = data["epics"][0]["stories"]
        ids = [s["id"] for s in stories]
        assert ids.index("01.001b") < ids.index("01.002")

    def test_insert_before_missing_target_errors(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        result = gs.add_story(
            "epic-01", "01.002", insert_before="99.999", root=str(proj)
        )
        assert "error" in result

    def test_load_sequence_missing_file(self, tmp_path):
        gs = _modules["generate_sequence"]
        data, path = gs.load_sequence(root=str(tmp_path))
        assert data is None

    def test_stories_carry_dependencies(self, proj):
        gs = _modules["generate_sequence"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        gs.add_story("epic-01", "01.002", dependencies=["01.001"], root=str(proj))
        data = read_seq(proj)
        stories = {s["id"]: s for s in data["epics"][0]["stories"]}
        assert "01.001" in stories["01.002"]["dependencies"]


# ---------------------------------------------------------------------------
# 4. story_templates
# ---------------------------------------------------------------------------


class TestStoryTemplates:
    def test_generate_story_yaml(self, proj):
        st = _modules["story_templates"]
        out = proj / "test_story.yaml"
        story_data = make_minimal_story_data("01.001", "epic-01")
        result = st.generate_story_yaml(story_data, str(out))
        assert result["success"] is True
        assert out.exists()
        with open(out) as f:
            content = f.read()
        # The file must contain the story id — valid JSON or YAML
        assert "01.001" in content

    def test_generate_story_yaml_creates_parent_dirs(self, proj):
        st = _modules["story_templates"]
        deep = proj / "a" / "b" / "c" / "story.yaml"
        result = st.generate_story_yaml(
            make_minimal_story_data("01.001", "epic-01"), str(deep)
        )
        assert result["success"] is True
        assert deep.exists()

    def test_generate_epic_yaml(self, proj):
        st = _modules["story_templates"]
        out = proj / "epic-01.yaml"
        stories = [
            {"id": "01.001", "title": "Story 1", "status": "backlog", "complexity": 2},
            {"id": "01.002", "title": "Story 2", "status": "done", "complexity": 1},
        ]
        result = st.generate_epic_yaml(1, "My Epic", "A description", stories, str(out))
        assert result["success"] is True
        with open(out) as f:
            data = f.read()
        assert "epic-01" in data

    def test_update_epic_yaml(self, proj):
        st = _modules["story_templates"]
        scaffold = _modules["scaffold_structure"]
        gs = _modules["generate_sequence"]

        # Create epic dir structure
        scaffold.create_epic(1, root=str(proj))
        epic_dir = proj / ".solution-factory" / "epics" / "epic-01"

        # Write initial epic YAML
        epic_yaml_path = epic_dir / "epic-01.yaml"
        stories_list = []
        st.generate_epic_yaml(1, "Test Epic", "desc", stories_list, str(epic_yaml_path))

        # Place a story YAML in backlog
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

        result = st.update_epic_yaml(str(epic_yaml_path), root=str(proj))
        assert result["success"] is True
        assert result["story_count"] == 1

    def test_update_epic_yaml_missing_file_errors(self, proj):
        st = _modules["story_templates"]
        result = st.update_epic_yaml(str(proj / "nonexistent.yaml"), root=str(proj))
        assert "error" in result


# ---------------------------------------------------------------------------
# 5. story_resolver
# ---------------------------------------------------------------------------


class TestStoryResolver:
    def _setup_epic_with_stories(self, proj, stories):
        """
        stories: list of (story_id, status, deps) tuples
        Writes story yamls and sequence entries.
        """
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        for story_id, status, deps in stories:
            write_story_yaml(proj, "epic-01", story_id, status)
            gs.add_story("epic-01", story_id, dependencies=deps, root=str(proj))
            if status != "backlog":
                gs.update_status(story_id, status, root=str(proj))

    def test_resolve_next_ready_no_deps(self, proj):
        self._setup_epic_with_stories(
            proj, [("01.001", "backlog", []), ("01.002", "backlog", [])]
        )
        sr = _modules["story_resolver"]
        result = sr.resolve_next(root=str(proj))
        assert result["status"] in ("ready", "active")
        assert result["story_id"] == "01.001"

    def test_resolve_next_active_takes_priority(self, proj):
        self._setup_epic_with_stories(
            proj,
            [
                ("01.001", "done", []),
                ("01.002", "active", []),
                ("01.003", "backlog", []),
            ],
        )
        sr = _modules["story_resolver"]
        result = sr.resolve_next(root=str(proj))
        assert result["status"] == "active"
        assert result["story_id"] == "01.002"

    def test_resolve_next_blocked_by_dep(self, proj):
        self._setup_epic_with_stories(
            proj,
            [
                ("01.001", "backlog", []),
                ("01.002", "backlog", ["01.001"]),
            ],
        )
        # Mark 01.001 as NOT done yet — 01.002 is blocked; 01.001 is ready
        sr = _modules["story_resolver"]
        result = sr.resolve_next(root=str(proj))
        assert result["story_id"] == "01.001"

    def test_resolve_next_dep_done_unblocks_story(self, proj):
        self._setup_epic_with_stories(
            proj,
            [
                ("01.001", "done", []),
                ("01.002", "backlog", ["01.001"]),
            ],
        )
        sr = _modules["story_resolver"]
        result = sr.resolve_next(root=str(proj))
        assert result["status"] == "ready"
        assert result["story_id"] == "01.002"

    def test_resolve_next_all_done(self, proj):
        self._setup_epic_with_stories(proj, [("01.001", "done", [])])
        sr = _modules["story_resolver"]
        result = sr.resolve_next(root=str(proj))
        assert result["status"] == "complete"

    def test_list_stories(self, proj):
        self._setup_epic_with_stories(
            proj,
            [("01.001", "backlog", []), ("01.002", "done", [])],
        )
        sr = _modules["story_resolver"]
        result = sr.list_stories(root=str(proj))
        assert result["count"] == 2

    def test_list_stories_status_filter(self, proj):
        self._setup_epic_with_stories(
            proj,
            [("01.001", "backlog", []), ("01.002", "done", [])],
        )
        sr = _modules["story_resolver"]
        result = sr.list_stories(status_filter="done", root=str(proj))
        assert result["count"] == 1
        assert result["stories"][0]["id"] == "01.002"

    def test_resolve_next_missing_sequence_errors(self, tmp_path):
        sr = _modules["story_resolver"]
        result = sr.resolve_next(root=str(tmp_path))
        assert "error" in result


# ---------------------------------------------------------------------------
# 6. validate_stories
# ---------------------------------------------------------------------------


class TestValidateStories:
    def _bootstrap(self, proj, stories):
        """
        stories: list of (story_id, status, deps, complexity)
        """
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        for story_id, status, deps, complexity in stories:
            data = make_minimal_story_data(story_id, "epic-01", complexity)
            write_story_yaml(proj, "epic-01", story_id, status, story_data=data)
            gs.add_story("epic-01", story_id, dependencies=deps, root=str(proj))
            if status != "backlog":
                gs.update_status(story_id, status, root=str(proj))

    def test_valid_stories_pass(self, proj):
        self._bootstrap(
            proj,
            [
                ("01.001", "backlog", [], 1),
                ("01.002", "backlog", ["01.001"], 2),
            ],
        )
        vs = _modules["validate_stories"]
        result = vs.validate(root=str(proj))
        assert result["valid"] is True
        assert result["errors"] == []

    def test_duplicate_id_detected(self, proj):
        # Manually force a duplicate in sequence.json
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

        # Inject a second entry with the same id directly into the JSON
        data = read_seq(proj)
        data["epics"][0]["stories"].append(
            {"id": "01.001", "status": "backlog", "dependencies": [], "completed": None}
        )
        with open(seq_path(proj), "w") as f:
            json.dump(data, f)

        vs = _modules["validate_stories"]
        result = vs.validate(root=str(proj))
        assert result["valid"] is False
        assert any("Duplicate" in e for e in result["errors"])

    def test_complexity_over_threshold_fails(self, proj):
        self._bootstrap(proj, [("01.001", "backlog", [], 5)])
        vs = _modules["validate_stories"]
        result = vs.validate(root=str(proj))
        assert result["valid"] is False
        assert any("complexity" in e.lower() for e in result["errors"])

    def test_forward_dependency_fails(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        # Add 01.002 first, then 01.001 — so 01.001 appears after 01.002
        gs.add_story("epic-01", "01.002", root=str(proj))
        # Manually inject a forward dep in sequence
        data = read_seq(proj)
        data["epics"][0]["stories"][0]["dependencies"] = ["01.001"]
        data["epics"][0]["stories"].append(
            {"id": "01.001", "status": "backlog", "dependencies": [], "completed": None}
        )
        with open(seq_path(proj), "w") as f:
            json.dump(data, f)

        vs = _modules["validate_stories"]
        result = vs.validate(root=str(proj))
        assert result["valid"] is False
        assert any("forward" in e.lower() for e in result["errors"])

    def test_cycle_detection(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        gs.add_story("epic-01", "01.002", root=str(proj))

        # Inject a cycle: 01.001 depends on 01.002, 01.002 depends on 01.001
        data = read_seq(proj)
        stories = data["epics"][0]["stories"]
        stories[0]["dependencies"] = ["01.002"]
        stories[1]["dependencies"] = ["01.001"]
        with open(seq_path(proj), "w") as f:
            json.dump(data, f)

        vs = _modules["validate_stories"]
        result = vs.validate(root=str(proj))
        assert result["valid"] is False
        assert any("cycle" in e.lower() for e in result["errors"])

    def test_invalid_id_format(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        # Inject a story with a bad ID directly
        data = read_seq(proj)
        data["epics"][0]["stories"].append(
            {"id": "story-one", "status": "backlog", "dependencies": [], "completed": None}
        )
        with open(seq_path(proj), "w") as f:
            json.dump(data, f)

        vs = _modules["validate_stories"]
        result = vs.validate(root=str(proj))
        assert result["valid"] is False
        assert any("format" in e.lower() or "invalid" in e.lower() for e in result["errors"])

    def test_unknown_dependency_fails(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", dependencies=["99.999"], root=str(proj))

        vs = _modules["validate_stories"]
        result = vs.validate(root=str(proj))
        assert result["valid"] is False
        assert any("unknown" in e.lower() for e in result["errors"])

    def test_validate_specific_epic(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        scaffold.create_epic(2, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        gs.add_epic("epic-02", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

        vs = _modules["validate_stories"]
        result = vs.validate(epic_id="epic-01", root=str(proj))
        assert result["valid"] is True
        assert result["stories_checked"] == 1


# ---------------------------------------------------------------------------
# 7. story_activator
# ---------------------------------------------------------------------------


class TestStoryActivator:
    def test_activate_story(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

        sa = _modules["story_activator"]
        result = sa.activate_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True
        active_dir = (
            proj
            / ".solution-factory"
            / "epics"
            / "epic-01"
            / "stories"
            / "active"
            / "01.001"
        )
        assert active_dir.exists()
        assert (active_dir / "local.md").exists()
        assert (active_dir / "summary.md").exists()

    def test_activate_already_active_is_idempotent(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "active")

        sa = _modules["story_activator"]
        result = sa.activate_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True
        assert result.get("already_active") is True

    def test_activate_missing_story_errors(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))

        sa = _modules["story_activator"]
        result = sa.activate_story("01.999", "epic-01", root=str(proj))
        assert "error" in result

    def test_activate_creates_local_md_with_story_id(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

        sa = _modules["story_activator"]
        sa.activate_story("01.001", "epic-01", root=str(proj))
        local_md = (
            proj
            / ".solution-factory"
            / "epics"
            / "epic-01"
            / "stories"
            / "active"
            / "01.001"
            / "local.md"
        )
        content = local_md.read_text()
        assert "01.001" in content


# ---------------------------------------------------------------------------
# 8. story_completer
# ---------------------------------------------------------------------------


class TestStoryCompleter:
    def _make_active_story(self, proj, story_id="01.001", epic_id="epic-01"):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, epic_id, story_id, "active")
        active_dir = (
            proj / ".solution-factory" / "epics" / epic_id / "stories" / "active" / story_id
        )
        return active_dir

    def test_validate_completion_no_plan_md(self, proj):
        active_dir = self._make_active_story(proj)
        sc = _modules["story_completer"]
        result = sc.validate_completion("01.001", "epic-01", root=str(proj))
        assert result["valid"] is False
        assert any("plan.md" in e for e in result["errors"])

    def test_validate_completion_with_unchecked_boxes(self, proj):
        active_dir = self._make_active_story(proj)
        (active_dir / "plan.md").write_text(
            "- [x] Done thing\n- [ ] Undone thing\n"
        )
        sc = _modules["story_completer"]
        result = sc.validate_completion("01.001", "epic-01", root=str(proj))
        assert result["valid"] is False
        assert any("unchecked" in e.lower() or "1" in e for e in result["errors"])

    def test_validate_completion_all_checked(self, proj):
        active_dir = self._make_active_story(proj)
        (active_dir / "plan.md").write_text("- [x] Done thing\n- [X] Also done\n")
        sc = _modules["story_completer"]
        result = sc.validate_completion("01.001", "epic-01", root=str(proj))
        assert result["valid"] is True

    def test_complete_story_moves_to_done(self, proj):
        active_dir = self._make_active_story(proj)
        sc = _modules["story_completer"]
        result = sc.complete_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True
        done_dir = (
            proj
            / ".solution-factory"
            / "epics"
            / "epic-01"
            / "stories"
            / "done"
            / "01.001"
        )
        assert done_dir.exists()
        # Backlog folder should no longer exist
        assert not active_dir.exists()

    def test_complete_missing_story_errors(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        sc = _modules["story_completer"]
        result = sc.complete_story("01.999", "epic-01", root=str(proj))
        assert "error" in result

    def test_rollback_story(self, proj):
        active_dir = self._make_active_story(proj)
        sc = _modules["story_completer"]
        # Complete first
        sc.complete_story("01.001", "epic-01", root=str(proj))
        # Then roll back
        result = sc.rollback_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True
        assert active_dir.exists()

    def test_rollback_missing_story_errors(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        sc = _modules["story_completer"]
        result = sc.rollback_story("01.999", "epic-01", root=str(proj))
        assert "error" in result


# ---------------------------------------------------------------------------
# 9. story_creator
# ---------------------------------------------------------------------------


class TestStoryCreator:
    def _bootstrap(self, proj):
        scaffold = _modules["scaffold_structure"]
        gs = _modules["generate_sequence"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

    def test_create_from_discovery(self, proj):
        self._bootstrap(proj)
        sc = _modules["story_creator"]
        story_data = make_minimal_story_data("01.002", "epic-01")
        result = sc.create_from_discovery("epic-01", story_data, root=str(proj))
        assert result["success"] is True
        backlog_dir = (
            proj
            / ".solution-factory"
            / "epics"
            / "epic-01"
            / "stories"
            / "backlog"
            / "01.002"
        )
        assert backlog_dir.exists()
        assert (backlog_dir / "01.002.json").exists()

    def test_create_from_discovery_updates_sequence(self, proj):
        self._bootstrap(proj)
        sc = _modules["story_creator"]
        story_data = make_minimal_story_data("01.002", "epic-01")
        sc.create_from_discovery("epic-01", story_data, root=str(proj))
        data = read_seq(proj)
        ids = [s["id"] for s in data["epics"][0]["stories"]]
        assert "01.002" in ids

    def test_create_from_discovery_insert_before(self, proj):
        self._bootstrap(proj)
        sc = _modules["story_creator"]
        story_data = make_minimal_story_data("01.000", "epic-01")
        result = sc.create_from_discovery(
            "epic-01", story_data, insert_before="01.001", root=str(proj)
        )
        assert result["success"] is True
        data = read_seq(proj)
        ids = [s["id"] for s in data["epics"][0]["stories"]]
        assert ids.index("01.000") < ids.index("01.001")

    def test_create_duplicate_story_errors(self, proj):
        self._bootstrap(proj)
        sc = _modules["story_creator"]
        story_data = make_minimal_story_data("01.001", "epic-01")
        result = sc.create_from_discovery("epic-01", story_data, root=str(proj))
        # The sequence add_story call should fail with error
        assert "error" in result or not result.get("success")


# ---------------------------------------------------------------------------
# 10. context_loader
# ---------------------------------------------------------------------------


class TestContextLoader:
    def _write_adr(self, proj, adr_id, content):
        d = proj / ".solution-factory" / "decisions"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{adr_id}.md").write_text(content)

    def _write_constraint(self, proj, const_id, content):
        d = proj / ".solution-factory" / "constraints"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{const_id}.md").write_text(content)

    def _write_capsule(self, proj, name, content):
        d = proj / ".solution-factory" / "context" / "capsules"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(content)

    def test_load_context_missing_story_errors(self, proj):
        cl = _modules["context_loader"]
        result = cl.load_context("01.001", "epic-01", root=str(proj))
        assert "error" in result

    def test_load_context_no_refs(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

        cl = _modules["context_loader"]
        result = cl.load_context("01.001", "epic-01", root=str(proj))
        assert result["story_id"] == "01.001"
        assert result["decisions"] == []
        assert result["constraints"] == []
        assert result["capsules"] == []

    def test_load_context_with_refs(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        story_data = make_minimal_story_data("01.001", "epic-01")
        story_data["decisions"] = ["adr-001"]
        story_data["constraints"] = ["const-001"]
        story_data["context"] = ["auth-capsule"]
        write_story_yaml(proj, "epic-01", "01.001", "backlog", story_data=story_data)

        self._write_adr(proj, "adr-001", "# ADR-001\nUse JWT")
        self._write_constraint(proj, "const-001", "# const-001\nNo PII in logs")
        self._write_capsule(proj, "auth-capsule", "# Auth\nUse JWT")

        cl = _modules["context_loader"]
        result = cl.load_context("01.001", "epic-01", root=str(proj))
        assert len(result["decisions"]) == 1
        assert result["decisions"][0]["id"] == "adr-001"
        assert len(result["constraints"]) == 1
        assert len(result["capsules"]) == 1

    def test_load_context_loads_dependency_summary(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        # Story 01.002 depends on 01.001
        story_data = make_minimal_story_data("01.002", "epic-01")
        story_data["dependencies"] = ["01.001"]
        write_story_yaml(proj, "epic-01", "01.002", "backlog", story_data=story_data)

        # 01.001 is done with a summary
        done_dir = (
            proj
            / ".solution-factory"
            / "epics"
            / "epic-01"
            / "stories"
            / "done"
            / "01.001"
        )
        done_dir.mkdir(parents=True, exist_ok=True)
        (done_dir / "summary.md").write_text("Summary of 01.001")

        cl = _modules["context_loader"]
        result = cl.load_context("01.002", "epic-01", root=str(proj))
        assert len(result["dependency_summaries"]) == 1
        assert result["dependency_summaries"][0]["story_id"] == "01.001"

    def test_load_full_context_includes_story_data(self, proj):
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

        cl = _modules["context_loader"]
        result = cl.load_full_context("01.001", "epic-01", root=str(proj))
        assert "story_data" in result
        assert result["story_data"]["id"] == "01.001"


# ---------------------------------------------------------------------------
# 11. discovery_promoter
# ---------------------------------------------------------------------------


class TestDiscoveryPromoter:
    def _discovery(self, score, disc_type="decision"):
        return {
            "title": "Use Redis for caching",
            "content": "Redis provides fast in-memory caching",
            "type": disc_type,
            "relevance": score,
            "source_story": "01.001",
        }

    def test_auto_promote_high_score(self, proj):
        dp = _modules["discovery_promoter"]
        result = dp.promote_discoveries([self._discovery(9)], root=str(proj))
        assert result["success"] is True
        assert len(result["promoted"]) == 1
        assert len(result["needs_confirmation"]) == 0
        assert len(result["discarded"]) == 0

    def test_prompt_range(self, proj):
        dp = _modules["discovery_promoter"]
        result = dp.promote_discoveries([self._discovery(6)], root=str(proj))
        assert len(result["needs_confirmation"]) == 1
        assert len(result["promoted"]) == 0

    def test_auto_discard_low_score(self, proj):
        dp = _modules["discovery_promoter"]
        result = dp.promote_discoveries([self._discovery(2)], root=str(proj))
        assert len(result["discarded"]) == 1
        assert len(result["promoted"]) == 0

    def test_promoted_file_written_to_decisions(self, proj):
        dp = _modules["discovery_promoter"]
        result = dp.promote_discoveries([self._discovery(10, "decision")], root=str(proj))
        assert len(result["promoted"]) == 1
        path = Path(result["promoted"][0]["path"])
        assert path.exists()
        assert "adr-" in path.stem

    def test_promoted_file_written_to_constraints(self, proj):
        dp = _modules["discovery_promoter"]
        result = dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        path = Path(result["promoted"][0]["path"])
        assert "const-" in path.stem

    def test_sequential_ids(self, proj):
        dp = _modules["discovery_promoter"]
        dp.promote_discoveries([self._discovery(10)], root=str(proj))
        dp.promote_discoveries([self._discovery(10)], root=str(proj))
        decisions_dir = proj / ".solution-factory" / "decisions"
        files = sorted(decisions_dir.glob("adr-*.md"))
        assert len(files) == 2
        assert files[0].stem == "adr-001"
        assert files[1].stem == "adr-002"

    def test_confirm_and_promote(self, proj):
        dp = _modules["discovery_promoter"]
        disc = self._discovery(3)  # would normally be discarded
        result = dp.confirm_and_promote(disc, root=str(proj))
        assert result["success"] is True
        assert len(result["promoted"]) == 1

    def test_mixed_batch(self, proj):
        dp = _modules["discovery_promoter"]
        discoveries = [
            self._discovery(9),   # auto-promote
            self._discovery(6),   # prompt
            self._discovery(2),   # discard
        ]
        result = dp.promote_discoveries(discoveries, root=str(proj))
        assert len(result["promoted"]) == 1
        assert len(result["needs_confirmation"]) == 1
        assert len(result["discarded"]) == 1


# ---------------------------------------------------------------------------
# 12. capsule_generator
# ---------------------------------------------------------------------------


class TestCapsuleGenerator:
    def _write_adr(self, proj, name, content):
        d = proj / ".solution-factory" / "decisions"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(content)

    def _write_constraint(self, proj, name, content):
        d = proj / ".solution-factory" / "constraints"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(content)

    def test_generate_capsules_empty(self, proj):
        cg = _modules["capsule_generator"]
        result = cg.generate_capsules(root=str(proj))
        assert result["success"] is True
        assert result["capsules_generated"] == 0

    def test_generate_capsules_with_docs(self, proj):
        self._write_adr(
            proj,
            "adr-001",
            "# Use JWT for authentication\nJWT tokens provide stateless auth.\n"
            "## Decision\nUse JWT for all API authentication.",
        )
        cg = _modules["capsule_generator"]
        result = cg.generate_capsules(root=str(proj))
        assert result["success"] is True
        assert result["capsules_generated"] >= 1
        assert "authentication" in result["topics_found"]

    def test_capsule_file_created(self, proj):
        self._write_adr(
            proj,
            "adr-001",
            "# JWT Auth\nUsing JWT token for session management and authentication.",
        )
        cg = _modules["capsule_generator"]
        cg.generate_capsules(root=str(proj))
        capsule_path = proj / ".solution-factory" / "context" / "capsules" / "authentication.md"
        assert capsule_path.exists()

    def test_capsule_content_references_source(self, proj):
        self._write_adr(
            proj,
            "adr-007",
            "# Logging Strategy\nAll services use structured logging for observability.",
        )
        cg = _modules["capsule_generator"]
        cg.generate_capsules(root=str(proj))
        capsule_path = (
            proj / ".solution-factory" / "context" / "capsules" / "observability.md"
        )
        assert capsule_path.exists()
        content = capsule_path.read_text()
        assert "adr-007" in content

    def test_classify_topic(self):
        cg = _modules["capsule_generator"]
        scores = cg.classify_topic("Use JWT for authentication and authorization")
        assert "authentication" in scores
        assert scores["authentication"] >= 1

    def test_classify_topic_no_match(self):
        cg = _modules["capsule_generator"]
        # Use a sentence that contains none of the topic keywords
        scores = cg.classify_topic("The cat sat on the mat and drank milk")
        assert scores == {}


# ---------------------------------------------------------------------------
# 13. read_docs
# ---------------------------------------------------------------------------


class TestReadDocs:
    def test_read_docs_no_docs_dir(self, proj):
        # Docs dir is created by init but no files in it
        rd = _modules["read_docs"]
        result = rd.read_docs(root=str(proj))
        assert "error" in result

    def test_read_docs_with_file(self, proj):
        docs_dir = proj / ".solution-factory" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "overview.md").write_text(
            "# Overview\n\nThis is the project overview.\n\n## Goals\n\n- Goal 1\n- Goal 2\n"
        )
        rd = _modules["read_docs"]
        result = rd.read_docs(root=str(proj))
        assert "files" in result
        assert len(result["files"]) == 1
        assert result["files"][0]["filename"] == "overview.md"

    def test_extract_markdown_sections(self, proj):
        rd = _modules["read_docs"]
        docs_dir = proj / ".solution-factory" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        md_file = docs_dir / "test.md"
        md_file.write_text(
            "# Title\n\nSome text here.\n\n## Section One\n\nMore text.\n\n- item 1\n- item 2\n"
        )
        extracted = rd.extract_markdown(md_file)
        assert extracted["filename"] == "test.md"
        assert len(extracted["sections"]) >= 2
        titles = [s["title"] for s in extracted["sections"]]
        assert "Title" in titles
        assert "Section One" in titles

    def test_extract_markdown_lists(self, proj):
        rd = _modules["read_docs"]
        docs_dir = proj / ".solution-factory" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        md_file = docs_dir / "test.md"
        md_file.write_text("# Requirements\n\n- Req A\n- Req B\n- Req C\n")
        extracted = rd.extract_markdown(md_file)
        section = extracted["sections"][0]
        assert "Req A" in section["lists"]
        assert len(section["lists"]) == 3

    def test_extract_sentences(self):
        rd = _modules["read_docs"]
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = rd.extract_sentences(text, count=2)
        assert "First sentence." in result
        assert "Second sentence." in result
        assert "Third" not in result


# ---------------------------------------------------------------------------
# 14. get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    def test_get_status_no_sequence_errors(self, tmp_path):
        gs_mod = _modules["get_status"]
        result = gs_mod.get_status(root=str(tmp_path))
        assert "error" in result

    def test_get_status_empty_sequence(self, proj):
        gs_mod = _modules["get_status"]
        result = gs_mod.get_status(root=str(proj))
        assert result["total_stories"] == 0
        assert result["total_epics"] == 0

    def test_get_status_counts(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        gs.add_story("epic-01", "01.002", root=str(proj))
        gs.update_status("01.001", "done", root=str(proj))
        gs.update_status("01.002", "active", root=str(proj))

        gs_mod = _modules["get_status"]
        result = gs_mod.get_status(root=str(proj))
        assert result["total_stories"] == 2
        assert result["done"] == 1
        assert result["active"] == 1
        assert result["active_story"] == "01.002"
        assert result["active_epic"] == "epic-01"

    def test_get_status_epic_summary_keys(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))

        gs_mod = _modules["get_status"]
        result = gs_mod.get_status(root=str(proj))
        assert result["total_epics"] == 1
        epic_summary = result["epics"][0]
        for key in ["id", "status", "total", "done", "active", "backlog", "deferred"]:
            assert key in epic_summary


# ---------------------------------------------------------------------------
# 15. check_plan_complete
# ---------------------------------------------------------------------------


class TestCheckPlanComplete:
    def _place_plan(self, proj, story_id, epic_id, status, content):
        story_dir = (
            proj
            / ".solution-factory"
            / "epics"
            / epic_id
            / "stories"
            / status
            / story_id
        )
        story_dir.mkdir(parents=True, exist_ok=True)
        (story_dir / "plan.md").write_text(content)

    def test_all_checked(self, proj):
        self._place_plan(
            proj, "01.001", "epic-01", "active",
            "- [x] Task one\n- [X] Task two\n"
        )
        cpc = _modules["check_plan_complete"]
        result = cpc.check_plan_complete("01.001", "epic-01", root=str(proj))
        assert result["complete"] is True
        assert result["total"] == 2

    def test_some_unchecked(self, proj):
        self._place_plan(
            proj, "01.001", "epic-01", "active",
            "- [x] Done\n- [ ] Not done\n"
        )
        cpc = _modules["check_plan_complete"]
        result = cpc.check_plan_complete("01.001", "epic-01", root=str(proj))
        assert result["complete"] is False
        assert "Not done" in result["incomplete"]

    def test_plan_not_found(self, proj):
        cpc = _modules["check_plan_complete"]
        result = cpc.check_plan_complete("01.001", "epic-01", root=str(proj))
        assert "error" in result

    def test_plan_in_done_folder(self, proj):
        self._place_plan(
            proj, "01.001", "epic-01", "done",
            "- [x] Task done\n"
        )
        cpc = _modules["check_plan_complete"]
        result = cpc.check_plan_complete("01.001", "epic-01", root=str(proj))
        assert result["complete"] is True


# ---------------------------------------------------------------------------
# 16. check_context
# ---------------------------------------------------------------------------


class TestCheckContext:
    def test_returns_valid_json_structure(self):
        cc = _modules["check_context"]
        result = cc.check_context()
        assert isinstance(result, dict)
        # Must have either 'clean' key
        assert "clean" in result
        # clean must be bool
        assert isinstance(result["clean"], bool)

    def test_returns_warning_when_no_clear(self, monkeypatch):
        """Force all history paths to non-existent to guarantee clean=False."""
        cc = _modules["check_context"]

        # Monkeypatch Path.home to return a path guaranteed not to have any history
        monkeypatch.setattr(
            "pathlib.Path.home",
            classmethod(lambda cls: Path("/nonexistent_home_path_xyz")),
        )
        result = cc.check_context()
        # With no history files, should report clean=False
        assert result["clean"] is False
        assert "warning" in result


# ---------------------------------------------------------------------------
# 17. check_venv
# ---------------------------------------------------------------------------


class TestCheckVenv:
    def test_returns_valid_json_structure(self):
        cv = _modules["check_venv"]
        result = cv.check_venv()
        assert isinstance(result, dict)
        assert "active" in result
        assert isinstance(result["active"], bool)

    def test_detects_virtual_env(self, monkeypatch):
        cv = _modules["check_venv"]
        monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")
        monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)
        result = cv.check_venv()
        assert result["active"] is True
        assert result["type"] == "virtualenv"
        assert result["path"] == "/path/to/venv"

    def test_detects_conda_env(self, monkeypatch):
        cv = _modules["check_venv"]
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setenv("CONDA_DEFAULT_ENV", "myenv")
        result = cv.check_venv()
        assert result["active"] is True
        assert result["type"] == "conda"
        assert result["env"] == "myenv"

    def test_no_venv_returns_warning(self, monkeypatch):
        cv = _modules["check_venv"]
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)
        result = cv.check_venv()
        assert result["active"] is False
        assert "warning" in result


# ---------------------------------------------------------------------------
# 18. wireframe_linker
# ---------------------------------------------------------------------------


class TestWireframeLinker:
    def test_no_config_errors(self, proj):
        wl = _modules["wireframe_linker"]
        result = wl.list_wireframes(root=str(proj))
        assert "error" in result

    def test_wireframe_path_not_configured(self, proj):
        """config.json exists but no wireframe_path set."""
        config_path = proj / ".solution-factory" / "config.json"
        config_path.write_text(json.dumps({"ux": {"wireframe_path": None}}))

        wl = _modules["wireframe_linker"]
        result = wl.list_wireframes(root=str(proj))
        assert "error" in result

    def test_wireframe_path_missing_dir(self, proj):
        """wireframe_path is configured but dir doesn't exist."""
        config_path = proj / ".solution-factory" / "config.json"
        config_path.write_text(json.dumps({"ux": {"wireframe_path": "wireframes"}}))

        wl = _modules["wireframe_linker"]
        result = wl.list_wireframes(root=str(proj))
        assert "error" in result

    def test_wireframe_list(self, proj):
        """Full happy path — reads config.json."""
        wf_dir = proj / "wireframes"
        wf_dir.mkdir()
        (wf_dir / "Dashboard.tsx").touch()
        (wf_dir / "Login.tsx").touch()

        config_path = proj / ".solution-factory" / "config.json"
        config_path.write_text(json.dumps({"ux": {"wireframe_path": "wireframes"}}))

        wl = _modules["wireframe_linker"]
        result = wl.list_wireframes(root=str(proj))
        assert result["count"] == 2
        names = [w["name"] for w in result["wireframes"]]
        assert "Dashboard" in names
        assert "Login" in names


# ---------------------------------------------------------------------------
# Full lifecycle integration test
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """
    End-to-end smoke test covering the complete pipeline:
    init -> epic -> stories -> validate -> activate -> complete ->
    promote discoveries -> generate capsules
    """

    def test_lifecycle(self, proj):
        scaffold = _modules["scaffold_structure"]
        gs = _modules["generate_sequence"]
        st = _modules["story_templates"]
        vs = _modules["validate_stories"]
        sa = _modules["story_activator"]
        sc = _modules["story_completer"]
        dp = _modules["discovery_promoter"]
        cg = _modules["capsule_generator"]
        gs_mod = _modules["get_status"]

        root = str(proj)

        # 1. Create epic scaffold
        scaffold.create_epic(1, root=root)
        gs.add_epic("epic-01", root=root)

        # 2. Add two stories
        gs.add_story("epic-01", "01.001", root=root)
        gs.add_story("epic-01", "01.002", dependencies=["01.001"], root=root)

        # Write story YAMLs
        for sid in ["01.001", "01.002"]:
            write_story_yaml(proj, "epic-01", sid, "backlog")

        # 3. Validate
        result = vs.validate(root=root)
        assert result["valid"] is True

        # 4. Activate first story
        result = sa.activate_story("01.001", "epic-01", root=root)
        assert result["success"] is True
        gs.update_status("01.001", "active", root=root)

        # 5. Check status shows active
        status = gs_mod.get_status(root=root)
        assert status["active"] == 1
        assert status["active_story"] == "01.001"

        # 6. Complete first story (add plan.md first)
        active_dir = (
            proj
            / ".solution-factory"
            / "epics"
            / "epic-01"
            / "stories"
            / "active"
            / "01.001"
        )
        (active_dir / "plan.md").write_text("- [x] Implement feature\n- [x] Write tests\n")

        result = sc.validate_completion("01.001", "epic-01", root=root)
        assert result["valid"] is True

        result = sc.complete_story("01.001", "epic-01", root=root)
        assert result["success"] is True
        gs.update_status("01.001", "done", root=root)

        # 7. Story 01.002 is now unblocked
        from story_resolver import resolve_next
        next_story = resolve_next(root=root)
        assert next_story["story_id"] == "01.002"

        # 8. Promote a discovery
        discoveries = [
            {
                "title": "Use Redis for session cache",
                "content": "Redis provides fast in-memory session storage and caching",
                "type": "decision",
                "relevance": 9,
                "source_story": "01.001",
            }
        ]
        result = dp.promote_discoveries(discoveries, root=root)
        assert result["success"] is True
        assert len(result["promoted"]) == 1

        # 9. Generate capsules
        result = cg.generate_capsules(root=root)
        assert result["success"] is True
        # The "performance" topic matches "caching"
        assert result["capsules_generated"] >= 1

        # 10. Final status
        status = gs_mod.get_status(root=root)
        assert status["done"] == 1
        assert status["backlog"] == 1


# ---------------------------------------------------------------------------
# 19. epic_run_manager
# ---------------------------------------------------------------------------


class TestEpicRunManager:
    def _write_epic_json(self, proj, epic_id, extra=None):
        epic_dir = proj / ".solution-factory" / "epics" / epic_id
        epic_dir.mkdir(parents=True, exist_ok=True)
        data = {"id": epic_id, "title": f"Epic {epic_id}", "stories": []}
        if extra:
            data.update(extra)
        (epic_dir / f"{epic_id}.json").write_text(json.dumps(data, indent=2))
        return epic_dir

    def test_start_run_writes_run_block(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        result = erm.start_run("epic-01", review_merges=False, root=str(proj))
        assert result["success"] is True
        assert result["run"]["status"] == "active"
        assert result["run"]["review_merges"] is False
        assert result["run"]["started_at"] is not None
        assert result["run"]["stopped_at"] is None
        assert result["run"]["current_story"] is None

    def test_start_run_review_merges_true(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        result = erm.start_run("epic-01", review_merges=True, root=str(proj))
        assert result["run"]["review_merges"] is True

    def test_start_run_missing_epic_errors(self, proj):
        erm = _modules["epic_run_manager"]
        result = erm.start_run("epic-99", review_merges=False, root=str(proj))
        assert "error" in result

    def test_stop_run_sets_status_and_timestamp(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        erm.start_run("epic-01", review_merges=False, root=str(proj))
        result = erm.stop_run("epic-01", root=str(proj))
        assert result["success"] is True
        assert result["run"]["status"] == "stopped"
        assert result["run"]["stopped_at"] is not None

    def test_stop_run_preserves_other_fields(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        erm.start_run("epic-01", review_merges=True, root=str(proj))
        erm.update_current_story("epic-01", "01.003", root=str(proj))
        result = erm.stop_run("epic-01", root=str(proj))
        assert result["run"]["review_merges"] is True
        assert result["run"]["current_story"] == "01.003"

    def test_stop_run_no_run_block_errors(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        result = erm.stop_run("epic-01", root=str(proj))
        assert "error" in result

    def test_complete_run_sets_status_and_clears_story(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        erm.start_run("epic-01", review_merges=False, root=str(proj))
        erm.update_current_story("epic-01", "01.002", root=str(proj))
        result = erm.complete_run("epic-01", root=str(proj))
        assert result["success"] is True
        assert result["run"]["status"] == "complete"
        assert result["run"]["current_story"] is None

    def test_update_current_story(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        erm.start_run("epic-01", review_merges=False, root=str(proj))
        result = erm.update_current_story("epic-01", "01.004", root=str(proj))
        assert result["success"] is True
        assert result["current_story"] == "01.004"

    def test_find_active_run_none_exist(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        result = erm.find_active_run(root=str(proj))
        assert result["found"] is False

    def test_find_active_run_finds_active(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        erm.start_run("epic-01", review_merges=False, root=str(proj))
        result = erm.find_active_run(root=str(proj))
        assert result["found"] is True
        assert result["epic_id"] == "epic-01"
        assert result["run"]["status"] == "active"

    def test_find_active_run_finds_stopped(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        erm.start_run("epic-01", review_merges=False, root=str(proj))
        erm.stop_run("epic-01", root=str(proj))
        result = erm.find_active_run(root=str(proj))
        assert result["found"] is True
        assert result["run"]["status"] == "stopped"

    def test_find_active_run_ignores_complete(self, proj):
        self._write_epic_json(proj, "epic-01")
        erm = _modules["epic_run_manager"]
        erm.start_run("epic-01", review_merges=False, root=str(proj))
        erm.complete_run("epic-01", root=str(proj))
        result = erm.find_active_run(root=str(proj))
        assert result["found"] is False

    def test_find_active_run_returns_first_match(self, proj):
        self._write_epic_json(proj, "epic-01")
        self._write_epic_json(proj, "epic-02")
        erm = _modules["epic_run_manager"]
        erm.start_run("epic-01", review_merges=False, root=str(proj))
        erm.start_run("epic-02", review_merges=True, root=str(proj))
        result = erm.find_active_run(root=str(proj))
        assert result["found"] is True
        assert result["epic_id"] == "epic-01"  # sorted glob, epic-01 first
