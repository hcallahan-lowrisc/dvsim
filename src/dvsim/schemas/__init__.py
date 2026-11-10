# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""JSON Schemas for the files DVSim writes for other tools to read.

The schemas are generated from the models, one per format, named after its
`kind`. They are committed next to this module, so they ship with DVSim and
show a format change in review. Readers ignore fields they don't know, so the
schemas allow them too: a file of a newer minor version still validates.
Regenerate the schemas after changing a model:

    python -m dvsim.schemas
"""

import json
from pathlib import Path

from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema

from dvsim.formats import MarkedFormat

__all__ = (
    "SCHEMA_DIR",
    "formats",
    "render_schema",
    "schema_path",
    "write_schemas",
)

SCHEMA_DIR = Path(__file__).parent
"""The directory the schemas are committed in."""

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


class _ReaderJsonSchema(GenerateJsonSchema):
    """Generate schemas that allow unknown fields, as readers must."""

    def model_schema(self, schema: core_schema.ModelSchema) -> JsonSchemaValue:
        """Leave out the "additionalProperties": false of models that forbid extras."""
        json_schema = super().model_schema(schema)
        if json_schema.get("additionalProperties") is False:
            del json_schema["additionalProperties"]
        return json_schema


def formats() -> tuple[type[MarkedFormat], ...]:
    """Return the models of the formats DVSim writes."""
    # Imported here: these modules import dvsim.formats, as this one does.
    from dvsim.instrumentation.records import InstrumentationResults  # noqa: PLC0415
    from dvsim.job.data import DeployDump  # noqa: PLC0415
    from dvsim.sim.data import SimFlowResults, SimResultsSummary  # noqa: PLC0415

    return (SimResultsSummary, SimFlowResults, InstrumentationResults, DeployDump)


def schema_path(model: type[MarkedFormat]) -> Path:
    """Return the path of a format's schema."""
    return SCHEMA_DIR / f"{model.model_fields['kind'].default}.json"


def render_schema(model: type[MarkedFormat]) -> str:
    """Return the JSON Schema of the files a model is written to."""
    schema = {
        "$schema": JSON_SCHEMA_DIALECT,
        **model.model_json_schema(mode="serialization", schema_generator=_ReaderJsonSchema),
    }
    return json.dumps(schema, indent=2) + "\n"


def write_schemas(directory: Path = SCHEMA_DIR) -> list[Path]:
    """Write the schema of every format to a directory.

    Returns:
        The paths written.

    """
    paths = []
    for model in formats():
        path = directory / schema_path(model).name
        path.write_text(render_schema(model), encoding="utf-8")
        paths.append(path)
    return paths
