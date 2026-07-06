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


def test_base_schema_path_uses_cyclus_rng_schema(monkeypatch, tmp_path: Path) -> None:
    executable = _executable(tmp_path / "cyclus")

    def fake_run(command, **_kwargs):
        assert command == [str(executable.resolve()), "--rng-schema"]
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="/opt/cyclus/share/cyclus/cyclus.rng.in\n",
            stderr="",
        )

    monkeypatch.setattr("cypher.discovery.subprocess.run", fake_run)
    adapter = CyclusAdapter(executable)

    path, warnings = adapter.base_schema_path()

    assert path == "/opt/cyclus/share/cyclus/cyclus.rng.in"
    assert warnings == ()


def test_full_schema_path_uses_cyclus_new_file(monkeypatch, tmp_path: Path) -> None:
    executable = _executable(tmp_path / "cyclus")

    def fake_run(command, **kwargs):
        assert command == [str(executable.resolve()), "-n", "simulation.xml"]
        cwd = Path(kwargs["cwd"])
        (cwd / "simulation.xml").write_text(
            '<?xml-model href="cyclus_grammar_fixture.rng" application="text/xml"?>\n'
            "<simulation />\n",
            encoding="utf-8",
        )
        (cwd / "cyclus_grammar_fixture.rng").write_text(
            "<grammar />\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="Experimental Warning: fixture\n",
        )

    monkeypatch.setattr("cypher.discovery.subprocess.run", fake_run)
    adapter = CyclusAdapter(executable)

    path, warnings = adapter.full_schema_path(tmp_path / "cache" / "schemas")

    assert path == str(tmp_path / "cache" / "schemas" / "cyclus-full-schema.rng")
    assert Path(path).read_text(encoding="utf-8") == "<grammar />\n"
    assert warnings == ("Experimental Warning: fixture",)


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
    assert "/opt/cyclus/share/cyclus/cyclus.rng.in" in report
    assert "/opt/cypher/cache/schemas/cyclus-full-schema.rng" in report
    assert "agents, cycamore" in report
