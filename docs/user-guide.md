# Cypher User Guide

This guide walks through the current Cypher workflow: discover the Cyclus
environment, author a simulation with Python objects, export Cyclus XML, run
Cyclus, and inspect the output.

Cypher is still pre-alpha software. The recommended environment today is the
project container, because it packages Cypher with compatible builds of
Cyclus, Cycamore, Cymetric, IPython, and the notebook stack. Ordinary `pip`
installation under the `cyclus-cypher` package name, and possibly Conda
installation, are planned near-term follow-up work. Until those paths are
finished and documented, use the container for normal evaluation.

## Environment

Pull the published image:

```console
docker pull deankrueger/cypher:alpha
```

Or build a local image from this repository:

```console
docker build -t cypher:local .
```

The image is meant to be used with a mounted workspace, for example through VS
Code Dev Containers or an interactive shell:

```console
docker run --rm -it -v "$PWD":/workspace -w /workspace deankrueger/cypher:alpha bash
```

Inside the container, verify the tools:

```console
python -c "import cypher; print(cypher.__version__)"
cyclus --version
```

## Discover Archetypes

Cypher does not hard-code Cycamore or any other archetype library. It discovers
the archetypes installed beside the target Cyclus executable and caches
normalized metadata locally:

```console
cypher discover
```

Discovery reports available libraries, compatibility warnings, the metadata
cache path, and generated type-stub paths. Rerun discovery when the Cyclus
installation, Cycamore installation, or active container image changes.

Use strict mode when you want discovery warnings to fail early:

```console
cypher discover --strict
```

To reprint the cached compatibility report:

```console
cypher compatibility
```

## Build A Simulation

The smallest complete example is `examples/bakery.py`. It builds a toy source
and sink simulation that can export and run through Cyclus.

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
toast_recipe = cypher.Recipe(
    "Toast",
    basis="atom",
    composition={10030000: 1.0},
)

bakery = cycamore.Source("Bakery", outcommod=toast, throughput=8334)
store = cycamore.Sink("Bread Store", in_commods=[toast], capacity=1000)

institution = agents.NullInst("OneInst")
institution.add_initial_facility(bakery)
institution.add_initial_facility(store)

region = agents.NullRegion("OneRegion")
region.add(institution)

simulation.add(toast_recipe, region)
```

The core pattern is:

1. Create `Control`.
2. Create a `Simulation`.
3. Add the archetype libraries that the simulation uses.
4. Build commodities, recipes, facility prototypes, institutions, and regions.
5. Add root objects to the simulation.

Cypher follows Python object references where it can. For example,
`outcommod=toast` records the same commodity object that was created earlier.
When Cyclus expects only a name, Cypher serializes the object to its name in
the exported XML. Strings still work for some references, but object references
let Cypher collect related objects and catch more mistakes before Cyclus runs.

### Nested container fields

Some archetypes expose configuration fields built from nested C++ containers.
Cypher translates supported combinations of `std::vector`, `std::list`,
`std::set`, `std::pair`, and `std::map` recursively into ordinary Python
collections. For example, the discovered Cycamore `Separations.streams` field
can be configured as:

```python
separations = cycamore.Separations(
    "Separations",
    feed_commods=["used_fuel"],
    feedbuf_size=1000.0,
    streams={
        "recovered_fuel": (
            1000.0,
            {922350000: 0.95, 942390000: 0.90},
        ),
    },
)
```

The generated signature and docstring show the Python shape discovered for the
active Cyclus environment. Field-level helpers are convenient in IPython:

```python
cycamore.Separations.describe_field("streams")
cycamore.Separations.field_example("streams")
```

`field_example()` returns a compact Python-shaped template labeled with XML
aliases, followed by an example value.
`field_example_value()` returns just the ordinary Python example value when that
is more convenient for programmatic inspection.

Maps accept either a Python mapping or a sequence of two-item pairs. The latter
form permits object references or complex keys that are not hashable:

```python
streams=[
    (recovered_commodity, (1000.0, {922350000: 0.95})),
]
```

Validation follows the complete nested shape and reports the path to an invalid
leaf. Serialization walks the same shape together with Cyclus's XML aliases, so
nesting depth is not limited to a fixed number of container layers.

## Validate And Export XML

Run validation explicitly when you want fast feedback:

```python
simulation.validate()
```

Export XML:

```python
simulation.export_to_xml("bakery.xml")
```

Or produce the XML string:

```python
xml_text = simulation.to_xml()
```

By default, Cypher includes the full generated Relax NG schema header that was
reported by `cypher discover`. This header comes from `cyclus -n`, which is the
authoritative way to ask the installed Cyclus environment for the complete
schema.

Disable the schema header:

```python
simulation.export_to_xml("bakery.xml", schema_path=None)
```

Use a specific schema path:

```python
simulation.export_to_xml("bakery.xml", schema_path="/path/to/cyclus.rng")
```

## Run Cyclus

`Simulation.run()` validates, exports XML, and launches Cyclus:

```python
result = simulation.run(directory="runs/bakery", overwrite=True)
print(result)
```

By default, Cypher refuses to overwrite existing input or output files. Pass
`overwrite=True` when replacing old run files is intentional.

The returned `RunResult` contains:

- `returncode`
- `success`
- `directory`
- `input_path`
- `output_path`
- `stdout`
- `stderr`
- `command`

Cypher streams Cyclus output while also capturing it. Disable streaming if you
only want the captured result:

```python
result = simulation.run(stream_output=False)
```

Pass Cyclus verbosity or advanced command-line arguments:

```python
simulation.run(verbosity=3, extra_args=["--warn-limit", "10"])
```

## Inspect Output

Cypher stops after producing the Cyclus SQLite output. Post-processing belongs
to Cymetric or user analysis code:

```python
import cymetric as cym

db = cym.dbopen(str(result.output_path))
```

The container includes Cymetric and Graphviz support for common notebook
analysis workflows.

## Troubleshooting

If `cypher discover` cannot find Cyclus, make sure you are in the container or
pass an executable explicitly:

```console
cypher discover --cyclus /path/to/cyclus
```

If an import such as `import cypher.cycamore` fails, rerun `cypher discover` in
the active environment. The dynamic library modules are backed by the discovery
cache.

If validation reports a missing library, call `simulation.add_library()` for
each archetype library used by the simulation.

If validation reports an unknown prototype reference, prefer passing the
prototype object instead of a string, or confirm the string exactly matches a
facility prototype name.

If XML exports without a schema header, rerun discovery in an environment where
`cyclus -n` succeeds. You can also pass `schema_path` explicitly or set it to
`None` for headerless XML.

If `Simulation.run()` refuses to overwrite files, choose a new run directory or
pass `overwrite=True`.

## Where To Go Next

- `examples/bakery.py` is the smallest runnable demonstration.
- `docs/examples.md` summarizes the larger example scenarios.
- `docs/code-tour.md` explains the implementation for technical reviewers.
- `docs/openmc-comparison.md` records the OpenMC comparison that informed this
  milestone.
