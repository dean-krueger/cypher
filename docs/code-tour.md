# Reviewer Code Tour

This document is a guided tour of Cypher's implementation. It is written for
technical reviewers who want enough detail to understand the architecture
before opening every source file.

Cypher's core promise is narrow: let users author Cyclus inputs with Python
objects, while keeping the installed Cyclus environment as the source of truth
for available archetypes and schema details. The code is organized around that
promise.

The shortest mental model is:

1. `cypher discover` asks a real Cyclus executable what archetypes and schemas
   are available.
2. Discovery normalizes that data into a cached `Catalog`.
3. Importing `cypher.cycamore` or `cypher.agents` dynamically creates Python
   classes from the catalog.
4. Users build a `Simulation` with handwritten Cyclus concepts and discovered
   archetype prototypes.
5. `Simulation` validates the object graph and serializes deterministic
   hierarchical XML.
6. `Simulation.run()` writes XML and launches Cyclus as an external process.

The rest of this tour follows that path.

## Source Layout

The package lives under `src/cypher/`.

- `__init__.py` defines the public import surface and installs the dynamic
  archetype-library import hook.
- `__main__.py` lets `python -m cypher` route to the command-line interface.
- `_imports.py` implements imports such as `import cypher.cycamore`.
- `cli.py` exposes `cypher discover` and `cypher compatibility`.
- `discovery.py` is the subprocess boundary for talking to Cyclus.
- `catalog.py` defines normalized metadata objects and cache handling.
- `shapes.py` models and validates recursive C++ container value shapes.
- `archetype.py` builds runtime classes for discovered archetypes.
- `core.py` defines handwritten simulation objects and graph validation.
- `xml.py` serializes validated simulations to hierarchical Cyclus XML.
- `execution.py` owns filesystem path resolution and Cyclus process execution.
- `errors.py` contains project-specific exception types.

Tests live in `tests/`. Most tests use fixture-backed metadata and should not
require Docker, network access, or a live Cyclus install. The optional
integration test is gated behind `CYPHER_TEST_CYCLUS`.

## Public Import Surface

`src/cypher/__init__.py` is intentionally small. It exports:

- handwritten authoring objects: `Simulation`, `Control`, `Commodity`,
  `Recipe`;
- catalog helpers: `Catalog`, `get_catalog`, `set_catalog`;
- execution result type: `RunResult`;
- project exceptions such as `DiscoveryError`, `ValidationError`, `RunError`;
- `__version__`.

It also calls `install_library_finder()` from `_imports.py`. That is important:
ordinary `import cypher` installs the hook needed for dynamic archetype
libraries, but it does **not** run Cyclus. If no discovery cache exists, the
base package can still import.

This boundary is one of the project's central safety properties. Importing
Cypher should be cheap and side-effect-light; discovery and execution are
explicit operations.

## Command-Line Entrypoints

`src/cypher/cli.py` defines two commands.

`cypher discover`:

- accepts `--cyclus` to select a Cyclus executable;
- accepts `--cache` to override the metadata cache path;
- accepts `--strict` to turn compatibility warnings into failures;
- calls `discovery.discover()`;
- prints a compatibility report;
- reports the cache path and generated stub location.

`cypher compatibility`:

- loads the current cache;
- prints the same compatibility report without rerunning discovery.

The CLI catches `CypherError` subclasses and returns status code `2` for
project-level failures. Unexpected Python exceptions are allowed to surface as
normal bugs.

## Executable Selection

`discovery.resolve_cyclus_executable()` chooses the Cyclus executable in a
fixed order:

1. an explicit path from the caller or CLI;
2. `CYPHER_CYCLUS_EXECUTABLE`;
3. `cyclus` on `PATH`.

Explicit and environment-provided paths must exist, be files, and be
executable. This validation happens before any subprocess call so discovery
errors are phrased in Cypher terms rather than as raw `OSError`s where
possible.

The same selection idea appears again during execution. `Simulation.run()` can
receive a `cyclus_executable` override, otherwise execution resolves Cyclus in
the same broad way. If execution uses a different executable than discovery,
Cypher warns that the metadata may not match the runtime environment.

## CyclusAdapter

`discovery.CyclusAdapter` is the narrow subprocess wrapper around one selected
executable. It has a deliberately small surface:

- `version()` runs `cyclus --version`;
- `metadata()` runs `cyclus --metadata` and parses JSON;
- `base_schema_path()` runs `cyclus --rng-schema`;
- `full_schema_path()` runs `cyclus -n` in a temporary directory and copies
  the generated full Relax NG schema into the Cypher cache.

`_run()` uses `subprocess.run(..., capture_output=True, text=True)`. Discovery
does not stream output because it is collecting metadata rather than running a
long simulation.

`metadata()` treats invalid JSON or non-object JSON as invocation failures. It
also records stderr lines as discovery warnings, because Cyclus can emit useful
warnings even when the metadata command succeeds.

The full schema step deserves special attention. Cyclus's base RNG schema is
not the same thing as the complete schema for the installed environment.
`cyclus -n` writes a skeleton input with an `xml-model` header pointing at the
full generated schema. Cypher reads that header, copies the referenced schema
into its cache under `schemas/cyclus-full-schema.rng`, and stores that cached
path in the catalog. XML export later uses this path for the default schema
header.

If base-schema or full-schema discovery fails, discovery remains nonfatal.
Cypher records warnings and proceeds with archetype metadata when possible.

## Discovery Flow

`discovery.discover()` coordinates the whole discovery operation:

1. create a `CyclusAdapter`;
2. collect metadata;
3. collect base schema provenance;
4. generate and cache the full schema;
5. stat the executable for stale-cache detection;
6. create a `Catalog` with `Catalog.from_metadata()`;
7. optionally fail on compatibility warnings in strict mode;
8. save the catalog;
9. write environment-local type stubs;
10. set the active in-process catalog.

The result is a `DiscoveryResult` containing the catalog, the saved cache path,
and generated stub paths.

The saved cache is what enables normal authoring sessions to import dynamic
libraries without rerunning Cyclus. It also lets tests inject fixture metadata
instead of depending on a live simulator.

## Catalog Data Model

`catalog.py` defines three main metadata types.

`FieldSpec` describes one archetype input field:

- `name`: the Python-facing field name;
- `alias`: the XML field name or nested alias path;
- `cpp_type`: the type reported or inferred from metadata/schema;
- `required`: whether the schema requires the field;
- `default` and `has_default`: default handling from annotations;
- `doc`: field documentation;
- `uitype`: semantic hints such as recipe, commodity, or prototype;
- `value_range`: numeric bounds when annotations provide a usable range.

`FieldSpec.python_type` maps C++/schema-ish types onto simple Python runtime
checks: `int`, `float`, `bool`, `str`, `list`, or `object`.

`ArchetypeSpec` describes one archetype:

- full Cyclus `path:library:name` spec;
- split path/library/name components;
- entity type such as facility, region, or institution;
- archetype documentation;
- ordered field specs;
- raw schema string;
- compatibility warnings.

`Catalog` groups archetypes by library and stores provenance:

- selected executable;
- Cyclus version;
- executable modification time;
- base schema path;
- generated full schema path;
- discovery warnings;
- cache format version.

The catalog exposes `library(name)` and `get(library, name)` helpers that
raise `DiscoveryError` with available alternatives. That keeps import and user
errors more actionable.

## Cache Handling

`cache_root()` follows normal platform conventions:

- `CYPHER_CACHE_DIR` if set;
- `%LOCALAPPDATA%/cypher` on Windows;
- `$XDG_CACHE_HOME/cypher` or `~/.cache/cypher` on POSIX.

`cache_file()` is `catalog.json` inside that root.

`Catalog.save()` writes JSON to a temporary sibling and atomically replaces the
target. `Catalog.load()` validates that the file exists, contains JSON, and
uses a supported cache format. Missing caches produce the familiar instruction
to run `cypher discover`.

`Catalog.stale_reason()` compares the recorded executable mtime with the
current executable. This is intentionally a warning-level check. It tells users
that the environment may have changed without making every import or
compatibility report fail.

## Metadata Normalization

`Catalog.from_metadata()` receives the raw `cyclus --metadata` object. It
expects:

- `annotations`: archetype annotations keyed by full spec;
- `schema`: archetype schema fragments keyed by full spec;
- `specs`: a list of full archetype spec strings.

Each spec is split with `split_spec()`, then `_normalize_fields()` combines the
annotation data with the archetype schema fragment.

`_normalize_fields()` wraps each schema fragment in a Relax NG grammar element
so `ElementTree` can parse it. It then finds top-level input elements and
matches them to annotation variables. If a schema element lacks a corresponding
annotation variable, Cypher still creates a field spec from the schema and
records a warning.

The normalizer intentionally interprets only a conservative subset of Relax NG:

- `grammar`;
- `interleave`;
- `optional`;
- `element`;
- `data`;
- `text`;
- `oneOrMore`;
- `zeroOrMore`;
- `documentation`;
- `param`.

Other schema constructs are reported as compatibility warnings. This is a
major reason strict mode exists: the project can be transparent about partial
support without blocking basic workflows by default.

Annotation variables can refer to another variable name, as Cycamore does for
the public Mixer `in_streams` and Separations `streams` fields. Normalization
resolves that indirection before building the `FieldSpec`; otherwise the real
container type and XML alias tree would be lost.

`shapes.py` parses supported scalar types and recursive combinations of
`std::vector`, `std::list`, `std::set`, `std::pair`, and `std::map` into a
`ValueShape` tree. Discovery checks the accompanying XML alias tree against
that shape and reports a compatibility warning rather than guessing when the
two cannot be reconciled.

## Compatibility Reports

`discovery.compatibility_report()` renders:

- executable path;
- Cyclus version;
- base schema path;
- generated full schema path;
- discovered libraries;
- archetype count;
- archetype compatibility warnings;
- discovery process warnings;
- stale cache warning, if applicable.

This report is meant for users and reviewers. It explains what Cypher thinks
the active environment is, and where support is incomplete.

## Generated Type Stubs

`discovery.write_stubs()` writes `.pyi` files under the cache root:

```text
<cache>/stubs/cypher/<library>.pyi
```

Each discovered library receives a stub module with one class per archetype.
The generated signatures include:

- `name: str | None = ...`;
- required fields without defaults;
- optional fields with `= ...`;
- coarse Python types derived from field metadata.

The stubs are environment-local because the available archetypes are
environment-local. Runtime imports work from the catalog regardless of whether
an editor discovers those stubs. Editor configuration is therefore a usability
layer, not a runtime dependency.

## Dynamic Library Imports

`_imports.py` implements the dynamic module hook.

`_LibraryFinder` is both a `MetaPathFinder` and `Loader`. It handles only
module names that:

- start with `cypher.`;
- have exactly one dot, such as `cypher.cycamore`;
- match a library present in the active or cached catalog.

It deliberately does not intercept deeper imports. That keeps the hook narrow
and avoids surprising Python's import system.

When Python imports `cypher.cycamore`, the loader:

1. loads the active catalog, or the cache if no active catalog is set;
2. looks up the requested library;
3. calls `make_archetype_class()` for each archetype in that library;
4. installs those classes into the module dictionary;
5. sets `__all__` and a short module docstring.

If there is no cache, the finder returns `None`, so the import fails naturally
instead of running discovery implicitly.

## Runtime Archetype Classes

`archetype.py` contains the machinery behind classes like
`cypher.cycamore.Source`.

`make_archetype_class()` creates a new Python class with:

- base class `Prototype`;
- `_archetype` pointing to the `ArchetypeSpec`;
- generated `__module__`;
- generated `__doc__`;
- generated `__annotations__`;
- generated `__signature__`.

The generated signature orders required fields before optional fields. This is
primarily for help output, notebooks, and editor introspection. The class does
not define a custom `__init__`; it inherits `Prototype.__init__`, which accepts
`name` and arbitrary keyword configuration.

`_class_doc()` builds a docstring that lists required fields, optional fields,
defaults, field documentation, and compatibility warnings. This is intentionally
plain text so `help(cycamore.Source)` remains useful in terminals and
notebooks.

## Prototype Semantics

`Prototype` is the runtime object users instantiate for archetypes.

Important attributes:

- `_values`: field values explicitly assigned by the user;
- `_explicit`: field names that should be serialized;
- `_children`: institutions nested under a region;
- `_initial_facilities`: facility prototypes initially deployed by an
  institution;
- `name`: the Cyclus prototype/agent name.

Unknown configuration keywords fail in `Prototype.__init__` with a list of
available fields. Unknown assignment after construction fails in
`__setattr__`. This makes typos visible before XML export.

`__getattr__` returns explicitly assigned values, field defaults when known, or
`None`. This lets users inspect defaults without those defaults becoming
explicit XML output.

`__setattr__` recursively validates scalar and container values, including
precise paths to invalid nested leaves. It also accepts `Commodity` objects for
fields marked as commodity-like and `Recipe` objects for fields marked as
recipe-like. Full input and simulation-semantic validation still belongs to
Cyclus.

Generated classes expose `field_example(name)`, `field_example_value(name)`,
and `describe_field(name)` for IPython discovery. The formatted example maps
container positions to XML aliases in a compact Python-shaped template. All
three use the same `ValueShape` that drives signatures, stubs, validation, and
serialization, preventing examples from drifting away from the implemented
input contract.

`explicit_items()` yields field specs and values in discovered field order, but
only for explicitly assigned fields. This is the mechanism that prevents Cypher
from writing optional defaults the user did not set.

Hierarchy helpers live here because they are archetype-agnostic Cyclus
concepts:

- `region.add(institution)` nests institutions below regions;
- `institution.add_initial_facility(facility, count=1)` records initial
  facility deployments.

These helpers validate entity types. A facility cannot contain an institution,
and a region cannot initially deploy a facility directly.

## Handwritten Core Concepts

`core.py` defines stable Cyclus input concepts that are not discovered
archetypes.

`Control` stores top-level simulation settings. Field metadata lives in
`CONTROL_FIELDS`, a table of `ControlField` objects. This table drives:

- assignment validation;
- required-field validation;
- XML field names;
- deterministic output order.

Required fields are currently duration, start year, and start month. Optional
scalar fields include simhandle, decay, dt, explicit inventory flags,
tolerances, seed, and stride. Validation is intentionally limited to clear
scalar constraints: type checks, month range, nonnegative or positive numeric
bounds, and the known decay choices.

`Commodity` is a named exchange commodity plus optional solver priority.
Commodities stringify to their names, and XML serialization writes only a
`commodity` block when `solution_priority` is supplied.

`Recipe` is a named material composition with a basis and nuclide-fraction map.
It validates:

- nonempty name;
- basis is `atom` or `mass`;
- nonempty composition;
- nuclide identifiers are strings or integers;
- fractions are numeric and nonnegative.

These objects keep common authoring mistakes near the authoring site while
leaving complete physics and schema validation to Cyclus.

## Simulation As Composition Root

`Simulation` is the main user-facing object in `core.py`.

Constructor inputs:

- optional `Control`;
- optional semantic `name`;
- optional persistent `input_path`;
- optional persistent `output_path`;
- optional `schema_path`;
- optional injected `Catalog`.

The `catalog` property returns the injected catalog when supplied, otherwise it
tries to load the active/cached catalog with `required=False`. This matters for
tests and for workflows that want to build some objects before discovery is
available.

`Simulation.add_library(name)` is an availability assertion. It checks that the
library exists in the catalog and records it. If any libraries are explicitly
added, validation later requires used archetypes to come from those libraries.
If no libraries are added, Cypher can still infer the XML `<archetypes>` block
from the object graph.

`Simulation.add()` accepts `Control`, `Recipe`, `Commodity`, and `Prototype`
objects. Adding the same instance twice is idempotent. Adding a different
control block after one is already present raises a `ValueError`.

## Graph Collection

`Simulation.graph()` walks from root objects and returns a `Graph` dataclass
containing:

- recipes;
- commodities;
- facility prototypes;
- regions;
- institutions;
- archetype specs.

The traversal is identity-based. It avoids revisiting the same object by
tracking `id(item)`.

The graph walker follows:

- explicit field values on prototypes;
- `Commodity` and `Recipe` objects inside values and lists;
- region children;
- institution initial-facility references when they are objects.

String references are not followed because Cypher cannot infer the target
object from a string alone. They are checked later against known names where
possible.

One subtle behavior: initially deployed facility prototypes are collected by
walking institution initial facilities. Deployed prototypes referenced by
`DeployInst.prototypes` are strings in the current discovered metadata, so the
larger examples add deployed reactor prototypes as simulation roots explicitly.

## Validation

`Simulation.validation_problems()` aggregates all pre-export checks and returns
strings. `Simulation.validate()` raises one `ValidationError` containing the
full list.

Validation includes:

- missing control block;
- control field problems;
- recipe and commodity problems;
- missing required archetype fields;
- duplicate names within facilities, regions, institutions, and recipes;
- institution string references to unknown facility prototypes;
- string recipe references to unknown recipes for recipe-like fields;
- explicitly requested libraries unavailable in the catalog;
- archetypes from libraries that were used without being added, when the user
  declared an explicit library set.

The design goal is consolidated feedback. Users should not fix one missing
field only to discover the next missing field on the next run.

Validation is not a replacement for Cyclus schema validation. It catches
mistakes that Cypher can understand from its object graph and normalized
metadata.

## Schema Header Selection

`Simulation` has a `schema_path` setting. The default is the sentinel string
`"auto"`, represented by `AUTO_SCHEMA_PATH`.

When XML is requested:

- `schema_path=None` or `False` omits the schema header;
- an explicit path is used directly;
- `"auto"` or `True` asks the catalog for `full_schema_path`;
- if no full schema path is known, Cypher warns and omits the header.

The automatic path is the cached full schema produced by `cyclus -n`. This is
why milestone four moved beyond using the base `cyclus.rng`: the generated full
schema is the one Cyclus itself points to for the active environment.

## XML Serialization

`xml.py` is deliberately narrow: it receives a validated `Simulation` and
writes hierarchical Cyclus XML.

Main entrypoints:

- `simulation_xml(simulation, schema_path=None, output_path=None)` returns a
  string;
- `export_xml(simulation, path, schema_path=None)` writes atomically and
  returns the target path.

Serialization order is deterministic:

1. `control`;
2. `commodity` blocks with solution priorities;
3. `archetypes`;
4. recipes;
5. facility prototypes;
6. regions, with nested institutions.

The serializer uses `xml.etree.ElementTree` and `ET.indent()` for readable
output.

`_field()` walks the recursive `ValueShape` and XML alias trees together.
Vectors become repeated elements, pairs become ordered sibling structures, and
maps accept mappings or sequences of key/value pairs. This handles structures
such as Mixer streams, Separations streams, and arbitrary deeper combinations
without archetype-specific serializer code. `_value_text()` converts booleans
to Cyclus-style `true`/`false` and converts `Commodity` or `Recipe` objects to
their names.

`export_xml()` writes to a temporary file in the target directory, preserves
existing POSIX file permissions when replacing an existing file, and uses
`os.replace()` for atomic replacement.

`_schema_processing_instruction()` writes the `xml-model` header. If the schema
path is absolute and an output path is known, `_schema_href()` attempts to make
the href relative to the output file directory.

## Execution

`execution.py` owns the boundary where Cypher touches user files and launches
Cyclus.

`normalize_simulation_name()` accepts a plain stem or a name ending in `.xml`
or `.sqlite`, strips those known suffixes, and rejects directory components or
unknown suffixes. This keeps simulation names semantic while leaving path
control to directory/input/output arguments.

`resolve_run_paths()` applies path precedence:

1. per-run `input_path` and `output_path`;
2. persistent paths stored on the `Simulation`;
3. simulation name;
4. default `simulation.xml` and `simulation.sqlite`.

If only an input path is supplied, the output path receives the same stem with
`.sqlite`. Input and output paths must not resolve to the same file.

`run_simulation()` then:

1. validates boolean flags and verbosity;
2. validates guarded advanced CLI args;
3. resolves paths;
4. refuses existing files unless `overwrite=True`;
5. resolves the Cyclus executable;
6. creates the run directory;
7. exports XML;
8. removes an old output file when overwriting;
9. launches Cyclus with input and output paths;
10. returns `RunResult` or raises `RunError`.

`run_command()` uses `subprocess.Popen` so stdout and stderr can be streamed
while also captured. It starts two daemon threads that drain each stream into
lists and optionally mirror output to `sys.stdout`/`sys.stderr`. The drains read
bounded byte chunks, decode UTF-8 incrementally, and synchronize display writes.
Chunked writes are important in notebooks: mirroring one character per write
causes Jupyter to render interleaved stdout, stderr, and carriage-return progress
updates as fragmented lines.

`RunResult` is frozen and stores:

- return code;
- run directory;
- input path;
- output path;
- stdout;
- stderr;
- command tuple.

Its `success` property is simply `returncode == 0`.

## Error Model

`errors.py` separates project-level failure categories:

- `CypherError`: base class;
- `DiscoveryError`: cache or discovery configuration problems;
- `CyclusInvocationError`: Cyclus command invocation or parse failures during
  discovery;
- `ValidationError`: consolidated simulation validation problems;
- `RunConfigurationError`: bad paths, overwrite conflicts, or execution
  configuration issues;
- `RunError`: Cyclus launched but returned nonzero.

The CLI catches `CypherError`. Library users can catch narrow subclasses.

## Test Suite Orientation

The tests mirror the architecture.

`tests/test_catalog.py` covers metadata normalization, cache handling, field
typing, stale-cache reporting, and compatibility warning behavior.

`tests/test_discovery.py` uses fake subprocess-like behavior to test executable
resolution, metadata parsing, schema discovery, strict mode, stub generation,
and compatibility reports without requiring live Cyclus.

`tests/test_archetype.py` covers dynamic class creation, generated signatures,
field validation, defaults, explicit-value tracking, and region/institution
helpers.

`tests/test_simulation.py` covers graph collection, validation, XML output,
object references, duplicate names, library assertions, and schema-header
behavior.

`tests/test_control_api.py` covers scalar control fields, validation, and XML
ordering.

`tests/test_execution.py` covers run path resolution, overwrite protection,
verbosity and extra arg guards, stream/capture behavior, failed runs, and
preflight validation.

`tests/test_help_format.py` protects generated help/docstring formatting.

`tests/test_package.py` checks package import behavior.

`tests/test_integration.py` is skipped unless `CYPHER_TEST_CYCLUS` is set. It
is where live Cyclus execution belongs.

This split is intentional. Most development feedback should be fast and
fixture-backed. Live Cyclus behavior is validated in the Docker image and
optional integration path.

## Container Verification

The Dockerfile is part of the integration story. The project image builds on
the official Cymetric environment and verifies:

- Cypher installation;
- discovery against the installed Cyclus/Cycamore stack;
- generated full schema caching;
- notebook kernel registration;
- import of the scientific notebook stack;
- a simple Matplotlib plotting smoke test;
- the bakery example through Cyclus.

The container is currently the recommended evaluation environment. Ordinary
`pip` installation under the planned `cyclus-cypher` distribution name and
possible Conda support are follow-up work.

## Design Tradeoffs

Cypher does not hard-code Cycamore field lists. That makes discovery essential
and keeps the project tied to the installed Cyclus environment.

Cypher does not import or link against Cyclus at ordinary import time. That
makes Python imports reliable in documentation, tests, and partial
environments, but it means users must run discovery explicitly.

Cypher validates what it can understand early, but it does not claim complete
schema validation. That keeps the Python layer tractable and leaves
environment-specific validation to Cyclus.

Cypher writes conventional hierarchical XML rather than inventing a new
intermediate file format. That keeps generated inputs reviewable by existing
Cyclus users.

Cypher keeps execution as an external process boundary. This avoids pretending
Cyclus is a Python library and makes stdout, stderr, paths, and return codes
explicit.

## Extension Points And Known Gaps

Recursive standard C++ containers are supported when Cyclus reports compatible
type and XML alias trees. Relax NG alternatives or custom input types outside
the supported scalar/vector/list/set/pair/map vocabulary remain
compatibility-report items rather than being silently interpreted.

Other likely extension points:

- richer notebook representations for `Simulation`, `Prototype`, and
  `RunResult`;
- generated docstring improvements from richer annotations;
- editor autocomplete documentation for generated stubs;
- published `pip` installation docs once packaging is available to users;
- possible Conda packaging policy;
- XML import or round-trip editing as a separate milestone;
- parameter-study helpers as a separate milestone;
- Cymetric analysis wrappers as a separate milestone.

These should remain explicit follow-on issues rather than being folded into
documentation work by accident.
