"""Deterministic hierarchical Cyclus XML serialization."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .archetype import Prototype
from .core import Commodity, Recipe, Simulation


def simulation_xml(simulation: Simulation) -> str:
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
    return ET.tostring(root, encoding="unicode", short_empty_elements=True) + "\n"


def export_xml(simulation: Simulation, path: Path) -> Path:
    """Atomically write validated simulation XML."""

    content = simulation.to_xml()
    target = path.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
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
    _text(element, "duration", simulation.control.duration)
    _text(element, "startmonth", simulation.control.start_month)
    _text(element, "startyear", simulation.control.start_year)


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
