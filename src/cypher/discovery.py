"""Cyclus executable selection and archetype discovery."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .catalog import Catalog, cache_file, cache_root, set_catalog
from .errors import CyclusInvocationError, DiscoveryError
from .shapes import ValueShape


@dataclass(frozen=True)
class DiscoveryResult:
    """Result paths and compatibility details from a discovery run."""

    catalog: Catalog
    cache_path: Path
    stub_paths: tuple[Path, ...]


def resolve_cyclus_executable(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Resolve Cyclus using explicit selection, environment, then ``PATH``."""

    candidate = explicit or os.environ.get("CYPHER_CYCLUS_EXECUTABLE")
    if candidate:
        path = Path(candidate).expanduser()
        if not path.exists():
            raise DiscoveryError(f"Selected Cyclus executable does not exist: {path}")
        if not path.is_file():
            raise DiscoveryError(f"Selected Cyclus executable is not a file: {path}")
        if not os.access(path, os.X_OK):
            raise DiscoveryError(
                f"Selected Cyclus executable is not executable: {path}"
            )
        return path.resolve()
    located = shutil.which("cyclus")
    if not located:
        raise DiscoveryError(
            "Could not find Cyclus. Pass --cyclus, set CYPHER_CYCLUS_EXECUTABLE, "
            "or put 'cyclus' on PATH."
        )
    return Path(located).resolve()


class CyclusAdapter:
    """Narrow subprocess boundary for one selected Cyclus executable."""

    def __init__(self, executable: str | os.PathLike[str] | None = None) -> None:
        self.executable = resolve_cyclus_executable(executable)

    def _run(
        self, arguments: list[str], *, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [str(self.executable), *arguments],
                check=False,
                capture_output=True,
                text=True,
                cwd=cwd,
            )
        except OSError as error:
            raise CyclusInvocationError(
                f"Could not invoke Cyclus executable {self.executable}: {error}"
            ) from error

    def version(self) -> str | None:
        result = self._run(["--version"])
        if result.returncode != 0:
            return None
        return result.stdout.strip() or result.stderr.strip() or None

    def metadata(self) -> tuple[dict[str, object], tuple[str, ...]]:
        result = self._run(["--metadata"])
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise CyclusInvocationError(
                f"Cyclus metadata discovery failed using {self.executable} "
                f"(exit {result.returncode}): {detail}"
            )
        try:
            metadata = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise CyclusInvocationError(
                f"Cyclus returned invalid metadata JSON using {self.executable}: "
                f"{error}"
            ) from error
        if not isinstance(metadata, dict):
            raise CyclusInvocationError("Cyclus metadata output is not a JSON object.")
        warnings = tuple(
            line.strip() for line in result.stderr.splitlines() if line.strip()
        )
        return metadata, warnings

    def base_schema_path(self) -> tuple[str | None, tuple[str, ...]]:
        """Return Cyclus's reported base Relax NG schema path when available."""

        result = self._run(["--rng-schema"])
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            return (
                None,
                (
                    "Cyclus did not report a base Relax NG schema path with "
                    f"--rng-schema (exit {result.returncode}): {detail}",
                ),
            )
        path = result.stdout.strip()
        if not path:
            return (
                None,
                ("Cyclus reported an empty base Relax NG schema path.",),
            )
        return path, tuple(
            line.strip() for line in result.stderr.splitlines() if line.strip()
        )

    def full_schema_path(
        self, destination_dir: Path
    ) -> tuple[str | None, tuple[str, ...]]:
        """Generate and cache Cyclus's full environment-specific schema."""

        with tempfile.TemporaryDirectory(prefix="cypher-schema-") as directory:
            working_dir = Path(directory)
            skeleton = working_dir / "simulation.xml"
            result = self._run(["-n", skeleton.name], cwd=working_dir)
            process_warnings = tuple(
                line.strip() for line in result.stderr.splitlines() if line.strip()
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "no output"
                return (
                    None,
                    (
                        "Cyclus did not generate a full Relax NG schema with "
                        f"-n (exit {result.returncode}): {detail}",
                    ),
                )
            try:
                header = skeleton.read_text(encoding="utf-8").splitlines()[0]
            except (FileNotFoundError, IndexError, OSError) as error:
                return (
                    None,
                    (f"Cyclus -n did not write a readable schema header: {error}",),
                )
            match = re.search(r'href="([^"]+)"', header)
            if match is None:
                return (
                    None,
                    ("Cyclus -n output did not include an xml-model href.",),
                )
            source = (working_dir / match.group(1)).resolve()
            if not source.is_file():
                return (
                    None,
                    (f"Cyclus -n referenced a schema that was not written: {source}",),
                )
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / "cyclus-full-schema.rng"
            temporary = destination.with_suffix(".rng.tmp")
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
        return str(destination), process_warnings


def discover(
    *,
    executable: str | os.PathLike[str] | None = None,
    cache_path: Path | None = None,
    strict: bool = False,
) -> DiscoveryResult:
    """Discover archetypes, cache normalized metadata, and write type stubs."""

    adapter = CyclusAdapter(executable)
    metadata, process_warnings = adapter.metadata()
    base_schema_path, schema_warnings = adapter.base_schema_path()
    target_cache = cache_path or cache_file()
    full_schema_path, full_schema_warnings = adapter.full_schema_path(
        target_cache.parent / "schemas"
    )
    stat = adapter.executable.stat()
    catalog = Catalog.from_metadata(
        metadata,
        executable=str(adapter.executable),
        cyclus_version=adapter.version(),
        executable_mtime_ns=stat.st_mtime_ns,
        base_schema_path=base_schema_path,
        full_schema_path=full_schema_path,
        discovery_warnings=process_warnings + schema_warnings + full_schema_warnings,
    )
    compatibility_warnings = [
        f"{archetype.spec}: {warning}"
        for archetype in catalog.archetypes.values()
        for warning in archetype.warnings
    ]
    if strict and compatibility_warnings:
        raise DiscoveryError(
            "Strict discovery rejected unsupported metadata:\n- "
            + "\n- ".join(compatibility_warnings)
        )
    saved = catalog.save(target_cache)
    stubs = write_stubs(catalog)
    set_catalog(catalog)
    return DiscoveryResult(catalog=catalog, cache_path=saved, stub_paths=stubs)


def write_stubs(catalog: Catalog, root: Path | None = None) -> tuple[Path, ...]:
    """Write environment-local ``.pyi`` interfaces for discovered libraries."""

    target_root = root or cache_root() / "stubs" / "cypher"
    target_root.mkdir(parents=True, exist_ok=True)
    paths = []
    for library in catalog.libraries:
        lines = [
            "from collections.abc import Mapping, Sequence, Set",
            "from typing import Any",
            "from cypher.archetype import Prototype",
            "",
        ]
        for archetype in catalog.library(library).values():
            parameters = ["name: str | None = ...", "*"]
            ordered_fields = sorted(
                archetype.fields, key=lambda field: not field.required
            )
            for field_spec in ordered_fields:
                annotation = _stub_type(field_spec.cpp_type)
                default = "" if field_spec.required else " = ..."
                parameters.append(f"{field_spec.name}: {annotation}{default}")
            lines.extend(
                [
                    f"class {archetype.name}(Prototype):",
                    f'    """{_one_line(archetype.doc)}"""',
                    f"    def __init__(self, {', '.join(parameters)}) -> None: ...",
                    "",
                ]
            )
        path = target_root / f"{library}.pyi"
        temporary = path.with_suffix(".pyi.tmp")
        temporary.write_text("\n".join(lines), encoding="utf-8")
        os.replace(temporary, path)
        paths.append(path)
    marker = target_root / "py.typed"
    marker.touch()
    return tuple(paths)


def compatibility_report(catalog: Catalog) -> str:
    """Render a concise human-readable discovery report."""

    lines = [
        f"Cyclus executable: {catalog.executable or 'unknown'}",
        f"Cyclus version: {catalog.cyclus_version or 'unknown'}",
        f"Base schema path: {catalog.base_schema_path or 'unknown'}",
        f"Generated full schema path: {catalog.full_schema_path or 'unknown'}",
        f"Libraries: {', '.join(catalog.libraries) or 'none'}",
        f"Archetypes: {len(catalog.archetypes)}",
    ]
    warnings = [
        f"{archetype.spec}: {warning}"
        for archetype in catalog.archetypes.values()
        for warning in archetype.warnings
    ]
    warnings.extend(catalog.discovery_warnings)
    if warnings:
        lines.append(f"Warnings ({len(warnings)}):")
        lines.extend(f"  - {warning}" for warning in warnings)
    else:
        lines.append("Compatibility: all discovered archetypes are supported.")
    stale = catalog.stale_reason()
    if stale:
        lines.append(f"Stale cache warning: {stale}")
    return "\n".join(lines)


def _stub_type(cpp_type: str | list[object]) -> str:
    return ValueShape.from_cpp_type(cpp_type).type_expression()


def _one_line(value: str) -> str:
    return " ".join(value.replace('"""', "'''").split())
