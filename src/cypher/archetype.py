"""Runtime archetype classes generated from normalized metadata."""

from __future__ import annotations

import inspect
import textwrap
from collections.abc import Iterator
from typing import Any

from .catalog import ArchetypeSpec, FieldSpec
from .shapes import (
    ValueShape,
    alias_problem,
    map_items,
    sequence_items,
    split_uitype,
)


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

    @classmethod
    def field_example(cls, name: str) -> str:
        """Describe aliases and show a small Python value for a field."""

        return _field_example_text(_class_field(cls, name))

    @classmethod
    def field_example_value(cls, name: str) -> Any:
        """Return the ordinary Python value used in a field's example."""

        field = _class_field(cls, name)
        _ensure_example_supported(field)
        return field.value_shape.example(field.uitype, alias=field.alias)

    @classmethod
    def describe_field(cls, name: str) -> str:
        """Describe a field's accepted Python shape and show an example."""

        field = _class_field(cls, name)
        required = "required" if field.required else "optional"
        return "\n".join(
            [
                f"{cls.__name__}.{field.name} ({required})",
                cls.field_example(name),
                field.doc or "No field documentation supplied.",
            ]
        )

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
        for field, value in self.explicit_items():
            try:
                _validate_field_value(self, field, value)
            except (TypeError, ValueError) as error:
                problems.append(str(error))
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
    return field.value_shape.annotation()


def _class_field(cls: type[Prototype], name: str) -> FieldSpec:
    field = cls._archetype.field(name)
    if field is not None:
        return field
    available = ", ".join(item.name for item in cls._archetype.fields) or "none"
    raise KeyError(
        f"{cls.__name__} has no field {name!r}. Available fields: {available}."
    )


def _ensure_example_supported(field: FieldSpec) -> None:
    shape = field.value_shape
    if not shape.supported:
        raise TypeError(
            f"Field {field.name!r} uses unsupported C++ type {field.cpp_type!r}."
        )
    if problem := alias_problem(shape, field.alias):
        raise TypeError(
            f"Field {field.name!r} has an incompatible XML alias: {problem}."
        )


def _field_example_text(field: FieldSpec) -> str:
    _ensure_example_supported(field)
    shape = field.value_shape
    value = shape.example(field.uitype, alias=field.alias)
    return "\n".join(
        [
            f"Example format: {shape.example_format(field.alias)}",
            f"Example value:  {value!r}",
        ]
    )


def _field_help_lines(field: FieldSpec) -> list[str]:
    shape = field.value_shape
    if not shape.children:
        return [f"        Python type: {shape.type_expression()}"]
    if not shape.supported or alias_problem(shape, field.alias):
        return ["        Example unavailable; see compatibility warnings below."]
    return [f"        {line}" for line in _field_example_text(field).splitlines()]


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
        lines.extend(_field_help_lines(field))
    lines.extend(["", "Optional fields:"])
    if not optional:
        lines.append("    None.")
    for field in optional:
        default = f" (default: {field.default!r})" if field.has_default else ""
        lines.append(
            f"    {field.name}{default}: "
            f"{field.doc or 'No field documentation supplied.'}"
        )
        lines.extend(_field_help_lines(field))
    if archetype.warnings:
        lines.extend(["", "Compatibility warnings:"])
        lines.extend(f"    - {warning}" for warning in archetype.warnings)
    return "\n".join(lines)


def _validate_field_value(owner: Prototype, field: FieldSpec, value: Any) -> None:
    path = f"{owner}.{field.name}"
    _validate_shape_value(field.value_shape, value, field.uitype, path)
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


def _validate_shape_value(
    shape: ValueShape, value: Any, uitype: Any, path: str
) -> None:
    from .core import Commodity, Recipe

    semantic, child_ui = split_uitype(uitype, len(shape.children))
    reference_type = _reference_type(semantic)
    if reference_type == "commodity" and isinstance(value, Commodity):
        return
    if reference_type == "recipe" and isinstance(value, Recipe):
        return
    if shape.kind == "unsupported":
        raise TypeError(f"{path} uses unsupported C++ type {shape.cpp_type}.")
    if shape.kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{path} must be a number; got {type(value).__name__}.")
        return
    if shape.kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{path} must be an integer; got {type(value).__name__}.")
        return
    if shape.kind == "bool":
        if not isinstance(value, bool):
            raise TypeError(f"{path} must be a boolean; got {type(value).__name__}.")
        return
    if shape.kind == "string":
        if not isinstance(value, str):
            raise TypeError(f"{path} must be a string; got {type(value).__name__}.")
        return
    if shape.kind in {"vector", "list", "set"}:
        items = sequence_items(value, allow_set=shape.kind == "set")
        if items is None:
            expected = (
                "a set or non-string sequence"
                if shape.kind == "set"
                else "a non-string sequence"
            )
            raise TypeError(f"{path} must be {expected}.")
        for index, item in enumerate(items):
            _validate_shape_value(
                shape.children[0], item, child_ui[0], f"{path}[{index}]"
            )
        return
    if shape.kind == "pair":
        if not isinstance(value, tuple) or len(value) != 2:
            raise TypeError(f"{path} must be a two-item tuple.")
        for index, (child, item, ui) in enumerate(
            zip(shape.children, value, child_ui, strict=True)
        ):
            _validate_shape_value(child, item, ui, f"{path}[{index}]")
        return
    if shape.kind == "map":
        entries = map_items(value)
        if entries is None:
            raise TypeError(
                f"{path} must be a mapping or a sequence of two-item pairs."
            )
        for index, (key, item) in enumerate(entries):
            rendered_key = _safe_repr(key)
            if _has_earlier_equal_key(entries, index, key):
                raise ValueError(f"{path} contains duplicate map key {rendered_key}.")
            key_path = f"{path}[{rendered_key}] (key)"
            _validate_shape_value(shape.children[0], key, child_ui[0], key_path)
            _validate_shape_value(
                shape.children[1], item, child_ui[1], f"{path}[{rendered_key}]"
            )


def _has_earlier_equal_key(
    entries: list[tuple[Any, Any]], index: int, key: Any
) -> bool:
    for previous, _value in entries[:index]:
        if previous is key or previous == key:
            return True
    return False


def _safe_repr(value: Any) -> str:
    try:
        return repr(value)
    except Exception:
        return f"<{type(value).__name__}>"


def _reference_type(uitype: str | list[Any] | None) -> str | None:
    values = uitype if isinstance(uitype, list) else [uitype]
    if any(value in {"incommodity", "outcommodity", "commodity"} for value in values):
        return "commodity"
    if any(value in {"inrecipe", "outrecipe", "recipe"} for value in values):
        return "recipe"
    return None
