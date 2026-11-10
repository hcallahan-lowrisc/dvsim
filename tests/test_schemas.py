# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the committed JSON Schemas."""

from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to

from dvsim.formats import MarkedFormat
from dvsim.schemas import SCHEMA_DIR, formats, render_schema, schema_path

__all__ = ()


@pytest.mark.parametrize("model", formats(), ids=lambda m: m.__name__)
def test_schema_is_current(model: type[MarkedFormat]) -> None:
    """The committed schema is the one the model generates."""
    path = schema_path(model)
    committed = path.read_text(encoding="utf-8") if path.exists() else ""

    assert_that(
        committed,
        equal_to(render_schema(model)),
        f"{path.name} is out of date: regenerate the schemas with `python -m dvsim.schemas`",
    )


def test_no_stale_schemas() -> None:
    """Every committed schema belongs to a format."""
    assert_that(
        sorted(p.name for p in SCHEMA_DIR.glob("*.json")),
        equal_to(sorted(schema_path(m).name for m in formats())),
    )


def test_unknown_fields_allowed() -> None:
    """No schema forbids unknown fields, which readers must ignore."""
    for model in formats():
        assert_that('"additionalProperties": false' in render_schema(model), equal_to(False))


def test_write_schemas(tmp_path: Path) -> None:
    """write_schemas writes one schema per format."""
    from dvsim.schemas import write_schemas  # noqa: PLC0415

    paths = write_schemas(tmp_path)

    assert_that(sorted(p.name for p in paths), equal_to(sorted(p.name for p in tmp_path.iterdir())))
    assert_that(len(paths), equal_to(len(formats())))
