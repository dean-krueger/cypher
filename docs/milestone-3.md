# Milestone 3: Notebook-Ready Container

Status: preliminary roadmap
Last updated: 2026-06-21

## Goal

Provide a reproducible, pleasant demonstration and development environment
containing:

- Cyclus;
- Cycamore;
- Cymetric;
- Cypher;
- IPython and a VS Code-selectable Jupyter kernel;
- a valid UTF-8 locale.

The initial user workflow should be:

```console
docker pull <cypher-image>
docker run -d \
  --name cypher-dev \
  -v "$PWD/my_project:/workspace" \
  -w /workspace \
  <cypher-image> \
  sleep infinity
```

The user then attaches VS Code through Dev Containers, opens or creates a
notebook beneath `/workspace`, selects the preinstalled Python kernel, and can
immediately import Cypher and its discovered libraries.

## Direction

The image should build on the tested official Cymetric image rather than
independently reconstructing the Cyclus ecosystem.

The base image is configurable:

```dockerfile
ARG CYMETRIC_IMAGE=ghcr.io/cyclus/.../cymetric:latest
FROM ${CYMETRIC_IMAGE}
```

`latest` is the development default so infrequent Cyclus ecosystem updates can
flow through. Reproducible builds may supply a pinned tag or digest.

The image build should:

- install Cypher from the current repository;
- configure a working UTF-8 locale;
- install IPython, `ipykernel`, and the dependencies needed for VS Code
  notebooks;
- run `cypher discover`;
- register a clearly named notebook kernel;
- run the bakery smoke test through Cyclus;
- retain a normal shell-oriented entry point suitable for `sleep infinity`.

The image should not automatically launch JupyterLab in this milestone.

## Persistence model

User notebooks, Python scripts, XML inputs, and SQLite outputs live in a mounted
project directory and therefore survive container replacement.

Packages and the discovery cache may live inside the image. After installing a
mounted third-party archetype library, the user reruns:

```console
cypher discover
```

## Local validation and publication boundary

Milestone three first produces a locally built and validated image.

Cypher may prepare:

- the Dockerfile;
- supporting scripts and documentation;
- image labels;
- a bakery health/smoke test;
- candidate Docker Hub tags and commands.

Cypher must not log in to Docker Hub, create repositories, or push images
without explicit user authorization. Manual publishing guidance follows local
validation.

Possible later tags include:

- `latest` for the latest stable Cypher image;
- `dev` for current development;
- versioned tags such as `0.2.0`.

## Explicit non-goals

The first container milestone does not require:

- PyNE;
- browser-hosted JupyterLab;
- multi-architecture builds;
- production-grade automated publishing;
- host-side Docker control from the Cypher Python API;
- automatic installation of arbitrary third-party archetypes;
- replacing native pip or Conda installation paths.

PyNE and classroom-oriented JupyterLab hosting remain valuable later goals.

