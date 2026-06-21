from __future__ import annotations

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
