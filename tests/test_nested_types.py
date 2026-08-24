from __future__ import annotations

import importlib
import inspect
from collections.abc import Mapping, Sequence, Set
from xml.etree import ElementTree as ET

import pytest

import cypher
from cypher.catalog import Catalog, set_catalog
from cypher.errors import ValidationError


@pytest.fixture
def nested_catalog() -> Catalog:
    mixer_type = [
        "std::vector",
        [
            "std::pair",
            ["std::pair", "double", "double"],
            ["std::map", "std::string", "double"],
        ],
    ]
    mixer_alias = [
        "in_streams",
        [
            "stream",
            ["info", "mixing_ratio", "buf_size"],
            [["commodities", "item"], "commodity", "pref"],
        ],
    ]
    separations_type = [
        "std::map",
        "std::string",
        ["std::pair", "double", ["std::map", "int", "double"]],
    ]
    separations_alias = [
        ["streams", "item"],
        "commod",
        [
            "info",
            "buf_size",
            [["efficiencies", "item"], "comp", "eff"],
        ],
    ]
    stress_type = [
        "std::map",
        "std::string",
        [
            "std::map",
            "std::string",
            ["std::pair", "double", "std::string"],
        ],
    ]
    stress_alias = [
        ["records", "item"],
        "group",
        [
            ["entries", "item"],
            "name",
            ["value", "number", "label"],
        ],
    ]
    metadata = {
        "specs": [
            ":test:Mixer",
            ":test:RecipeReferences",
            ":test:Separations",
            ":test:Stress",
        ],
        "annotations": {
            ":test:Mixer": {
                "entity": "facility",
                "vars": {
                    "in_streams": "streams_",
                    "streams_": {
                        "alias": mixer_alias,
                        "type": mixer_type,
                        "uitype": [
                            "oneormore",
                            [
                                "pair",
                                ["pair", "double", "double"],
                                ["oneormore", "incommodity", "double"],
                            ],
                        ],
                    },
                },
            },
            ":test:Separations": {
                "entity": "facility",
                "vars": {
                    "streams": "streams_",
                    "streams_": {
                        "alias": separations_alias,
                        "type": separations_type,
                        "uitype": [
                            "oneormore",
                            "outcommodity",
                            [
                                "pair",
                                "double",
                                ["oneormore", "nuclide", "double"],
                            ],
                        ],
                    },
                },
            },
            ":test:RecipeReferences": {
                "entity": "facility",
                "vars": {
                    "groups": {
                        "alias": [
                            "groups",
                            [["recipes", "item"], "label", "recipe"],
                        ],
                        "type": [
                            "std::vector",
                            ["std::map", "std::string", "std::string"],
                        ],
                        "uitype": [
                            "oneormore",
                            ["oneormore", "string", "inrecipe"],
                        ],
                    },
                },
            },
            ":test:Stress": {
                "entity": "facility",
                "vars": {
                    "records": {
                        "alias": stress_alias,
                        "type": stress_type,
                    },
                    "ordered": {
                        "alias": ["ordered", "val"],
                        "type": ["std::list", "std::string"],
                    },
                    "unique": {
                        "alias": ["unique", "val"],
                        "type": ["std::set", "int"],
                    },
                },
            },
        },
        "schema": {
            ":test:Mixer": '<element name="in_streams"><text/></element>',
            ":test:Separations": '<element name="streams"><text/></element>',
            ":test:RecipeReferences": '<element name="groups"><text/></element>',
            ":test:Stress": """
                <interleave>
                  <element name="records"><text/></element>
                  <optional><element name="ordered"><text/></element></optional>
                  <optional><element name="unique"><text/></element></optional>
                </interleave>
            """,
        },
    }
    catalog = Catalog.from_metadata(metadata)
    set_catalog(catalog)
    yield catalog
    set_catalog(None)


def _simulation(catalog: Catalog, prototype: object) -> cypher.Simulation:
    simulation = cypher.Simulation(
        cypher.Control(duration=1, start_year=2000, start_month=1),
        catalog=catalog,
        schema_path=None,
    )
    simulation.add_library("test")
    simulation.add(prototype)
    return simulation


def _configuration(xml: str, archetype: str) -> ET.Element:
    root = ET.fromstring(xml)
    element = root.find(f"./facility/config/{archetype}")
    assert element is not None
    return element


def test_annotation_indirection_preserves_real_nested_metadata(nested_catalog) -> None:
    mixer = nested_catalog.get("test", "Mixer").field("in_streams")
    separations = nested_catalog.get("test", "Separations").field("streams")

    assert mixer is not None
    assert mixer.python_type is list
    assert mixer.value_shape.type_expression() == (
        "Sequence[tuple[tuple[float, float], Mapping[str, float] | "
        "Sequence[tuple[str, float]]]]"
    )
    assert separations is not None
    assert separations.python_type is dict
    assert separations.value_shape.type_expression() == (
        "Mapping[str, tuple[float, Mapping[int, float] | "
        "Sequence[tuple[int, float]]]] | Sequence[tuple[str, "
        "tuple[float, Mapping[int, float] | Sequence[tuple[int, float]]]]]"
    )


def test_mixer_nested_vector_pair_map_serialization(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")
    fresh = cypher.Commodity("fresh_uox")
    recycled = cypher.Commodity("recycled_uox")
    mixer = module.Mixer(
        "Mixer",
        in_streams=[
            ((1.0, 100.0), [(fresh, 1.0), (recycled, 0.5)]),
        ],
    )

    config = _configuration(_simulation(nested_catalog, mixer).to_xml(), "Mixer")

    assert config.findtext("./in_streams/stream/info/mixing_ratio") == "1.0"
    assert config.findtext("./in_streams/stream/info/buf_size") == "100.0"
    assert [
        (item.findtext("commodity"), item.findtext("pref"))
        for item in config.findall("./in_streams/stream/commodities/item")
    ] == [("fresh_uox", "1.0"), ("recycled_uox", "0.5")]
    commodities = _simulation(nested_catalog, mixer).graph().commodities
    assert [item.name for item in commodities] == [
        "fresh_uox",
        "recycled_uox",
    ]


def test_separations_nested_map_pair_map_serialization(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")
    product = cypher.Commodity("separated_uox")
    separations = module.Separations(
        "Separations",
        streams=[(product, (1000.0, {922350000: 0.95, 942390000: 0.90}))],
    )

    config = _configuration(
        _simulation(nested_catalog, separations).to_xml(), "Separations"
    )
    item = config.find("./streams/item")
    assert item is not None
    assert item.findtext("commod") == "separated_uox"
    assert item.findtext("./info/buf_size") == "1000.0"
    assert [
        (entry.findtext("comp"), entry.findtext("eff"))
        for entry in item.findall("./info/efficiencies/item")
    ] == [("922350000", "0.95"), ("942390000", "0.9")]


def test_hidden_map_map_pair_stress_type(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")
    stress = module.Stress(
        "Stress",
        records={"outer": {"inner": (3.14, "description")}},
        ordered=["first", "second"],
        unique={3, 1, 2},
    )

    field = nested_catalog.get("test", "Stress").field("records")
    assert field is not None
    assert field.value_shape.type_expression() == (
        "Mapping[str, Mapping[str, tuple[float, str]] | "
        "Sequence[tuple[str, tuple[float, str]]]] | Sequence[tuple[str, "
        "Mapping[str, tuple[float, str]] | Sequence[tuple[str, "
        "tuple[float, str]]]]]"
    )
    assert inspect.signature(module.Stress).parameters["records"].annotation == (
        Mapping[
            str,
            Mapping[str, tuple[float, str]] | Sequence[tuple[str, tuple[float, str]]],
        ]
        | Sequence[
            tuple[
                str,
                Mapping[str, tuple[float, str]]
                | Sequence[tuple[str, tuple[float, str]]],
            ]
        ]
    )
    assert module.Stress.field_example_value("records") == {
        "value": {"value": (1.0, "value")}
    }
    example = module.Stress.field_example("records")
    assert "Example format: {<group>: {<name>: (<number>, <label>)}}" in example
    assert "Example value:  {'value': {'value': (1.0, 'value')}}" in example
    assert "Example format: {<group>: {<name>: (<number>, <label>)}}" in (
        module.Stress.describe_field("records")
    )

    config = _configuration(_simulation(nested_catalog, stress).to_xml(), "Stress")
    item = config.find("./records/item")
    assert item is not None
    assert item.findtext("group") == "outer"
    assert item.findtext("./entries/item/name") == "inner"
    assert item.findtext("./entries/item/value/number") == "3.14"
    assert item.findtext("./entries/item/value/label") == "description"
    assert [item.text for item in config.findall("./ordered/val")] == [
        "first",
        "second",
    ]
    assert [item.text for item in config.findall("./unique/val")] == ["1", "2", "3"]


def test_nested_validation_reports_the_precise_value_path(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")

    with pytest.raises(
        TypeError,
        match=r"Stress\(name='Stress'\)\.records\['outer'\]\['inner'\]\[0\]",
    ):
        module.Stress(
            "Stress",
            records={"outer": {"inner": ("not-a-double", "description")}},
        )


def test_container_annotations_match_accepted_inputs(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")
    signature = inspect.signature(module.Stress)

    assert signature.parameters["ordered"].annotation == Sequence[str]
    assert signature.parameters["unique"].annotation == Set[int] | Sequence[int]
    module.Stress(
        "Stress",
        records={"outer": {"inner": (3.14, "description")}},
        ordered=("first", "second"),
        unique=frozenset({1, 2}),
    )

    with pytest.raises(TypeError, match="must be a two-item tuple"):
        module.Stress(
            "Stress",
            records={"outer": {"inner": [3.14, "description"]}},
        )


def test_nested_recipe_names_are_validated_recursively(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")
    references = module.RecipeReferences(
        "References",
        groups=[{"fuel": "known_recipe", "waste": "missing_recipe"}],
    )
    simulation = _simulation(nested_catalog, references)
    simulation.add(
        cypher.Recipe(
            "known_recipe", basis="mass", composition={922350000: 1.0}
        )
    )

    with pytest.raises(ValidationError, match="unknown recipe 'missing_recipe'"):
        simulation.validate()


def test_nested_recipe_names_accept_declared_recipes(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")
    references = module.RecipeReferences(
        "References", groups=[{"fuel": "known_recipe"}]
    )
    simulation = _simulation(nested_catalog, references)
    simulation.add(
        cypher.Recipe(
            "known_recipe", basis="mass", composition={922350000: 1.0}
        )
    )

    simulation.validate()


def test_maps_accept_sequence_of_pairs_for_unhashable_future_keys(
    nested_catalog,
) -> None:
    module = importlib.import_module("cypher.test")
    stress = module.Stress(
        "Stress",
        records=[("outer", [("inner", (2.5, "description"))])],
    )

    config = _configuration(_simulation(nested_catalog, stress).to_xml(), "Stress")
    assert config.findtext("./records/item/entries/item/value/label") == "description"


def test_map_pair_sequences_reject_duplicate_keys(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")

    with pytest.raises(ValueError, match="duplicate map key 'outer'"):
        module.Stress(
            "Stress",
            records=[
                ("outer", [("inner", (2.5, "first"))]),
                ("outer", [("inner", (3.0, "second"))]),
            ],
        )


def test_separations_help_gives_a_compact_alias_template(nested_catalog) -> None:
    module = importlib.import_module("cypher.test")

    example = module.Separations.field_example("streams")

    assert example == "\n".join(
        [
            "Example format: {<commod>: (<buf_size>, {<comp>: <eff>})}",
            "Example value:  {'commodity': (1.0, {922350000: 1.0})}",
        ]
    )
