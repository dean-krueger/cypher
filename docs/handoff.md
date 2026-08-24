# Project Handoff

Last updated: 2026-08-24
Current planning branch: `nested-types`

This document records short-term implementation state so development can resume
without relying on chat history. Durable project rules remain in `AGENTS.md`;
product direction remains in `docs/design.md`.

## Current state

Milestones one, two, three, and four are ready from the prior branches.
Milestone three was published to Docker Hub as an alpha and successfully tested
on a second Linux computer. Milestone four is implemented, locally validated,
and folded into the current milestone-five documentation push.

Implemented capabilities:

- Cyclus executable selection:
  1. explicit CLI/API path;
  2. `CYPHER_CYCLUS_EXECUTABLE`;
  3. `cyclus` on `PATH`.
- `cypher discover` metadata discovery and environment-local caching.
- Compatibility reports and strict discovery mode.
- Dynamic archetype-library imports such as `cypher.cycamore`.
- Runtime archetype classes with signatures, docstrings, assignment
  validation, default inspection, and explicit-value tracking.
- Generated environment-local `.pyi` type stubs.
- Handwritten `Simulation`, `Control`, `Commodity`, and `Recipe` objects.
- Nested region/institution composition and initial facility deployment.
- Recursive object/dependency collection.
- Consolidated simulation validation.
- Deterministic, atomic export of conventional hierarchical Cyclus XML.
- Safe, notebook-friendly `Simulation.run()` execution.
- Predictable input/output naming with persistent defaults and per-run
  overrides.
- No-overwrite-by-default behavior and explicit replacement.
- Live output streaming with complete stdout/stderr capture.
- Cyclus verbosity levels and guarded advanced CLI arguments.
- Structured `RunResult`, `RunError`, and preflight `RunConfigurationError`.
- A complete runnable bakery example in `examples/bakery.py`.
- Milestone-five user documentation in `docs/user-guide.md`.
- Scenario documentation in `docs/examples.md`.
- A technical reviewer code tour in `docs/code-tour.md`.
- An OpenMC comparison note in `docs/openmc-comparison.md`.
- Larger non-authoritative authoring examples in `examples/once_through.py`
  and `examples/eg23_transition.py`, based on older XML files.
- A notebook-ready Linux `amd64` image based on the official Cymetric image.
- Preinstalled IPython and a registered `Python (Cypher)` Jupyter kernel.
- A scientific notebook stack containing NumPy, pandas, Matplotlib, SciPy, and
  Seaborn.
- Graphviz system and Python support for Cymetric flow graphs.
- Build-time discovery, component verification, real kernel launch, and bakery
  smoke test.
- Generated full-schema discovery via `cyclus -n`, with automatic XML headers
  pointing at the cached full Relax NG schema.
- Optional scalar Cyclus control fields beyond duration, start year, and start
  month.
- Recursive validation, type information, examples, and XML serialization for
  standard nested C++ scalar, vector, list, set, pair, and map archetype fields.
- Faithful live-tested Cycamore Mixer and Separations stream serialization.

Cypher's workflow intentionally ends at the SQLite output. Cymetric remains
responsible for database querying and analysis.

## Verification completed

- Current fixture-backed suite: 86 tests passed.
- Two opt-in integration tests are skipped unless `CYPHER_TEST_CYCLUS` is set;
  once configured, an invalid executable or metadata-discovery failure fails
  the suite.
- Ruff lint and formatting checks passed.
- Source distribution and wheel built successfully.
- Both distributions passed `twine check` when run with packaging tooling new
  enough to understand PEP 639 license metadata.
- The built wheel imported and exposed its CLI from an isolated target
  directory.
- Live testing used the local image:
  `ghcr.io/cyclus/cymetric_24.04_apt/cymetric:latest`.
- Live discovery found 19 archetypes across `agents` and `cycamore`.
- The bakery example exported XML that Cyclus accepted and ran successfully,
  producing a SQLite output.
- The milestone-two bakery workflow ran through `Simulation.run()` in the
  Cymetric container, streamed normal output, returned a successful
  `RunResult`, and produced a nonempty SQLite database.
- Local image `cypher:milestone-3` built successfully from the official
  Cymetric image.
- Image verification confirmed Cyclus, Cycamore, Cymetric, Cypher, IPython,
  ipykernel, the discovery cache, and a valid UTF-8 locale.
- The registered `Python (Cypher)` kernel launched and imported Cypher.
- A detached `sleep infinity` container with a host-mounted `/workspace` ran
  the bakery simulation and persisted readable XML and SQLite files.
- Final image architecture: Linux `amd64`; image ID begins
  `sha256:e3e57faee23f` and size is approximately 891 MB.
- Docker Hub tags `deankrueger/cypher:alpha` and
  `deankrueger/cypher:0.1.0-alpha.1` reference that image.
- The published alpha was pulled and exercised through VS Code Dev Containers
  on a second Linux computer; imports, notebooks, simulation execution,
  scientific packages, and Cymetric Graphviz support worked.
- Local image `cypher:milestone-4` built successfully from the official
  Cymetric image after milestone-four changes.
- Final local milestone-four image: `cypher:milestone-4`, image ID beginning
  `sha256:8c88f8d2cce8`, size approximately 4.11 GB.
- The milestone-four image verifier confirmed the registered kernel can import
  the scientific stack and execute a simple `matplotlib.pyplot.plot(...)`
  call.
- `cypher discover` in the milestone-four image cached a generated full Relax
  NG schema from `cyclus -n` at
  `/root/.cache/cypher/schemas/cyclus-full-schema.rng`.
- The milestone-four bakery smoke test exported XML with an `xml-model` header
  pointing at the cached full schema and Cyclus accepted the input.

The original GitHub packaging checks failed because modern setuptools rejects
the legacy BSD license classifier when a PEP 639 license expression is also
present. The redundant classifier has been removed. Local `twine check` should
use a recent `packaging` release; the optional dev dependency now requires
`packaging>=24.2`.

## Docker development workflow

Build the repository image:

```console
docker build -t cypher:milestone-4 .
```

Start the VS Code Dev Containers target with a persistent host workspace:

```console
docker run -d \
  --name cypher-dev \
  -v "$PWD/my_project:/workspace" \
  -w /workspace \
  cypher:milestone-4 \
  sleep infinity
```

Attach VS Code to `cypher-dev`, open `/workspace`, and choose
`Python (Cypher)` for notebooks. Cypher, Cyclus, Cycamore, Cymetric, and the
discovery cache are already installed. Full instructions are in
`docs/container.md`.

## Known limitations and design notes

- Compatibility warnings are nonfatal during ordinary discovery and are shown
  in its report. `--strict` makes them fatal.
- The tested environment still reports nonfatal compatibility warnings for a
  small number of imperfect range annotations, plus experimental warnings
  emitted by Cyclus and its archetype libraries.
- Generated stubs are written to Cypher's environment cache. Runtime imports
  work from the cache; editor configuration may need refinement before every
  IDE automatically discovers those external stubs.
- The local WSL Cyclus build was not runnable during implementation because
  several linked libraries were unavailable. Container integration supplied the
  authoritative live test instead.
- Archetype-library declarations are inferred from objects actually used.
  `Simulation.add_library()` currently acts as an availability assertion and
  requires used archetypes to come from an added library.
- Optional/defaulted archetype fields are omitted unless explicitly assigned.
- The official Cymetric base and current Cypher image are Linux `amd64` only;
  multi-architecture and native Apple Silicon support are out of scope.
- The public API remains pre-alpha and should be refined from hands-on use.

## Nested field implementation

The `nested-types` branch adds a recursive `ValueShape` model derived from
Cyclus annotation types. It resolves annotation indirection used by Mixer and
Separations, validates the XML alias tree during discovery, generates recursive
runtime and stub annotations, validates nested Python values with precise error
paths, and serializes the type and alias trees together.

Maps accept either mappings or sequences of two-item tuples. Generated classes
provide alias-aware `field_example(name)`, raw `field_example_value(name)`, and
`describe_field(name)` so notebook users can inspect complicated fields without
reading C++ source. The compact Python-shaped template labels positions with
aliases such as `commod`, `buf_size`, `comp`, and `eff` without repeating the
full recursive type at every nesting level.

Execution streaming now reads bounded byte chunks and synchronizes display
writes instead of flushing one character at a time. This preserves complete,
separate stdout and stderr capture while preventing severely fragmented Cyclus
output in Jupyter notebooks.

Fixture coverage includes Mixer, Separations, and a stress type equivalent to
`map<string, map<string, pair<double, string>>>`. Live container validation
discovered the installed Cycamore metadata and successfully ran a one-timestep
simulation containing a recursively nested Mixer through Cyclus 1.6.0.

## Completed milestone-four work

Milestone four implementation is complete locally:

- `Control` now uses table-driven scalar field metadata.
- The base scalar control fields from the Cyclus grammar serialize in grammar
  order when explicitly supplied.
- Invalid scalar control assignments such as bad months, unsupported decay
  modes, string booleans, and nonpositive seeds fail before XML export.
- `Simulation` defaults to automatic schema-header generation using the
  discovered full schema path when available.
- `Simulation.to_xml()` and `Simulation.export_to_xml()` accept `schema_path`
  overrides and emit the Cyclus-style `xml-model` processing instruction.
- Users can pass `schema_path=None` to omit the header.
- XML export computes a relative schema `href` from the output path when
  practical.
- Discovery calls `cyclus --rng-schema` for base-schema provenance, runs
  `cyclus -n` in a temporary directory, copies the generated full Relax NG
  schema into the Cypher cache, and reports both paths through compatibility
  output. Missing support remains nonfatal.
- The Dockerfile pins `matplotlib-inline` to the 0.1 series so notebook
  plotting remains compatible with the Ubuntu Matplotlib 3.6 package in the
  Cymetric base image.
- The image verifier now launches the registered kernel and executes a simple
  `plt.plot(...)` smoke test.

## Milestone-five documentation work

Milestone five now focuses on documentation rather than API redesign. The
OpenMC comparison suggested small polish opportunities, but no large changes
were needed before writing the guide and reviewer material.

The current documentation set emphasizes that the container is the recommended
evaluation path. Ordinary `pip` installation under the `cyclus-cypher` package
name, and possible Conda support, are planned follow-on work rather than
completed milestone-five capabilities.

## Feedback collection

Small observations can be kept in personal notes and pasted into the next
prompt. For longer testing sessions, create `docs/refinement-notes.md` with
short entries containing:

- what you attempted;
- the smallest reproducing code;
- what happened;
- what you expected;
- whether it felt like a bug, usability issue, or new feature.

That file should be treated as a working notebook, not durable architecture.
