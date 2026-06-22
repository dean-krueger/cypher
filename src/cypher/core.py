"""Handwritten Cyclus simulation concepts and object graph validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .archetype import Prototype
from .catalog import Catalog, get_catalog
from .errors import DiscoveryError, ValidationError

if TYPE_CHECKING:
    from .execution import RunResult


@dataclass
class Control:
    """Core Cyclus simulation control settings."""

    duration: int | None = None
    start_year: int | None = None
    start_month: int | None = None

    def validation_problems(self) -> list[str]:
        problems = []
        if self.duration is None:
            problems.append("control is missing required field 'duration'")
        elif isinstance(self.duration, bool) or not isinstance(self.duration, int):
            problems.append("control duration must be an integer")
        elif self.duration < 0:
            problems.append("control duration must be nonnegative")
        if self.start_year is None:
            problems.append("control is missing required field 'start_year'")
        elif isinstance(self.start_year, bool) or not isinstance(self.start_year, int):
            problems.append("control start_year must be an integer")
        elif self.start_year < 0:
            problems.append("control start_year must be nonnegative")
        if self.start_month is None:
            problems.append("control is missing required field 'start_month'")
        elif isinstance(self.start_month, bool) or not isinstance(
            self.start_month, int
        ):
            problems.append("control start_month must be an integer")
        elif not 1 <= self.start_month <= 12:
            problems.append("control start_month must be between 1 and 12")
        return problems


@dataclass
class Commodity:
    """A reusable commodity name and optional solver priority declaration."""

    name: str
    solution_priority: float | None = None

    def validation_problems(self) -> list[str]:
        problems = []
        if not isinstance(self.name, str) or not self.name.strip():
            problems.append("commodity name must be a nonempty string")
        if self.solution_priority is not None and (
            isinstance(self.solution_priority, bool)
            or not isinstance(self.solution_priority, (int, float))
        ):
            problems.append(
                f"commodity {self.name!r} solution_priority must be a number"
            )
        return problems

    def __str__(self) -> str:
        return self.name


@dataclass
class Recipe:
    """A named Cyclus material composition recipe."""

    name: str
    basis: str
    composition: dict[int | str, float]

    def validation_problems(self) -> list[str]:
        problems = []
        if not isinstance(self.name, str) or not self.name.strip():
            problems.append("recipe name must be a nonempty string")
        if self.basis not in {"atom", "mass"}:
            problems.append(
                f"recipe {self.name!r} basis must be 'atom' or 'mass', "
                f"got {self.basis!r}"
            )
        if not self.composition:
            problems.append(f"recipe {self.name!r} composition must not be empty")
        for nuclide, fraction in self.composition.items():
            if not isinstance(nuclide, (int, str)) or isinstance(nuclide, bool):
                problems.append(
                    f"recipe {self.name!r} has invalid nuclide identifier {nuclide!r}"
                )
            if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
                problems.append(
                    f"recipe {self.name!r} fraction for {nuclide!r} must be a number"
                )
            elif fraction < 0:
                problems.append(
                    f"recipe {self.name!r} fraction for {nuclide!r} is negative"
                )
        return problems

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Graph:
    recipes: tuple[Recipe, ...]
    commodities: tuple[Commodity, ...]
    facilities: tuple[Prototype, ...]
    regions: tuple[Prototype, ...]
    institutions: tuple[Prototype, ...]
    archetypes: tuple[object, ...]


class Simulation:
    """A composable Cyclus simulation that can validate and export XML."""

    def __init__(
        self,
        control: Control | None = None,
        *,
        name: str | None = None,
        input_path: str | Path | None = None,
        output_path: str | Path | None = None,
        catalog: Catalog | None = None,
    ) -> None:
        self.control = control
        self._name: str | None = None
        self.name = name
        self.input_path = (
            Path(input_path).expanduser() if input_path is not None else None
        )
        self.output_path = (
            Path(output_path).expanduser() if output_path is not None else None
        )
        self._catalog = catalog
        self._roots: list[Recipe | Commodity | Prototype] = []
        self._libraries: list[str] = []

    @property
    def name(self) -> str | None:
        """Human-readable simulation name used to derive run filenames."""

        return self._name

    @name.setter
    def name(self, value: str | None) -> None:
        from .execution import normalize_simulation_name

        self._name = normalize_simulation_name(value)

    @property
    def catalog(self) -> Catalog | None:
        if self._catalog is not None:
            return self._catalog
        return get_catalog(required=False)

    def add_library(self, name: str) -> Simulation:
        """Assert that an archetype library is available to this simulation."""

        catalog = self.catalog
        if catalog is None:
            raise DiscoveryError(
                f"Cannot add library {name!r} without discovery metadata. "
                "Run 'cypher discover' first."
            )
        catalog.library(name)
        if name not in self._libraries:
            self._libraries.append(name)
        return self

    @property
    def libraries(self) -> tuple[str, ...]:
        return tuple(self._libraries)

    def add(self, *objects: Control | Recipe | Commodity | Prototype) -> Simulation:
        """Add one or more root objects; adding the same instance is idempotent."""

        for item in objects:
            if isinstance(item, Control):
                if self.control is None:
                    self.control = item
                elif self.control is not item:
                    raise ValueError(
                        "Simulation already has a different control block. "
                        "Modify the existing block or create a new Simulation."
                    )
                continue
            if not isinstance(item, (Recipe, Commodity, Prototype)):
                raise TypeError(
                    "Simulation.add accepts Control, Recipe, Commodity, or "
                    f"archetype objects; got {type(item).__name__}."
                )
            if not any(existing is item for existing in self._roots):
                self._roots.append(item)
        return self

    def graph(self) -> Graph:
        recipes: list[Recipe] = []
        commodities: list[Commodity] = []
        facilities: list[Prototype] = []
        regions: list[Prototype] = []
        institutions: list[Prototype] = []
        archetypes: list[object] = []
        seen: set[int] = set()

        def append_identity(collection: list[Any], item: Any) -> None:
            if not any(existing is item for existing in collection):
                collection.append(item)

        def visit_value(value: Any) -> None:
            if isinstance(value, Commodity):
                append_identity(commodities, value)
            elif isinstance(value, Recipe):
                append_identity(recipes, value)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    visit_value(child)

        def visit(item: Recipe | Commodity | Prototype) -> None:
            if id(item) in seen:
                return
            seen.add(id(item))
            if isinstance(item, Recipe):
                recipes.append(item)
                return
            if isinstance(item, Commodity):
                commodities.append(item)
                return
            if item._archetype not in archetypes:
                archetypes.append(item._archetype)
            for _, value in item.explicit_items():
                visit_value(value)
            if item.entity == "facility":
                facilities.append(item)
            elif item.entity == "region":
                regions.append(item)
                for child in item.children:
                    visit(child)
            elif item.entity == "institution":
                institutions.append(item)
                for target, _count in item.initial_facilities:
                    if isinstance(target, Prototype):
                        visit(target)

        for root in self._roots:
            visit(root)
        return Graph(
            recipes=tuple(recipes),
            commodities=tuple(commodities),
            facilities=tuple(facilities),
            regions=tuple(regions),
            institutions=tuple(institutions),
            archetypes=tuple(archetypes),
        )

    @property
    def recipes(self) -> tuple[Recipe, ...]:
        return self.graph().recipes

    @property
    def prototypes(self) -> tuple[Prototype, ...]:
        return self.graph().facilities

    @property
    def regions(self) -> tuple[Prototype, ...]:
        return self.graph().regions

    def validation_problems(self) -> list[str]:
        problems = []
        if self.control is None:
            problems.append("simulation is missing a control block")
        else:
            problems.extend(self.control.validation_problems())
        graph = self.graph()
        for recipe in graph.recipes:
            problems.extend(recipe.validation_problems())
        for commodity in graph.commodities:
            problems.extend(commodity.validation_problems())
        for item in (*graph.facilities, *graph.regions, *graph.institutions):
            problems.extend(item.validation_problems())
        problems.extend(_duplicate_name_problems(graph))
        problems.extend(_reference_problems(graph))

        available_libraries = set(self.catalog.libraries) if self.catalog else set()
        for requested in self._libraries:
            if requested not in available_libraries:
                problems.append(
                    f"requested archetype library {requested!r} is unavailable"
                )
        for archetype in graph.archetypes:
            if self._libraries and archetype.library not in self._libraries:
                problems.append(
                    f"archetype {archetype.spec} is used but library "
                    f"{archetype.library!r} was not added to the simulation"
                )
        return problems

    def validate(self) -> None:
        """Raise one consolidated error if the simulation is invalid."""

        problems = self.validation_problems()
        if problems:
            raise ValidationError(problems)

    def to_xml(self) -> str:
        """Validate and return deterministic hierarchical Cyclus XML."""

        from .xml import simulation_xml

        self.validate()
        return simulation_xml(self)

    def export_to_xml(self, path: str | Path) -> Path:
        """Validate and atomically write hierarchical Cyclus XML."""

        from .xml import export_xml

        return export_xml(self, Path(path))

    def run(
        self,
        *,
        directory: str | Path = ".",
        input_path: str | Path | None = None,
        output_path: str | Path | None = None,
        overwrite: bool = False,
        stream_output: bool = True,
        verbosity: int | None = None,
        extra_args: list[str] | tuple[str, ...] | None = None,
        cyclus_executable: str | Path | None = None,
    ) -> RunResult:
        """Validate, export, and run this simulation through Cyclus."""

        from .execution import run_simulation

        return run_simulation(
            self,
            directory=directory,
            input_path=input_path,
            output_path=output_path,
            overwrite=overwrite,
            stream_output=stream_output,
            verbosity=verbosity,
            extra_args=extra_args,
            cyclus_executable=cyclus_executable,
        )


def _duplicate_name_problems(graph: Graph) -> list[str]:
    problems = []
    categories = {
        "facility prototype": graph.facilities,
        "region": graph.regions,
        "institution": graph.institutions,
        "recipe": graph.recipes,
    }
    for category, items in categories.items():
        names: dict[str, object] = {}
        for item in items:
            name = item.name
            if not name:
                continue
            previous = names.get(name)
            if previous is not None and previous is not item:
                problems.append(f"distinct {category} objects share the name {name!r}")
            else:
                names[name] = item
    return problems


def _reference_problems(graph: Graph) -> list[str]:
    problems = []
    facility_names = {facility.name for facility in graph.facilities if facility.name}
    recipe_names = {recipe.name for recipe in graph.recipes if recipe.name}
    for institution in graph.institutions:
        for target, _count in institution.initial_facilities:
            if isinstance(target, str) and target not in facility_names:
                problems.append(
                    f"institution {institution.name!r} references unknown facility "
                    f"prototype {target!r}"
                )
    for facility in graph.facilities:
        for field, value in facility.explicit_items():
            uitypes = field.uitype if isinstance(field.uitype, list) else [field.uitype]
            if "recipe" in uitypes and isinstance(value, str):
                if value and value not in recipe_names:
                    problems.append(
                        f"{facility.library}:{facility._archetype.name} "
                        f"{facility.name!r} field {field.name!r} references unknown "
                        f"recipe {value!r}"
                    )
    return problems
