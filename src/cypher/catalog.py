"""Normalized metadata describing archetype libraries and fields."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .errors import DiscoveryError
from .shapes import ValueShape, alias_problem

RNG_NAMESPACE = "http://relaxng.org/ns/structure/1.0"
RNG = f"{{{RNG_NAMESPACE}}}"


@dataclass(frozen=True)
class ControlField:
    """One supported scalar field in Cyclus's simulation control block."""

    name: str
    xml_name: str
    required: bool = False
    kind: str = "string"
    minimum: int | float | None = None
    maximum: int | float | None = None
    choices: tuple[str, ...] = ()
    doc: str = ""

    @property
    def python_type(self) -> type[Any]:
        return {"bool": bool, "float": float, "int": int, "string": str}[self.kind]


# These policies retain the small amount of Python ergonomics and semantic
# validation that Relax NG alone cannot express.  Other scalar fields come
# directly from the selected Cyclus control grammar.
_CONTROL_ALIASES = {"startyear": "start_year", "startmonth": "start_month"}
_CONTROL_POLICIES: dict[str, dict[str, Any]] = {
    "duration": {"minimum": 0},
    "startyear": {"minimum": 0},
    "startmonth": {"minimum": 1, "maximum": 12},
    "decay": {"choices": ("never", "manual", "lazy")},
    "dt": {"minimum": 0},
    "seed": {"minimum": 1},
    "stride": {"minimum": 1},
}


DEFAULT_CONTROL_FIELDS: tuple[ControlField, ...] = (
    ControlField("simhandle", "simhandle"),
    ControlField("duration", "duration", required=True, kind="int", minimum=0),
    ControlField("start_year", "startyear", required=True, kind="int", minimum=0),
    ControlField(
        "start_month", "startmonth", required=True, kind="int", minimum=1, maximum=12
    ),
    ControlField("decay", "decay", choices=("never", "manual", "lazy")),
    ControlField("dt", "dt", kind="int", minimum=0),
    ControlField("explicit_inventory", "explicit_inventory", kind="bool"),
    ControlField(
        "explicit_inventory_compact", "explicit_inventory_compact", kind="bool"
    ),
    ControlField("tolerance_generic", "tolerance_generic", kind="float"),
    ControlField("tolerance_resource", "tolerance_resource", kind="float"),
    ControlField("seed", "seed", kind="int", minimum=1),
    ControlField("stride", "stride", kind="int", minimum=1),
)


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
        """Return the coarse outer Python runtime type for compatibility."""

        shape = self.value_shape
        containers = {
            "vector": list,
            "list": list,
            "set": set,
            "pair": tuple,
            "map": dict,
        }
        if shape.kind in containers:
            return containers[shape.kind]
        annotation = shape.annotation()
        return annotation if isinstance(annotation, type) else object

    @property
    def value_shape(self) -> ValueShape:
        return ValueShape.from_cpp_type(self.cpp_type)


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
    base_schema_path: str | None = None
    full_schema_path: str | None = None
    control_fields: tuple[ControlField, ...] = DEFAULT_CONTROL_FIELDS
    discovery_warnings: tuple[str, ...] = ()
    format_version: int = 3
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
        base_schema_path: str | None = None,
        full_schema_path: str | None = None,
        control_fields: tuple[ControlField, ...] = DEFAULT_CONTROL_FIELDS,
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
            base_schema_path=base_schema_path,
            full_schema_path=full_schema_path,
            control_fields=control_fields,
            discovery_warnings=discovery_warnings,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "executable": self.executable,
            "cyclus_version": self.cyclus_version,
            "executable_mtime_ns": self.executable_mtime_ns,
            "base_schema_path": self.base_schema_path,
            "full_schema_path": self.full_schema_path,
            "control_fields": [asdict(item) for item in self.control_fields],
            "discovery_warnings": list(self.discovery_warnings),
            "archetypes": {
                spec: asdict(archetype) for spec, archetype in self.archetypes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Catalog:
        format_version = data.get("format_version")
        if format_version not in {1, 2, 3}:
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
        raw_control_fields = data.get("control_fields")
        if raw_control_fields is None:
            control_fields = DEFAULT_CONTROL_FIELDS
        elif not isinstance(raw_control_fields, list):
            raise DiscoveryError("Cypher discovery cache has invalid control fields.")
        else:
            try:
                control_fields = tuple(
                    ControlField(
                        **{
                            **dict(item),
                            "choices": tuple(dict(item).get("choices", ())),
                        }
                    )
                    for item in raw_control_fields
                )
            except (TypeError, ValueError) as error:
                raise DiscoveryError(
                    "Cypher discovery cache has invalid control field metadata."
                ) from error
        return cls(
            archetypes=archetypes,
            executable=data.get("executable"),
            cyclus_version=data.get("cyclus_version"),
            executable_mtime_ns=data.get("executable_mtime_ns"),
            base_schema_path=data.get("base_schema_path"),
            full_schema_path=data.get("full_schema_path"),
            control_fields=control_fields,
            discovery_warnings=tuple(data.get("discovery_warnings", ())),
            format_version=3,
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


def control_fields_from_schema(
    schema: str,
) -> tuple[tuple[ControlField, ...], tuple[str, ...]]:
    """Normalize the conservative scalar subset of a Cyclus control grammar.

    Complex control content is intentionally reported rather than guessed.  The
    returned field order is the grammar's source order, used as Cypher's stable
    XML order even though Relax NG ``interleave`` is unordered semantically.
    """

    try:
        root = ET.fromstring(schema)
    except ET.ParseError as error:
        return (), (f"Could not parse the Cyclus base control grammar: {error}",)
    control = next(
        (
            element
            for element in root.iter(RNG + "element")
            if element.get("name") == "control"
        ),
        None,
    )
    if control is None:
        return (), ("Cyclus base grammar does not define a control block.",)
    container = next(
        (child for child in control if child.tag == RNG + "interleave"), None
    )
    if container is None:
        return (), ("Cyclus control grammar has no supported interleave block.",)

    fields: list[ControlField] = []
    warnings: list[str] = []
    for child in container:
        required = child.tag != RNG + "optional"
        element = child if required else next(
            (item for item in child if item.tag == RNG + "element"), None
        )
        if element is None or element.tag != RNG + "element":
            warnings.append("Cyclus control grammar contains an unsupported construct.")
            continue
        xml_name = element.get("name")
        if not xml_name:
            warnings.append("Cyclus control grammar contains an unnamed control field.")
            continue
        scalar = next(
            (item for item in element if item.tag in {RNG + "data", RNG + "text"}),
            None,
        )
        if scalar is None or any(
            item is not scalar and not item.tag.endswith("documentation")
            for item in element
        ):
            warnings.append(
                f"control field {xml_name!r} uses an unsupported non-scalar structure"
            )
            continue
        kind = _control_scalar_kind(scalar)
        if kind is None:
            warnings.append(
                f"control field {xml_name!r} uses unsupported scalar type "
                f"{scalar.get('type', 'text')!r}"
            )
            continue
        policy = _CONTROL_POLICIES.get(xml_name, {})
        fields.append(
            ControlField(
                name=_CONTROL_ALIASES.get(xml_name, xml_name),
                xml_name=xml_name,
                required=required,
                kind=kind,
                minimum=policy.get("minimum"),
                maximum=policy.get("maximum"),
                choices=policy.get("choices", ()),
                doc=_rng_documentation(element),
            )
        )
    return tuple(fields), tuple(warnings)


def _control_scalar_kind(element: ET.Element) -> str | None:
    if element.tag == RNG + "text":
        return "string"
    kinds = {
        "boolean": "bool",
        "decimal": "float",
        "double": "float",
        "float": "float",
        "integer": "int",
        "nonNegativeInteger": "int",
        "positiveInteger": "int",
        "string": "string",
    }
    return kinds.get(element.get("type", "string"))


def _rng_documentation(element: ET.Element) -> str:
    return " ".join(
        " ".join(item.itertext()).strip()
        for item in element
        if item.tag.endswith("documentation")
    ).strip()


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
        if isinstance(raw, str):
            target = raw
            raw = variables.get(target)
            if not isinstance(raw, dict):
                warnings.append(
                    f"schema input field {name!r} refers to missing annotation "
                    f"variable {target!r}"
                )
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
        value_shape = ValueShape.from_cpp_type(cpp_type)
        if not value_shape.supported:
            warnings.append(
                f"field {name!r} uses unsupported C++ input type {cpp_type!r}"
            )
        elif problem := alias_problem(value_shape, alias):
            warnings.append(f"field {name!r} has incompatible XML alias: {problem}")

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
