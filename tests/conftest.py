from __future__ import annotations

import pytest

from cypher import Catalog, set_catalog


@pytest.fixture
def metadata() -> dict[str, object]:
    source_schema = """
<interleave>
  <element name="outcommod"><data type="string"/></element>
  <optional><element name="throughput"><data type="double"/></element></optional>
</interleave>
"""
    sink_schema = """
<interleave>
  <element name="in_commods">
    <oneOrMore><element name="val"><data type="string"/></element></oneOrMore>
  </element>
  <optional><element name="capacity"><data type="double"/></element></optional>
</interleave>
"""
    null_schema = "<interleave/>"
    return {
        "specs": [
            ":agents:NullInst",
            ":agents:NullRegion",
            ":cycamore:Source",
            ":cycamore:Sink",
        ],
        "annotations": {
            ":agents:NullInst": {
                "entity": "institution",
                "name": "cyclus::NullInst",
                "doc": "An institution with no behavior.",
                "vars": {},
            },
            ":agents:NullRegion": {
                "entity": "region",
                "name": "cyclus::NullRegion",
                "doc": "A region with no behavior.",
                "vars": {},
            },
            ":cycamore:Source": {
                "entity": "facility",
                "name": "cycamore::Source",
                "doc": "A source facility.",
                "vars": {
                    "outcommod": {
                        "alias": "outcommod",
                        "index": 0,
                        "type": "std::string",
                        "uitype": "outcommodity",
                        "doc": "Output commodity.",
                    },
                    "throughput": {
                        "alias": "throughput",
                        "index": 1,
                        "type": "double",
                        "default": 1.0e299,
                        "range": [0.0, 1.0e299],
                        "doc": "Maximum throughput.",
                    },
                    "inventory": {
                        "index": 2,
                        "type": ["cyclus::toolkit::ResBuf", "cyclus::Material"],
                    },
                },
            },
            ":cycamore:Sink": {
                "entity": "facility",
                "name": "cycamore::Sink",
                "doc": "A sink facility.",
                "vars": {
                    "in_commods": {
                        "alias": ["in_commods", "val"],
                        "index": 0,
                        "type": ["std::vector", "std::string"],
                        "uitype": ["oneormore", "incommodity"],
                        "doc": "Input commodities.",
                    },
                    "capacity": {
                        "alias": "capacity",
                        "index": 1,
                        "type": "double",
                        "range": [0.0, 1.0e299],
                        "doc": "Maximum capacity.",
                    },
                },
            },
        },
        "schema": {
            ":agents:NullInst": null_schema,
            ":agents:NullRegion": null_schema,
            ":cycamore:Source": source_schema,
            ":cycamore:Sink": sink_schema,
        },
    }


@pytest.fixture
def catalog(metadata: dict[str, object]) -> Catalog:
    value = Catalog.from_metadata(
        metadata,
        executable="/opt/cyclus/bin/cyclus",
        cyclus_version="cyclus version fixture",
    )
    set_catalog(value)
    yield value
    set_catalog(None)
