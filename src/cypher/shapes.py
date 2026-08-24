"""Recursive value shapes for discovered Cyclus configuration fields."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from typing import Any

_INTEGER_TYPES = {"int", "long", "long int", "unsigned int"}
_FLOAT_TYPES = {"double", "float"}
_STRING_TYPES = {"std::string", "string"}


@dataclass(frozen=True)
class ValueShape:
    """A recursive, language-neutral description of one field value."""

    kind: str
    cpp_type: str
    children: tuple[ValueShape, ...] = ()

    @classmethod
    def from_cpp_type(cls, value: str | list[Any]) -> ValueShape:
        if isinstance(value, str):
            if value in _INTEGER_TYPES:
                return cls("int", value)
            if value in _FLOAT_TYPES:
                return cls("float", value)
            if value == "bool":
                return cls("bool", value)
            if value in _STRING_TYPES:
                return cls("string", value)
            return cls("unsupported", value)
        if not value or not isinstance(value[0], str):
            return cls("unsupported", repr(value))
        container = value[0]
        arities = {
            "std::vector": 1,
            "std::list": 1,
            "std::set": 1,
            "std::pair": 2,
            "std::map": 2,
        }
        kind = {
            "std::vector": "vector",
            "std::list": "list",
            "std::set": "set",
            "std::pair": "pair",
            "std::map": "map",
        }.get(container)
        if kind is None or len(value) != arities.get(container, -1) + 1:
            return cls("unsupported", repr(value))
        return cls(
            kind,
            container,
            tuple(cls.from_cpp_type(child) for child in value[1:]),
        )

    @property
    def supported(self) -> bool:
        return self.kind != "unsupported" and all(
            child.supported for child in self.children
        )

    def annotation(self) -> Any:
        """Return a runtime annotation suitable for generated signatures."""

        if self.kind == "int":
            return int
        if self.kind == "float":
            return float
        if self.kind == "bool":
            return bool
        if self.kind == "string":
            return str
        if self.kind in {"vector", "list"}:
            return list[self.children[0].annotation()]
        if self.kind == "set":
            child = self.children[0].annotation()
            return set[child] | Sequence[child]
        if self.kind == "pair":
            return tuple[
                self.children[0].annotation(), self.children[1].annotation()
            ]
        if self.kind == "map":
            key = self.children[0].annotation()
            item = self.children[1].annotation()
            return Mapping[key, item] | Sequence[tuple[key, item]]
        return Any

    def type_expression(self) -> str:
        """Return an evaluable-looking Python type expression for help and stubs."""

        scalar = {
            "int": "int",
            "float": "float",
            "bool": "bool",
            "string": "str",
            "unsupported": "Any",
        }
        if self.kind in scalar:
            return scalar[self.kind]
        if self.kind in {"vector", "list"}:
            return f"list[{self.children[0].type_expression()}]"
        if self.kind == "set":
            child = self.children[0].type_expression()
            return f"set[{child}] | Sequence[{child}]"
        if self.kind == "pair":
            first, second = self.children
            return f"tuple[{first.type_expression()}, {second.type_expression()}]"
        if self.kind == "map":
            key, item = self.children
            key_type = key.type_expression()
            item_type = item.type_expression()
            return (
                f"Mapping[{key_type}, {item_type}] | "
                f"Sequence[tuple[{key_type}, {item_type}]]"
            )
        return "Any"

    def example(self, uitype: Any = None, *, alias: Any) -> Any:
        """Build a small valid-shaped example using ordinary Python values."""

        semantic, child_ui = split_uitype(uitype, len(self.children))
        if self.kind == "string":
            if semantic in {"incommodity", "outcommodity", "commodity"}:
                return "commodity"
            if semantic in {"inrecipe", "outrecipe", "recipe"}:
                return "recipe"
            return "value"
        if self.kind == "int":
            return 922350000 if semantic == "nuclide" else 1
        if self.kind == "float":
            return 1.0
        if self.kind == "bool":
            return True
        if self.kind in {"vector", "list", "set"}:
            return [
                self.children[0].example(child_ui[0], alias=alias[1])
            ]
        if self.kind == "pair":
            return tuple(
                child.example(ui, alias=alias[index + 1])
                for index, (child, ui) in enumerate(
                    zip(self.children, child_ui, strict=True)
                )
            )
        if self.kind == "map":
            key = self.children[0].example(child_ui[0], alias=alias[1])
            item = self.children[1].example(child_ui[1], alias=alias[2])
            try:
                return {key: item}
            except TypeError:
                return [(key, item)]
        return None

    def example_format(self, alias: Any) -> str:
        """Return a compact Python-shaped template labeled with XML aliases."""

        if self.kind in {"int", "float", "bool", "string"}:
            return f"<{alias}>"
        if self.kind in {"vector", "list", "set"}:
            return f"[{self.children[0].example_format(alias[1])}]"
        if self.kind == "pair":
            first = self.children[0].example_format(alias[1])
            second = self.children[1].example_format(alias[2])
            return f"({first}, {second})"
        if self.kind == "map":
            key = self.children[0].example_format(alias[1])
            item = self.children[1].example_format(alias[2])
            return f"{{{key}: {item}}}"
        return "<value>"


def split_uitype(uitype: Any, child_count: int) -> tuple[str | None, list[Any]]:
    """Split a metadata UI-type node into its marker and child nodes."""

    if not isinstance(uitype, list):
        return (uitype if isinstance(uitype, str) else None), [None] * child_count
    marker = uitype[0] if uitype and isinstance(uitype[0], str) else None
    children = list(uitype[1 : 1 + child_count])
    children.extend([None] * (child_count - len(children)))
    return marker, children


def map_items(value: Any) -> list[tuple[Any, Any]] | None:
    """Return map entries from a mapping or a sequence of two-item pairs."""

    if isinstance(value, Mapping):
        return list(value.items())
    if not is_sequence(value):
        return None
    entries = []
    for item in value:
        if not is_sequence(item) or len(item) != 2:
            return None
        entries.append((item[0], item[1]))
    return entries


def is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def sequence_items(value: Any, *, allow_set: bool = False) -> list[Any] | None:
    """Return deterministic items for a sequence-like C++ container."""

    if is_sequence(value):
        return list(value)
    if allow_set and isinstance(value, Set):
        return sorted(value, key=repr)
    return None


def alias_problem(shape: ValueShape, alias: Any, *, path: str = "alias") -> str | None:
    """Explain the first mismatch between a C++ value shape and an XML alias."""

    if shape.kind in {"int", "float", "bool", "string"}:
        return None if isinstance(alias, str) else f"{path} must be an element name"
    if shape.kind == "unsupported":
        return None
    expected = 2 if shape.kind in {"vector", "list", "set"} else 3
    if not isinstance(alias, list) or len(alias) != expected:
        return f"{path} must contain {expected} parts for {shape.cpp_type}"
    if shape.kind in {"vector", "list", "set", "pair"} and not isinstance(
        alias[0], str
    ):
        return f"{path}[0] must be a wrapper element name"
    if shape.kind == "map":
        entry_alias = alias[0]
        valid_entry = isinstance(entry_alias, str) or (
            isinstance(entry_alias, list)
            and len(entry_alias) == 2
            and all(isinstance(item, str) for item in entry_alias)
        )
        if not valid_entry:
            return f"{path}[0] must name a map entry or [wrapper, entry]"
    for index, child in enumerate(shape.children):
        child_index = index + 1
        problem = alias_problem(
            child, alias[child_index], path=f"{path}[{child_index}]"
        )
        if problem:
            return problem
    return None
