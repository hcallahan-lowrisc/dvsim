# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Format markers for the JSON files DVSim writes for other tools to read.

Each such file starts with two fields: `kind` names its format, and
`schema_version` gives the version of that format as MAJOR.MINOR.PATCH:

- MAJOR: a breaking change: a field removed or renamed, or given a new type
  or meaning.
- MINOR: a field added. Readers ignore fields they don't know, so a file
  with a newer minor version still loads.
- PATCH: a change that leaves the fields as they were, such as a clearer
  description.

A file with no marker was written before DVSim added them, and reads as
version 1.0.0.
"""

from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationInfo, model_validator
from pydantic.config import ExtraValues
from typing_extensions import Self

from dvsim.logging import log

__all__ = (
    "UNMARKED_VERSION",
    "MarkedFormat",
)

UNMARKED_VERSION = "1.0.0"
"""The version of a file written before DVSim marked its formats."""


def _major(version: str) -> int | None:
    """Return the major version of a MAJOR.MINOR.PATCH string, or None if it isn't one."""
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):  # noqa: PLR2004
        return None
    return int(parts[0])


class MarkedFormat(BaseModel):
    """Base class for a model that is written to a file with a format marker.

    A subclass declares the marker as its first two fields: `kind`, with a
    `Literal` type and the format's name as the default, and `schema_version`,
    with the version it writes as the default.
    """

    load_extra: ClassVar[ExtraValues | None] = "ignore"
    """How `load()` treats fields it doesn't know: "ignore" them, or None to
    leave it to each model's own `extra` setting."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        """Check that the subclass declares the marker fields with defaults."""
        super().__pydantic_init_subclass__(**kwargs)
        for name in ("kind", "schema_version"):
            field = cls.model_fields.get(name)
            if field is None or not isinstance(field.default, str):
                msg = f"{cls.__name__} must declare {name!r} with a string default"
                raise TypeError(msg)

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load a file of this format.

        Fields this DVSim doesn't know are ignored, unless the class sets
        `load_extra` otherwise.

        Args:
            path: to the JSON file to load.

        Raises:
            ValidationError: if the file doesn't match the model, or is marked
                as another format.

        """
        return cls.model_validate_json(
            path.read_text(encoding="utf-8"),
            extra=cls.load_extra,
            context={"path": path},
        )

    @model_validator(mode="before")
    @classmethod
    def _check_marker(cls, data: Any, info: ValidationInfo) -> Any:  # noqa: ANN401
        """Check the marker of a file being loaded; leave other data as it is."""
        if not isinstance(data, dict) or not info.context or "path" not in info.context:
            return data

        path = info.context["path"]
        kind = cls.model_fields["kind"].default
        version = cls.model_fields["schema_version"].default

        if data.setdefault("kind", kind) != kind:
            msg = f"{path} is a {data['kind']!r} file, not {kind!r}"
            raise ValueError(msg)

        file_version = data.setdefault("schema_version", UNMARKED_VERSION)
        file_major = _major(file_version) if isinstance(file_version, str) else None
        if file_major is None or file_major > (_major(version) or 0):
            log.warning(
                "%s has %s format version %s, but this DVSim reads version %s. "
                "Trying to load it anyway: if that fails, use a newer DVSim.",
                path,
                kind,
                file_version,
                version,
            )

        return data
