# Cypher Container

Cypher's container is a notebook-ready development and demonstration
environment built on the official Cymetric image. It contains Cyclus,
Cycamore, Cymetric, Cypher, IPython, and a registered Jupyter kernel named
`Python (Cypher)`. The notebook environment also includes NumPy, pandas,
Matplotlib, SciPy, Seaborn, and Graphviz support for Cymetric flow graphs.

The container does not launch JupyterLab. Its intended workflow is to keep a
container running, attach VS Code through Dev Containers, and use VS Code's
notebook interface.

## Build locally

From the repository root:

```console
docker build -t cypher:local .
```

The default base is:

```text
ghcr.io/cyclus/cymetric_24.04_apt/cymetric:latest
```

Use a different tag or digest when a reproducible or experimental base is
needed:

```console
docker build \
  --build-arg CYMETRIC_IMAGE=ghcr.io/cyclus/cymetric_24.04_apt/cymetric@sha256:... \
  -t cypher:local \
  .
```

Building the image runs `cypher discover`, launches the registered notebook
kernel, and runs the bakery simulation through Cyclus. A successful build
therefore verifies more than package installation.

## Start a development container

Create a host directory for notebooks, scripts, XML, and SQLite output:

```console
mkdir -p my_project
```

Start a long-running container with that directory mounted:

```console
docker run -d \
  --name cypher-dev \
  -v "$PWD/my_project:/workspace" \
  -w /workspace \
  cypher:local \
  sleep infinity
```

To use the published alpha instead of a local build, substitute
`deankrueger/cypher:alpha`. For a reproducible test, use
`deankrueger/cypher:0.1.0-alpha.1`.

The files beneath `my_project` survive container removal and replacement.

In VS Code:

1. Install the Dev Containers, Python, and Jupyter extensions.
2. Run **Dev Containers: Attach to Running Container...**.
3. Select `cypher-dev`.
4. Open `/workspace`.
5. Create or open a notebook and select `Python (Cypher)` as its kernel.

Cypher, its discovered `agents` and `cycamore` modules, Cyclus, and Cymetric
are immediately available.

Stop and remove the container when finished:

```console
docker stop cypher-dev
docker rm cypher-dev
```

## Verify an image

The same verifier used while building the image can be run manually:

```console
docker run --rm cypher:local \
  python3 /opt/cypher/docker/verify_image.py
```

It checks the UTF-8 locale, Cyclus executable, Cypher discovery cache,
archetype-library imports, Cymetric and notebook dependencies, kernel
registration, and a real kernel launch.

## Additional archetype libraries

Install a mounted third-party archetype library using that project's normal
instructions, then refresh Cypher's environment-specific interfaces:

```console
cypher discover
```

The refreshed cache lives in the container. Rebuild a custom image if the
additional library should survive container replacement.

## Platform scope

The current official Cymetric base is a Linux `amd64` image, so milestone
three validates that platform only. Multi-architecture builds and native Apple
Silicon support are not currently in scope.

## Published alpha

The first manually published image is available as:

```console
docker pull deankrueger/cypher:alpha
```

The same image also has the reproducible tag:

```console
docker pull deankrueger/cypher:0.1.0-alpha.1
```

`latest` is intentionally unused while Cypher remains pre-alpha.
