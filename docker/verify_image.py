"""Verify the runtime components promised by the Cypher container."""

from __future__ import annotations

import importlib
import locale
import shutil

import cymetric
import ipykernel
import IPython
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

import cypher
from cypher.catalog import Catalog


def verify_kernel() -> None:
    """Launch the registered kernel and import Cypher inside it."""

    manager = KernelManager(kernel_name="cypher")
    manager.start_kernel()
    client = manager.client()
    client.start_channels()
    try:
        client.wait_for_ready(timeout=20)
        message_id = client.execute(
            "import cypher, graphviz, matplotlib, numpy, pandas, scipy, seaborn"
        )
        while True:
            reply = client.get_shell_msg(timeout=20)
            if reply.get("parent_header", {}).get("msg_id") == message_id:
                break
        if reply.get("content", {}).get("status") != "ok":
            raise RuntimeError(
                f"Cypher kernel import failed: {reply.get('content', {})}"
            )
    finally:
        client.stop_channels()
        manager.shutdown_kernel(now=True)


def main() -> int:
    encoding = locale.getpreferredencoding(False).lower().replace("-", "")
    if encoding != "utf8":
        raise RuntimeError(f"Expected a UTF-8 locale, found {encoding!r}.")

    executable = shutil.which("cyclus")
    if executable is None:
        raise RuntimeError("Cyclus is not available on PATH.")
    if shutil.which("dot") is None:
        raise RuntimeError("The Graphviz 'dot' executable is not available on PATH.")

    catalog = Catalog.load()
    required_libraries = {"agents", "cycamore"}
    missing = required_libraries.difference(catalog.libraries)
    if missing:
        raise RuntimeError(
            f"Discovery cache is missing required libraries: {sorted(missing)}"
        )
    for library in sorted(required_libraries):
        importlib.import_module(f"cypher.{library}")

    kernels = KernelSpecManager().find_kernel_specs()
    scientific_modules = {
        name: importlib.import_module(name)
        for name in ("matplotlib", "numpy", "pandas", "scipy", "seaborn")
    }
    graphviz = importlib.import_module("graphviz")
    rendered_graph = graphviz.Digraph().pipe(format="svg")
    if b"<svg" not in rendered_graph:
        raise RuntimeError("Graphviz did not render the verification SVG.")

    if "cypher" not in kernels:
        raise RuntimeError("The 'cypher' Jupyter kernel is not registered.")

    verify_kernel()
    print(f"Cypher: {cypher.__version__}")
    print(f"Cymetric: {getattr(cymetric, '__version__', 'installed')}")
    print(f"IPython: {IPython.__version__}")
    print(f"ipykernel: {ipykernel.__version__}")
    print(f"Cyclus: {executable}")
    print(f"Archetype libraries: {', '.join(catalog.libraries)}")
    print(f"Jupyter kernel: {kernels['cypher']}")
    print(f"Locale encoding: {locale.getpreferredencoding(False)}")
    print(f"Graphviz: {graphviz.__version__} ({shutil.which('dot')})")
    print(
        "Scientific Python: "
        + ", ".join(
            f"{name} {module.__version__}"
            for name, module in scientific_modules.items()
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
