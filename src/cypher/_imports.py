"""Import hook for environment-discovered archetype library modules."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType

from .archetype import make_archetype_class
from .catalog import get_catalog


class _LibraryFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    prefix = "cypher."

    def find_spec(self, fullname: str, path: object = None, target: object = None):
        if not fullname.startswith(self.prefix) or fullname.count(".") != 1:
            return None
        library = fullname.removeprefix(self.prefix)
        catalog = get_catalog(required=False)
        if catalog is None or library not in catalog.libraries:
            return None
        return importlib.machinery.ModuleSpec(fullname, self)

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        return None

    def exec_module(self, module: ModuleType) -> None:
        catalog = get_catalog()
        assert catalog is not None
        library = module.__name__.removeprefix(self.prefix)
        classes = {}
        for name, archetype in catalog.library(library).items():
            classes[name] = make_archetype_class(archetype, module_name=module.__name__)
        module.__dict__.update(classes)
        module.__dict__["__all__"] = sorted(classes)
        module.__dict__["__doc__"] = (
            f"Archetypes discovered from the Cyclus {library!r} library."
        )


_finder = _LibraryFinder()


def install_library_finder() -> None:
    """Install the dynamic-library finder once without performing discovery."""

    if not any(isinstance(item, _LibraryFinder) for item in sys.meta_path):
        sys.meta_path.insert(0, _finder)
