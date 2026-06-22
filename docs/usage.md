# Using Cypher

Cypher is pre-alpha. It discovers installed Cyclus archetypes, builds a
simulation from Python objects, exports readable hierarchical XML, and runs
that input through Cyclus.

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

## Build a simulation

```python
import cypher
import cypher.agents as agents
import cypher.cycamore as cycamore

simulation = cypher.Simulation(
    cypher.Control(duration=10, start_year=2000, start_month=1),
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
simulation.validate()
simulation.export_to_xml("bakery.xml")
```

Objects may be configured incrementally. Missing required fields are allowed
while constructing a model, but `validate()` and `export_to_xml()` report them
together before writing XML.

The control block may also be added incrementally:

```python
simulation = cypher.Simulation()
simulation.add(cypher.Control(duration=10, start_year=2000, start_month=1))
```

The complete runnable authoring example is in
[`examples/bakery.py`](../examples/bakery.py).

## Run Cyclus

Run the current object graph directly from Python:

```python
result = simulation.run()
```

Every run validates the model, exports fresh XML, invokes Cyclus, streams its
normal output, and captures that output in the returned `RunResult`. The named
simulation above creates `bakery.xml` and `bakery.sqlite` in the current working
directory. An unnamed simulation uses `simulation.xml` and
`simulation.sqlite`.

The result is convenient to inspect in a notebook:

```python
result.success
result.input_path
result.output_path
result.returncode
result.stdout
result.stderr
result.command
```

Existing input or output files are protected by default. Opt into replacement
explicitly:

```python
result = simulation.run(overwrite=True)
```

Paths can be stored on the simulation or supplied for one run. If only the
input is named, the SQLite output receives the same stem:

```python
result = simulation.run(
    directory="study/case-1",
    input_path="my_sim.xml",
)
# study/case-1/my_sim.xml
# study/case-1/my_sim.sqlite
```

`stream_output=False` captures Cyclus output without displaying it. Cyclus
verbosity remains a separate integer setting from 0 through 11; leaving it as
`None` preserves the executable's native default:

```python
result = simulation.run(stream_output=False, verbosity=6)
```

Less common Cyclus CLI options may be passed as individual strings with
`extra_args`. Cypher rejects input, output, and verbosity flags there because
it owns those settings:

```python
result = simulation.run(extra_args=["--warn-limit", "100"])
```

On a nonzero Cyclus exit, `run()` raises `cypher.RunError`; its `.result`
contains the command, return code, paths, stdout, and stderr for diagnosis.

Run Cypher inside the same native, Conda, or container environment used for
discovery so validation and execution observe the same libraries. Cypher's
workflow ends at the SQLite output; use Cymetric for querying and analysis.
