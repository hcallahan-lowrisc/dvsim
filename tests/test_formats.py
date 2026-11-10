# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the format markers on the JSON files DVSim writes."""

import json
from pathlib import Path
from typing import Literal

import pytest
from hamcrest import assert_that, contains_string, empty, equal_to, has_length
from pydantic import ConfigDict, ValidationError

from dvsim.formats import UNMARKED_VERSION, MarkedFormat
from dvsim.instrumentation.records import InstrumentationResults, SchedulerInstrumentationResults

__all__ = ()


class Example(MarkedFormat):
    """A marked format for testing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["dvsim.example"] = "dvsim.example"
    schema_version: str = "2.1.0"

    value: int


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data))
    return path


class TestWrite:
    """Writing a marked format."""

    @staticmethod
    def test_marker_comes_first() -> None:
        """The marker is the first two fields, with the current version."""
        data = json.loads(Example(value=1).model_dump_json())

        assert_that(
            list(data.items())[:2],
            equal_to([("kind", "dvsim.example"), ("schema_version", "2.1.0")]),
        )


class TestLoad:
    """Loading a marked format."""

    @staticmethod
    def test_same_version(tmp_path: Path, dvsim_log: pytest.LogCaptureFixture) -> None:
        """A file of the current version loads without a warning."""
        path = _write(tmp_path / "a.json", Example(value=1).model_dump(mode="json"))

        assert_that(Example.load(path), equal_to(Example(value=1)))
        assert_that(dvsim_log.records, empty())

    @staticmethod
    def test_unmarked(tmp_path: Path, dvsim_log: pytest.LogCaptureFixture) -> None:
        """A file with no marker reads as version 1.0.0 of the format."""
        loaded = Example.load(_write(tmp_path / "a.json", {"value": 1}))

        assert_that(loaded.kind, equal_to("dvsim.example"))
        assert_that(loaded.schema_version, equal_to(UNMARKED_VERSION))
        assert_that(dvsim_log.records, empty())

    @staticmethod
    def test_newer_minor(tmp_path: Path, dvsim_log: pytest.LogCaptureFixture) -> None:
        """A newer minor version loads without a warning, ignoring added fields."""
        path = _write(
            tmp_path / "a.json",
            {"kind": "dvsim.example", "schema_version": "2.9.0", "value": 1, "added": True},
        )

        assert_that(Example.load(path).value, equal_to(1))
        assert_that(dvsim_log.records, empty())

    @staticmethod
    @pytest.mark.parametrize("version", ["3.0.0", "3", "not a version"])
    def test_newer_major(tmp_path: Path, dvsim_log: pytest.LogCaptureFixture, version: str) -> None:
        """A newer major version, or one that can't be read, warns and still loads."""
        path = _write(
            tmp_path / "a.json",
            {"kind": "dvsim.example", "schema_version": version, "value": 1},
        )

        assert_that(Example.load(path).schema_version, equal_to(version))
        assert_that(dvsim_log.records, has_length(1))
        assert_that(dvsim_log.records[0].getMessage(), contains_string(f"version {version}"))

    @staticmethod
    def test_other_kind(tmp_path: Path) -> None:
        """A file marked as another format is an error that names both."""
        path = _write(tmp_path / "a.json", {"kind": "dvsim.other", "value": 1})

        with pytest.raises(ValidationError) as error:
            Example.load(path)
        assert_that(str(error.value), contains_string("'dvsim.other' file, not 'dvsim.example'"))

    @staticmethod
    def test_build_is_unchecked() -> None:
        """Building a model in code takes the marker as given, with no load checks."""
        assert_that(Example(value=1).schema_version, equal_to("2.1.0"))
        assert_that(Example(schema_version="9.0.0", value=1).schema_version, equal_to("9.0.0"))


class TestInstrumentationLoad:
    """metrics.json keeps the extra metrics its models allow."""

    @staticmethod
    def test_keeps_extra_metrics(tmp_path: Path) -> None:
        """A metric from an instrumentation plugin survives a write and load."""
        results = InstrumentationResults(
            scheduler=SchedulerInstrumentationResults(plugin={"count": 3}),  # type: ignore[reportCallIssue]
        )
        path = _write(tmp_path / "metrics.json", results.model_dump(mode="json"))

        loaded = InstrumentationResults.load(path)

        assert_that(loaded.kind, equal_to("dvsim.instrumentation"))
        assert_that(loaded.scheduler.model_extra, equal_to({"plugin": {"count": 3}}))


class TestDeclare:
    """Declaring a marked format."""

    @staticmethod
    def test_marker_fields_required() -> None:
        """A subclass that leaves out a marker field, or its default, is an error."""
        with pytest.raises(TypeError, match="'schema_version'"):

            class _NoVersion(MarkedFormat):
                kind: Literal["dvsim.bad"] = "dvsim.bad"
                schema_version: str
