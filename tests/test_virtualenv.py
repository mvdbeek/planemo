"""Tests for Planemo's Galaxy virtualenv selection."""

import os
import subprocess
import sys
from unittest.mock import (
    call,
    patch,
)

from planemo import virtualenv
from planemo.galaxy.run import CREATE_COMMAND_TEMPLATE


def test_galaxy_python_versions_are_explicit_and_current():
    assert virtualenv.GALAXY_PYTHON_VERSION_CHOICES == (
        "3.8",
        "3.9",
        "3.10",
        "3.11",
        "3.12",
        "3.13",
        "3.14",
    )
    assert "3" not in virtualenv.GALAXY_PYTHON_VERSION_CHOICES


def test_default_python_version_uses_latest_supported_version():
    assert virtualenv.DEFAULT_PYTHON_VERSION == os.environ.get("PLANEMO_DEFAULT_PYTHON_VERSION", "3.14")


def test_create_command_uses_default_python_version():
    with (
        patch.object(virtualenv, "DEFAULT_PYTHON_VERSION", "3.14"),
        patch.object(virtualenv, "which", side_effect=["/opt/python3.14", None]) as which,
    ):
        command = virtualenv.create_command("/tmp/galaxy-venv")

    assert command == "/opt/python3.14 -m venv /tmp/galaxy-venv"
    assert which.call_args_list == [call("python3.14"), call("virtualenv")]


def test_create_command_honors_explicit_python_version():
    with patch.object(virtualenv, "which", side_effect=["/opt/python3.10", "/opt/virtualenv"]) as which:
        command = virtualenv.create_command("/tmp/galaxy-venv", "3.10")

    assert command == "/opt/virtualenv /tmp/galaxy-venv -p /opt/python3.10"
    assert which.call_args_list == [call("python3.10"), call("virtualenv")]


def _run_create_template(create_command, virtualenv_path):
    script = CREATE_COMMAND_TEMPLATE.safe_substitute(create_virtualenv=create_command)
    env = dict(os.environ, GALAXY_VIRTUAL_ENV=str(virtualenv_path))
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, check=True)


def _fallback_create_command():
    # ``true`` stands in for Planemo's interpreter so running the command creates nothing.
    with (
        patch.object(virtualenv, "which", side_effect=[None, None]),
        patch.object(virtualenv.sys, "executable", "true"),
    ):
        return virtualenv.create_command("$GALAXY_VIRTUAL_ENV", "3.14")


def test_create_command_defers_fallback_warning_to_the_shell(capsys):
    command = _fallback_create_command()

    assert command.endswith(" && true -m venv $GALAXY_VIRTUAL_ENV")
    # Nothing is printed while building the command, only when it runs.
    assert capsys.readouterr().err == ""


def test_fallback_warning_only_shown_when_virtualenv_is_created(tmp_path):
    command = _fallback_create_command()
    expected = "python3.14 was not found on PATH, creating the Galaxy virtualenv with Planemo's own interpreter"

    missing = _run_create_template(command, tmp_path / "missing")
    assert expected in missing.stderr
    assert "Created virtualenv" in missing.stdout

    existing = tmp_path / "existing"
    existing.mkdir()
    result = _run_create_template(command, existing)
    assert result.stderr == ""
    assert result.stdout == ""


def test_create_command_does_not_warn_when_python_found():
    with patch.object(virtualenv, "which", side_effect=["/opt/python3.10", None]):
        command = virtualenv.create_command("/tmp/galaxy-venv", "3.10")

    assert command == "/opt/python3.10 -m venv /tmp/galaxy-venv"


def test_resolve_python_names_interpreter_actually_used():
    with patch.object(virtualenv, "which", return_value="/opt/python3.10"):
        assert virtualenv.resolve_python("3.10") == ("/opt/python3.10", "3.10", False)
    with patch.object(virtualenv, "which", return_value=None):
        _, version, fallback = virtualenv.resolve_python("3.10")
    assert fallback
    assert version == "%d.%d" % sys.version_info[:2]
