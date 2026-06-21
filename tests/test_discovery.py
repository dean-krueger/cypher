from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cypher.discovery import (
    CyclusAdapter,
    compatibility_report,
    resolve_cyclus_executable,
    write_stubs,
)
from cypher.errors import CyclusInvocationError, DiscoveryError


def _executable(path: Path, content: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.write_text(content)
    path.chmod(0o755)
    return path


def test_executable_resolution_order(monkeypatch, tmp_path: Path) -> None:
    explicit = _executable(tmp_path / "explicit")
    environment = _executable(tmp_path / "environment")
    path_entry = tmp_path / "bin"
    path_entry.mkdir()
    path_cyclus = _executable(path_entry / "cyclus")
    monkeypatch.setenv("CYPHER_CYCLUS_EXECUTABLE", str(environment))

    assert resolve_cyclus_executable(explicit) == explicit.resolve()
    assert resolve_cyclus_executable() == environment.resolve()

    monkeypatch.delenv("CYPHER_CYCLUS_EXECUTABLE")
    monkeypatch.setattr("cypher.discovery.shutil.which", lambda _name: str(path_cyclus))
    assert resolve_cyclus_executable() == path_cyclus.resolve()


def test_missing_executable_is_actionable(monkeypatch) -> None:
    monkeypatch.delenv("CYPHER_CYCLUS_EXECUTABLE", raising=False)
    monkeypatch.setenv("PATH", "")
    with pytest.raises(DiscoveryError, match="CYPHER_CYCLUS_EXECUTABLE"):
        resolve_cyclus_executable()


def test_invocation_error_contains_loader_output(monkeypatch, tmp_path: Path) -> None:
    executable = _executable(tmp_path / "cyclus")
    monkeypatch.setattr(
        "cypher.discovery.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=127,
            stdout="",
            stderr="missing shared library",
        ),
    )
    adapter = CyclusAdapter(executable)

    with pytest.raises(CyclusInvocationError, match="missing shared library"):
        adapter.metadata()


def test_stubs_are_written_for_each_library(tmp_path: Path, catalog) -> None:
    paths = write_stubs(catalog, tmp_path)

    assert {path.name for path in paths} == {"agents.pyi", "cycamore.pyi"}
    cycamore_stub = (tmp_path / "cycamore.pyi").read_text()
    assert "class Source" in cycamore_stub
    assert (
        "name: str | None = ..., *, outcommod: str, throughput: float = ..."
        in cycamore_stub
    )
    assert (tmp_path / "py.typed").exists()


def test_compatibility_report_identifies_environment(catalog) -> None:
    report = compatibility_report(catalog)
    assert "/opt/cyclus/bin/cyclus" in report
    assert "agents, cycamore" in report
