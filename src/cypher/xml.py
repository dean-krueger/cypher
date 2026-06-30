"""Deterministic hierarchical Cyclus XML serialization."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .archetype import Prototype
from .core import Commodity, Recipe, Simulation


def simulation_xml(
    simulation: Simulation,
    *,
    schema_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> str:
    """Serialize a validated simulation as readable hierarchical XML."""

    graph = simulation.graph()
    root = ET.Element("simulation")
    _control(root, simulation)
    for commodity in graph.commodities:
        if commodity.solution_priority is not None:
            _commodity(root, commodity)
    _archetypes(root, graph.archetypes)
    for recipe in graph.recipes:
        _recipe(root, recipe)
    for facility in graph.facilities:
        _prototype(root, facility, "facility")
    for region in graph.regions:
        _region(root, region)
    ET.indent(root, space="  ")
    content = ET.tostring(root, encoding="unicode", short_empty_elements=True) + "\n"
    if schema_path is not None:
        content = _schema_processing_instruction(schema_path, output_path) + content
    return content


def export_xml(
    simulation: Simulation,
    path: Path,
    *,
    schema_path: str | Path | None = None,
) -> Path:
    """Atomically write validated simulation XML."""

    target = path.expanduser()
    content = simulation.to_xml(schema_path=schema_path, output_path=target)
    target.parent.mkdir(parents=True, exist_ok=True)
    permissions = None
    if os.name == "posix":
        permissions = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        if permissions is not None:
            os.chmod(temporary_name, permissions)
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return target


def _control(root: ET.Element, simulation: Simulation) -> None:
    assert simulation.control is not None
    element = ET.SubElement(root, "control")
    for field, value in simulation.control.explicit_items():
        _text(element, field.xml_name, value)


def _commodity(root: ET.Element, commodity: Commodity) -> None:
    element = ET.SubElement(root, "commodity")
    _text(element, "name", commodity.name)
    _text(element, "solution_priority", commodity.solution_priority)


def _archetypes(root: ET.Element, archetypes: tuple[object, ...]) -> None:
    element = ET.SubElement(root, "archetypes")
    for archetype in archetypes:
        spec = ET.SubElement(element, "spec")
        if archetype.path:
            _text(spec, "path", archetype.path)
        _text(spec, "lib", archetype.library)
        _text(spec, "name", archetype.name)


def _recipe(root: ET.Element, recipe: Recipe) -> None:
    element = ET.SubElement(root, "recipe")
    _text(element, "name", recipe.name)
    _text(element, "basis", recipe.basis)
    for nuclide, fraction in recipe.composition.items():
        nuclide_element = ET.SubElement(element, "nuclide")
        _text(nuclide_element, "id", nuclide)
        _text(nuclide_element, "comp", fraction)


def _prototype(parent: ET.Element, prototype: Prototype, tag: str) -> ET.Element:
    element = ET.SubElement(parent, tag)
    _text(element, "name", prototype.name)
    config = ET.SubElement(element, "config")
    archetype = ET.SubElement(config, prototype._archetype.name)
    for field, value in prototype.explicit_items():
        _field(archetype, field.alias, value)
    return element


def _region(root: ET.Element, region: Prototype) -> None:
    element = _prototype(root, region, "region")
    for institution in region.children:
        _institution(element, institution)


def _institution(parent: ET.Element, institution: Prototype) -> None:
    element = ET.SubElement(parent, "institution")
    _text(element, "name", institution.name)
    if institution.initial_facilities:
        listing = ET.SubElement(element, "initialfacilitylist")
        for target, count in institution.initial_facilities:
            entry = ET.SubElement(listing, "entry")
            _text(
                entry,
                "prototype",
                target.name if isinstance(target, Prototype) else target,
            )
            _text(entry, "number", count)
    config = ET.SubElement(element, "config")
    archetype = ET.SubElement(config, institution._archetype.name)
    for field, value in institution.explicit_items():
        _field(archetype, field.alias, value)


def _field(parent: ET.Element, alias: str | list[Any], value: Any) -> None:
    if isinstance(alias, list):
        if not alias:
            raise ValueError("Cannot serialize an empty field alias.")
        if len(alias) == 1:
            element = ET.SubElement(parent, str(alias[0]))
            element.text = _value_text(value)
            return
        outer = ET.SubElement(parent, str(alias[0]))
        values = value if isinstance(value, (list, tuple)) else [value]
        child_alias = alias[1] if len(alias) == 2 else alias[1:]
        for item in values:
            _field(outer, child_alias, item)
        return
    element = ET.SubElement(parent, alias)
    element.text = _value_text(value)


def _text(parent: ET.Element, name: str, value: Any) -> ET.Element:
    element = ET.SubElement(parent, name)
    element.text = _value_text(value)
    return element


def _value_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (Commodity, Recipe)):
        return value.name
    return str(value)


def _schema_processing_instruction(
    schema_path: str | Path,
    output_path: str | Path | None,
) -> str:
    href = _schema_href(schema_path, output_path)
    return (
        f'<?xml-model href="{_xml_attribute(href)}" type="application/xml" '
        'schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
    )


def _schema_href(schema_path: str | Path, output_path: str | Path | None) -> str:
    schema = Path(schema_path).expanduser()
    if not schema.is_absolute():
        return schema.as_posix()
    if output_path is None:
        return schema.as_posix()
    output = Path(output_path).expanduser()
    if not output.is_absolute():
        output = output.resolve()
    try:
        relative = os.path.relpath(schema, start=output.parent)
    except ValueError:
        return schema.as_posix()
    return Path(relative).as_posix()


def _xml_attribute(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
