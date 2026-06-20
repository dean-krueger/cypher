"""Cyclus executable selection and archetype discovery."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .catalog import Catalog, cache_root, set_catalog
from .errors import CyclusInvocationError, DiscoveryError


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

    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [str(self.executable), *arguments],
                check=False,
                capture_output=True,
                text=True,
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


def discover(
    *,
    executable: str | os.PathLike[str] | None = None,
    cache_path: Path | None = None,
    strict: bool = False,
) -> DiscoveryResult:
    """Discover archetypes, cache normalized metadata, and write type stubs."""

    adapter = CyclusAdapter(executable)
    metadata, process_warnings = adapter.metadata()
    stat = adapter.executable.stat()
    catalog = Catalog.from_metadata(
        metadata,
        executable=str(adapter.executable),
        cyclus_version=adapter.version(),
        executable_mtime_ns=stat.st_mtime_ns,
        discovery_warnings=process_warnings,
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
    saved = catalog.save(cache_path)
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
            "from typing import Any",
            "from cypher.archetype import Prototype",
            "",
        ]
        for archetype in catalog.library(library).values():
            parameters = ["name: str | None = ..."]
            for field_spec in archetype.fields:
                annotation = _stub_type(field_spec.cpp_type)
                parameters.append(f"{field_spec.name}: {annotation} = ...")
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
    if isinstance(cpp_type, list):
        inner = _stub_type(cpp_type[1]) if len(cpp_type) > 1 else "Any"
        return f"list[{inner}]"
    return {
        "bool": "bool",
        "double": "float",
        "float": "float",
        "int": "int",
        "long": "int",
        "std::string": "str",
        "string": "str",
    }.get(cpp_type, "Any")


def _one_line(value: str) -> str:
    return " ".join(value.replace('"""', "'''").split())
