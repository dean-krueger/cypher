# Milestone 2: Run Cyclus

Status: proposed for review
Last updated: 2026-06-21

## Goal

Complete Cypher's core workflow by running the current Python-authored
simulation through Cyclus:

```python
result = simulation.run()
```

`run()` validates the current object graph, exports fresh hierarchical XML,
invokes the selected Cyclus executable, streams and captures its output, and
returns a structured description of the run.

Cypher stops at the successful creation of the Cyclus SQLite output. Cymetric
remains the separate tool responsible for querying and analyzing that database.

## Target user experience

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

# Build and add recipes, prototypes, institutions, and regions.

result = simulation.run()
```

Normal Cyclus output is visible while the process runs. On success, the result
is inspectable in a notebook:

```python
result.success
result.input_path
result.output_path
result.returncode
result.stdout
result.stderr
result.command
```

With the name above, the default files are:

```text
./bakery.xml
./bakery.sqlite
```

An unnamed simulation uses:

```text
./simulation.xml
./simulation.sqlite
```

## Proposed public API

The intended constructor additions are conceptually:

```python
cypher.Simulation(
    control=None,
    *,
    name=None,
    input_path=None,
    output_path=None,
    catalog=None,
)
```

The intended execution interface is:

```python
simulation.run(
    *,
    directory=".",
    input_path=None,
    output_path=None,
    overwrite=False,
    stream_output=True,
    verbosity=None,
    extra_args=None,
    cyclus_executable=None,
)
```

Exact internal organization may change during implementation, but the behavior
below is the milestone contract.

## File naming and path resolution

### Working directory

The default run directory is the process's current working directory,
`Path.cwd()`, matching OpenMC's execution convention.

`directory` provides an explicit working directory. Relative input and output
paths are interpreted beneath that directory.

Cypher does not attempt to infer the directory containing the calling `.py`
file or notebook. Notebook working directories depend on how the kernel was
launched, so `Path.cwd()` is the predictable Python convention.

### Persistent defaults and per-run overrides

`Simulation` may store:

- a human-readable `name`;
- a default `input_path`;
- a default `output_path`.

The corresponding arguments supplied to `run()` take precedence for that run
without permanently changing the simulation's stored defaults.

The precedence is:

1. a path passed directly to `run()`;
2. the corresponding path stored on `Simulation`;
3. a path derived from the simulation name;
4. the unnamed default.

### Name normalization

The preferred simulation name is a plain stem:

```python
simulation.name = "bakery"
```

For convenience, a name ending in `.xml` or `.sqlite` is normalized to its
stem. Thus `name="bakery.xml"` still derives `bakery.xml` and
`bakery.sqlite`.

A name is not itself a path. Directory components belong in `directory`,
`input_path`, or `output_path`.

### Input and output derivation

- With no name or paths: `simulation.xml` and `simulation.sqlite`.
- With `name="bakery"`: `bakery.xml` and `bakery.sqlite`.
- With only `input_path="my_sim.xml"`: derive `my_sim.sqlite` beside it.
- With only `output_path="results.sqlite"`: retain the independently derived
  input name; do not rename the XML implicitly.
- An explicit output path always wins over output derivation.

Input paths should end in `.xml` and output paths should end in `.sqlite`.
Cypher may append the expected suffix when it is omitted, but must reject a
conflicting suffix rather than silently reinterpret it.

### Overwrite safety

Cypher never prompts interactively and never overwrites by default.

Before writing or running, Cypher checks both resolved paths. If either already
exists and `overwrite=False`, `run()` raises an actionable error without
modifying either file.

With `overwrite=True`, the fresh XML and SQLite output may replace existing
files. Cypher should still use atomic XML export so a validation or
serialization failure cannot leave a partial input file.

## Execution behavior

Every call to `run()`:

1. resolves all paths and checks overwrite safety;
2. validates the current simulation;
3. exports fresh XML representing the current object state;
4. resolves one Cyclus executable;
5. constructs the Cyclus command;
6. runs Cyclus in the selected directory;
7. streams and captures process output;
8. returns `RunResult` on success;
9. raises `RunError` with the failed result attached on failure.

Cypher does not run a previously exported or manually edited XML file through
`Simulation.run()`. Users who want that behavior should invoke Cyclus directly.

## Cyclus executable consistency

Execution uses the existing resolution order:

1. `cyclus_executable` passed to `run()`;
2. the executable recorded by the simulation's discovery catalogue;
3. `CYPHER_CYCLUS_EXECUTABLE`;
4. `cyclus` on `PATH`.

If an explicit execution override differs from the discovery executable,
Cypher should warn clearly that the authoring metadata and execution
environment may not match.

Within one run, validation-related subprocess work and execution must use the
same resolved executable.

## Output streaming and capture

`stream_output=True` is the default for a pleasant terminal and notebook
experience. Cyclus stdout and stderr are:

- displayed while the simulation runs;
- captured in full on `RunResult`;
- preserved without enabling extra Cyclus logging.

`stream_output=False` captures output silently.

This setting is separate from Cyclus log verbosity. In particular, normal
output and future progress-bar output should remain visible without passing
`-v`.

Implementation should preserve output ordering and carriage-return behavior as
well as practical so Cyclus progress displays remain usable. Ordinary unit
tests should use a fake process boundary; container integration tests should
exercise real streaming.

## Verbosity

Cyclus accepts:

```text
-v <level>
```

where the documented integer range is 0 through 11:

- 0: errors;
- 1: warnings;
- 2 through 6: increasing informational logging;
- 7 through 11: increasing debugging logging.

The Cypher API is:

```python
verbosity: int | None = None
```

- `None` omits `-v` and preserves the selected Cyclus version's native
  default.
- An integer from 0 through 11 adds `-v <level>`.
- Booleans and values outside 0 through 11 are rejected before launching
  Cyclus.

Cypher should enforce the documented range even if a particular Cyclus CLI
version accepts other integers.

## Advanced arguments

Milestone two provides friendly parameters for paths and verbosity.

`extra_args` supplies an advanced escape hatch for less common Cyclus options:

```python
result = simulation.run(
    extra_args=["--warn-limit", "100", "--no-mem"],
)
```

`extra_args` is a sequence of individual argument strings, never a shell
command. Cypher invokes Cyclus without a shell.

Cypher-owned options such as input path, output path, and verbosity must not be
silently overridden through `extra_args`. Conflicts should produce a clear
error.

Mirroring every Cyclus CLI option with a dedicated Python parameter is not part
of this milestone.

## RunResult

`RunResult` is an immutable structured result containing at least:

```python
result.success
result.returncode
result.directory
result.input_path
result.output_path
result.stdout
result.stderr
result.command
```

Additional useful fields may include start/end times or elapsed duration, but
they are not required for milestone completion.

Paths should be resolved `Path` objects. `command` should be a tuple of argument
strings suitable for diagnostics, not a shell-formatted command string.

`repr(result)` and notebook display should be concise and emphasize:

- success or failure;
- input path;
- output path;
- return code.

The full captured logs remain available through attributes.

## Failure behavior

A nonzero Cyclus exit status raises `cypher.RunError`.

The exception:

- has a concise message containing the return code and selected paths;
- exposes the complete failed `RunResult` as `error.result`;
- preserves captured stdout and stderr;
- does not delete the generated XML, because that file is useful for
  diagnosis;
- does not claim that the output database is valid merely because a file was
  created.

Missing executables, invalid paths, overwrite conflicts, invalid verbosity, and
invalid advanced arguments should fail before launching Cyclus with focused
exception types or messages.

## Acceptance criteria

Milestone two is complete when:

1. Bare `simulation.run()` validates, exports, and runs a complete simulation.
2. Unnamed runs default to `simulation.xml` and `simulation.sqlite` in
   `Path.cwd()`.
3. Named simulations and explicit paths follow the documented precedence and
   suffix rules.
4. Supplying only an input path derives a same-stem SQLite path.
5. Existing files are protected unless `overwrite=True`.
6. Normal Cyclus output streams by default and is also captured.
7. `stream_output=False` runs silently while retaining captured logs.
8. `verbosity=None` omits `-v`; levels 0 through 11 pass the corresponding
   Cyclus argument; invalid levels fail before execution.
9. A successful run returns a useful `RunResult`.
10. A failed run raises `RunError` with the failed result attached.
11. The same selected Cyclus executable is used consistently during a run.
12. The bakery example runs successfully through `Simulation.run()` in the
    prepared Cymetric container and produces a nonempty SQLite database.
13. The default unit-test suite still requires neither Cyclus nor Docker.
14. The wheel, source distribution, Ruff checks, and Twine checks pass.

## Test strategy

### Unit tests

Use a fake subprocess adapter to cover:

- executable precedence and mismatch warnings;
- unnamed, named, persistent, and per-run path resolution;
- suffix normalization and rejection;
- same-stem output derivation;
- overwrite preflight behavior;
- command construction;
- verbosity validation and omission;
- conflicting `extra_args`;
- successful and failed result construction;
- stream-enabled and stream-disabled capture;
- `RunError.result`;
- validation/export occurring before process launch.

### Integration tests

In the prepared Cymetric container:

- discover real `agents` and Cycamore archetypes;
- run the bakery simulation through the Python API;
- observe normal Cyclus output;
- confirm the result reports success;
- confirm the XML and SQLite paths exist;
- confirm the SQLite output is nonempty;
- exercise at least one safe verbosity level;
- exercise overwrite refusal.

An unavailable Cyclus integration environment remains an explicit skip.

## Explicit non-goals

Milestone two does not include:

- querying or analyzing SQLite output;
- wrapping Cymetric;
- parameter studies or parallel run orchestration;
- restart/snapshot workflows;
- a `cypher run` command for arbitrary Python model files;
- XML import or round-trip editing;
- flat-schema export;
- host-side Docker orchestration;
- Docker image publication;
- automatic Cyclus/archetype installation;
- exhaustive dedicated wrappers for Cyclus CLI flags;
- automatic run numbering or timestamped run directories;
- PyPI or Conda publication;
- a stable `1.0` API commitment.

## Review questions allowed during implementation

The following details may be refined while preserving the behavior above:

- exact exception class hierarchy;
- exact `RunResult` notebook representation;
- whether captured stdout/stderr are strings or richer log objects;
- internal technique used to stream and capture both process channels;
- whether `Simulation` paths are plain attributes or validated properties;
- precise wording and timing of discovery/execution mismatch warnings.

