# Project Handoff

Last updated: 2026-06-20  
Current implementation branch: `milestone-one`

This document records short-term implementation state so development can resume
without relying on chat history. Durable project rules remain in `AGENTS.md`;
product direction remains in `docs/design.md`.

## Current state

Milestone one is implemented but not yet committed on the branch named above.

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
- A complete bakery example in `examples/bakery.py`.

`Simulation.run()`, XML import, output analysis, Docker-image publication, and
flat-schema export remain deferred.

## Verification completed

- Fixture-backed suite: 22 tests passed.
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

The original GitHub packaging checks failed because modern setuptools rejects
the legacy BSD license classifier when a PEP 639 license expression is also
present. The redundant classifier has been removed.

## Docker development workflow

Mounting the repository makes its files visible but does not install the Python
package. Use either an editable install:

```console
python -m pip install -e /cypher
cypher discover
```

or, for a quick source-tree experiment:

```console
export PYTHONPATH=/cypher/src
python -m cypher discover
```

The editable install is preferred because it also installs the `cypher`
command. Run discovery inside the same container/environment whose Cyclus and
archetype libraries should be used.

The existing Cymetric image already contains runnable Cyclus and Cycamore
installations. Mounting and rebuilding separate Cyclus/Cycamore source trees is
only necessary when testing changes to those source versions. If rebuilt, they
must also be installed or exposed through the normal Cyclus executable and
module search environment before running discovery.

Jupyter or IPython must separately be available in the selected image. A
notebook server also requires a published port and an appropriate working
directory.

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
- The public API remains pre-alpha and should be refined from hands-on use.

## Suggested next session

1. Review and manually exercise `docs/usage.md` and `examples/bakery.py`.
2. Record usability surprises, desired spellings, confusing errors, and missing
   workflows.
3. Decide whether those findings are milestone-one defects or later features.
4. Add focused regression tests before changing behavior.
5. Update this handoff after major implementation or verification changes.

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
