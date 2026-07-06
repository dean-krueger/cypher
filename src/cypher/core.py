"""Handwritten Cyclus simulation concepts and object graph validation."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .archetype import Prototype
from .catalog import Catalog, get_catalog
from .errors import DiscoveryError, ValidationError

if TYPE_CHECKING:
    from .execution import RunResult

AUTO_SCHEMA_PATH = "auto"
SchemaPath = str | Path | None | bool


@dataclass
class ControlField:
    """Metadata for one scalar field in the Cyclus control block."""

    name: str
    xml_name: str
    required: bool = False
    type_: type[Any] = str
    minimum: int | float | None = None
    maximum: int | float | None = None
    choices: tuple[str, ...] = ()


CONTROL_FIELDS: tuple[ControlField, ...] = (
    ControlField("simhandle", "simhandle", type_=str),
    ControlField("duration", "duration", required=True, type_=int, minimum=0),
    ControlField("start_year", "startyear", required=True, type_=int, minimum=0),
    ControlField(
        "start_month", "startmonth", required=True, type_=int, minimum=1, maximum=12
    ),
    ControlField("decay", "decay", type_=str, choices=("never", "manual", "lazy")),
    ControlField("dt", "dt", type_=int, minimum=0),
    ControlField("explicit_inventory", "explicit_inventory", type_=bool),
    ControlField(
        "explicit_inventory_compact", "explicit_inventory_compact", type_=bool
    ),
    ControlField("tolerance_generic", "tolerance_generic", type_=float),
    ControlField("tolerance_resource", "tolerance_resource", type_=float),
    ControlField("seed", "seed", type_=int, minimum=1),
    ControlField("stride", "stride", type_=int, minimum=1),
)
_CONTROL_FIELD_BY_NAME = {field.name: field for field in CONTROL_FIELDS}


@dataclass
class Control:
    """Core Cyclus simulation control settings."""

    simhandle: str | None = None
    duration: int | None = None
    start_year: int | None = None
    start_month: int | None = None
    decay: str | None = None
    dt: int | None = None
    explicit_inventory: bool | None = None
    explicit_inventory_compact: bool | None = None
    tolerance_generic: float | None = None
    tolerance_resource: float | None = None
    seed: int | None = None
    stride: int | None = None

    def __setattr__(self, name: str, value: Any) -> None:
        field = _CONTROL_FIELD_BY_NAME.get(name)
        if field is not None and value is not None:
            problem = _control_field_problem(field, value)
            if problem is not None:
                raise ValueError(problem)
        super().__setattr__(name, value)

    def validation_problems(self) -> list[str]:
        problems = []
        for field in CONTROL_FIELDS:
            value = getattr(self, field.name)
            if value is None:
                if field.required:
                    problems.append(
                        f"control is missing required field {field.name!r}"
                    )
                continue
            problem = _control_field_problem(field, value)
            if problem is not None:
                problems.append(problem)
        return problems

    def explicit_items(self) -> tuple[tuple[ControlField, Any], ...]:
        """Return supplied control values in Cyclus grammar order."""

        return tuple(
            (field, value)
            for field in CONTROL_FIELDS
            if (value := getattr(self, field.name)) is not None
        )


def _control_field_problem(field: ControlField, value: Any) -> str | None:
    label = field.name
    if field.type_ is bool:
        if not isinstance(value, bool):
            return f"control {label} must be a boolean"
    elif field.type_ is int:
        if isinstance(value, bool) or not isinstance(value, int):
            return f"control {label} must be an integer"
    elif field.type_ is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"control {label} must be a number"
    elif field.type_ is str and not isinstance(value, str):
        return f"control {label} must be a string"
    if isinstance(value, str):
        if not value.strip():
            return f"control {label} must be a nonempty string"
        if field.choices and value not in field.choices:
            allowed = ", ".join(repr(choice) for choice in field.choices)
            return f"control {label} must be one of {allowed}"
    if field.minimum is not None and value < field.minimum:
        if field.minimum == 0:
            return f"control {label} must be nonnegative"
        return f"control {label} must be at least {field.minimum}"
    if field.maximum is not None and value > field.maximum:
        return f"control {label} must be at most {field.maximum}"
    return None


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
        schema_path: SchemaPath = AUTO_SCHEMA_PATH,
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
        self.schema_path = schema_path
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

    def to_xml(
        self,
        *,
        schema_path: SchemaPath = AUTO_SCHEMA_PATH,
        output_path: str | Path | None = None,
    ) -> str:
        """Validate and return deterministic hierarchical Cyclus XML."""

        from .xml import simulation_xml

        self.validate()
        return simulation_xml(
            self,
            schema_path=self._resolve_schema_path(schema_path),
            output_path=output_path,
        )

    def export_to_xml(
        self,
        path: str | Path,
        *,
        schema_path: SchemaPath = AUTO_SCHEMA_PATH,
    ) -> Path:
        """Validate and atomically write hierarchical Cyclus XML."""

        from .xml import export_xml

        return export_xml(
            self, Path(path), schema_path=self._resolve_schema_path(schema_path)
        )

    def _resolve_schema_path(
        self, override: SchemaPath = AUTO_SCHEMA_PATH
    ) -> str | Path | None:
        selected = self.schema_path if override == AUTO_SCHEMA_PATH else override
        if selected in {None, False}:
            return None
        if selected == AUTO_SCHEMA_PATH or selected is True:
            catalog = self.catalog
            if catalog is not None and catalog.full_schema_path:
                return catalog.full_schema_path
            warnings.warn(
                "Cypher could not include an XML schema header because discovery "
                "did not report a generated full Cyclus Relax NG schema path. Run "
                "'cypher discover' in the target Cyclus environment or pass "
                "schema_path explicitly.",
                UserWarning,
                stacklevel=3,
            )
            return None
        return selected

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
