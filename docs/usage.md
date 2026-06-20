# Using Cypher

Cypher is pre-alpha. The milestone-one interface discovers installed Cyclus
archetypes, builds a simulation from Python objects, and exports readable
hierarchical Cyclus XML.

## Discover the Cyclus environment

Install Cypher in the same native, Conda, or container environment as Cyclus,
then run:

```console
cypher discover
```

Cypher selects an executable in this order:

1. `cypher discover --cyclus /path/to/cyclus`
2. `CYPHER_CYCLUS_EXECUTABLE`
3. `cyclus` on `PATH`

The command reports discovered libraries and compatibility warnings, caches
normalized metadata, and generates environment-local type stubs. Repeat it
after changing the Cyclus installation or installed archetype libraries.

Use strict mode when every compatibility warning should fail discovery:

```console
cypher discover --strict
```

Inspect the cached report later with:

```console
cypher compatibility
```

## Build and export a simulation

```python
import cypher
import cypher.agents as agents
import cypher.cycamore as cycamore

simulation = cypher.Simulation(
    control=cypher.Control(duration=10, start_year=2000, start_month=1)
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
simulation.validate()
simulation.export_to_xml("bakery.xml")
```

Objects may be configured incrementally. Missing required fields are allowed
while constructing a model, but `validate()` and `export_to_xml()` report them
together before writing XML.

The complete runnable authoring example is in
[`examples/bakery.py`](../examples/bakery.py).

## Run Cyclus

Simulation execution from Python is deferred to milestone two. Run the exported
input with the same environment used for discovery:

```console
cyclus bakery.xml -o bakery.sqlite
```

Within Docker, run Cypher inside the Cyclus container so executable resolution,
discovery, and validation all observe the same installed libraries.
