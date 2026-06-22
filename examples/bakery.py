"""Build and run the bakery simulation through Cypher."""

from __future__ import annotations

import argparse
from pathlib import Path

import cypher
import cypher.agents as agents
import cypher.cycamore as cycamore


def build_simulation() -> cypher.Simulation:
    """Return a small compositional Cyclus simulation."""

    simulation = cypher.Simulation(
        cypher.Control(
            duration=10,
            start_year=2000,
            start_month=1,
        ),
        name="bakery",
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("."))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbosity", type=int, choices=range(12))
    arguments = parser.parse_args()
    result = build_simulation().run(
        directory=arguments.directory,
        overwrite=arguments.overwrite,
        verbosity=arguments.verbosity,
    )
    print()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
