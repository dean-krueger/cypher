# Examples

Cypher includes one small runnable demonstration and two larger authoring
examples based on older Cyclus XML inputs.

## Bakery

`examples/bakery.py` is the smallest complete script demonstration.
`examples/bakery.ipynb` presents the same model as a teaching notebook, with
the simulation built up section by section. Both create a toy commodity,
source, sink, institution, and region; export XML; and run Cyclus through
`Simulation.run()`.

Run it inside the Cypher container:

```console
python examples/bakery.py --directory runs/bakery --overwrite
```

Or open `examples/bakery.ipynb` with the `Python (Cypher)` kernel in the
container and run the cells in order.

Expected outputs:

- `runs/bakery/bakery.xml`
- `runs/bakery/bakery.sqlite`
- a printed `RunResult`

This example is intentionally tiny. Its job is to prove that the environment,
discovery cache, XML export, schema header, and Cyclus execution path all work.

## Once-Through Fuel Cycle

`examples/once_through.xml` is the older source XML. `examples/once_through.py`
is the corresponding Cypher authoring script. `examples/once_through.ipynb`
builds the same example as a teaching notebook.

> [!WARNING]
> This example demonstrates how one might build a more complicated fuel-cycle
> scenario using Cypher. It is intended as a software and authoring example
> only. It should not be treated as a validated nuclear fuel-cycle model, used
> to draw technical conclusions, or cited as the basis for real fuel-cycle
> analysis.

The scenario shape is:

- natural uranium source;
- conversion and enrichment;
- fuel mixing;
- one LWR-style reactor prototype;
- spent fuel storage, interim storage, and repository sink;
- an initial facilities institution and a deployment institution.

The script is meant to make the mapping from a familiar hierarchical Cyclus XML
input to Cypher objects easy to inspect. Some details have been simplified or
kept as direct translations from the old XML. The mixer configuration
demonstrates Cypher's recursive support for nested vector, pair, and map fields.
Review the generated XML and the scenario's modeling assumptions before using
the pattern in new work.

## EG Transition Scenario

`examples/EG23.xml` is the older source XML. `examples/eg23_transition.py` is a
Cypher authoring script based on its overall structure.
`examples/eg23_transition.ipynb` builds the same example as a teaching
notebook.

> [!WARNING]
> This example demonstrates how one might build a more complicated fuel-cycle
> scenario using Cypher. It is intended as a software and authoring example
> only. It should not be treated as a validated nuclear fuel-cycle model, used
> to draw technical conclusions, or cited as the basis for real fuel-cycle
> analysis.

The scenario shape is:

- mine and enrichment support facilities;
- LWR deployment over the first part of the simulation;
- used UOX cooling and reprocessing;
- SFR fuel mixing, SFR deployment, used SFR cooling, and SFR reprocessing;
- a waste repository;
- separate institutions for initial support facilities, LWR deployment, and
  SFR deployment.

The EG script is intentionally an authoring example, not a benchmark
definition or integration test. It shows how a larger Cyclus scenario can be
organized in Python while preserving the main XML concepts: recipes,
prototypes, initial facilities, deployment schedules, regions, and
institutions. Cypher can serialize the nested Separations and Mixer container
structures, but the translated scenario and its numerical assumptions remain
non-authoritative and should be independently reviewed before technical use.

## Comparing XML And Cypher

Cypher writes hierarchical XML, so the generated files should still look
recognizable to Cyclus users. The biggest authoring difference is that Cypher
lets Python objects carry references until export time. For example, a facility
can receive a `Commodity` object while the XML receives the commodity name.

Intentional differences to expect:

- generated XML ordering follows Cypher's deterministic serializer;
- schema headers use the full schema path discovered from `cyclus -n`;
- object references may appear as names in the XML;
- examples may omit comments or old XML formatting that do not affect Cyclus
  input semantics.
