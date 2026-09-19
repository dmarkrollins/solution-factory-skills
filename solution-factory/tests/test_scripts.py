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
    "schedule_stories",
    "idea_store",
    "idea_plan_check",
    "read_idea_plan",
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
        assert "epic_run" in cfg

    def test_epic_run_defaults(self, proj):
        loader = _modules["config_loader"]
        cfg = loader.load_config(root=str(proj))["config"]["epic_run"]
        assert cfg == {
            "max_concurrent": 3,
            "shared_paths": [".solution-factory/**"],
            "worktree_setup": None,
        }

    def test_epic_run_partial_override_keeps_other_defaults(self, proj):
        loader = _modules["config_loader"]
        cfg_path = proj / ".solution-factory" / "config.json"
        cfg_path.write_text(json.dumps({
            "epic_run": {"max_concurrent": 1, "worktree_setup": "npm ci"}
        }))
        cfg = loader.load_config(root=str(proj))["config"]["epic_run"]
        assert cfg["max_concurrent"] == 1
        assert cfg["worktree_setup"] == "npm ci"
        assert cfg["shared_paths"] == [".solution-factory/**"]

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

    def test_merge_branch_defaults_to_main(self, proj):
        loader = _modules["config_loader"]
        result = loader.load_config(root=str(proj))
        assert result["config"]["stories"]["merge_branch"] == "main"

    def test_merge_branch_override_from_config(self, proj):
        loader = _modules["config_loader"]
        config_path = proj / ".solution-factory" / "config.json"
        config_path.write_text(json.dumps({"stories": {"merge_branch": "develop"}}))
        result = loader.load_config(root=str(proj))
        assert result["config"]["stories"]["merge_branch"] == "develop"

    def test_merge_branch_survives_partial_stories_override(self, proj):
        loader = _modules["config_loader"]
        config_path = proj / ".solution-factory" / "config.json"
        config_path.write_text(json.dumps({"stories": {"automerge": False}}))
        result = loader.load_config(root=str(proj))
        assert result["config"]["stories"]["merge_branch"] == "main"
        assert result["config"]["stories"]["automerge"] is False

    def test_auto_accept_recommendations_defaults_true(self, proj):
        loader = _modules["config_loader"]
        result = loader.load_config(root=str(proj))
        assert result["config"]["stories"]["auto_accept_recommendations"] is True


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

    # -- outputs: {create, modify} ------------------------------------------

    def _write_with_outputs(self, proj, outputs):
        st = _modules["story_templates"]
        out = proj / "story.json"
        data = make_minimal_story_data("01.001", "epic-01")
        if outputs is not None:
            data["outputs"] = outputs
        result = st.generate_story_yaml(data, str(out))
        written = json.loads(out.read_text()) if out.exists() else None
        return result, written

    def test_outputs_written_in_create_modify_shape(self, proj):
        result, written = self._write_with_outputs(
            proj, {"create": ["src/new.py"], "modify": ["src/app.py", "tests/test_app.py"]}
        )
        assert result["success"] is True
        assert written["outputs"] == {
            "create": ["src/new.py"],
            "modify": ["src/app.py", "tests/test_app.py"],
        }

    def test_outputs_missing_key_defaults_to_empty_list(self, proj):
        result, written = self._write_with_outputs(proj, {"modify": ["src/app.py"]})
        assert result["success"] is True
        assert written["outputs"] == {"create": [], "modify": ["src/app.py"]}

    def test_outputs_paths_stripped_and_deduplicated(self, proj):
        result, written = self._write_with_outputs(
            proj, {"create": [" src/a.py ", "src/a.py", ""], "modify": []}
        )
        assert result["success"] is True
        assert written["outputs"] == {"create": ["src/a.py"], "modify": []}

    def test_outputs_omitted_when_absent_or_empty(self, proj):
        _, written = self._write_with_outputs(proj, None)
        assert "outputs" not in written
        _, written = self._write_with_outputs(proj, {"create": [], "modify": []})
        assert "outputs" not in written

    def test_outputs_rejects_plain_list(self, proj):
        result, written = self._write_with_outputs(proj, ["src/app.py"])
        assert "error" in result and "outputs" in result["error"]
        assert written is None

    def test_outputs_rejects_unknown_keys_and_non_string_paths(self, proj):
        result, _ = self._write_with_outputs(proj, {"delete": ["x"]})
        assert "error" in result and "unknown keys" in result["error"]
        result, _ = self._write_with_outputs(proj, {"modify": [42]})
        assert "error" in result and "outputs.modify" in result["error"]


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

    # -- outputs shape, missing-outputs warning, hot-file warning ------------

    def _bootstrap_with_outputs(self, proj, stories):
        """stories: list of (story_id, status, outputs-or-None)."""
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        for story_id, status, outputs in stories:
            data = make_minimal_story_data(story_id, "epic-01")
            if outputs is not None:
                data["outputs"] = outputs
            write_story_yaml(proj, "epic-01", story_id, status, story_data=data)
            gs.add_story("epic-01", story_id, root=str(proj))
            if status != "backlog":
                gs.update_status(story_id, status, root=str(proj))
        return _modules["validate_stories"].validate(epic_id="epic-01", root=str(proj))

    def test_well_formed_outputs_pass_without_warnings(self, proj):
        result = self._bootstrap_with_outputs(proj, [
            ("01.001", "backlog", {"create": ["src/a.py"], "modify": ["src/app.py"]}),
            ("01.002", "backlog", {"create": [], "modify": ["src/b.py"]}),
        ])
        assert result["valid"] is True
        assert result["warnings"] == []

    def test_outputs_shape_errors(self, proj):
        result = self._bootstrap_with_outputs(proj, [
            ("01.001", "backlog", ["src/a.py"]),
            ("01.002", "backlog", {"modify": "src/b.py"}),
            ("01.003", "backlog", {"create": ["/abs/path.py", "../escape.py", ""]}),
            ("01.004", "backlog", {"remove": ["x"]}),
        ])
        assert result["valid"] is False
        errs = "\n".join(result["errors"])
        assert "01.001 outputs must be an object" in errs
        assert "01.002 outputs.modify must be a list" in errs
        assert "01.003 outputs.create path must be repo-relative: /abs/path.py" in errs
        assert "01.003 outputs.create path must be repo-relative: ../escape.py" in errs
        assert "01.003 outputs.create contains a non-string or empty path" in errs
        assert "01.004 outputs has unknown keys: ['remove']" in errs

    def test_missing_outputs_warns_for_open_stories_only(self, proj):
        result = self._bootstrap_with_outputs(proj, [
            ("01.001", "done", None),
            ("01.002", "backlog", None),
            ("01.003", "active", None),
            ("01.004", "backlog", {"modify": ["src/x.py"]}),
        ])
        assert result["valid"] is True
        missing = [w for w in result["warnings"] if "declare no outputs" in w]
        assert len(missing) == 1
        assert "2 open stories" in missing[0]
        assert "01.002, 01.003" in missing[0]
        assert "01.001" not in missing[0]

    def test_hot_file_warning_names_file_and_stories(self, proj):
        result = self._bootstrap_with_outputs(proj, [
            ("01.001", "backlog", {"modify": ["src/utils.py"]}),
            ("01.002", "backlog", {"modify": ["src/utils.py", "src/other.py"]}),
            ("01.003", "backlog", {"modify": ["src/utils.py"]}),
            ("01.004", "backlog", {"create": ["src/utils.py"]}),
        ])
        assert result["valid"] is True
        hot = [w for w in result["warnings"] if "hot file" in w]
        assert len(hot) == 1
        assert "src/utils.py is modified by 3 stories (01.001, 01.002, 01.003)" in hot[0]

    # -- cross-epic dependency resolution ----------------------------------
    #
    # Dependencies are GLOBAL story IDs and epics run sequentially, so a story
    # in epic-NN+1 may legitimately depend on one in epic-NN -- /create-stories
    # sanctions this explicitly, and it happens routinely whenever an epic is
    # split at the story cap. The bug these cover: --epic filtered the epic
    # list first, then resolved every dependency against that same filtered
    # list, so a cross-epic dependency could never resolve.

    def _two_epics(self, proj, epic_01_stories, epic_02_stories):
        """Scaffold two epics. Stories are (story_id, dependencies) tuples.

        epic-01 is added to sequence.json before epic-02, so every story in
        epic-01 precedes every story in epic-02 in global execution order.
        """
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        scaffold.create_epic(1, root=str(proj))
        scaffold.create_epic(2, root=str(proj))
        gs.add_epic("epic-01", root=str(proj))
        gs.add_epic("epic-02", root=str(proj))
        for epic_id, stories in (
            ("epic-01", epic_01_stories),
            ("epic-02", epic_02_stories),
        ):
            for story_id, deps in stories:
                write_story_yaml(proj, epic_id, story_id, "backlog")
                gs.add_story(epic_id, story_id, dependencies=deps, root=str(proj))

    def test_cross_epic_dependency_on_earlier_epic_passes_when_scoped(self, proj):
        """A dependency living in an EARLIER epic must resolve even when only
        the later epic is under validation -- this is the regression."""
        self._two_epics(proj, [("01.001", [])], [("02.001", ["01.001"])])
        vs = _modules["validate_stories"]
        result = vs.validate(epic_id="epic-02", root=str(proj))
        assert result["valid"] is True
        assert result["errors"] == []

    def test_cross_epic_dependency_on_earlier_epic_passes_unscoped(self, proj):
        """The same sequence validated whole must also pass."""
        self._two_epics(proj, [("01.001", [])], [("02.001", ["01.001"])])
        vs = _modules["validate_stories"]
        result = vs.validate(root=str(proj))
        assert result["valid"] is True
        assert result["errors"] == []

    def test_cross_epic_forward_reference_still_fails(self, proj):
        """A dependency on a LATER epic is still a forward reference. Accepting
        cross-epic deps must not degrade into accepting every cross-epic dep."""
        self._two_epics(proj, [("01.001", ["02.001"])], [("02.001", [])])
        vs = _modules["validate_stories"]
        result = vs.validate(epic_id="epic-01", root=str(proj))
        assert result["valid"] is False
        assert any("forward" in e.lower() for e in result["errors"])

    def test_unknown_dependency_still_fails_when_epic_scoped(self, proj):
        """A dependency in no epic at all is still unknown, not cross-epic."""
        self._two_epics(proj, [("01.001", [])], [("02.001", ["99.999"])])
        vs = _modules["validate_stories"]
        result = vs.validate(epic_id="epic-02", root=str(proj))
        assert result["valid"] is False
        assert any("unknown" in e.lower() for e in result["errors"])

    def test_intra_epic_forward_reference_still_fails_when_scoped(self, proj):
        """Within one epic, depending on a later story is still a forward ref."""
        self._two_epics(
            proj, [("01.001", [])], [("02.001", ["02.002"]), ("02.002", [])]
        )
        vs = _modules["validate_stories"]
        result = vs.validate(epic_id="epic-02", root=str(proj))
        assert result["valid"] is False
        assert any("forward" in e.lower() for e in result["errors"])

    def test_epic_scoped_run_does_not_report_other_epic_errors(self, proj):
        """Resolving against the global order must not widen REPORTING scope:
        epic-01's broken dependency belongs to epic-01's own validation run."""
        self._two_epics(proj, [("01.001", ["99.999"])], [("02.001", ["01.001"])])
        vs = _modules["validate_stories"]

        scoped = vs.validate(epic_id="epic-02", root=str(proj))
        assert scoped["valid"] is True
        assert scoped["errors"] == []

        # ...but a whole-sequence run still surfaces it.
        full = vs.validate(root=str(proj))
        assert full["valid"] is False
        assert any("unknown" in e.lower() for e in full["errors"])

    def test_cycle_spanning_epic_boundary_detected_when_scoped(self, proj):
        """Cycle detection builds its graph from ALL epics, so a cycle crossing
        an epic boundary is traversable while validating just one epic. Before
        the fix the graph was built from the filtered list and the traversal
        dead-ended at the epic boundary."""
        self._two_epics(proj, [("01.001", ["02.001"])], [("02.001", ["01.001"])])
        vs = _modules["validate_stories"]
        result = vs.validate(epic_id="epic-01", root=str(proj))
        assert result["valid"] is False
        assert any("cycle" in e.lower() for e in result["errors"])


# ---------------------------------------------------------------------------
# 7. story_activator
# ---------------------------------------------------------------------------


class TestStoryActivator:
    def test_activate_story(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
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
        assert not (active_dir / "summary.md").exists()

    def test_activate_already_active_is_idempotent(self, proj):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        gs.update_status("01.001", "active", root=str(proj))
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
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
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

    def test_activate_story_syncs_sequence_status(self, proj):
        """Activation must flip sequence.json's status in the SAME call that
        moves the folder -- never a separate step an orchestrator can skip or
        get interrupted between."""
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, "epic-01", "01.001", "backlog")

        sa = _modules["story_activator"]
        result = sa.activate_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True

        story = read_seq(proj)["epics"][0]["stories"][0]
        assert story["status"] == "active"

    def test_activate_self_heals_stale_sequence_status(self, proj):
        """Simulates an interrupted prior activation: the folder was already
        moved to active/ but sequence.json was never flipped (still backlog).
        Re-running activate_story must repair sequence.json -- not just report
        'already active' and leave the drift in place."""
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        gs.add_epic("epic-01", root=str(proj))
        gs.add_story("epic-01", "01.001", root=str(proj))
        scaffold.create_epic(1, root=str(proj))
        # Folder physically already in active/...
        write_story_yaml(proj, "epic-01", "01.001", "active")
        # ...but sequence.json was never updated past its seeded "backlog"
        assert read_seq(proj)["epics"][0]["stories"][0]["status"] == "backlog"

        sa = _modules["story_activator"]
        result = sa.activate_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True
        assert result.get("already_active") is True

        story = read_seq(proj)["epics"][0]["stories"][0]
        assert story["status"] == "active"

    # -- pre-existing active/ directory ------------------------------------
    #
    # shutil.move(src, dst) RENAMES when dst does not exist, but moves src
    # *inside* dst when dst is an existing directory -- even an empty one. So a
    # stray `mkdir` of active/{id}/ turns activation into a silent
    # active/{id}/{id}/ nesting rather than an error.

    def _backlog_story(self, proj, story_id="01.001", epic_id="epic-01"):
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        gs.add_epic(epic_id, root=str(proj))
        gs.add_story(epic_id, story_id, root=str(proj))
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, epic_id, story_id, "backlog")
        return proj / ".solution-factory" / "epics" / epic_id / "stories"

    def test_activate_over_empty_active_dir_does_not_nest(self, proj):
        """An empty pre-existing active/{id}/ must be cleared, not moved into:
        the story's files land directly in active/{id}/, never active/{id}/{id}/."""
        stories = self._backlog_story(proj)
        active_dir = stories / "active" / "01.001"
        active_dir.mkdir(parents=True)  # stray empty dir, e.g. from tooling

        sa = _modules["story_activator"]
        result = sa.activate_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True

        assert (active_dir / "01.001.json").exists()
        assert (active_dir / "local.md").exists()
        assert not (active_dir / "01.001").exists()  # the nesting bug
        assert not (stories / "backlog" / "01.001").exists()

    def test_activate_over_empty_active_dir_still_syncs_sequence(self, proj):
        """Clearing the stray directory must not skip the status sync."""
        stories = self._backlog_story(proj)
        (stories / "active" / "01.001").mkdir(parents=True)

        sa = _modules["story_activator"]
        assert sa.activate_story("01.001", "epic-01", root=str(proj))["success"] is True
        assert read_seq(proj)["epics"][0]["stories"][0]["status"] == "active"

    def test_activate_over_nonempty_active_dir_errors(self, proj):
        """Story present in BOTH backlog and active is a split-brain state.
        Refuse -- do not clobber the active copy and do not nest into it."""
        stories = self._backlog_story(proj)
        active_dir = stories / "active" / "01.001"
        active_dir.mkdir(parents=True)
        (active_dir / "local.md").write_text("work in progress")

        sa = _modules["story_activator"]
        result = sa.activate_story("01.001", "epic-01", root=str(proj))
        assert "error" in result
        assert "non-empty" in result["error"]

        # Nothing moved, nothing overwritten.
        assert (active_dir / "local.md").read_text() == "work in progress"
        assert (stories / "backlog" / "01.001" / "01.001.json").exists()
        assert not (active_dir / "01.001").exists()

    def test_activate_over_nonempty_active_dir_leaves_status_untouched(self, proj):
        """A refused activation must not flip sequence.json to active."""
        stories = self._backlog_story(proj)
        active_dir = stories / "active" / "01.001"
        active_dir.mkdir(parents=True)
        (active_dir / "local.md").write_text("work in progress")

        sa = _modules["story_activator"]
        assert "error" in sa.activate_story("01.001", "epic-01", root=str(proj))
        assert read_seq(proj)["epics"][0]["stories"][0]["status"] == "backlog"


# ---------------------------------------------------------------------------
# 8. story_completer
# ---------------------------------------------------------------------------


class TestStoryCompleter:
    def _make_active_story(self, proj, story_id="01.001", epic_id="epic-01"):
        scaffold = _modules["scaffold_structure"]
        gs = _modules["generate_sequence"]
        scaffold.create_epic(1, root=str(proj))
        write_story_yaml(proj, epic_id, story_id, "active")
        # Seed sequence.json too -- in real usage every story is registered
        # there (via /create-stories) before it can ever be activated, and
        # complete_story/rollback_story now require the entry to exist so
        # they can sync its status atomically with the folder move.
        gs.add_epic(epic_id, root=str(proj))
        gs.add_story(epic_id, story_id, root=str(proj))
        gs.update_status(story_id, "active", root=str(proj))
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

    def test_complete_story_syncs_sequence_status(self, proj):
        """Completion must flip sequence.json's status (and stamp `completed`)
        in the SAME call that moves the folder to done/ -- mirrors the
        activation fix so the active->done transition can't drift either."""
        self._make_active_story(proj)

        sc = _modules["story_completer"]
        result = sc.complete_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True

        story = read_seq(proj)["epics"][0]["stories"][0]
        assert story["status"] == "done"
        assert story["completed"] is not None

    def test_rollback_story_syncs_sequence_status(self, proj):
        """Rollback must flip sequence.json's status back to active in the
        SAME call that moves the folder back from done/ -- mirrors the
        activation fix so the done->active transition can't drift either."""
        gs = _modules["generate_sequence"]
        self._make_active_story(proj)

        sc = _modules["story_completer"]
        sc.complete_story("01.001", "epic-01", root=str(proj))
        # Force sequence.json to "done" regardless of whether complete_story
        # itself synced it -- isolates rollback's own sync behaviour so this
        # test can't pass vacuously off an unrelated fix.
        gs.update_status("01.001", "done", root=str(proj))

        result = sc.rollback_story("01.001", "epic-01", root=str(proj))
        assert result["success"] is True

        story = read_seq(proj)["epics"][0]["stories"][0]
        assert story["status"] == "active"


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

    # -- list_existing -----------------------------------------------------

    def test_list_existing_empty(self, proj):
        dp = _modules["discovery_promoter"]
        result = dp.list_existing(root=str(proj))
        assert result["success"] is True
        assert result["items"] == []

    def test_list_existing_returns_id_type_title(self, proj):
        dp = _modules["discovery_promoter"]
        dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        result = dp.list_existing(root=str(proj))
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["id"] == "const-001"
        assert item["type"] == "constraint"
        assert item["title"] == "Use Redis for caching"
        assert item["path"].endswith("const-001.md")

    def test_list_existing_includes_decisions_and_constraints(self, proj):
        dp = _modules["discovery_promoter"]
        dp.promote_discoveries([self._discovery(10, "decision")], root=str(proj))
        dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        result = dp.list_existing(root=str(proj))
        types = {item["type"] for item in result["items"]}
        assert types == {"decision", "constraint"}

    # -- amend (consolidation) ----------------------------------------------

    def test_amend_updates_existing_file_no_new_id(self, proj):
        dp = _modules["discovery_promoter"]
        first = dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        target_id = first["promoted"][0]["id"]

        amend_disc = self._discovery(9, "constraint")
        amend_disc["title"] = "Redis eviction policy must be noeviction"
        amend_disc["content"] = "Follow-up: cache must use noeviction to avoid silent data loss."
        amend_disc["action"] = "amend"
        amend_disc["target_id"] = target_id

        result = dp.promote_discoveries([amend_disc], root=str(proj))
        assert result["success"] is True
        assert len(result["promoted"]) == 0
        assert len(result["amended"]) == 1
        assert result["amended"][0]["id"] == target_id

        constraints_dir = proj / ".solution-factory" / "constraints"
        files = sorted(constraints_dir.glob("const-*.md"))
        assert len(files) == 1  # no new file created

        content = files[0].read_text()
        assert "noeviction" in content
        assert "Redis eviction policy must be noeviction" in content

    def test_amend_rewrites_cleanly_no_accumulated_history(self, proj):
        """Amending replaces the body rather than appending — file stays current, not a log."""
        dp = _modules["discovery_promoter"]
        first = dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        target_id = first["promoted"][0]["id"]
        original_content = Path(first["promoted"][0]["path"]).read_text()

        amend_disc = self._discovery(9, "constraint")
        amend_disc["content"] = "Updated understanding of the caching constraint."
        amend_disc["action"] = "amend"
        amend_disc["target_id"] = target_id
        dp.promote_discoveries([amend_disc], root=str(proj))

        new_content = Path(first["promoted"][0]["path"]).read_text()
        assert "Redis provides fast in-memory caching" not in new_content
        assert "Updated understanding of the caching constraint." in new_content
        assert new_content != original_content

    def test_amend_falls_back_to_new_when_target_missing(self, proj):
        dp = _modules["discovery_promoter"]
        disc = self._discovery(9, "constraint")
        disc["action"] = "amend"
        disc["target_id"] = "const-999"  # does not exist

        result = dp.promote_discoveries([disc], root=str(proj))
        assert len(result["amended"]) == 0
        assert len(result["promoted"]) == 1
        assert result["promoted"][0]["id"] == "const-001"

    def test_amend_in_prompt_range_carries_target_id(self, proj):
        dp = _modules["discovery_promoter"]
        disc = self._discovery(6, "constraint")  # prompt range
        disc["action"] = "amend"
        disc["target_id"] = "const-001"
        result = dp.promote_discoveries([disc], root=str(proj))
        assert len(result["needs_confirmation"]) == 1
        assert result["needs_confirmation"][0]["action"] == "amend"
        assert result["needs_confirmation"][0]["target_id"] == "const-001"

    def test_confirm_and_promote_respects_amend(self, proj):
        dp = _modules["discovery_promoter"]
        first = dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        target_id = first["promoted"][0]["id"]

        disc = self._discovery(3, "constraint")  # would normally be discarded
        disc["action"] = "amend"
        disc["target_id"] = target_id
        result = dp.confirm_and_promote(disc, root=str(proj))
        assert result["success"] is True
        assert len(result["amended"]) == 1
        assert len(result["promoted"]) == 0

    # -- amend preserves the target file ------------------------------------
    #
    # An amend refines ONE finding. It is not a regeneration: the target may
    # hold hundreds of lines of hand-maintained detail the discovery knows
    # nothing about. Regression -- amend rewrote the file from a template
    # seeded only with disc["content"], turning a 405-line constraint into 15
    # lines of placeholder comments.

    def _rich_constraint(self, proj, cid="const-001", detail_lines=400):
        """Write a substantial existing constraint in the repo's conventional
        Status/Context/Decision/Consequences shape."""
        d = proj / ".solution-factory" / "constraints"
        d.mkdir(parents=True, exist_ok=True)
        detail = "\n".join(f"line {i} of hard-won detail" for i in range(1, detail_lines + 1))
        f = d / f"{cid}.md"
        f.write_text(
            f"# {cid}: API rate limits\n\n"
            "**Status:** Accepted\n"
            "**Type:** technology\n"
            "**Date:** 2020-01-01\n"
            "**Source:** Story 01.001\n"
            "**Relevance Score:** 8\n\n"
            "## Context\nThe original context.\n\n"
            "## Decision\nThe decision we reached after a long argument.\n\n"
            f"## Consequences\n{detail}\n"
        )
        return f

    def _amendment(self, target_id="const-001", content="Refined: limit is 300 rpm."):
        disc = self._discovery(10, "constraint")
        disc["title"] = "API rate limits"
        disc["content"] = content
        disc["action"] = "amend"
        disc["target_id"] = target_id
        disc["source_story"] = "19.002"
        return disc

    def test_amend_preserves_untouched_sections(self, proj):
        """The sections the discovery says nothing about must survive verbatim."""
        dp = _modules["discovery_promoter"]
        f = self._rich_constraint(proj)
        before = len(f.read_text().splitlines())

        dp.promote_discoveries([self._amendment()], root=str(proj))

        after = f.read_text()
        assert "The decision we reached after a long argument." in after
        assert "line 1 of hard-won detail" in after
        assert "line 400 of hard-won detail" in after
        # 411 -> 15 was the bug; the file must not collapse.
        assert len(after.splitlines()) >= before

    def test_amend_replaces_only_the_context_section(self, proj):
        dp = _modules["discovery_promoter"]
        f = self._rich_constraint(proj)

        dp.promote_discoveries([self._amendment()], root=str(proj))

        after = f.read_text()
        assert "Refined: limit is 300 rpm." in after
        assert "The original context." not in after  # superseded, not appended

    def test_amend_keeps_repo_section_convention(self, proj):
        """Constraints follow Status/Context/Decision/Consequences, same as
        decisions. Amending must not reshape a file into Constraint/Impact/
        Mitigation, and must not inject placeholder comments."""
        dp = _modules["discovery_promoter"]
        f = self._rich_constraint(proj)

        dp.promote_discoveries([self._amendment()], root=str(proj))

        after = f.read_text()
        headings = [ln for ln in after.splitlines() if ln.startswith("## ")]
        assert headings == ["## Context", "## Decision", "## Consequences"]
        assert "<!--" not in after

    def test_amend_refreshes_tracking_metadata(self, proj):
        dp = _modules["discovery_promoter"]
        f = self._rich_constraint(proj)

        dp.promote_discoveries([self._amendment()], root=str(proj))

        after = f.read_text()
        assert "**Source:** Story 19.002 (amended)" in after
        assert "**Relevance Score:** 10" in after
        assert "**Date:** 2020-01-01" not in after

    def test_amend_preserves_unrelated_metadata(self, proj):
        """Status/Type and any project-specific keys are not ours to rewrite."""
        dp = _modules["discovery_promoter"]
        f = self._rich_constraint(proj)

        dp.promote_discoveries([self._amendment()], root=str(proj))

        after = f.read_text()
        assert "**Status:** Accepted" in after
        assert "**Type:** technology" in after

    def test_amend_keeps_id_and_updates_title(self, proj):
        dp = _modules["discovery_promoter"]
        f = self._rich_constraint(proj)
        disc = self._amendment()
        disc["title"] = "API rate limits (revised)"

        dp.promote_discoveries([disc], root=str(proj))

        assert f.read_text().splitlines()[0] == "# const-001: API rate limits (revised)"

    def test_amend_is_idempotent_across_repeated_runs(self, proj):
        """Amending twice with the same discovery must not duplicate sections
        or metadata -- the file is current state, not an append log."""
        dp = _modules["discovery_promoter"]
        f = self._rich_constraint(proj)

        dp.promote_discoveries([self._amendment()], root=str(proj))
        once = f.read_text()
        dp.promote_discoveries([self._amendment()], root=str(proj))
        twice = f.read_text()

        assert once == twice
        assert twice.count("## Context") == 1
        assert twice.count("**Relevance Score:**") == 1

    def test_amend_preserves_decision_files_too(self, proj):
        """The decision branch must preserve exactly as the constraint one does."""
        dp = _modules["discovery_promoter"]
        d = proj / ".solution-factory" / "decisions"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "adr-001.md"
        f.write_text(
            "# adr-001: Use Postgres\n\n**Status:** Accepted\n\n"
            "## Context\nOld context.\n\n"
            "## Decision\nPostgres, for the JSONB support.\n\n"
            "## Consequences\nOperational burden of a managed instance.\n"
        )

        disc = self._discovery(10, "decision")
        disc["title"] = "Use Postgres"
        disc["content"] = "Revisited: JSONB plus logical replication."
        disc["action"] = "amend"
        disc["target_id"] = "adr-001"
        result = dp.promote_discoveries([disc], root=str(proj))

        assert len(result["amended"]) == 1
        after = f.read_text()
        assert "Revisited: JSONB plus logical replication." in after
        assert "Postgres, for the JSONB support." in after
        assert "Operational burden of a managed instance." in after

    def test_amend_updates_legacy_constraint_section(self, proj):
        """Files an earlier version of this script rewrote carry '## Constraint'
        instead of '## Context'. Update that section rather than inserting a
        second one beside it."""
        dp = _modules["discovery_promoter"]
        d = proj / ".solution-factory" / "constraints"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "const-001.md"
        f.write_text(
            "# const-001: API rate limits\n\n**Type:** technology\n\n"
            "## Constraint\nStale text.\n\n"
            "## Impact\nKeep me.\n"
        )

        dp.promote_discoveries([self._amendment()], root=str(proj))

        after = f.read_text()
        assert after.count("## Constraint") == 1
        assert "## Context" not in after
        assert "Refined: limit is 300 rpm." in after
        assert "Stale text." not in after
        assert "Keep me." in after

    def test_amend_file_without_sections_keeps_existing_prose(self, proj):
        """A hand-written target with no '## ' headings still gets a Context
        section without losing what was already there."""
        dp = _modules["discovery_promoter"]
        d = proj / ".solution-factory" / "constraints"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "const-001.md"
        f.write_text("# const-001: API rate limits\n\n**Type:** technology\n")

        dp.promote_discoveries([self._amendment()], root=str(proj))

        after = f.read_text()
        assert "**Type:** technology" in after
        assert "## Context" in after
        assert "Refined: limit is 300 rpm." in after

    # -- merge_into (backward consolidation) --------------------------------

    def test_merge_into_stubs_sources_and_writes_target(self, proj):
        dp = _modules["discovery_promoter"]
        a = dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        b_disc = self._discovery(10, "constraint")
        b_disc["title"] = "Cache key namespacing"
        b = dp.promote_discoveries([b_disc], root=str(proj))

        id_a = a["promoted"][0]["id"]
        id_b = b["promoted"][0]["id"]

        merged_md = "# const-001: Redis caching (consolidated)\n\nMerged content covering caching + key namespacing.\n"
        result = dp.merge_into([id_a, id_b], id_a, merged_md, root=str(proj))

        assert result["success"] is True
        assert result["stubbed"] == [id_b]

        target_content = Path(result["target_path"]).read_text()
        assert target_content == merged_md

        stub_content = (proj / ".solution-factory" / "constraints" / f"{id_b}.md").read_text()
        assert "Superseded by" in stub_content
        assert id_a in stub_content

    def test_merge_into_unknown_source_fails(self, proj):
        dp = _modules["discovery_promoter"]
        result = dp.merge_into(["const-999"], "const-999", "content", root=str(proj))
        assert result["success"] is False
        assert "error" in result

    def test_merge_into_fresh_target_creates_it_and_stubs_all_sources(self, proj):
        """target_id may be an ID that does not exist yet -- it is created with
        the merged content and every source is stubbed."""
        dp = _modules["discovery_promoter"]
        a = dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        b_disc = self._discovery(10, "constraint")
        b_disc["title"] = "Cache key namespacing"
        b = dp.promote_discoveries([b_disc], root=str(proj))
        id_a, id_b = a["promoted"][0]["id"], b["promoted"][0]["id"]

        merged_md = "# const-050: Caching (consolidated)\n\nEverything about caching.\n"
        result = dp.merge_into([id_a, id_b], "const-050", merged_md, root=str(proj))

        assert result["success"] is True
        assert sorted(result["stubbed"]) == sorted([id_a, id_b])

        target = proj / ".solution-factory" / "constraints" / "const-050.md"
        assert target.read_text() == merged_md
        for sid in (id_a, id_b):
            stub = (proj / ".solution-factory" / "constraints" / f"{sid}.md").read_text()
            assert "Superseded by" in stub
            assert "const-050" in stub

    def test_merge_into_stub_keeps_original_header(self, proj):
        """A stub must still identify itself, so references to the old ID
        remain readable rather than resolving to an anonymous pointer."""
        dp = _modules["discovery_promoter"]
        a = dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        b_disc = self._discovery(10, "constraint")
        b_disc["title"] = "Cache key namespacing"
        b = dp.promote_discoveries([b_disc], root=str(proj))
        id_a, id_b = a["promoted"][0]["id"], b["promoted"][0]["id"]

        dp.merge_into([id_a, id_b], id_a, "merged", root=str(proj))
        stub = (proj / ".solution-factory" / "constraints" / f"{id_b}.md").read_text()
        assert stub.startswith(f"# {id_b}: Cache key namespacing")

    def test_merge_into_target_in_sources_is_not_stubbed(self, proj):
        """The target must never stub itself into a pointer to itself."""
        dp = _modules["discovery_promoter"]
        a = dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        id_a = a["promoted"][0]["id"]

        result = dp.merge_into([id_a], id_a, "merged body", root=str(proj))
        assert result["stubbed"] == []
        assert Path(result["target_path"]).read_text() == "merged body"

    def test_merge_into_decisions_resolve_by_adr_prefix(self, proj):
        """resolve_target_path routes by ID prefix, so adr-* must land in
        decisions/ and not be looked up under constraints/."""
        dp = _modules["discovery_promoter"]
        a = dp.promote_discoveries([self._discovery(10, "decision")], root=str(proj))
        id_a = a["promoted"][0]["id"]
        assert id_a.startswith("adr-")

        result = dp.merge_into([id_a], id_a, "merged adr", root=str(proj))
        assert result["success"] is True
        assert Path(result["target_path"]).parent.name == "decisions"

    # -- list_existing edge cases ------------------------------------------

    def test_list_existing_falls_back_to_stem_when_no_title_header(self, proj):
        """A hand-written file without the '# id: title' header must still be
        listed -- dedup checks depend on seeing every existing item."""
        dp = _modules["discovery_promoter"]
        d = proj / ".solution-factory" / "constraints"
        d.mkdir(parents=True, exist_ok=True)
        (d / "const-001.md").write_text("Some notes with no header at all.\n")

        items = dp.list_existing(root=str(proj))["items"]
        assert len(items) == 1
        assert items[0]["id"] == "const-001"
        assert items[0]["title"] == "const-001"

    def test_list_existing_ignores_unrelated_files(self, proj):
        dp = _modules["discovery_promoter"]
        dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        d = proj / ".solution-factory" / "constraints"
        (d / "README.md").write_text("not a constraint")
        (d / "notes.txt").write_text("nor this")

        items = dp.list_existing(root=str(proj))["items"]
        assert [i["id"] for i in items] == ["const-001"]

    def test_list_existing_sorted_within_type(self, proj):
        dp = _modules["discovery_promoter"]
        for _ in range(3):
            dp.promote_discoveries([self._discovery(10, "constraint")], root=str(proj))
        items = dp.list_existing(root=str(proj))["items"]
        assert [i["id"] for i in items] == ["const-001", "const-002", "const-003"]


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


# ---------------------------------------------------------------------------
# 20. idea_store
# ---------------------------------------------------------------------------


class TestIdeaStore:
    def test_add_works_without_full_scaffold(self, tmp_path):
        """Capture must not require .solution-factory/ to exist yet."""
        store = _modules["idea_store"]
        assert not (tmp_path / ".solution-factory").exists()
        result = store.add("Dark mode toggle", "Users keep asking for it.", root=str(tmp_path))
        assert result["success"] is True
        assert result["id"] == "IDEA-001"
        assert (tmp_path / ".solution-factory" / "ideas" / "IDEA-001" / "idea.md").exists()
        # Only the ideas/ folder was scaffolded, not the full tree
        assert not (tmp_path / ".solution-factory" / "decisions").exists()

    def test_add_allocates_sequential_ids(self, tmp_path):
        store = _modules["idea_store"]
        first = store.add("First idea", root=str(tmp_path))
        second = store.add("Second idea", root=str(tmp_path))
        assert first["id"] == "IDEA-001"
        assert second["id"] == "IDEA-002"

    def test_add_defaults_to_raw_state(self, tmp_path):
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        shown = store.show("IDEA-001", root=str(tmp_path))
        assert shown["frontmatter"]["state"] == "raw"

    def test_list_and_show_roundtrip(self, tmp_path):
        store = _modules["idea_store"]
        store.add("First idea", "some body text", root=str(tmp_path))
        listing = store.list_ideas(root=str(tmp_path))
        assert len(listing["ideas"]) == 1
        assert listing["ideas"][0]["id"] == "IDEA-001"
        assert listing["ideas"][0]["title"] == "First idea"

        shown = store.show("IDEA-001", root=str(tmp_path))
        assert "some body text" in shown["body"]

    def test_list_filters_by_state(self, tmp_path):
        store = _modules["idea_store"]
        store.add("Keep raw", root=str(tmp_path))
        store.add("Will triage", root=str(tmp_path))
        store.set_state("IDEA-002", "triaged", root=str(tmp_path))

        raw_only = store.list_ideas(root=str(tmp_path), state="raw")
        assert [i["id"] for i in raw_only["ideas"]] == ["IDEA-001"]

    def test_show_missing_idea_errors(self, tmp_path):
        store = _modules["idea_store"]
        result = store.show("IDEA-999", root=str(tmp_path))
        assert "error" in result

    def test_set_state_rejects_invalid_state(self, tmp_path):
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        result = store.set_state("IDEA-001", "bogus", root=str(tmp_path))
        assert "error" in result

    def test_discard_sets_state_and_records_reason(self, tmp_path):
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        result = store.discard("IDEA-001", reason="duplicate", root=str(tmp_path))
        assert result["success"] is True
        shown = store.show("IDEA-001", root=str(tmp_path))
        assert shown["frontmatter"]["state"] == "discarded"
        assert "duplicate" in shown["body"]

    def test_discard_promoted_idea_errors(self, tmp_path):
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        store.set_state("IDEA-001", "triaged", root=str(tmp_path))
        store.set_state("IDEA-001", "planning", root=str(tmp_path))
        store.set_state("IDEA-001", "planned", root=str(tmp_path))
        store.promote("IDEA-001", 3, root=str(tmp_path))
        result = store.discard("IDEA-001", root=str(tmp_path))
        assert "error" in result

    def test_promote_requires_planned_state(self, tmp_path):
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        result = store.promote("IDEA-001", 3, root=str(tmp_path))
        assert "error" in result
        assert "planned" in result["error"]

    def test_promote_success_stamps_epic_num_and_state(self, tmp_path):
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        store.set_state("IDEA-001", "triaged", root=str(tmp_path))
        store.set_state("IDEA-001", "planning", root=str(tmp_path))
        store.set_state("IDEA-001", "planned", root=str(tmp_path))
        result = store.promote("IDEA-001", 3, root=str(tmp_path))
        assert result["success"] is True
        assert result["epic"] == "epic-03"
        shown = store.show("IDEA-001", root=str(tmp_path))
        assert shown["frontmatter"]["state"] == "promoted"
        assert shown["frontmatter"]["epic_num"] == "epic-03"


# ---------------------------------------------------------------------------
# 21. idea_plan_check
# ---------------------------------------------------------------------------


VALID_PLAN_MD = """## Technical Approach

Reuse the existing upload pipeline; add a bounded-concurrency queue in the
frontend. Leave configurability of the concurrency cap out of scope (YAGNI)
until real-volume testing suggests otherwise.
"""

EMPTY_SECTION_PLAN_MD = """## Technical Approach

"""


class TestIdeaPlanCheck:
    def test_parse_valid_technical_approach_section(self):
        checker = _modules["idea_plan_check"]
        result = checker.parse_technical_approach_section(VALID_PLAN_MD)
        assert result["warnings"] == []
        assert "bounded-concurrency queue" in result["content"]

    def test_missing_technical_approach_section_errors(self):
        checker = _modules["idea_plan_check"]
        result = checker.parse_technical_approach_section(
            "## Something Else\n\nno approach here\n"
        )
        assert "error" in result

    def test_empty_section_surfaces_as_warning_not_silent_pass(self):
        """An empty Technical Approach section must never silently pass."""
        checker = _modules["idea_plan_check"]
        result = checker.parse_technical_approach_section(EMPTY_SECTION_PLAN_MD)
        assert result["content"] == ""
        assert len(result["warnings"]) == 1

    def test_check_plan_missing_plan_file_errors(self, tmp_path):
        checker = _modules["idea_plan_check"]
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        result = checker.check_plan("IDEA-001", root=str(tmp_path))
        assert "error" in result

    def test_check_plan_reports_presence_and_warnings(self, tmp_path):
        checker = _modules["idea_plan_check"]
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        plan_path = tmp_path / ".solution-factory" / "ideas" / "IDEA-001" / "plan.md"
        plan_path.write_text(EMPTY_SECTION_PLAN_MD)
        result = checker.check_plan("IDEA-001", root=str(tmp_path))
        assert result["technical_approach_present"] is False
        assert len(result["warnings"]) == 1

    def test_check_plan_clean_when_populated(self, tmp_path):
        checker = _modules["idea_plan_check"]
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        plan_path = tmp_path / ".solution-factory" / "ideas" / "IDEA-001" / "plan.md"
        plan_path.write_text(VALID_PLAN_MD)
        result = checker.check_plan("IDEA-001", root=str(tmp_path))
        assert result["technical_approach_present"] is True
        assert result["warnings"] == []


# ---------------------------------------------------------------------------
# 22. read_idea_plan
# ---------------------------------------------------------------------------


class TestReadIdeaPlan:
    def _make_planned_idea(self, tmp_path, plan_text=VALID_PLAN_MD):
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        plan_path = tmp_path / ".solution-factory" / "ideas" / "IDEA-001" / "plan.md"
        plan_path.write_text(plan_text)
        store.set_state("IDEA-001", "triaged", root=str(tmp_path))
        store.set_state("IDEA-001", "planning", root=str(tmp_path))
        store.set_state("IDEA-001", "planned", root=str(tmp_path))

    def test_fails_when_not_planned(self, tmp_path):
        reader = _modules["read_idea_plan"]
        store = _modules["idea_store"]
        store.add("First idea", root=str(tmp_path))
        result = reader.read_idea_plan("IDEA-001", root=str(tmp_path))
        assert "error" in result
        assert "planned" in result["error"]

    def test_fails_when_section_empty(self, tmp_path):
        reader = _modules["read_idea_plan"]
        self._make_planned_idea(tmp_path, plan_text=EMPTY_SECTION_PLAN_MD)
        result = reader.read_idea_plan("IDEA-001", root=str(tmp_path))
        assert "error" in result
        assert "warnings" in result

    def test_fails_when_section_missing(self, tmp_path):
        reader = _modules["read_idea_plan"]
        self._make_planned_idea(tmp_path, plan_text="## Something Else\n\nnothing here\n")
        result = reader.read_idea_plan("IDEA-001", root=str(tmp_path))
        assert "error" in result

    def test_success_returns_title_body_and_technical_approach(self, tmp_path):
        reader = _modules["read_idea_plan"]
        self._make_planned_idea(tmp_path)
        result = reader.read_idea_plan("IDEA-001", root=str(tmp_path))
        assert result["success"] is True
        assert result["title"] == "First idea"
        assert "body" in result
        assert "bounded-concurrency queue" in result["technical_approach"]


# ---------------------------------------------------------------------------
# schedule_stories
# ---------------------------------------------------------------------------


class TestScheduleStories:
    def _bootstrap(self, proj, stories, config=None, epic="epic-01"):
        """stories: list of (story_id, status, deps, outputs-or-None)."""
        gs = _modules["generate_sequence"]
        scaffold = _modules["scaffold_structure"]
        num = int(epic.split("-")[1])
        scaffold.create_epic(num, root=str(proj))
        gs.add_epic(epic, root=str(proj))
        for story_id, status, deps, outputs in stories:
            data = make_minimal_story_data(story_id, epic)
            if outputs is not None:
                data["outputs"] = outputs
            write_story_yaml(proj, epic, story_id, status, story_data=data)
            gs.add_story(epic, story_id, dependencies=deps, root=str(proj))
            if status != "backlog":
                gs.update_status(story_id, status, root=str(proj))
        if config is not None:
            (proj / ".solution-factory" / "config.json").write_text(json.dumps(config))

    def _run(self, proj, **kw):
        return _modules["schedule_stories"].schedule(kw.pop("epic", "epic-01"), root=str(proj), **kw)

    def _ids(self, entries):
        return [e["id"] for e in entries]

    def test_disjoint_ready_stories_all_start(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], {"modify": ["a.py"]}),
            ("01.002", "backlog", [], {"create": ["b.py"]}),
            ("01.003", "backlog", [], {"modify": ["c.py"]}),
        ])
        r = self._run(proj)
        assert r["mode"] == "concurrent"
        assert self._ids(r["startable"]) == ["01.001", "01.002", "01.003"]
        assert r["held"] == []
        assert r["free_slots"] == 0

    def test_max_concurrent_limits_starts_in_sequence_order(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], {"modify": ["a.py"]}),
            ("01.002", "backlog", [], {"modify": ["b.py"]}),
            ("01.003", "backlog", [], {"modify": ["c.py"]}),
        ], config={"epic_run": {"max_concurrent": 2}})
        r = self._run(proj)
        assert self._ids(r["startable"]) == ["01.001", "01.002"]
        assert r["held"] == [{"id": "01.003", "reason": "no free slot"}]

    def test_in_flight_stories_consume_slots_and_block_overlap(self, proj):
        self._bootstrap(proj, [
            ("01.001", "active", [], {"modify": ["a.py", "shared.py"]}),
            ("01.002", "backlog", [], {"modify": ["shared.py"]}),
            ("01.003", "backlog", [], {"modify": ["c.py"]}),
        ])
        r = self._run(proj)  # in_flight defaults to active stories
        assert self._ids(r["in_flight"]) == ["01.001"]
        assert self._ids(r["startable"]) == ["01.003"]
        assert r["held"] == [{"id": "01.002", "reason": "shares shared.py with 01.001"}]
        assert r["free_slots"] == 1

    def test_explicit_in_flight_overrides_active_default(self, proj):
        self._bootstrap(proj, [
            ("01.001", "active", [], {"modify": ["a.py"]}),
            ("01.002", "backlog", [], {"modify": ["b.py"]}),
        ])
        r = self._run(proj, in_flight=[])
        assert r["in_flight"] == []
        assert self._ids(r["startable"]) == ["01.002"]
        assert r["free_slots"] == 2

    def test_ready_stories_that_overlap_each_other_start_first_only(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], {"modify": ["utils.py"]}),
            ("01.002", "backlog", [], {"modify": ["utils.py"]}),
            ("01.003", "backlog", [], {"modify": ["other.py"]}),
        ])
        r = self._run(proj)
        assert self._ids(r["startable"]) == ["01.001", "01.003"]
        assert r["held"] == [{"id": "01.002", "reason": "shares utils.py with 01.001"}]

    def test_unmet_dependency_holds_story(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], {"modify": ["a.py"]}),
            ("01.002", "backlog", ["01.001"], {"modify": ["b.py"]}),
        ])
        r = self._run(proj)
        assert self._ids(r["startable"]) == ["01.001"]
        assert r["held"] == [{"id": "01.002", "reason": "waits for 01.001"}]

    def test_cross_epic_dependency_resolved_globally(self, proj):
        self._bootstrap(proj, [("01.001", "done", [], {"modify": ["a.py"]})], epic="epic-01")
        self._bootstrap(proj, [("02.001", "backlog", ["01.001"], {"modify": ["b.py"]})], epic="epic-02")
        r = self._run(proj, epic="epic-02")
        assert self._ids(r["startable"]) == ["02.001"]

    def test_story_without_outputs_runs_alone(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], None),
            ("01.002", "backlog", [], {"modify": ["b.py"]}),
        ])
        r = self._run(proj)
        assert self._ids(r["startable"]) == ["01.001"]
        assert r["held"] == [{"id": "01.002", "reason": "01.001 declares no outputs and runs alone"}]
        assert r["startable"][0]["files"] is None

    def test_story_without_outputs_waits_for_empty_run(self, proj):
        self._bootstrap(proj, [
            ("01.001", "active", [], {"modify": ["a.py"]}),
            ("01.002", "backlog", [], None),
            ("01.003", "backlog", [], {"modify": ["c.py"]}),
        ])
        r = self._run(proj)
        assert self._ids(r["startable"]) == ["01.003"]
        assert r["held"] == [{"id": "01.002", "reason": "declares no outputs; waits until nothing is in flight (01.001)"}]

    def test_shared_paths_excluded_from_overlap_check(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], {"modify": ["a.py", "CLAUDE.md", ".meteor/versions"]}),
            ("01.002", "backlog", [], {"modify": ["b.py", "CLAUDE.md", ".meteor/versions"]}),
        ], config={"epic_run": {"shared_paths": ["CLAUDE.md", ".meteor/*"]}})
        r = self._run(proj)
        assert self._ids(r["startable"]) == ["01.001", "01.002"]
        assert r["startable"][0]["files"] == ["a.py"]

    def test_default_shared_paths_ignore_solution_factory_tree(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], {"modify": [".solution-factory/decisions/adr-001.md", "a.py"]}),
            ("01.002", "backlog", [], {"modify": [".solution-factory/decisions/adr-001.md", "b.py"]}),
        ])
        r = self._run(proj)
        assert self._ids(r["startable"]) == ["01.001", "01.002"]

    def test_outputs_made_only_of_shared_paths_count_as_undeclared(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], {"modify": [".solution-factory/x.md"]}),
            ("01.002", "backlog", [], {"modify": ["b.py"]}),
        ])
        r = self._run(proj)
        assert self._ids(r["startable"]) == ["01.001"]
        assert r["open_stories"][0]["declared"] is False

    def test_max_concurrent_one_reports_sequential_mode(self, proj):
        self._bootstrap(proj, [
            ("01.001", "backlog", [], {"modify": ["a.py"]}),
            ("01.002", "backlog", [], {"modify": ["b.py"]}),
        ], config={"epic_run": {"max_concurrent": 1}})
        r = self._run(proj)
        assert r["mode"] == "sequential"
        assert self._ids(r["startable"]) == ["01.001"]
        assert r["held"] == [{"id": "01.002", "reason": "no free slot"}]

    def test_open_stories_table_covers_backlog_and_active_only(self, proj):
        self._bootstrap(proj, [
            ("01.001", "done", [], {"modify": ["a.py"]}),
            ("01.002", "active", [], {"modify": ["b.py"]}),
            ("01.003", "backlog", ["01.002"], {"create": ["c.py"], "modify": ["b.py"]}),
            ("01.004", "deferred", [], None),
        ])
        r = self._run(proj)
        assert self._ids(r["open_stories"]) == ["01.002", "01.003"]
        row = r["open_stories"][1]
        assert row == {
            "id": "01.003", "title": "Story 01.003", "status": "backlog",
            "files": ["b.py", "c.py"], "declared": True, "deps_pending": ["01.002"],
        }

    def test_missing_epic_and_missing_sequence_error(self, proj, tmp_path):
        self._bootstrap(proj, [("01.001", "backlog", [], None)])
        assert "error" in self._run(proj, epic="epic-99")
        empty = tmp_path / "empty"
        empty.mkdir()
        assert "error" in _modules["schedule_stories"].schedule("epic-01", root=str(empty))
