from __future__ import annotations

import os
from pathlib import Path

import pytest

from cypher.discovery import CyclusAdapter
from cypher.errors import CypherError


@pytest.mark.integration
def test_selected_cyclus_can_report_metadata() -> None:
    executable = os.environ.get("CYPHER_TEST_CYCLUS")
    if not executable:
        pytest.skip("set CYPHER_TEST_CYCLUS to run Cyclus integration tests")
    path = Path(executable)
    if not path.exists():
        pytest.skip(f"configured Cyclus executable does not exist: {path}")
    try:
        metadata, _warnings = CyclusAdapter(path).metadata()
    except CypherError as error:
        pytest.skip(f"configured Cyclus environment is not runnable: {error}")

    assert ":agents:NullInst" in metadata["specs"]
    assert ":agents:NullRegion" in metadata["specs"]
