from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cypher
import pytest
from cypher.errors import RunConfigurationError, RunError, ValidationError
from cypher.execution import resolve_run_paths, run_command


def valid_simulation(**kwargs) -> cypher.Simulation:
    return cypher.Simulation(
        cypher.Control(duration=1, start_year=2000, start_month=1),
        **kwargs,
    )


def install_fake_execution(monkeypatch, *, returncode: int = 0):
    calls = []

    monkeypatch.setattr(
        "cypher.execution.resolve_cyclus_executable",
        lambda explicit=None: Path(explicit or "/fake/cyclus"),
    )

    def fake_run(command, *, cwd, stream_output):
        calls.append((command, cwd, stream_output))
        output_path = Path(command[command.index("-o") + 1])
        if returncode == 0:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"sqlite")
        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout="normal output\n",
            stderr="diagnostic output\n" if returncode else "",
        )

    monkeypatch.setattr("cypher.execution.run_command", fake_run)
    return calls


def test_unnamed_default_paths(tmp_path: Path) -> None:
    paths = resolve_run_paths(valid_simulation(), directory=tmp_path)

    assert paths.input_path == tmp_path / "simulation.xml"
    assert paths.output_path == tmp_path / "simulation.sqlite"


def test_name_normalizes_supported_suffixes(tmp_path: Path) -> None:
    simulation = valid_simulation(name="bakery.xml")

    paths = resolve_run_paths(simulation, directory=tmp_path)

    assert simulation.name == "bakery"
    assert paths.input_path == tmp_path / "bakery.xml"
    assert paths.output_path == tmp_path / "bakery.sqlite"


@pytest.mark.parametrize("name", ["subdir/bakery", "bakery.txt", "", "   "])
def test_invalid_simulation_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        valid_simulation(name=name)


def test_input_path_derives_same_stem_output(tmp_path: Path) -> None:
    paths = resolve_run_paths(
        valid_simulation(),
        directory=tmp_path,
        input_path="inputs/my_sim.xml",
    )

    assert paths.input_path == tmp_path / "inputs" / "my_sim.xml"
    assert paths.output_path == tmp_path / "inputs" / "my_sim.sqlite"


def test_run_arguments_override_persistent_paths(tmp_path: Path) -> None:
    simulation = valid_simulation(
        input_path="stored.xml",
        output_path="stored.sqlite",
    )

    paths = resolve_run_paths(
        simulation,
        directory=tmp_path,
        input_path="current.xml",
        output_path="current.sqlite",
    )

    assert paths.input_path == tmp_path / "current.xml"
    assert paths.output_path == tmp_path / "current.sqlite"
    assert simulation.input_path == Path("stored.xml")
    assert simulation.output_path == Path("stored.sqlite")


def test_missing_suffix_is_appended_and_conflicting_suffix_rejected(
    tmp_path: Path,
) -> None:
    paths = resolve_run_paths(
        valid_simulation(),
        directory=tmp_path,
        input_path="model",
        output_path="database",
    )
    assert paths.input_path.name == "model.xml"
    assert paths.output_path.name == "database.sqlite"

    with pytest.raises(RunConfigurationError, match=r"end in \.xml"):
        resolve_run_paths(
            valid_simulation(), directory=tmp_path, input_path="model.json"
        )


def test_existing_files_are_protected_before_export(
    monkeypatch, tmp_path: Path
) -> None:
    simulation = valid_simulation()
    existing = tmp_path / "simulation.xml"
    existing.write_text("keep me")
    install_fake_execution(monkeypatch)

    with pytest.raises(RunConfigurationError, match="overwrite"):
        simulation.run(directory=tmp_path, cyclus_executable="/fake/cyclus")

    assert existing.read_text() == "keep me"


@pytest.mark.parametrize("target_name", ["simulation.xml", "simulation.sqlite"])
def test_existing_directory_is_never_treated_as_run_file(
    monkeypatch, tmp_path: Path, target_name: str
) -> None:
    simulation = valid_simulation()
    (tmp_path / target_name).mkdir()
    install_fake_execution(monkeypatch)

    with pytest.raises(RunConfigurationError, match="existing directories"):
        simulation.run(
            directory=tmp_path,
            overwrite=True,
            cyclus_executable="/fake/cyclus",
        )


def test_overwrite_replaces_files(monkeypatch, tmp_path: Path) -> None:
    simulation = valid_simulation()
    input_path = tmp_path / "simulation.xml"
    output_path = tmp_path / "simulation.sqlite"
    input_path.write_text("old input")
    output_path.write_text("old output")
    calls = install_fake_execution(monkeypatch)

    result = simulation.run(
        directory=tmp_path,
        overwrite=True,
        cyclus_executable="/fake/cyclus",
    )

    assert result.success
    assert input_path.read_text().startswith("<simulation>")
    assert output_path.read_bytes() == b"sqlite"
    assert calls[0][2] is True


def test_command_omits_default_verbosity_and_accepts_levels(
    monkeypatch, tmp_path: Path
) -> None:
    calls = install_fake_execution(monkeypatch)
    simulation = valid_simulation()

    simulation.run(directory=tmp_path, cyclus_executable="/fake/cyclus")
    assert "-v" not in calls[-1][0]

    simulation.run(
        directory=tmp_path,
        overwrite=True,
        verbosity=6,
        cyclus_executable="/fake/cyclus",
    )
    assert calls[-1][0][-2:] == ("-v", "6")


@pytest.mark.parametrize("verbosity", [-1, 12])
def test_invalid_verbosity_range_is_rejected(verbosity: int, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="between 0 and 11"):
        valid_simulation().run(directory=tmp_path, verbosity=verbosity)


@pytest.mark.parametrize("verbosity", [True, 1.5, "6"])
def test_invalid_verbosity_type_is_rejected(verbosity, tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="integer"):
        valid_simulation().run(directory=tmp_path, verbosity=verbosity)


def test_extra_args_and_conflicts(monkeypatch, tmp_path: Path) -> None:
    calls = install_fake_execution(monkeypatch)
    simulation = valid_simulation()
    simulation.run(
        directory=tmp_path,
        extra_args=["--warn-limit", "100", "--no-mem"],
        cyclus_executable="/fake/cyclus",
    )
    assert calls[-1][0][-3:] == ("--warn-limit", "100", "--no-mem")

    with pytest.raises(RunConfigurationError, match="Cypher-owned"):
        simulation.run(
            directory=tmp_path,
            overwrite=True,
            extra_args=["-o", "other.sqlite"],
            cyclus_executable="/fake/cyclus",
        )


@pytest.mark.parametrize(
    "argument",
    [
        "--input-file=other.xml",
        "--output-path=other.sqlite",
        "--verb=6",
        "-iother.xml",
        "-oother.sqlite",
        "-v6",
    ],
)
def test_attached_cypher_owned_extra_args_are_rejected(
    argument: str, tmp_path: Path
) -> None:
    with pytest.raises(RunConfigurationError, match="Cypher-owned"):
        valid_simulation().run(directory=tmp_path, extra_args=[argument])


def test_failed_run_raises_with_result(monkeypatch, tmp_path: Path) -> None:
    install_fake_execution(monkeypatch, returncode=7)
    simulation = valid_simulation()

    with pytest.raises(RunError) as caught:
        simulation.run(directory=tmp_path, cyclus_executable="/fake/cyclus")

    result = caught.value.result
    assert not result.success
    assert result.returncode == 7
    assert result.stderr == "diagnostic output\n"
    assert result.input_path.exists()


def test_invalid_simulation_fails_before_execution(monkeypatch, tmp_path: Path) -> None:
    calls = install_fake_execution(monkeypatch)

    with pytest.raises(ValidationError):
        cypher.Simulation().run(directory=tmp_path, cyclus_executable="/fake/cyclus")

    assert calls == []


def test_stream_output_flag_reaches_process_boundary(
    monkeypatch, tmp_path: Path
) -> None:
    calls = install_fake_execution(monkeypatch)
    valid_simulation().run(
        directory=tmp_path,
        stream_output=False,
        cyclus_executable="/fake/cyclus",
    )
    assert calls[0][2] is False


def test_run_command_streams_and_captures(capsys, tmp_path: Path) -> None:
    command = (
        sys.executable,
        "-c",
        "import sys; print('hello'); print('warning', file=sys.stderr)",
    )

    completed = run_command(command, cwd=tmp_path, stream_output=True)

    captured = capsys.readouterr()
    assert completed.stdout == "hello\n"
    assert completed.stderr == "warning\n"
    assert captured.out == "hello\n"
    assert captured.err == "warning\n"


def test_explicit_executable_mismatch_warns(
    monkeypatch, tmp_path: Path, catalog
) -> None:
    simulation = valid_simulation(catalog=catalog)
    install_fake_execution(monkeypatch)

    with pytest.warns(RuntimeWarning, match="differs"):
        simulation.run(
            directory=tmp_path,
            cyclus_executable="/different/cyclus",
        )
