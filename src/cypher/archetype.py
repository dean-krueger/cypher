"""Runtime archetype classes generated from normalized metadata."""

from __future__ import annotations

import inspect
import textwrap
from collections.abc import Iterator
from typing import Any

from .catalog import ArchetypeSpec, FieldSpec

UNSET = object()


class Prototype:
    """A named configuration of a discovered Cyclus archetype."""

    _archetype: ArchetypeSpec

    def __init__(self, name: str | None = None, **configuration: Any) -> None:
        object.__setattr__(self, "_values", {})
        object.__setattr__(self, "_explicit", set())
        object.__setattr__(self, "_children", [])
        object.__setattr__(self, "_initial_facilities", [])
        self.name = name
        unknown = sorted(set(configuration) - {field.name for field in self.fields})
        if unknown:
            available = ", ".join(field.name for field in self.fields) or "none"
            raise TypeError(
                f"{type(self).__name__} got unknown field(s): {', '.join(unknown)}. "
                f"Available fields: {available}."
            )
        for field_name, value in configuration.items():
            setattr(self, field_name, value)

    @property
    def fields(self) -> tuple[FieldSpec, ...]:
        return self._archetype.fields

    @property
    def entity(self) -> str:
        return self._archetype.entity

    @property
    def library(self) -> str:
        return self._archetype.library

    def __getattr__(self, name: str) -> Any:
        field = self._archetype.field(name)
        if field is None:
            raise AttributeError(name)
        if name in self._values:
            return self._values[name]
        if field.has_default:
            return field.default
        return None

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or name == "name":
            object.__setattr__(self, name, value)
            return
        field = self._archetype.field(name)
        if field is None:
            raise AttributeError(
                f"{type(self).__name__} has no configuration field {name!r}."
            )
        _validate_field_value(self, field, value)
        self._values[name] = value
        self._explicit.add(name)

    def is_set(self, name: str) -> bool:
        """Return whether a field was explicitly assigned."""

        return name in self._explicit

    def explicit_items(self) -> Iterator[tuple[FieldSpec, Any]]:
        for field in self.fields:
            if field.name in self._explicit:
                yield field, self._values[field.name]

    def add(self, *children: Prototype) -> Prototype:
        """Nest institutions below a region."""

        if self.entity != "region":
            raise TypeError(
                f"Only region archetypes can contain institutions, not {self}."
            )
        for child in children:
            if not isinstance(child, Prototype) or child.entity != "institution":
                raise TypeError("Regions may only contain institution archetypes.")
            if child not in self._children:
                self._children.append(child)
        return self

    @property
    def children(self) -> tuple[Prototype, ...]:
        return tuple(self._children)

    def add_initial_facility(
        self, prototype: Prototype | str, *, count: int = 1
    ) -> Prototype:
        """Add initially deployed facilities to an institution."""

        if self.entity != "institution":
            raise TypeError(
                f"Only institution archetypes can deploy facilities, not {self}."
            )
        if isinstance(prototype, Prototype) and prototype.entity != "facility":
            raise TypeError(
                "Initial facility references must target facility prototypes."
            )
        if not isinstance(prototype, (Prototype, str)):
            raise TypeError(
                "Initial facility must be a prototype object or name string."
            )
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("Initial facility count must be a positive integer.")
        entry = (prototype, count)
        if entry not in self._initial_facilities:
            self._initial_facilities.append(entry)
        return self

    @property
    def initial_facilities(self) -> tuple[tuple[Prototype | str, int], ...]:
        return tuple(self._initial_facilities)

    def validation_problems(self) -> list[str]:
        label = f"{self.library}:{self._archetype.name} {self.name!r}"
        problems = []
        if not self.name:
            problems.append(f"{label} is missing its prototype/agent name")
        for field in self.fields:
            if field.required and not self.is_set(field.name):
                problems.append(f"{label} is missing required field {field.name!r}")
        # Compatibility warnings are reported by discovery and strict mode.
        return problems

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"


def make_archetype_class(
    archetype: ArchetypeSpec, *, module_name: str
) -> type[Prototype]:
    """Create one inspectable Python class from an archetype specification."""

    parameters = [
        inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=None,
            annotation=str | None,
        )
    ]
    annotations: dict[str, Any] = {"name": str | None}
    ordered_fields = sorted(archetype.fields, key=lambda field: not field.required)
    for field in ordered_fields:
        annotation = _annotation(field)
        annotations[field.name] = annotation
        if field.required:
            default = inspect.Parameter.empty
        elif field.has_default:
            default = field.default
        else:
            default = None
        parameters.append(
            inspect.Parameter(
                field.name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
        )
    namespace = {
        "_archetype": archetype,
        "__module__": module_name,
        "__doc__": _class_doc(archetype),
        "__annotations__": annotations,
        "__signature__": inspect.Signature(parameters),
    }
    return type(archetype.name, (Prototype,), namespace)


def _annotation(field: FieldSpec) -> Any:
    python_type = field.python_type
    if python_type is list:
        return list[Any]
    return python_type


def _class_doc(archetype: ArchetypeSpec) -> str:
    required = [field for field in archetype.fields if field.required]
    optional = [field for field in archetype.fields if not field.required]
    required_names = ", ".join(field.name for field in required) or "none"
    optional_names = ", ".join(field.name for field in optional) or "none"
    lines = [
        f"Required: {required_names}",
        f"Optional: {optional_names}",
        "",
        "Description:",
        textwrap.indent(archetype.doc or f"Cyclus archetype {archetype.spec}.", "    "),
        "",
        "Required fields:",
    ]
    if not required:
        lines.append("    None.")
    for field in required:
        lines.append(
            f"    {field.name}: {field.doc or 'No field documentation supplied.'}"
        )
    lines.extend(["", "Optional fields:"])
    if not optional:
        lines.append("    None.")
    for field in optional:
        default = f" (default: {field.default!r})" if field.has_default else ""
        lines.append(
            f"    {field.name}{default}: "
            f"{field.doc or 'No field documentation supplied.'}"
        )
    if archetype.warnings:
        lines.extend(["", "Compatibility warnings:"])
        lines.extend(f"    - {warning}" for warning in archetype.warnings)
    return "\n".join(lines)


def _validate_field_value(owner: Prototype, field: FieldSpec, value: Any) -> None:
    from .core import Commodity, Recipe

    expected = field.python_type
    reference_type = _reference_type(field.uitype)
    if reference_type == "commodity" and isinstance(value, Commodity):
        pass
    elif reference_type == "recipe" and isinstance(value, Recipe):
        pass
    elif expected is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{owner}.{field.name} must be a number.")
    elif expected is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{owner}.{field.name} must be an integer.")
    elif expected is bool:
        if not isinstance(value, bool):
            raise TypeError(f"{owner}.{field.name} must be a boolean.")
    elif expected is str:
        if not isinstance(value, str):
            raise TypeError(f"{owner}.{field.name} must be a string.")
    elif expected is list:
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"{owner}.{field.name} must be a list or tuple.")
    if (
        field.value_range
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        minimum, maximum = field.value_range
        if not minimum <= value <= maximum:
            raise ValueError(
                f"{owner}.{field.name} must be between {minimum} and {maximum}; "
                f"got {value}."
            )


def _reference_type(uitype: str | list[Any] | None) -> str | None:
    values = uitype if isinstance(uitype, list) else [uitype]
    if any(value in {"incommodity", "outcommodity", "commodity"} for value in values):
        return "commodity"
    if "recipe" in values:
        return "recipe"
    return None
