# Milestone 4: Cyclus Grammar and Control Compatibility

Status: implemented on milestone-four
Last updated: 2026-06-29

## Goal

Bring Cypher generated hierarchical XML closer to established Cyclus inputs by adding optional Relax NG grammar-header support and expanding the top-level control block beyond the three required fields.

The current authoring workflow works, but Cypher omits XML grammar metadata and supports only duration, start_year, and start_month. Cyclus base grammar also documents optional control fields such as simhandle, decay, dt, explicit inventory flags, tolerances, seed, and stride.

## Required Capabilities

### XML Grammar Header

- Support the XML processing instruction form used by existing inputs.
- Keep generated XML deterministic and readable.
- Include the header automatically when discovery reports a schema path.
- Warn and omit the header when automatic schema selection is requested but no
  schema path is known.
- Let users opt out of the header when portability is more important.
- Prefer a relative href when the schema path and output path have a sensible relationship.
- Provide an explicit override so advanced users can point at a specific cyclus.rng.
- Avoid baking machine-specific absolute paths into default output.

### Base Grammar Discovery

- Investigate whether the selected Cyclus environment exposes the base cyclus.rng path or contents during discovery.
- Cache any available base-grammar provenance without making ordinary imports run Cyclus.
- Fall back cleanly when the grammar path cannot be discovered.

### Control Block Coverage

- Continue supporting required duration, startyear, and startmonth output.
- Add straightforward optional scalar fields from the base grammar: simhandle, decay, dt, explicit_inventory, explicit_inventory_compact, tolerance_generic, tolerance_resource, seed, and stride.
- Preserve deterministic control-element order matching the grammar.
- Validate assigned scalar values early when the grammar provides an unambiguous datatype or small enum.
- Defer full nested solver configuration if a clean first implementation would otherwise balloon.

### Control Extensibility

- Keep a public cypher.Control object.
- Move field definitions toward a table-driven or schema-backed representation.
- Preserve documentation and metadata in a form that can later feed runtime help and generated docs.
- Avoid hard-coding behavior that would make future Cyclus control fields difficult to add.

## Acceptance Criteria

1. Existing bakery authoring code continues to work.
2. Golden XML tests cover automatic header output and an explicit no-header
   opt-out.
3. Optional control fields serialize only when explicitly supplied.
4. Invalid scalar control values fail before XML is written.
5. The generated control block remains deterministic and grammar ordered.
6. Header generation can use an explicit schema path and produce a portable relative href where possible.
7. Any discovered base-grammar information is cached or reported clearly.
8. The fixture-backed test suite still does not require Cyclus, Docker, Conda, or network access.

## Explicit Non-Goals

Milestone four does not include XML import, flat-schema export, full solver modeling, OpenMC comparison work, broad editor-autocomplete fixes, documentation-site generation, or publishing a new container image.

## Follow-On Work

Milestone five should compare Cypher authoring style against canonical OpenMC examples, including assignment-time validation and editor autocomplete behavior. Milestone six should then write the deeper user guide and reviewer code tour after the milestone-four and milestone-five APIs settle.

## Implementation Notes

Cyclus exposes the base Relax NG schema path through `cyclus --rng-schema`.
Cypher discovery now calls that hook, caches the reported path as provenance,
and includes it in compatibility reports. Failure to report the path remains
nonfatal so unusual or older Cyclus installations can still discover
archetypes.

Generated XML includes the schema header by default when discovery reported a
base schema path. Users can pass `schema_path=None` to `Simulation` or an
individual export call to omit the header, or pass an explicit path to override
the discovered value. Export computes a relative `href` from the output file
location when practical.
