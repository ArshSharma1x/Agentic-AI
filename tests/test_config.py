import json

import pytest

from squad.config import ConfigError, load_config


def write(tmp_path, data):
    path = tmp_path / "squad.config.json"
    path.write_text(json.dumps(data))
    return path


def test_key_comes_from_the_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert load_config(write(tmp_path, {"anthropic": {"api_key": "sk-ant-real"}})).api_key == "sk-ant-real"


def test_the_example_placeholder_counts_as_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert load_config(write(tmp_path, {"anthropic": {"api_key": "sk-ant-REPLACE_ME"}})).api_key is None


def test_the_environment_overrides_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    assert load_config(write(tmp_path, {"anthropic": {"api_key": "sk-ant-file"}})).api_key == "sk-ant-env"


def test_a_missing_file_is_just_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert load_config(tmp_path / "nope.json").api_key is None


def test_bad_json_and_bad_servers_are_reported_with_the_file_name(tmp_path):
    bad = tmp_path / "squad.config.json"
    bad.write_text("{nope")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_config(bad)
    with pytest.raises(ConfigError, match="mcpServers.jira"):
        load_config(write(tmp_path, {"mcpServers": {"jira": {"args": []}}}))


def test_the_committed_example_is_valid_and_has_no_usable_key(monkeypatch):
    from squad.paths import ROOT

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = load_config(ROOT / "squad.config.example.json")
    assert config.api_key is None and config.mcp_servers == {}  # built-in servers are the default


def test_relative_server_commands_resolve_against_the_config_file(tmp_path, monkeypatch):
    from squad.orchestrator import server_params

    cfg = tmp_path / "squad.config.json"
    cfg.write_text('{"mcpServers": {"jira": {"command": ".venv/bin/python", "args": ["-m", "x"]}, "workspace": {"command": "python3"}}}')
    monkeypatch.setenv("SQUAD_CONFIG", str(cfg))
    monkeypatch.chdir(tmp_path.parent)
    assert server_params("jira").command == str(tmp_path / ".venv/bin/python")
    assert server_params("workspace").command == "python3"  # a bare command still comes from PATH
