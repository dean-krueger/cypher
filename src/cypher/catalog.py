"""Normalized metadata describing archetype libraries and fields."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .errors import DiscoveryError

RNG_NAMESPACE = "http://relaxng.org/ns/structure/1.0"
RNG = f"{{{RNG_NAMESPACE}}}"


@dataclass(frozen=True)
class FieldSpec:
    """A serializable archetype input field."""

    name: str
    alias: str | list[Any]
    cpp_type: str | list[Any]
    required: bool
    default: Any = None
    has_default: bool = False
    doc: str = ""
    uitype: str | list[Any] | None = None
    value_range: tuple[float, float] | None = None

    @property
    def python_type(self) -> type[Any]:
        type_name = self.cpp_type
        if isinstance(type_name, list):
            return list if type_name and type_name[0] == "std::vector" else object
        if type_name in {"int", "long", "long int", "unsigned int"}:
            return int
        if type_name in {"double", "float"}:
            return float
        if type_name == "bool":
            return bool
        if type_name in {"std::string", "string"}:
            return str
        return object


@dataclass(frozen=True)
class ArchetypeSpec:
    """Normalized description of one Cyclus archetype."""

    spec: str
    path: str
    library: str
    name: str
    entity: str
    doc: str
    fields: tuple[FieldSpec, ...]
    schema: str
    warnings: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return not self.warnings

    def field(self, name: str) -> FieldSpec | None:
        return next((item for item in self.fields if item.name == name), None)


@dataclass
class Catalog:
    """Discovered archetypes plus provenance for their Cyclus environment."""

    archetypes: dict[str, ArchetypeSpec]
    executable: str | None = None
    cyclus_version: str | None = None
    executable_mtime_ns: int | None = None
    discovery_warnings: tuple[str, ...] = ()
    format_version: int = 1
    _libraries: dict[str, dict[str, ArchetypeSpec]] = field(
        init=False, repr=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        libraries: dict[str, dict[str, ArchetypeSpec]] = {}
        for archetype in self.archetypes.values():
            libraries.setdefault(archetype.library, {})[archetype.name] = archetype
        self._libraries = libraries

    @property
    def libraries(self) -> tuple[str, ...]:
        return tuple(sorted(self._libraries))

    def library(self, name: str) -> dict[str, ArchetypeSpec]:
        try:
            return self._libraries[name]
        except KeyError as error:
            available = ", ".join(self.libraries) or "none"
            raise DiscoveryError(
                f"Archetype library {name!r} is not available. "
                f"Discovered libraries: {available}."
            ) from error

    def get(self, library: str, name: str) -> ArchetypeSpec:
        try:
            return self.library(library)[name]
        except KeyError as error:
            available = ", ".join(sorted(self.library(library))) or "none"
            raise DiscoveryError(
                f"Archetype {library}:{name} is not available. "
                f"Available in {library!r}: {available}."
            ) from error

    @classmethod
    def from_metadata(
        cls,
        metadata: dict[str, Any],
        *,
        executable: str | None = None,
        cyclus_version: str | None = None,
        executable_mtime_ns: int | None = None,
        discovery_warnings: tuple[str, ...] = (),
    ) -> Catalog:
        annotations = metadata.get("annotations")
        schemas = metadata.get("schema")
        specs = metadata.get("specs")
        if not isinstance(annotations, dict) or not isinstance(schemas, dict):
            raise DiscoveryError(
                "Cyclus metadata must contain object-valued 'annotations' and "
                "'schema' entries."
            )
        if not isinstance(specs, list):
            raise DiscoveryError("Cyclus metadata must contain a list-valued 'specs'.")

        archetypes: dict[str, ArchetypeSpec] = {}
        for raw_spec in specs:
            if not isinstance(raw_spec, str):
                raise DiscoveryError("Every Cyclus archetype spec must be a string.")
            path, library, name = split_spec(raw_spec)
            annotation = annotations.get(raw_spec, {})
            schema = schemas.get(raw_spec, "")
            if not isinstance(annotation, dict) or not isinstance(schema, str):
                raise DiscoveryError(f"Invalid metadata for archetype {raw_spec!r}.")
            fields, warnings = _normalize_fields(annotation, schema)
            archetypes[raw_spec] = ArchetypeSpec(
                spec=raw_spec,
                path=path,
                library=library,
                name=name,
                entity=str(annotation.get("entity", "archetype")),
                doc=str(annotation.get("doc", "")).strip(),
                fields=tuple(fields),
                schema=schema,
                warnings=tuple(warnings),
            )
        return cls(
            archetypes=archetypes,
            executable=executable,
            cyclus_version=cyclus_version,
            executable_mtime_ns=executable_mtime_ns,
            discovery_warnings=discovery_warnings,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "executable": self.executable,
            "cyclus_version": self.cyclus_version,
            "executable_mtime_ns": self.executable_mtime_ns,
            "discovery_warnings": list(self.discovery_warnings),
            "archetypes": {
                spec: asdict(archetype) for spec, archetype in self.archetypes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Catalog:
        if data.get("format_version") != 1:
            raise DiscoveryError(
                "The discovery cache format is unsupported. Run 'cypher discover' "
                "to refresh it."
            )
        archetypes = {}
        for spec, item in data.get("archetypes", {}).items():
            raw_item = dict(item)
            fields = []
            for field_data in raw_item.get("fields", []):
                raw_field = dict(field_data)
                if raw_field.get("value_range") is not None:
                    raw_field["value_range"] = tuple(raw_field["value_range"])
                fields.append(FieldSpec(**raw_field))
            raw_item["fields"] = tuple(fields)
            raw_item["warnings"] = tuple(raw_item.get("warnings", ()))
            archetypes[spec] = ArchetypeSpec(**raw_item)
        return cls(
            archetypes=archetypes,
            executable=data.get("executable"),
            cyclus_version=data.get("cyclus_version"),
            executable_mtime_ns=data.get("executable_mtime_ns"),
            discovery_warnings=tuple(data.get("discovery_warnings", ())),
            format_version=data["format_version"],
        )

    def save(self, path: Path | None = None) -> Path:
        target = path or cache_file()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(f"{target.suffix}.tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> Catalog:
        target = path or cache_file()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise DiscoveryError(
                "No Cypher discovery cache was found. Run 'cypher discover' in "
                "the environment containing Cyclus."
            ) from error
        except (OSError, json.JSONDecodeError) as error:
            raise DiscoveryError(
                f"Could not read Cypher discovery cache {target}: {error}"
            ) from error
        if not isinstance(data, dict):
            raise DiscoveryError(f"Invalid Cypher discovery cache {target}.")
        return cls.from_dict(data)

    def stale_reason(self) -> str | None:
        if not self.executable:
            return None
        executable = Path(self.executable)
        if not executable.exists():
            return f"selected Cyclus executable no longer exists: {executable}"
        if self.executable_mtime_ns is None:
            return None
        if executable.stat().st_mtime_ns != self.executable_mtime_ns:
            return f"selected Cyclus executable has changed: {executable}"
        return None


def split_spec(spec: str) -> tuple[str, str, str]:
    """Split Cyclus's ``path:library:name`` archetype notation."""

    parts = spec.rsplit(":", 2)
    if len(parts) != 3 or not parts[1] or not parts[2]:
        raise DiscoveryError(
            f"Invalid Cyclus archetype spec {spec!r}; expected path:library:name."
        )
    return parts[0], parts[1], parts[2]


def cache_root() -> Path:
    override = os.environ.get("CYPHER_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return base / "cypher"
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "cypher"


def cache_file() -> Path:
    return cache_root() / "catalog.json"


_active_catalog: Catalog | None = None


def set_catalog(catalog: Catalog | None) -> None:
    """Set the catalogue used by dynamic library imports in this process."""

    global _active_catalog
    _active_catalog = catalog


def get_catalog(*, required: bool = True) -> Catalog | None:
    """Return the active or cached catalogue."""

    global _active_catalog
    if _active_catalog is None:
        try:
            _active_catalog = Catalog.load()
        except DiscoveryError:
            if required:
                raise
            return None
    return _active_catalog


def _normalize_fields(
    annotation: dict[str, Any], schema: str
) -> tuple[list[FieldSpec], list[str]]:
    warnings: list[str] = []
    try:
        root = ET.fromstring(
            f'<grammar xmlns="{RNG_NAMESPACE}" '
            f'xmlns:a="http://relaxng.org/ns/annotation/1.0">'
            f"{schema}</grammar>"
        )
    except ET.ParseError as error:
        return [], [f"archetype schema is not parseable XML: {error}"]

    elements = _top_level_elements(root)
    variables = annotation.get("vars", {})
    if not isinstance(variables, dict):
        return [], ["annotations 'vars' entry is not an object"]

    fields: list[FieldSpec] = []
    for name, (element, required) in elements.items():
        raw = variables.get(name)
        if not isinstance(raw, dict):
            warnings.append(
                f"schema input field {name!r} has no corresponding annotation"
            )
            raw = {}
        cpp_type = raw.get("type", _schema_type(element))
        alias = raw.get("alias", name)
        value_range = raw.get("range")
        normalized_range = None
        if (
            isinstance(value_range, list)
            and len(value_range) == 2
            and all(isinstance(value, (int, float)) for value in value_range)
        ):
            normalized_range = (float(value_range[0]), float(value_range[1]))
        elif value_range is not None:
            warnings.append(f"field {name!r} has an unsupported range annotation")
        fields.append(
            FieldSpec(
                name=name,
                alias=alias,
                cpp_type=cpp_type,
                required=required,
                default=raw.get("default"),
                has_default="default" in raw,
                doc=str(raw.get("doc", "")).strip(),
                uitype=raw.get("uitype"),
                value_range=normalized_range,
            )
        )

    supported = {
        "grammar",
        "interleave",
        "optional",
        "element",
        "data",
        "text",
        "oneOrMore",
        "zeroOrMore",
        "documentation",
        "param",
    }
    unsupported = sorted(
        {
            _local_name(node.tag)
            for node in root.iter()
            if _local_name(node.tag) not in supported
        }
    )
    if unsupported:
        warnings.append(
            "schema uses constructs not yet interpreted by Cypher: "
            + ", ".join(unsupported)
        )
    return fields, warnings


def _top_level_elements(
    root: ET.Element,
) -> dict[str, tuple[ET.Element, bool]]:
    result: dict[str, tuple[ET.Element, bool]] = {}

    def visit(node: ET.Element, *, optional: bool, inside_element: bool) -> None:
        local = _local_name(node.tag)
        now_optional = optional or local in {"optional", "zeroOrMore"}
        if local == "element":
            name = node.get("name")
            if name and not inside_element:
                result[name] = (node, not now_optional)
            inside_element = True
        for child in node:
            visit(child, optional=now_optional, inside_element=inside_element)

    visit(root, optional=False, inside_element=False)
    return result


def _schema_type(element: ET.Element) -> str | list[str]:
    repeated = element.find(f".//{RNG}oneOrMore") is not None
    data = element.find(f".//{RNG}data")
    type_name = data.get("type", "string") if data is not None else "string"
    mapped = {
        "boolean": "bool",
        "double": "double",
        "float": "double",
        "int": "int",
        "integer": "int",
        "nonNegativeInteger": "int",
        "positiveInteger": "int",
        "string": "std::string",
        "token": "std::string",
    }.get(type_name, "std::string")
    return ["std::vector", mapped] if repeated else mapped


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
