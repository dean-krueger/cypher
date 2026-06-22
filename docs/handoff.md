# Project Handoff

Last updated: 2026-06-22
Current planning branch: `milestone-three`

This document records short-term implementation state so development can resume
without relying on chat history. Durable project rules remain in `AGENTS.md`;
product direction remains in `docs/design.md`.

## Current state

Milestones one and two are merged into `main`. Milestone three is implemented
on `milestone-three`, published to Docker Hub as an alpha, and successfully
tested on a second Linux computer.

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
- A notebook-ready Linux `amd64` image based on the official Cymetric image.
- Preinstalled IPython and a registered `Python (Cypher)` Jupyter kernel.
- A scientific notebook stack containing NumPy, pandas, Matplotlib, SciPy, and
  Seaborn.
- Graphviz system and Python support for Cymetric flow graphs.
- Build-time discovery, component verification, real kernel launch, and bakery
  smoke test.

Cypher's workflow intentionally ends at the SQLite output. Cymetric remains
responsible for database querying and analysis.

## Verification completed

- Fixture-backed suite after milestone-three implementation: 58 tests passed.
- One opt-in integration test skipped unless `CYPHER_TEST_CYCLUS` is set.
- Ruff lint and formatting checks passed.
- Source distribution and wheel built successfully.
- Both distributions passed `twine check`.
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

The original GitHub packaging checks failed because modern setuptools rejects
the legacy BSD license classifier when a PEP 639 license expression is also
present. The redundant classifier has been removed.

## Docker development workflow

Build the repository image:

```console
docker build -t cypher:milestone-3 .
```

Start the VS Code Dev Containers target with a persistent host workspace:

```console
docker run -d \
  --name cypher-dev \
  -v "$PWD/my_project:/workspace" \
  -w /workspace \
  cypher:milestone-3 \
  sleep infinity
```

Attach VS Code to `cypher-dev`, open `/workspace`, and choose
`Python (Cypher)` for notebooks. Cypher, Cyclus, Cycamore, Cymetric, and the
discovery cache are already installed. Full instructions are in
`docs/container.md`.

## Known limitations and design notes

- Compatibility warnings are nonfatal during ordinary discovery and are shown
  in its report. `--strict` makes them fatal.
- The tested Cymetric environment currently reports compatibility warnings for
  several complex or imperfectly annotated fields. These do not prevent Source,
  Sink, NullInst, or NullRegion from supporting the bakery workflow.
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

## Suggested next session

1. Merge the reviewed `milestone-three` branch.
2. Gather usability feedback from additional Cyclus users.
3. Define the next milestone only after prioritizing that feedback; likely
   candidates include distribution polish, broader examples, and generated
   editor-interface refinement.

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
