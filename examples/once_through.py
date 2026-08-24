"""Cypher authoring example based on an older once-through Cyclus XML input.

This example demonstrates how one might build a more complicated fuel-cycle
scenario using Cypher. It is intended as a software and authoring example only.
It should not be treated as a validated nuclear fuel-cycle model, used to draw
technical conclusions, or cited as the basis for real fuel-cycle analysis.
"""

from __future__ import annotations

import cypher.agents as agents
import cypher.cycamore as cycamore

import cypher

NOTICE = (
    "This example demonstrates how one might build a more complicated "
    "fuel-cycle scenario using Cypher. It is intended as a software and "
    "authoring example only. It should not be treated as a validated nuclear "
    "fuel-cycle model, used to draw technical conclusions, or cited as the "
    "basis for real fuel-cycle analysis."
)


def build_simulation() -> cypher.Simulation:
    """Return a once-through fuel-cycle authoring example."""

    simulation = cypher.Simulation(
        cypher.Control(duration=1080, start_year=2000, start_month=1),
        name="once_through",
    )
    simulation.add_library("agents")
    simulation.add_library("cycamore")

    natl_u = cypher.Commodity("natl_u")
    converted_u = cypher.Commodity("converted_u")
    enriched_u = cypher.Commodity("enriched_u")
    depleted_u = cypher.Commodity("depleted_u")
    fresh_uox = cypher.Commodity("fresh_uox")
    used_uox = cypher.Commodity("used_uox")

    natl_u_recipe = cypher.Recipe(
        "natl_u",
        basis="mass",
        composition={922350000: 0.00711, 922380000: 0.99289},
    )
    enriched_u_recipe = cypher.Recipe(
        "enriched_u",
        basis="mass",
        composition={922350000: 0.04, 922380000: 0.96},
    )
    spent_uox_recipe = cypher.Recipe(
        "spent_uox",
        basis="mass",
        composition={
            922350000: 0.008,
            922380000: 0.922,
            942390000: 0.012,
            551370000: 0.004,
            541350000: 0.006,
            430990000: 0.004,
            400950000: 0.004,
            380900000: 0.004,
            30000000: 0.036,
        },
    )

    mine = cycamore.Source(
        "UraniumMine",
        outcommod=natl_u,
        outrecipe=natl_u_recipe.name,
        throughput=1e299,
    )
    conversion = cycamore.Conversion(
        "Conversion",
        incommods=[natl_u],
        outcommod=converted_u,
        throughput=1e299,
    )
    enrichment = cycamore.Enrichment(
        "Enrichment",
        feed_commod=converted_u,
        feed_recipe=natl_u_recipe.name,
        product_commod=enriched_u,
        tails_commod=depleted_u,
        tails_assay=0.0025,
        swu_capacity=1e299,
    )
    mixer = cycamore.Mixer(
        "Mixer",
        in_streams=[
            (
                (1.0, 1e299),
                [(enriched_u, 1.0)],
            )
        ],
        out_commod=fresh_uox,
        throughput=1e299,
    )
    reactor = cycamore.Reactor(
        "Reactor",
        fuel_incommods=[fresh_uox],
        fuel_inrecipes=[enriched_u_recipe.name],
        fuel_outcommods=[used_uox],
        fuel_outrecipes=[spent_uox_recipe.name],
        cycle_time=18,
        refuel_time=1,
        assem_size=33000,
        n_assem_core=3,
        n_assem_batch=1,
        power_cap=1000,
    )
    spent_storage = cycamore.Storage(
        "SpentFuelStorage",
        in_commods=[used_uox],
        out_commods=[used_uox],
        residence_time=60,
        throughput=1e299,
    )
    interim_storage = cycamore.Storage(
        "InterimStorage",
        in_commods=[used_uox],
        out_commods=[used_uox],
        residence_time=300,
        throughput=1e299,
    )
    repository = cycamore.Sink(
        "Repository",
        in_commods=[used_uox, depleted_u],
        capacity=1e299,
    )

    support = agents.NullInst("TestInst")
    for facility in (
        mine,
        conversion,
        enrichment,
        mixer,
        spent_storage,
        interim_storage,
        repository,
    ):
        support.add_initial_facility(facility)

    deployer = cycamore.DeployInst(
        "ReactorInst",
        prototypes=[reactor.name],
        build_times=[1],
        n_build=[1],
        lifetimes=[476],
    )

    region = agents.NullRegion("SingleRegion")
    region.add(support, deployer)

    simulation.add(
        natl_u_recipe,
        enriched_u_recipe,
        spent_uox_recipe,
        reactor,
        region,
    )
    return simulation


if __name__ == "__main__":
    print(NOTICE)
    print(build_simulation().to_xml())
