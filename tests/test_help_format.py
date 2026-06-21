from __future__ import annotations

import inspect

from cypher.archetype import make_archetype_class
from cypher.catalog import ArchetypeSpec, FieldSpec


def test_help_orders_required_fields_before_optional_fields() -> None:
    archetype = ArchetypeSpec(
        spec=":example:OutOfOrder",
        path="",
        library="example",
        name="OutOfOrder",
        entity="facility",
        doc="An archetype whose schema lists an optional field first.",
        fields=(
            FieldSpec(
                name="optional_first",
                alias="optional_first",
                cpp_type="double",
                required=False,
                default=12.0,
                has_default=True,
                doc="Optional field.",
            ),
            FieldSpec(
                name="required_second",
                alias="required_second",
                cpp_type="std::string",
                required=True,
                doc="Required field.",
            ),
        ),
        schema="<interleave/>",
    )

    generated = make_archetype_class(archetype, module_name="cypher.example")
    signature = inspect.signature(generated)

    assert list(signature.parameters) == [
        "name",
        "required_second",
        "optional_first",
    ]
    assert generated.__doc__.index("required_second") < generated.__doc__.index(
        "optional_first"
    )
    lines = generated.__doc__.splitlines()
    assert lines[:2] == [
        "Required: required_second",
        "Optional: optional_first",
    ]
    assert generated.__doc__.index("Description:") < generated.__doc__.index(
        "Required fields:"
    )
    assert generated.__doc__.index("Required fields:") < generated.__doc__.index(
        "Optional fields:"
    )
