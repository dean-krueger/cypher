from __future__ import annotations

import json
from pathlib import Path

import pytest

from cypher import Catalog
from cypher.catalog import cache_root
from cypher.errors import DiscoveryError


def test_metadata_normalizes_only_schema_input_fields(metadata) -> None:
    catalog = Catalog.from_metadata(metadata)
    source = catalog.get("cycamore", "Source")

    assert [field.name for field in source.fields] == ["outcommod", "throughput"]
    assert source.field("outcommod").required
    assert not source.field("throughput").required
    assert source.field("throughput").default == 1.0e299


def test_catalog_round_trip(tmp_path: Path, catalog: Catalog) -> None:
    path = tmp_path / "catalog.json"
    catalog.save(path)

    loaded = Catalog.load(path)

    assert loaded.to_dict() == catalog.to_dict()
    assert json.loads(path.read_text())["format_version"] == 1


def test_unknown_library_lists_available_libraries(catalog: Catalog) -> None:
    with pytest.raises(DiscoveryError, match="agents, cycamore"):
        catalog.library("tricycle")


def test_cache_root_honors_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CYPHER_CACHE_DIR", str(tmp_path))
    assert cache_root() == tmp_path


def test_choice_schema_is_reported_as_unsupported(metadata) -> None:
    metadata["schema"][":cycamore:Source"] = """
    <choice>
      <element name="a"><text/></element>
      <element name="b"><text/></element>
    </choice>
    """

    source = Catalog.from_metadata(metadata).get("cycamore", "Source")

    assert any("choice" in warning for warning in source.warnings)
