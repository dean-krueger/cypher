from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

import cypher
from cypher.catalog import Catalog, set_catalog
from cypher.discovery import CyclusAdapter


@pytest.fixture(scope="module")
def live_cyclus() -> tuple[Path, dict[str, Any]]:
    executable = os.environ.get("CYPHER_TEST_CYCLUS")
    if not executable:
        pytest.skip("set CYPHER_TEST_CYCLUS to run Cyclus integration tests")
    path = Path(executable)
    if not path.exists():
        pytest.fail(f"configured Cyclus executable does not exist: {path}")
    metadata, _warnings = CyclusAdapter(path).metadata()
    return path.resolve(), metadata


@pytest.mark.integration
def test_selected_cyclus_can_report_metadata(live_cyclus) -> None:
    _path, metadata = live_cyclus

    assert ":agents:NullInst" in metadata["specs"]
    assert ":agents:NullRegion" in metadata["specs"]


@pytest.mark.integration
def test_live_nested_mixer_round_trip(live_cyclus, tmp_path: Path) -> None:
    """Discover, serialize, and run a real nested Cycamore configuration."""

    executable, metadata = live_cyclus
    assert ":cycamore:Mixer" in metadata["specs"]
    catalog = Catalog.from_metadata(metadata, executable=str(executable))
    set_catalog(catalog)
    try:
        import cypher.agents as agents
        import cypher.cycamore as cycamore

        feed = cypher.Commodity("mixer_feed")
        product = cypher.Commodity("mixer_product")
        mixer = cycamore.Mixer(
            "NestedMixer",
            in_streams=[((1.0, 100.0), [(feed, 1.0)])],
            out_commod=product,
            throughput=100.0,
        )
        institution = agents.NullInst("Institution")
        institution.add_initial_facility(mixer)
        region = agents.NullRegion("Region")
        region.add(institution)
        simulation = cypher.Simulation(
            cypher.Control(duration=1, start_year=2000, start_month=1),
            catalog=catalog,
            schema_path=None,
        )
        simulation.add_library("agents")
        simulation.add_library("cycamore")
        simulation.add(
            cypher.Recipe(
                "integration_recipe",
                basis="mass",
                composition={922350000: 1.0},
            )
        )
        simulation.add(region)

        result = simulation.run(
            directory=tmp_path,
            stream_output=False,
            cyclus_executable=executable,
        )

        assert result.success
        assert result.output_path.is_file()
        xml = result.input_path.read_text(encoding="utf-8")
        assert "<in_streams>" in xml
        assert "<commodity>mixer_feed</commodity>" in xml
    finally:
        set_catalog(None)
