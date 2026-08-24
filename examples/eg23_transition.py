"""Cypher authoring example based on an older EG transition XML input.

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
    """Return an EG transition-style authoring example."""

    simulation = cypher.Simulation(
        cypher.Control(duration=1200, start_year=2000, start_month=1),
        name="eg23_transition",
    )
    simulation.add_library("agents")
    simulation.add_library("cycamore")

    natl_u = cypher.Commodity("natl_u")
    enriched_u = cypher.Commodity("enriched_u")
    depleted_u = cypher.Commodity("depleted_u")
    fresh_lwr_fuel = cypher.Commodity("fresh_lwr_fuel")
    used_lwr_fuel = cypher.Commodity("used_lwr_fuel")
    separated_uox = cypher.Commodity("separated_uox")
    fresh_sfr_fuel = cypher.Commodity("fresh_sfr_fuel")
    used_sfr_fuel = cypher.Commodity("used_sfr_fuel")
    separated_sfr = cypher.Commodity("separated_sfr")
    waste = cypher.Commodity("waste")

    natl_u_recipe = cypher.Recipe(
        "natl_u_recipe",
        basis="mass",
        composition={922350000: 0.00711, 922380000: 0.99289},
    )
    fresh_lwr_recipe = cypher.Recipe(
        "fresh_lwr_fuel_recipe",
        basis="mass",
        composition={922350000: 0.04, 922380000: 0.96},
    )
    used_lwr_recipe = cypher.Recipe(
        "used_lwr_fuel_recipe",
        basis="mass",
        composition={922350000: 0.008, 922380000: 0.93, 942390000: 0.012},
    )
    fresh_sfr_recipe = cypher.Recipe(
        "fresh_sfr_fuel_recipe",
        basis="mass",
        composition={922380000: 0.8, 942390000: 0.2},
    )
    used_sfr_recipe = cypher.Recipe(
        "used_sfr_fuel_recipe",
        basis="mass",
        composition={922380000: 0.75, 942390000: 0.17, 551370000: 0.08},
    )

    mine = cycamore.Source(
        "Mine",
        outcommod=natl_u,
        outrecipe=natl_u_recipe.name,
        throughput=1e299,
    )
    enrichment = cycamore.Enrichment(
        "Enrichment",
        feed_commod=natl_u,
        feed_recipe=natl_u_recipe.name,
        product_commod=enriched_u,
        tails_commod=depleted_u,
        tails_assay=0.0025,
        swu_capacity=1e299,
    )
    lwr = cycamore.Reactor(
        "LWR",
        fuel_incommods=[fresh_lwr_fuel],
        fuel_inrecipes=[fresh_lwr_recipe.name],
        fuel_outcommods=[used_lwr_fuel],
        fuel_outrecipes=[used_lwr_recipe.name],
        cycle_time=18,
        refuel_time=1,
        assem_size=33000,
        n_assem_core=3,
        n_assem_batch=1,
        power_cap=1000,
    )
    uox_cooling = cycamore.Storage(
        "UOX_Cooling_Pool",
        in_commods=[used_lwr_fuel],
        out_commods=[used_lwr_fuel],
        residence_time=60,
        throughput=1e299,
    )
    uox_reprocessing = cycamore.Separations(
        "UOX_Reprocessing",
        feed_commods=[used_lwr_fuel],
        feed_commod_prefs=[1.0],
        feedbuf_size=1e299,
        streams=[
            (
                separated_uox,
                (1e299, {922350000: 0.99, 942390000: 0.99}),
            )
        ],
        leftover_commod=waste,
        throughput=1e299,
    )
    sfr_mixer = cycamore.Mixer(
        "SFR_Mixer",
        in_streams=[
            (
                (1.0, 1e299),
                [(separated_uox, 1.0), (separated_sfr, 1.0)],
            )
        ],
        out_commod=fresh_sfr_fuel,
        throughput=1e299,
    )
    sfr = cycamore.Reactor(
        "SFR",
        fuel_incommods=[fresh_sfr_fuel],
        fuel_inrecipes=[fresh_sfr_recipe.name],
        fuel_outcommods=[used_sfr_fuel],
        fuel_outrecipes=[used_sfr_recipe.name],
        cycle_time=18,
        refuel_time=1,
        assem_size=40000,
        n_assem_core=3,
        n_assem_batch=1,
        power_cap=1000,
    )
    sfr_cooling = cycamore.Storage(
        "SFR_Cooling_Pool",
        in_commods=[used_sfr_fuel],
        out_commods=[used_sfr_fuel],
        residence_time=60,
        throughput=1e299,
    )
    sfr_reprocessing = cycamore.Separations(
        "SFR_Reprocessing",
        feed_commods=[used_sfr_fuel],
        feed_commod_prefs=[1.0],
        feedbuf_size=1e299,
        streams=[
            (
                separated_sfr,
                (1e299, {922350000: 0.99, 942390000: 0.99}),
            )
        ],
        leftover_commod=waste,
        throughput=1e299,
    )
    repository = cycamore.Sink(
        "Waste_Repository",
        in_commods=[waste, depleted_u],
        capacity=1e299,
    )

    initial_facilities = agents.NullInst("Initial_Facilities")
    for facility in (
        mine,
        enrichment,
        sfr_mixer,
        uox_cooling,
        uox_reprocessing,
        sfr_cooling,
        sfr_reprocessing,
        repository,
    ):
        initial_facilities.add_initial_facility(facility)

    lwr_times = list(range(12, 121, 12))
    sfr_times = list(range(600, 709, 12))
    lwr_institution = cycamore.DeployInst(
        "LWR_Institution",
        prototypes=[lwr.name for _ in lwr_times],
        build_times=lwr_times,
        n_build=[2 for _ in lwr_times],
    )
    sfr_institution = cycamore.DeployInst(
        "SFR_Institution",
        prototypes=[sfr.name for _ in sfr_times],
        build_times=sfr_times,
        n_build=[2 for _ in sfr_times],
    )

    region = agents.NullRegion("TransitionRegion")
    region.add(initial_facilities, lwr_institution, sfr_institution)

    simulation.add(
        natl_u_recipe,
        fresh_lwr_recipe,
        used_lwr_recipe,
        fresh_sfr_recipe,
        used_sfr_recipe,
        lwr,
        sfr,
        region,
    )
    return simulation


if __name__ == "__main__":
    print(NOTICE)
    print(build_simulation().to_xml())
