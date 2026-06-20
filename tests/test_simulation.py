from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import cypher
from cypher.errors import ValidationError


def bakery(catalog) -> cypher.Simulation:
    agents = importlib.import_module("cypher.agents")
    cycamore = importlib.import_module("cypher.cycamore")
    simulation = cypher.Simulation(
        control=cypher.Control(duration=10, start_year=2000, start_month=1),
        catalog=catalog,
    )
    simulation.add_library("agents")
    simulation.add_library("cycamore")
    toast = cypher.Commodity("Toast")
    recipe = cypher.Recipe("Toast", basis="atom", composition={10030000: 1.0})
    source = cycamore.Source("Bakery", outcommod=toast, throughput=8334)
    sink = cycamore.Sink("Bread Store", in_commods=[toast], capacity=1000)
    institution = agents.NullInst("OneInst")
    institution.add_initial_facility(source)
    institution.add_initial_facility(sink)
    region = agents.NullRegion("OneRegion")
    region.add(institution)
    simulation.add(recipe)
    simulation.add(region)
    return simulation


def test_bakery_matches_golden_xml(catalog) -> None:
    expected = (Path(__file__).parent / "fixtures" / "bakery.xml").read_text(
        encoding="utf-8"
    )

    assert bakery(catalog).to_xml() == expected


def test_export_is_deterministic_and_atomic(catalog, tmp_path: Path) -> None:
    simulation = bakery(catalog)
    path = tmp_path / "bakery.xml"

    simulation.export_to_xml(path)
    first = path.read_bytes()
    simulation.export_to_xml(path)

    assert path.read_bytes() == first
    assert not list(tmp_path.glob("*.tmp"))


def test_nested_objects_are_collected_recursively(catalog) -> None:
    simulation = bakery(catalog)
    graph = simulation.graph()

    assert [item.name for item in graph.facilities] == ["Bakery", "Bread Store"]
    assert [item.name for item in graph.institutions] == ["OneInst"]
    assert [item.name for item in graph.regions] == ["OneRegion"]
    assert [item.name for item in graph.commodities] == ["Toast"]


def test_commodity_block_only_exists_with_priority(catalog) -> None:
    simulation = bakery(catalog)
    assert "<commodity>" not in simulation.to_xml()

    simulation.add(cypher.Commodity("electricity", solution_priority=10))

    assert "<solution_priority>10</solution_priority>" in simulation.to_xml()


def test_validation_consolidates_incomplete_objects(catalog) -> None:
    cycamore = importlib.import_module("cypher.cycamore")
    simulation = cypher.Simulation(control=cypher.Control(), catalog=catalog)
    simulation.add(cycamore.Source())

    with pytest.raises(ValidationError) as caught:
        simulation.validate()

    message = str(caught.value)
    assert "duration" in message
    assert "start_year" in message
    assert "outcommod" in message
    assert "prototype/agent name" in message


def test_duplicate_prototype_names_are_rejected(catalog) -> None:
    cycamore = importlib.import_module("cypher.cycamore")
    simulation = cypher.Simulation(
        control=cypher.Control(duration=1, start_year=2000, start_month=1),
        catalog=catalog,
    )
    simulation.add(
        cycamore.Source("Same", outcommod="a"),
        cycamore.Source("Same", outcommod="b"),
    )

    with pytest.raises(ValidationError, match="distinct facility prototype"):
        simulation.validate()


def test_same_object_added_twice_is_idempotent(catalog) -> None:
    cycamore = importlib.import_module("cypher.cycamore")
    source = cycamore.Source("Mine", outcommod="uranium")
    simulation = cypher.Simulation(
        control=cypher.Control(duration=1, start_year=2000, start_month=1),
        catalog=catalog,
    )
    simulation.add(source, source)

    assert simulation.prototypes == (source,)
