# Milestone 5: User Guide, Examples, and Reviewer Code Tour

Status: planned
Last updated: 2026-07-06

## Goal

Make Cypher understandable and reviewable by writing the documentation needed
for new users, Cyclus-familiar evaluators, and technical advisors to assess the
project without relying on chat history or source spelunking.

After milestone four, the core authoring workflow appears directionally stable:
Cypher can discover archetypes, build compositional simulations, export
readable hierarchical XML with a Cyclus-compatible grammar header, and run
models through Cyclus. The OpenMC notebook comparison did not reveal a need for
large API redesign. Milestone five should therefore focus on explaining the
current API clearly, adding representative examples, and documenting the
implementation well enough for expert review.

Small documentation-adjacent polish is in scope when it directly improves the
reader experience. Larger behavior or API changes discovered while writing the
docs should be recorded as follow-up issues rather than folded into this
milestone.

## Target Audiences

### New Cyclus and Cypher Users

The user guide and examples should assume readers may be new to both Cyclus and
Cypher. These docs should explain the workflow in approachable terms, show
complete runnable examples, and avoid requiring knowledge of Cypher internals.

Important reader questions include:

- How do I get an environment where Cypher, Cyclus, Cycamore, and Cymetric
  work today?
- What is the current status of planned `pip` and possible Conda installation
  paths?
- What does `cypher discover` do and when do I rerun it?
- How do I build a simulation from Python objects?
- How do object references differ from string references?
- How do I export XML, run Cyclus, and find the SQLite output?
- What owns post-processing after Cypher finishes running?
- What should I do when discovery, validation, schema headers, or file
  overwrite protection produce errors?

### Cyclus-Familiar Users Who Are New to Cypher

Some early readers will already understand Cyclus XML and archetype concepts.
The docs should connect Cypher's Python objects back to familiar Cyclus input
sections, including:

- control blocks;
- recipes and commodities;
- archetype library declarations;
- facility prototypes;
- regions, institutions, and initial facilities;
- hierarchical XML export;
- the generated full Relax NG schema header.

The examples should make it easy to compare a known XML input with its Cypher
authoring equivalent.

### Technical Advisors and Reviewers

The code tour is for highly skilled reviewers, including PI/advisor-level
software readers. It should be more detailed than the user guide and should
explain why the implementation is structured the way it is.

That tour should cover:

- package layout and public API boundaries;
- executable selection and subprocess isolation;
- discovery, metadata normalization, compatibility reporting, and cache
  provenance;
- generated import hooks and environment-local type stubs;
- handwritten core objects such as `Simulation`, `Control`, `Commodity`, and
  `Recipe`;
- dynamic archetype prototypes and explicit-value tracking;
- object graph collection, validation, and duplicate/reference checking;
- XML serialization and schema-header selection;
- execution boundaries, output streaming, and no-overwrite behavior;
- container verification and the role of Docker in live Cyclus coverage;
- testing strategy, including fixture-backed unit tests versus optional
  integration checks;
- known limitations and the rationale for deferring broader features.

## Required Documentation

### User Guide

Create a Markdown user guide in `docs/` that walks through the ordinary Cypher
workflow from environment setup through running a simulation.

The guide should cover:

- installation status and container options;
- the current recommendation to use the container until ordinary package
  installation workflows are closed;
- planned near-term `pip` and possible Conda availability, with language that
  can be updated once those paths are ready;
- discovery and compatibility reports;
- importing discovered archetype libraries;
- constructing a simulation;
- validating and exporting XML;
- schema-header behavior and opt-out/override options;
- running Cyclus through `Simulation.run()`;
- interpreting `RunResult`;
- handing SQLite output to Cymetric;
- common errors and troubleshooting.

### Examples

Keep bakery as the smallest complete example that demonstrates that Cypher can
build, export, and run a simulation.

Add two additional examples based on representative XML inputs:

1. A simple once-through fuel cycle, based on `examples/once_through.xml`.
2. An EG transition scenario or a suitably scoped excerpt of one, based on
   `examples/EG23.xml`.

For each example, provide:

- the original or motivating Cyclus XML source;
- the corresponding Cypher authoring script;
- a short explanation of the model structure;
- expected exported files and run outputs;
- any intentional differences between the original XML and Cypher's generated
  XML.

The source XML files are older inputs and may contain modeling assumptions,
outdated patterns, or errors. They should guide the shape and complexity of the
Cypher examples, but they should not be presented as authoritative fuel-cycle
models.

Each derived example must include a prominent notice near the top explaining
that it demonstrates how one might build a more complicated fuel cycle using
Cypher, but should not generally be used to inform actual nuclear fuel-cycle
models or cited as a validated scenario.

Suggested notice text:

```text
This example demonstrates how one might build a more complicated fuel-cycle
scenario using Cypher. It is intended as a software and authoring example only.
It should not be treated as a validated nuclear fuel-cycle model, used to draw
technical conclusions, or cited as the basis for real fuel-cycle analysis.
```

### Reviewer Code Tour

Create a Markdown code tour in `docs/` for expert reviewers. The tour should
be explicit about architectural decisions, tradeoffs, and extension points. It
should favor concrete file and object references over broad prose.

The code tour should be detailed enough for reviewers to understand how Cypher
avoids hard-coding Cycamore, why discovery is isolated behind a subprocess
adapter, how cached metadata supports dynamic imports, and how serialization
remains testable without a live Cyclus installation.

### README and Navigation Updates

Update `README.md` and existing docs as needed so readers can find the new user
guide, examples, and code tour.

The README should remain concise. It should point to the right document for
each reader rather than duplicating the full guide.

### OpenMC Comparison Note

Record a short design note summarizing what the OpenMC notebook comparison
suggested for Cypher.

The note should distinguish:

- similarities worth preserving, such as object-oriented composition,
  notebook-friendly construction, and export/run from Python;
- differences that are simulator-driven, such as OpenMC's geometry/material
  object hierarchy and component-level XML files;
- small polish opportunities, such as better object representations,
  simulation summaries, generated docstrings, and autocomplete verification.

This note should not attempt to make Cypher mimic OpenMC where Cyclus concepts
are different.

## Documentation-Adjacent Polish

The milestone may include small changes when they directly improve the docs,
such as:

- clearer docstrings;
- improved error-message wording;
- README link fixes;
- small example helper comments;
- lightweight `repr` or display improvements if they are obviously useful and
  low risk.

Larger behavior changes should be documented as follow-up issues instead of
implemented in this milestone. Examples include new public API names, new
simulation graph features, broader editor-autocomplete machinery, or any
change that requires substantial new behavioral tests.

## Acceptance Criteria

Milestone five is complete when:

1. A new user can follow the user guide to discover archetypes, build a small
   simulation, export XML, run Cyclus, and locate the SQLite output.
2. A Cyclus-familiar reader can understand how Cypher maps Python objects onto
   conventional hierarchical Cyclus XML.
3. The user guide clearly states that the container is the current recommended
   path, while ordinary `pip` and possible Conda installation support are
   expected soon but not yet documented as available.
4. The bakery example remains the simplest runnable demonstration.
5. Once-through and EG transition examples are added using the provided XML
   inputs as non-authoritative shape references.
6. The once-through and EG transition examples carry prominent notices that
   they are software examples, not validated or citable fuel-cycle analyses.
7. The reviewer code tour explains the main implementation modules and
   architectural boundaries in enough detail for expert review.
8. The OpenMC comparison note records the rationale for keeping Cypher
   Cyclus-shaped while borrowing useful authoring patterns.
9. README and existing documentation links point readers to the new docs.
10. Documentation examples are checked for syntactic correctness where
   practical.
11. Any code changes are limited to documentation-adjacent polish, with larger
   ideas recorded as follow-up issues.

## Explicit Non-Goals

Milestone five does not include:

- large public API redesign;
- broad editor/autocomplete implementation changes;
- XML import or round-trip editing;
- flat-schema export;
- parameter-study APIs;
- Cymetric analysis wrappers;
- host-side Docker orchestration;
- package or container publishing automation;
- completing `pip` or Conda packaging itself;
- a full documentation website.

## Suggested Work Plan

1. Draft the user guide outline and decide final filenames.
2. Write the bakery-centered guide path using the current container workflow.
3. Add the code tour, starting from the existing package layout.
4. Add the OpenMC comparison note.
5. Integrate once-through and EG transition examples from `examples/once_through.xml`
   and `examples/EG23.xml`, with non-authoritative-model notices.
6. Update README and cross-links.
7. Run documentation-adjacent checks and the existing fixture-backed test suite
   if code or examples changed.

## Follow-On Work

After milestone five, the project can decide whether to pursue:

- a documentation website;
- generated API reference;
- richer notebook examples;
- improved notebook display objects;
- reproducible discovery lock/export workflows;
- completing and documenting ordinary `pip` and possible Conda installation
  workflows;
- broader autocomplete and editor configuration support;
- a later beta release once the public API has been exercised by outside users.
