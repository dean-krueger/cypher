# OpenMC Comparison Note

Milestone-five planning included a review of the official OpenMC notebook
examples available in the local `openmc-notebooks` checkout. The comparison
was meant to test whether Cypher needed a large authoring redesign before
investing in documentation.

The short answer is no: Cypher and OpenMC already share the most important
high-level authoring pattern. Both favor notebook-friendly Python objects,
composition in ordinary Python, explicit export to simulator input files, and
the ability to run the simulator from Python when the environment is ready.

## Similarities To Preserve

OpenMC examples tend to build named domain objects, connect them with object
references, export simulator inputs, run the simulator, and analyze the result
in Python. That maps well to Cypher's current direction:

- `Control`, `Recipe`, `Commodity`, and archetype prototypes are ordinary
  Python objects;
- object references can be passed where Cyclus ultimately wants names;
- XML export is explicit and inspectable;
- execution returns a structured result instead of hiding process state;
- notebook use is a first-class workflow in the container.

This is enough OpenMC similarity for users to recognize the style without
forcing Cyclus into an OpenMC-shaped model.

## Simulator-Driven Differences

OpenMC's inputs are built around materials, geometry, settings, tallies, and
source definitions. It also commonly writes multiple component XML files.

Cyclus inputs are built around simulation control, recipes, commodities,
archetype libraries, facility prototypes, regions, institutions, and
deployment relationships. Cyclus commonly uses one hierarchical input file.

Those differences are substantive, not cosmetic. Cypher should remain
Cyclus-shaped:

- archetype metadata should continue to come from discovery rather than from a
  hand-written Cycamore object hierarchy;
- regions and institutions should stay visible because they are central Cyclus
  concepts;
- XML output should preserve Cyclus's hierarchical structure;
- schema headers should come from the active Cyclus environment.

## Small Polish Opportunities

The OpenMC examples do suggest some incremental polish ideas:

- richer object representations for notebooks;
- short simulation summaries before export or run;
- generated docstring improvements for discovered archetype classes;
- stronger autocomplete verification in the container;
- more examples that start small and then layer in complexity.

These are useful follow-ups, but they do not require a milestone-five API
redesign. The larger need is clear documentation that explains Cypher's current
Cyclus-centered workflow.
