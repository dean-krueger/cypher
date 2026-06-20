"""Python tools for authoring Cyclus simulation inputs.

Run ``cypher discover`` after installing Cyclus and its archetype libraries.
Discovered libraries then become importable as modules such as
``cypher.cycamore``.
"""

__version__ = "0.1.0"

from ._imports import install_library_finder
from .catalog import Catalog, get_catalog, set_catalog
from .core import Commodity, Control, Recipe, Simulation
from .errors import (
    CyclusInvocationError,
    CypherError,
    DiscoveryError,
    ValidationError,
)

install_library_finder()

__all__ = [
    "Catalog",
    "Commodity",
    "Control",
    "CyclusInvocationError",
    "CypherError",
    "DiscoveryError",
    "Recipe",
    "Simulation",
    "ValidationError",
    "__version__",
    "get_catalog",
    "set_catalog",
]
