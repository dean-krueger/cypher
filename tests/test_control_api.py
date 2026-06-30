from __future__ import annotations

from pathlib import Path

import pytest

import cypher


def test_control_may_be_positional(catalog) -> None:
    control = cypher.Control(duration=1, start_year=2000, start_month=1)

    simulation = cypher.Simulation(control, catalog=catalog)

    assert simulation.control is control


def test_control_may_be_added(catalog) -> None:
    control = cypher.Control(duration=1, start_year=2000, start_month=1)
    simulation = cypher.Simulation(catalog=catalog)

    simulation.add(control)
    simulation.add(control)

    assert simulation.control is control


def test_adding_a_different_control_is_rejected(catalog) -> None:
    simulation = cypher.Simulation(
        cypher.Control(duration=1, start_year=2000, start_month=1),
        catalog=catalog,
    )

    with pytest.raises(ValueError, match="different control block"):
        simulation.add(cypher.Control(duration=2, start_year=2001, start_month=2))


def test_optional_control_fields_serialize_in_grammar_order(catalog) -> None:
    simulation = cypher.Simulation(
        cypher.Control(
            simhandle="case-1",
            duration=1,
            start_year=2000,
            start_month=1,
            decay="lazy",
            dt=86400,
            explicit_inventory=True,
            explicit_inventory_compact=False,
            tolerance_generic=1e-6,
            tolerance_resource=2e-6,
            seed=20240101,
            stride=1234,
        ),
        schema_path=None,
        catalog=catalog,
    )

    control_block = simulation.to_xml().split("  </control>", maxsplit=1)[0].rstrip()

    assert control_block == """<simulation>
  <control>
    <simhandle>case-1</simhandle>
    <duration>1</duration>
    <startyear>2000</startyear>
    <startmonth>1</startmonth>
    <decay>lazy</decay>
    <dt>86400</dt>
    <explicit_inventory>true</explicit_inventory>
    <explicit_inventory_compact>false</explicit_inventory_compact>
    <tolerance_generic>1e-06</tolerance_generic>
    <tolerance_resource>2e-06</tolerance_resource>
    <seed>20240101</seed>
    <stride>1234</stride>"""


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("duration", -1, "nonnegative"),
        ("start_month", 13, "at most 12"),
        ("decay", "sometimes", "must be one of"),
        ("explicit_inventory", "true", "boolean"),
        ("seed", 0, "at least 1"),
    ],
)
def test_invalid_control_values_fail_on_assignment(
    field: str, value: object, message: str
) -> None:
    control = cypher.Control(duration=1, start_year=2000, start_month=1)

    with pytest.raises(ValueError, match=message):
        setattr(control, field, value)


def test_to_xml_can_include_explicit_schema_header(catalog) -> None:
    simulation = cypher.Simulation(
        cypher.Control(duration=1, start_year=2000, start_month=1),
        catalog=catalog,
    )

    xml = simulation.to_xml(schema_path="schemas/cyclus.rng")

    assert xml.startswith(
        '<?xml-model href="schemas/cyclus.rng" type="application/xml" '
        'schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
        "<simulation>"
    )


def test_simulation_uses_discovered_schema_header_by_default(catalog) -> None:
    simulation = cypher.Simulation(
        cypher.Control(duration=1, start_year=2000, start_month=1),
        catalog=catalog,
    )

    assert simulation.to_xml().startswith(
        '<?xml-model href="/opt/cyclus/share/cyclus/cyclus.rng.in" '
        'type="application/xml" '
        'schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
    )


def test_schema_header_can_be_disabled(catalog) -> None:
    simulation = cypher.Simulation(
        cypher.Control(duration=1, start_year=2000, start_month=1),
        schema_path=None,
        catalog=catalog,
    )

    assert simulation.to_xml().startswith("<simulation>")
    assert simulation.to_xml(schema_path=None).startswith("<simulation>")


def test_auto_schema_warns_when_discovery_has_no_schema_path(metadata) -> None:
    catalog = cypher.Catalog.from_metadata(metadata)
    simulation = cypher.Simulation(
        cypher.Control(duration=1, start_year=2000, start_month=1),
        catalog=catalog,
    )

    with pytest.warns(UserWarning, match="schema header"):
        xml = simulation.to_xml()

    assert xml.startswith("<simulation>")


def test_export_uses_portable_relative_schema_href(catalog, tmp_path: Path) -> None:
    schema = tmp_path / "case" / "schemas" / "cyclus.rng"
    output = tmp_path / "case" / "inputs" / "simulation.xml"
    schema.parent.mkdir(parents=True)
    schema.touch()
    simulation = cypher.Simulation(
        cypher.Control(duration=1, start_year=2000, start_month=1),
        catalog=catalog,
    )

    simulation.export_to_xml(output, schema_path=schema)

    assert output.read_text(encoding="utf-8").startswith(
        '<?xml-model href="../schemas/cyclus.rng" type="application/xml" '
        'schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
    )
