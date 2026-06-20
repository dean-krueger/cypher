# Milestone 1: Bakery XML

Status: proposed for review  
Last updated: 2026-06-20

## Goal

Prove Cypher's central architecture by constructing a small Cyclus simulation
from Python objects and exporting deterministic, human-readable hierarchical XML
that Cyclus accepts.

The milestone is successful without running the simulation from Python. A user
may invoke Cyclus manually on the exported file.

## Target user experience

The target script should be close to:

```python
import cypher
import cypher.agents as agents
import cypher.cycamore as cycamore

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
institution.add_initial_facility(bakery, count=1)
institution.add_initial_facility(store, count=1)

region = agents.NullRegion("OneRegion")
region.add(institution)

simulation.add(recipe)
simulation.add(region)

simulation.validate()
simulation.export_to_xml("bakery.xml")
```

Exact method names may change during implementation if tests reveal a clearer
model. Changes should preserve the compositional workflow rather than weaken it.

## Required capabilities

### Executable resolution

- Resolve Cyclus from an explicit selection, then
  `CYPHER_CYCLUS_EXECUTABLE`, then `PATH`.
- Report the selected executable clearly.
- Use one selected executable consistently during a discovery or validation
  operation.
- Produce actionable errors when Cyclus cannot be located or invoked.

### Discovery

- Provide a `cypher discover` command.
- Obtain installed archetype metadata and schemas through Cyclus's discovery
  interface.
- Identify at least the built-in `agents` library and local Cycamore
  installation in the development integration environment.
- Normalize discovery output into an internal format usable without rerunning
  Cyclus.
- Cache enough provenance to identify the source environment and possible
  staleness.
- Produce a compatibility report.
- Warn prominently about unsupported schema constructs without making unrelated
  supported archetypes unavailable.
- Offer a strict mode that fails on unsupported constructs.

### Generated archetype interface

- Make discovered libraries importable through a form equivalent to
  `import cypher.cycamore as cycamore`.
- Expose at least `cycamore.Source`, `cycamore.Sink`, `agents.NullInst`, and
  `agents.NullRegion` in the integration environment.
- Permit the prototype name as the only positional argument.
- Permit configuration through keyword arguments and later assignment.
- Preserve dynamic archetype field names from metadata/schema.
- Provide useful signatures, docstrings, annotations, `help()` output, and
  editor/type-stub information.
- Preserve whether optional/defaulted values were explicitly assigned.

### Handwritten model

- Implement a top-level `Simulation`.
- Implement `Control` with at least duration, start year, and start month.
- Implement `Commodity`, including optional `solution_priority`.
- Implement `Recipe` with atom or mass basis and nuclide fractions.
- Provide a generic `Simulation.add(...)` entry point.
- Support nested region/institution relationships.
- Support initial facility deployment by prototype and count.
- Recursively collect nested objects, referenced prototypes, and required
  archetype declarations.
- Preserve insertion order.

### Validation

- Permit temporarily incomplete objects.
- Validate individual assigned values when constraints are unambiguous.
- Aggregate validation errors across the simulation.
- Detect at least:
  - missing required fields;
  - unknown or unavailable libraries/archetypes;
  - duplicate names within the same Cyclus namespace;
  - unresolved object or string references;
  - basic datatype/range violations available from metadata/schema;
  - structurally unsupported fields that cannot be serialized safely.
- Error messages identify the object, archetype, and field involved.
- Adding the same object instance more than once is harmless.
- Distinct conflicting objects fail clearly.

### XML export

- Export conventional hierarchical Cyclus XML.
- Use deterministic section and insertion ordering.
- Use consistent indentation and readable line breaks.
- Emit only archetype declarations actually required by the object graph, plus
  any explicitly requested declarations whose semantics require retention.
- Emit `<commodity>` only when settings such as `solution_priority` require it.
- Omit optional/defaulted archetype fields not explicitly set.
- Never omit explicitly supplied values silently.
- Avoid timestamps, absolute host paths, and generated comments.
- Write through a safe temporary file and replace the target only after
  successful validation and serialization, so failed export does not leave a
  partial XML file.

## Acceptance criteria

Milestone one is complete when all of the following are demonstrated:

1. A clean installation of Cypher can run unit tests without Cyclus installed.
2. `cypher discover` can inspect a prepared local development environment and
   report its compatible and unsupported archetypes.
3. The target bakery script can be written using discovered `agents` and
   Cycamore classes.
4. The script exports stable hierarchical XML representing its control block,
   archetypes, recipe, facility prototypes, region, institution, and initial
   facilities.
5. Repeated exports of the same object graph are byte-for-byte identical.
6. The generated XML passes validation by the same selected Cyclus
   installation.
7. Invalid variants produce consolidated, actionable error reports.
8. Generated classes are meaningfully inspectable through `help()`, IPython,
   and editor tooling.
9. The package builds successfully as both a source distribution and wheel.

## Test strategy

### Unit tests

Use small, checked-in fixtures representing normalized metadata and schema
fragments. Unit tests must not require Cyclus, Cycamore, Docker, Conda, or
network access.

Cover:

- executable-selection logic without launching real Cyclus;
- metadata normalization;
- generated field descriptors/signatures and assignment;
- default-versus-explicit field state;
- object graph traversal and idempotent addition;
- duplicate-name and reference errors;
- commodity priority behavior;
- deterministic XML;
- compatibility warnings and strict-mode failures;
- atomic export failure behavior.

### Golden XML

Check a readable expected bakery XML file into the test fixtures. Compare output
byte-for-byte after the serializer's format is intentionally established.

Golden-file changes require review for both semantic correctness and human
readability.

### Integration tests

Keep integration tests separately selectable. In a prepared environment they
should:

- invoke the selected Cyclus executable for discovery;
- confirm expected local archetypes are visible;
- build and export the bakery input;
- ask that same Cyclus installation to validate the XML.

An unavailable integration environment should produce an explicit skip, not a
false pass or a unit-test failure.

### Repository checks

```console
ruff check .
pytest
python -m build
python -m twine check dist/*
```

## Explicit non-goals

Milestone one does not include:

- `Simulation.run()` or output database management;
- XML import or round-trip editing;
- flat-schema XML;
- Cymetric or PyNE integration;
- parameter sweeps;
- Docker image creation or host-side container orchestration;
- automatic installation of Cyclus or archetype libraries;
- PyPI or Conda publication;
- a frozen stable public API;
- exhaustive support for every Relax NG construct;
- hard-coded Cycamore or third-party archetype classes;
- preserving comments or formatting from existing XML;
- automatically emitting every Cyclus default.

## Review questions before implementation

The following details are intentionally allowed to move during the first
implementation pass:

- the exact spelling of nesting/deployment methods;
- whether `simulation.add_library(...)` retains all library declarations or
  serves primarily as an availability assertion;
- how generated runtime modules and `.pyi` files are exposed to Python's import
  system;
- the platform-specific cache location and stale-cache policy;
- the normalized schema representation;
- which safe generic escape hatch is viable for unsupported archetype fields.

Any choice should preserve the project's north stars and remain replaceable
while the package is pre-alpha.

