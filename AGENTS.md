# Cypher Contributor Guidance

This file contains durable instructions for humans and coding agents working in
this repository. Product direction belongs in `docs/design.md`, and the current
implementation target belongs in `docs/milestone-1.md`.

## Project purpose

Cypher is a Python front-end for authoring inputs for
[Cyclus](https://github.com/cyclus/cyclus). Its primary interface should let
users build a simulation from composable Python objects and export readable,
valid Cyclus XML.

The project's north stars are:

1. Treat Cyclus metadata and schemas as authoritative so Cypher remains in sync
   with Cyclus and independently developed archetype libraries.
2. Offer an object-oriented authoring experience inspired by OpenMC's Python
   interface.
3. Minimize long-term maintenance, especially maintenance caused by duplicating
   information already supplied by Cyclus or its archetypes.

## Sources of truth

When sources disagree, use this order:

1. Metadata and annotations reported by the selected Cyclus installation.
2. Archetype Relax NG schemas reported by Cyclus.
3. The Cyclus base simulation grammar.
4. Small, documented Cypher policies needed for Python ergonomics.

Do not inspect or parse Cycamore or third-party source code to construct their
public Cypher interfaces. Do not hard-code a catalogue of archetype libraries,
archetypes, or archetype fields.

Keep handwritten support for stable, core Cyclus concepts separate from
metadata-driven archetype support.

## Compatibility principles

- Cypher must not be a dependency of Cyclus or any archetype library.
- Importing `cypher` must not run Cyclus, discover archetypes, access the
  network, or mutate the user's environment.
- Discovery must not assume Conda, Docker, or a particular installation prefix.
- Resolve the Cyclus executable in this order:
  1. an explicit API or CLI argument;
  2. `CYPHER_CYCLUS_EXECUTABLE`;
  3. `cyclus` on `PATH`.
- Use the same resolved executable for discovery and authoritative validation
  within one operation. Do not silently mix installations.
- Put all subprocess interaction with Cyclus behind a narrow adapter that can be
  replaced with a test double.
- Keep the core package usable from cached metadata without requiring a live
  Cyclus subprocess for every authoring session.
- Keep the package installable with ordinary `pip`.

## Public API principles

- Favor composable domain objects collected by a top-level `Simulation`.
- Favor the concise archetype form
  `cycamore.Source("Mine", outcommod=commodity)` while retaining a uniform
  internal prototype representation.
- Allow an archetype prototype's name as its sole positional argument. Require
  configuration fields to be keyword arguments.
- Permit incremental construction. Missing required fields may exist
  temporarily, but `validate()` and `export_to_xml()` must reject incomplete
  simulations with a consolidated, actionable report.
- Validate supplied values early when constraints are unambiguous and cheap to
  check. Cyclus remains the final authority.
- Support object references and string references where practical. Encourage
  object references because they enable typo detection and safe renaming.
- Recursively collect nested objects and their dependencies when an object is
  added to a simulation.
- Adding the same object more than once should be idempotent. Distinct objects
  with conflicting names in the same Cyclus namespace must produce a clear
  error.
- Stable handwritten APIs may use idiomatic Python names. Dynamically generated
  archetype fields must preserve their schema/XML names unless an explicit,
  documented compatibility policy says otherwise.
- Preserve whether an optional field was explicitly assigned. Omit unassigned
  optional/defaulted fields from XML so Cyclus applies its authoritative
  defaults.
- Generated classes and stubs should provide useful signatures, type
  information, docstrings, `help()` output, editor hover information, and
  IPython/Jupyter introspection.

## Discovery and generated interfaces

- `cypher discover` should inspect the selected Cyclus environment, normalize
  its metadata, report compatibility, and create refreshable environment-local
  interfaces and type information.
- Discovery output is environment-specific. Record enough provenance to detect
  stale data, including the selected executable and available Cyclus/archetype
  version information when reported.
- Unsupported schema constructs must never be silently ignored or guessed.
- Normal discovery may succeed with prominent warnings and a compatibility
  report when some constructs are unsupported.
- Keep unaffected archetypes usable when one archetype contains an unsupported
  construct.
- Provide a generic configuration escape hatch where it can preserve data
  safely. Strict discovery may fail on unsupported constructs.
- Do not commit environment-generated interfaces as the normal workflow.
  Reproducible export or locking may be added as a later, explicit feature.

## XML and validation

- Milestone one exports the conventional hierarchical Cyclus XML format.
- XML must be deterministic, consistently indented, and easy for a human to
  review.
- Preserve user insertion order where Cyclus permits it.
- Use stable section ordering that resembles conventional handwritten Cyclus
  inputs.
- Do not add timestamps, host paths, or other machine-specific data to XML.
- Do not generate comments unless a later requirement establishes their value.
- Never silently discard a user value or serialize a different interpretation
  without reporting it.
- Error messages should identify the affected object, archetype, field, and
  source constraint whenever available.
- Cyclus validation is required in integration coverage, but ordinary unit
  tests must not require a Cyclus installation.

## Dependency and implementation discipline

- Prefer the Python standard library and a small dependency surface.
- Keep the normalized metadata model independent of subprocess output and
  generated Python presentation.
- Keep serialization independent of discovery so fixture-backed unit tests can
  exercise it.
- Favor reversible designs while the public API is pre-alpha.
- Do not implement XML import, simulation execution, output analysis, parameter
  studies, Docker orchestration, or package publishing unless the current task
  explicitly includes them.
- Do not register names, upload distributions, publish containers, push
  branches, or create releases without explicit user authorization.

## Testing and verification

For implementation changes, add the narrowest useful tests and run all
available checks relevant to the change:

```console
ruff check .
pytest
python -m build
python -m twine check dist/*
```

Tests should include:

- unit tests backed by small checked-in metadata/schema fixtures;
- deterministic XML or golden-file tests;
- failure tests for incomplete objects, duplicate names, unavailable libraries,
  unsupported constructs, and stale discovery data;
- focused integration tests against a real Cyclus installation when the
  environment provides one.

Do not make the default unit-test suite depend on Cyclus, Cycamore, Conda,
Docker, or network access. Clearly report checks that could not run.

