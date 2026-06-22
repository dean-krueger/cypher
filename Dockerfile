ARG CYMETRIC_IMAGE=ghcr.io/cyclus/cymetric_24.04_apt/cymetric:latest
FROM ${CYMETRIC_IMAGE}

ARG CYPHER_VERSION=0.1.0

LABEL org.opencontainers.image.title="Cypher"
LABEL org.opencontainers.image.description="Notebook-ready Cyclus, Cycamore, Cymetric, and Cypher environment"
LABEL org.opencontainers.image.source="https://github.com/dean-krueger/cypher"
LABEL org.opencontainers.image.licenses="BSD-3-Clause"
LABEL org.opencontainers.image.version="${CYPHER_VERSION}"

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/cypher

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY docker ./docker

RUN python3 -m pip install \
        --user \
        --break-system-packages \
        --no-cache-dir \
        . \
        "ipython>=8,<10" \
        "ipykernel>=6,<8" \
        "seaborn==0.13.2" \
        "graphviz>=0.20,<1" \
    && python3 -m ipykernel install \
        --user \
        --name cypher \
        --display-name "Python (Cypher)" \
    && cypher discover \
    && python3 docker/verify_image.py \
    && mkdir -p /tmp/cypher-smoke \
    && python3 examples/bakery.py --directory /tmp/cypher-smoke \
    && test -s /tmp/cypher-smoke/bakery.xml \
    && test -s /tmp/cypher-smoke/bakery.sqlite \
    && rm -rf /tmp/cypher-smoke

WORKDIR /workspace

CMD ["/bin/bash"]
