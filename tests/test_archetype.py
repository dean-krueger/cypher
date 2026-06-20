from __future__ import annotations

import importlib
import inspect

import pytest

from cypher import Commodity


def test_discovered_library_import_and_signature(catalog) -> None:
    cycamore = importlib.import_module("cypher.cycamore")

    signature = inspect.signature(cycamore.Source)

    assert list(signature.parameters) == ["name", "outcommod", "throughput"]
    assert "Output commodity" in cycamore.Source.__doc__


def test_incremental_configuration_tracks_explicit_defaults(catalog) -> None:
    cycamore = importlib.import_module("cypher.cycamore")
    source = cycamore.Source()

    assert source.throughput == 1.0e299
    assert not source.is_set("throughput")

    source.name = "Mine"
    source.outcommod = Commodity("natural_uranium")
    source.throughput = 1000

    assert source.is_set("outcommod")
    assert source.is_set("throughput")


def test_generated_field_validation(catalog) -> None:
    cycamore = importlib.import_module("cypher.cycamore")

    with pytest.raises(ValueError, match="between"):
        cycamore.Source("Mine", outcommod="uranium", throughput=-1)
    with pytest.raises(TypeError, match="unknown field"):
        cycamore.Source("Mine", made_up=1)


def test_region_and_institution_composition(catalog) -> None:
    agents = importlib.import_module("cypher.agents")
    cycamore = importlib.import_module("cypher.cycamore")
    mine = cycamore.Source("Mine", outcommod="uranium")
    institution = agents.NullInst("Institution")
    region = agents.NullRegion("Region")

    institution.add_initial_facility(mine, count=2)
    region.add(institution)

    assert region.children == (institution,)
    assert institution.initial_facilities == ((mine, 2),)
