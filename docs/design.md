# Cypher Design Direction

Status: exploratory, pre-alpha
Last updated: 2026-06-22

This document records the current product direction. It is intentionally
revisable: implementation and hands-on user testing are expected to refine the
pre-alpha API.

## Vision

Cypher is a Python front-end for Cyclus. It should let a user construct a
simulation from understandable, composable Python objects and export the
corresponding Cyclus XML, then run that model through Cyclus.

The desired experience is inspired by OpenMC's Python input interface: users
create domain objects, connect them into a larger model, inspect and validate
that model, and export an input. Cypher should borrow this style without forcing
Cyclus concepts into OpenMC abstractions where the underlying simulators differ.

Success is not merely producing XML. Cypher should make Cyclus inputs easier to:

- author programmatically;
- inspect interactively;
- validate before execution;
- refactor without breaking string references;
- discover through editor autocomplete, signatures, and documentation;
- review as readable generated XML.

## North stars

### Schema- and metadata-driven behavior

Cyclus and its archetype libraries already expose machine-readable information.
In particular, Cyclus discovery can report installed archetype specifications,
annotations, and archetype Relax NG schemas. The base Cyclus grammar describes
the surrounding simulation structure.

Cypher should consume those interfaces rather than maintain parallel knowledge
of Cycamore, Tricycle, Recycle, or other libraries. A correctly installed
third-party archetype should not require a Cypher release merely to become
discoverable.

The archetype annotations are important alongside the grammar. Relax NG
describes valid XML structure, while annotations can provide defaults, types,
documentation, UI labels, ranges, aliases, and other information useful for a
friendly Python API.

### OpenMC-like composition

The ordinary workflow should resemble:

```python
import cypher
import cypher.agents as agents
import cypher.cycamore as cycamore

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
institution.add_initial_facility(bakery, count=1)
institution.add_initial_facility(store, count=1)

region = agents.NullRegion("OneRegion")
region.add(institution)

simulation.add(recipe)
simulation.add(region)

simulation.validate()
result = simulation.run()
```
The precise method names remain provisional. The important behavior is that
users build independent objects, nest or reference them naturally, and add a

small number of roots to the simulation.

### Low maintenance

Cyclus ecosystem projects often outlive the students who first implement them.
Cypher should therefore avoid designs that require routine synchronization with
archetype releases. Small dependencies, isolated adapters, fixture-backed tests,
and explicit compatibility reporting are product requirements, not merely code
style preferences.

## Conceptual model

### Stable handwritten core

Cypher should handwrite the relatively stable concepts belonging to the Cyclus
simulation format itself, likely including:

- `Simulation`
- `Control`
- `Commodity`
- `Recipe`
- common reference and validation infrastructure
- archetype-library declarations
- hierarchical XML serialization

Handwritten core APIs may use idiomatic Python spellings such as `start_year`
while serializing canonical Cyclus tags such as `<startyear>`.

### Metadata-driven archetypes

Archetype libraries and their fields should be discovered from Cyclus. The
friendly public form should make a configured archetype look like a named
Python object:

```python
mine = cycamore.Source(
    "Mine",
    outcommod=natural_uranium,
    throughput=1000,
)
```

The same object may be built incrementally:

```python
mine = cycamore.Source()
mine.name = "Mine"
mine.outcommod = natural_uranium
mine.throughput = 1000
```

Internally, both forms represent a named prototype configured with a particular
archetype:

```text
Prototype
├── name: "Mine"
├── archetype: "cycamore:Source"
└── configuration
    ├── outcommod: "natural_uranium"
    └── throughput: 1000
```

This uniform internal representation keeps XML serialization and validation
independent of the generated Python class. A lower-level public prototype API
may eventually serve unsupported or highly dynamic cases.

### Object graph and recursive collection

Nested composition should be the preferred style:

```python
region.add(institution)
institution.add_initial_facility(mine)
simulation.add(region)
```

Adding the region should recursively register the institution, referenced
prototype, and required archetype declarations. Independent addition and
explicit parent references may also be supported for programmatic generation,
but both styles should resolve to one internal relationship graph.

Adding one object twice is harmless. Adding distinct objects that conflict in a
Cyclus namespace is an error. Object references should follow safe renames;
string references cannot provide the same guarantee.

### Commodities

A commodity object primarily provides a reusable, validated name:

```python
toast = cypher.Commodity("Toast")
```

Using this object in an archetype configuration does not automatically require a
top-level `<commodity>` element. If solver priority is supplied, Cypher emits
that optional block:

```python
toast = cypher.Commodity("Toast", solution_priority=10.0)
```

This distinction reflects Cyclus: commodity names can be used without explicit
solver-priority declarations.

### Partial objects and validation

Cypher should permit temporary incompleteness so users can construct objects
interactively. Assignment validates supplied values when constraints are clear.
Missing required values are checked when the user calls `validate()` or
`export_to_xml()`.

Validation should aggregate errors rather than reveal one missing field at a
time. Messages should make it difficult to enter a "this does not work and I do
not know why" loop.

Cypher should validate:

- required fields known from metadata/schema;
- straightforward Python and XML datatype constraints;
- obvious reference resolution;
- duplicate names and incompatible graph relationships;
- supported structural constraints.

Cyclus remains authoritative for complete input validity and simulation
semantics. Cypher should not duplicate complicated business rules already owned
by Cyclus.

### Defaults

An archetype field may have a default reported by Cyclus. Cypher should expose
the effective default for introspection while separately tracking whether the
user explicitly assigned the field.

Unassigned optional fields should normally be omitted from XML. This lets the
selected Cyclus/archetype version apply its own default rather than embedding a
possibly stale value in the generated input.

### XML output

The initial canonical output is conventional hierarchical Cyclus XML. Flat
schema output is deferred.

Generated XML should:

- be deterministic;
- preserve user insertion order where valid;
- use a stable, conventional section order;
- be consistently indented;
- omit unset optional/defaulted values;
- avoid machine-specific data and timestamps;
- remain suitable for human verification and inclusion with research work.

Generated comments and source-format preservation are not initial goals.

## Discovery and autocomplete

Runtime-only dynamic classes would adapt well but provide weak static editor
support. Shipping handwritten Cycamore classes would provide autocomplete but
violate the maintenance goal. The current direction is a hybrid.

An explicit command:

```console
cypher discover
```

should:

1. resolve the selected Cyclus executable;
2. obtain installed archetype metadata and schemas;
3. normalize that data into a versioned cache;
4. report supported and unsupported constructs;
5. provide importable library namespaces;
6. generate signatures, docstrings, and type information for editors and
   IPython/Jupyter.

After discovery:

```python
import cypher.cycamore as cycamore
help(cycamore.Source)
```

should be useful without running discovery during import.

Discovery data is tied to an environment. The cache should record its
provenance and detect when it may be stale. Users explicitly refresh it after
changing their Cyclus installation or installed archetypes.

Normal discovery should preserve usable interfaces while warning about
unsupported constructs. It should produce an explicit compatibility report and
offer a strict mode. Unknown schema content must not disappear silently.

Generated interfaces should normally live in a platform-appropriate
environment-level cache. A future lock/export mechanism may support projects
that need reproducible checked-in discovery data.

## Selecting Cyclus

Cypher should resolve the executable predictably:

1. explicit API or CLI selection;
2. `CYPHER_CYCLUS_EXECUTABLE`;
3. `cyclus` found on `PATH`.

This means an ordinary Conda user sees the same Cyclus installation that the
shell would invoke. It also means a user running Cypher inside a Cyclus
development container naturally discovers the container's Cyclus installation
and installed/mounted archetype libraries.

Cypher should initially run *inside* the environment that contains Cyclus. Host
orchestration of Docker containers is not part of the core design.

## Execution direction

Milestone two adds execution without expanding Cypher into an analysis tool:

```text
run()
  → validate()
  → export_to_xml()
  → invoke the selected Cyclus executable
  → return structured paths, status, stdout, and stderr
```

Execution defaults to the current working directory, following OpenMC's model
execution convention. Unnamed simulations derive `simulation.xml` and
`simulation.sqlite`; named simulations derive same-stem files. Explicit paths
and a run directory remain available.

Cypher never overwrites input or output files unless explicitly requested. Each
run exports the current object state rather than reusing stale XML.

Normal stdout and stderr should stream and be captured by default. This is
separate from Cyclus log verbosity. Cypher omits `-v` by default and accepts an
explicit integer verbosity from 0 through 11.

Cypher's responsibility ends with Cyclus process execution and a usable SQLite
path. Cymetric remains responsible for querying and analyzing that output.
`RunResult.output_path` is sufficient interoperability; Cypher should not
duplicate Cymetric's API.

See `docs/milestone-2.md` for the execution contract.

## Deployment direction

Cypher should work in:

- native environments where Cyclus and archetypes are installed through Conda
  or another supported mechanism;
- Cyclus/Cymetric development containers where source directories or inputs are
  mounted;
- a notebook-ready Cypher image containing Cyclus, Cycamore, Cymetric, and
  Cypher.

Mounted third-party libraries should become discoverable after they are
installed into the container's Cyclus environment and `cypher discover` is run.

Milestone three builds on the official Cymetric image, defaulting to its
`latest` tag while permitting a pinned tag or digest. The image targets VS Code
Dev Containers and includes IPython, a selectable kernel, a UTF-8 locale,
discovery data, scientific Python packages, Graphviz, and a bakery smoke test.
It does not automatically launch JupyterLab.

User notebooks and results live in mounted host directories. The first Linux
`amd64` alpha is published as `deankrueger/cypher:alpha` and
`deankrueger/cypher:0.1.0-alpha.1`. PyNE, browser-hosted JupyterLab,
multi-architecture builds, and mature automated publishing are later
extensions.

See `docs/milestone-3.md` for the completed container milestone.

## Roadmap

1. Milestone one: metadata-driven authoring and hierarchical XML export.
2. Milestone two: safe, notebook-friendly Cyclus execution.
3. Milestone three: a published alpha of the notebook-ready ecosystem container.
4. Later: distribution maturity, parameter studies, reproducible discovery,
   and broader schema support as real usage demands them.

## Decisions intentionally deferred

- Reading existing XML and round-trip editing
- Flat-schema export
- Parameter studies
- Host-side Docker control
- Reproducible discovery lockfiles
- Fully expanded XML containing all defaults
- Generated comments
- PyNE integration
- Browser-hosted JupyterLab and classroom deployment
- Mature Docker image publishing automation
- PyPI and Conda publication policy
- Stable public names for every method shown in examples
- Long-term compatibility and deprecation policy

