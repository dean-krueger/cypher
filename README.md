# Cypher

Cypher is a Python front-end for
[Cyclus](https://github.com/cyclus/cyclus), an agent-based nuclear fuel cycle
simulator. It lets users define Cyclus simulations with composable Python
objects, generate readable XML inputs, and run them through Cyclus.

The project takes inspiration from the Python input API provided by
[OpenMC](https://github.com/openmc-dev/openmc). Where the two simulators have
analogous concepts, Cypher should feel familiar to OpenMC users while
remaining faithful to Cyclus's own model and terminology.

> [!IMPORTANT]
> Cypher is in pre-alpha development. Its public API will continue to evolve.

## Naming

- PyPI distribution: `cyclus-cypher`
- Python import: `cypher`
- Source repository: `dean-krueger/cypher`

The distribution and import names intentionally differ:

```console
python -m pip install cyclus-cypher
```

```python
import cypher
```

See [Using Cypher](docs/usage.md) and the complete
[`examples/bakery.py`](examples/bakery.py) authoring example.

Current roadmap documents:
[milestone two execution](docs/milestone-2.md) and
[milestone three container](docs/milestone-3.md).

## Development

Create a virtual environment and install the package with its development
tools:

```console
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the initial checks with:

```console
ruff check .
pytest
python -m build
python -m twine check dist/*
```

## License

Cypher is available under the BSD 3-Clause License, matching the Cyclus
ecosystem. See [LICENSE](LICENSE).
