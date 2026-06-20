"""Build the milestone-one bakery simulation and export its Cyclus XML."""

from __future__ import annotations

import argparse
from pathlib import Path

import cypher.agents as agents
import cypher.cycamore as cycamore

import cypher


def build_simulation() -> cypher.Simulation:
    """Return a small compositional Cyclus simulation."""

    simulation = cypher.Simulation(
        control=cypher.Control(
            duration=10,
            start_year=2000,
            start_month=1,
        )
    )
    simulation.add_library("agents")
    simulation.add_library("cycamore")

    toast = cypher.Commodity("Toast")
    recipe = cypher.Recipe(
        "Toast",
        basis="atom",
        composition={10030000: 1.0},
    )
    bakery = cycamore.Source(
        "Bakery",
        outcommod=toast,
        throughput=8334,
    )
    store = cycamore.Sink(
        "Bread Store",
        in_commods=[toast],
        capacity=1000,
    )
    institution = agents.NullInst("OneInst")
    institution.add_initial_facility(bakery)
    institution.add_initial_facility(store)
    region = agents.NullRegion("OneRegion")
    region.add(institution)

    simulation.add(recipe)
    simulation.add(region)
    return simulation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=Path("bakery.xml"))
    arguments = parser.parse_args()
    build_simulation().export_to_xml(arguments.output)
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
