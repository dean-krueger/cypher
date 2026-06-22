"""Safe Cyclus execution for authored simulations."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from .discovery import resolve_cyclus_executable
from .errors import DiscoveryError, RunConfigurationError, RunError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .core import Simulation


@dataclass(frozen=True)
class RunPaths:
    """Resolved filesystem locations for one run."""

    directory: Path
    input_path: Path
    output_path: Path


@dataclass(frozen=True)
class RunResult:
    """Captured result of one Cyclus process."""

    returncode: int
    directory: Path
    input_path: Path
    output_path: Path
    stdout: str
    stderr: str
    command: tuple[str, ...]

    @property
    def success(self) -> bool:
        """Whether Cyclus exited successfully."""

        return self.returncode == 0

    def __repr__(self) -> str:
        status = "successful" if self.success else "failed"
        return (
            f"RunResult({status}, returncode={self.returncode}, "
            f"input_path={str(self.input_path)!r}, "
            f"output_path={str(self.output_path)!r})"
        )


def normalize_simulation_name(name: str | None) -> str | None:
    """Normalize an optional semantic simulation name to a filename stem."""

    if name is None:
        return None
    if not isinstance(name, str):
        raise TypeError("Simulation name must be a string or None.")
    value = name.strip()
    if not value:
        raise ValueError("Simulation name must not be empty.")
    path = Path(value)
    if path.name != value:
        raise ValueError(
            "Simulation name must not contain directory components; use "
            "directory, input_path, or output_path instead."
        )
    if path.suffix.lower() in {".xml", ".sqlite"}:
        value = path.stem
    elif path.suffix:
        raise ValueError(
            "Simulation name may be a plain name or end in .xml or .sqlite."
        )
    if not value:
        raise ValueError("Simulation name must contain a filename stem.")
    return value


def resolve_run_paths(
    simulation: Simulation,
    *,
    directory: str | os.PathLike[str] = ".",
    input_path: str | os.PathLike[str] | None = None,
    output_path: str | os.PathLike[str] | None = None,
) -> RunPaths:
    """Resolve run paths using per-run, persistent, name, and default precedence."""

    run_directory = Path(directory).expanduser().resolve()
    if run_directory.exists() and not run_directory.is_dir():
        raise RunConfigurationError(
            f"Run directory is not a directory: {run_directory}"
        )

    selected_input = input_path if input_path is not None else simulation.input_path
    selected_output = output_path if output_path is not None else simulation.output_path
    stem = simulation.name or "simulation"

    if selected_input is None:
        resolved_input = run_directory / f"{stem}.xml"
    else:
        resolved_input = _resolve_path(selected_input, run_directory, ".xml", "input")

    if selected_output is None:
        if selected_input is not None:
            resolved_output = resolved_input.with_suffix(".sqlite")
        else:
            resolved_output = run_directory / f"{stem}.sqlite"
    else:
        resolved_output = _resolve_path(
            selected_output, run_directory, ".sqlite", "output"
        )

    resolved_input = resolved_input.resolve()
    resolved_output = resolved_output.resolve()
    if resolved_input == resolved_output:
        raise RunConfigurationError("Input and output paths must be different.")
    return RunPaths(
        directory=run_directory,
        input_path=resolved_input,
        output_path=resolved_output,
    )


def run_simulation(
    simulation: Simulation,
    *,
    directory: str | os.PathLike[str] = ".",
    input_path: str | os.PathLike[str] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    overwrite: bool = False,
    stream_output: bool = True,
    verbosity: int | None = None,
    extra_args: Sequence[str] | None = None,
    cyclus_executable: str | os.PathLike[str] | None = None,
) -> RunResult:
    """Validate, export, and execute one simulation."""

    if not isinstance(overwrite, bool):
        raise TypeError("overwrite must be a boolean.")
    if not isinstance(stream_output, bool):
        raise TypeError("stream_output must be a boolean.")
    _validate_verbosity(verbosity)
    advanced = _validate_extra_args(extra_args)
    paths = resolve_run_paths(
        simulation,
        directory=directory,
        input_path=input_path,
        output_path=output_path,
    )
    existing_directories = [
        path for path in (paths.input_path, paths.output_path) if path.is_dir()
    ]
    if existing_directories:
        rendered = ", ".join(str(path) for path in existing_directories)
        raise RunConfigurationError(
            f"Run file path(s) refer to existing directories: {rendered}."
        )
    conflicts = [
        path for path in (paths.input_path, paths.output_path) if path.exists()
    ]
    if conflicts and not overwrite:
        rendered = ", ".join(str(path) for path in conflicts)
        raise RunConfigurationError(
            f"Refusing to overwrite existing run file(s): {rendered}. "
            "Pass overwrite=True to replace them."
        )

    executable = _resolve_execution_executable(simulation, cyclus_executable)
    paths.directory.mkdir(parents=True, exist_ok=True)
    simulation.export_to_xml(paths.input_path)
    if overwrite and paths.output_path.exists():
        paths.output_path.unlink()

    command = [str(executable), str(paths.input_path), "-o", str(paths.output_path)]
    if verbosity is not None:
        command.extend(["-v", str(verbosity)])
    paths.output_path.parent.mkdir(parents=True, exist_ok=True)
    command.extend(advanced)
    completed = run_command(
        tuple(command), cwd=paths.directory, stream_output=stream_output
    )
    result = RunResult(
        returncode=completed.returncode,
        directory=paths.directory,
        input_path=paths.input_path,
        output_path=paths.output_path,
        stdout=completed.stdout,
        stderr=completed.stderr,
        command=tuple(command),
    )
    if not result.success:
        raise RunError(result)
    return result


def run_command(
    command: tuple[str, ...], *, cwd: Path, stream_output: bool
) -> subprocess.CompletedProcess[str]:
    """Run a command while optionally streaming and always capturing output."""

    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        raise RunConfigurationError(
            f"Could not launch Cyclus command {command[0]!r}: {error}"
        ) from error

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    threads = [
        threading.Thread(
            target=_drain_stream,
            args=(
                process.stdout,
                stdout_parts,
                sys.stdout if stream_output else None,
            ),
            daemon=True,
        ),
        threading.Thread(
            target=_drain_stream,
            args=(
                process.stderr,
                stderr_parts,
                sys.stderr if stream_output else None,
            ),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    returncode = process.wait()
    for thread in threads:
        thread.join()
    return subprocess.CompletedProcess(
        args=command,
        returncode=returncode,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
    )


def _resolve_path(
    value: str | os.PathLike[str],
    directory: Path,
    suffix: str,
    label: str,
) -> Path:
    path = Path(value).expanduser()
    if not path.suffix:
        path = path.with_suffix(suffix)
    elif path.suffix.lower() != suffix:
        raise RunConfigurationError(f"Cyclus {label} path must end in {suffix}: {path}")
    if not path.is_absolute():
        path = directory / path
    return path


def _validate_verbosity(verbosity: int | None) -> None:
    if verbosity is None:
        return
    if isinstance(verbosity, bool) or not isinstance(verbosity, int):
        raise TypeError("verbosity must be an integer from 0 through 11 or None.")
    if not 0 <= verbosity <= 11:
        raise ValueError("verbosity must be between 0 and 11.")


def _validate_extra_args(extra_args: Sequence[str] | None) -> tuple[str, ...]:
    if extra_args is None:
        return ()
    if isinstance(extra_args, (str, bytes)):
        raise TypeError("extra_args must be a sequence of individual strings.")
    values = tuple(extra_args)
    if not all(isinstance(value, str) for value in values):
        raise TypeError("Every extra_args entry must be a string.")
    forbidden = {"-i", "--input-file", "-o", "--output-path", "-v", "--verb"}
    long_prefixes = ("--input-file=", "--output-path=", "--verb=")
    short_prefixes = ("-i", "-o", "-v")
    conflicts = sorted(
        value
        for value in values
        if value in forbidden
        or value.startswith(long_prefixes)
        or (len(value) > 2 and value.startswith(short_prefixes))
    )
    if conflicts:
        raise RunConfigurationError(
            "extra_args may not override Cypher-owned options: " + ", ".join(conflicts)
        )
    return values


def _resolve_execution_executable(
    simulation: Simulation,
    explicit: str | os.PathLike[str] | None,
) -> Path:
    catalog_executable = simulation.catalog.executable if simulation.catalog else None
    if explicit is not None:
        resolved = resolve_cyclus_executable(explicit)
        if catalog_executable:
            discovered = Path(catalog_executable).expanduser().resolve()
            if resolved != discovered:
                warnings.warn(
                    "The selected Cyclus executable differs from the executable "
                    "used for discovery; archetype metadata may not match execution.",
                    RuntimeWarning,
                    stacklevel=3,
                )
        return resolved
    if catalog_executable:
        try:
            return resolve_cyclus_executable(catalog_executable)
        except DiscoveryError as error:
            warnings.warn(
                f"The Cyclus executable recorded during discovery is unavailable "
                f"({error}); falling back to environment/PATH resolution.",
                RuntimeWarning,
                stacklevel=3,
            )
    return resolve_cyclus_executable()


def _drain_stream(
    stream: TextIO | None,
    capture: list[str],
    destination: TextIO | None,
) -> None:
    if stream is None:
        return
    try:
        while True:
            chunk = stream.read(1)
            if chunk == "":
                break
            capture.append(chunk)
            if destination is not None:
                destination.write(chunk)
                destination.flush()
    finally:
        stream.close()
