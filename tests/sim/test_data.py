# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the simulation results data models."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to
from pydantic import ValidationError

from dvsim.report.data import IPMeta, ToolMeta
from dvsim.sim.data import SimFlowResults, SimFlowSummary, SimResultsSummary
from dvsim.sim_results import BucketedFailures

__all__ = ()

IP = IPMeta(
    name="test_ip",
    commit="0123456789abcdef",
    commit_short="0123456",
    branch="main",
    url=None,
    revision_info=None,
)
TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _flow_results() -> SimFlowResults:
    return SimFlowResults(
        block=IP,
        tool=ToolMeta(name="vcs", version="1.0"),
        timestamp=TIMESTAMP,
        build_seed=None,
        testplan_ref=None,
        stages={},
        coverage=None,
        cov_report_page=None,
        vplan_report_page=None,
        failed_jobs=BucketedFailures(buckets={}),
        passed=1,
        total=1,
        percent=100.0,
    )


def _summary() -> SimResultsSummary:
    return SimResultsSummary(
        top=IP,
        version="1.0.0",
        timestamp=TIMESTAMP,
        build_seed=None,
        flow_results={"test_ip": _flow_results().summary()},
        report_path=Path("report.html"),
    )


def _write_with_unknown_keys(path: Path, data: dict, nested: str) -> None:
    """Write data as JSON with an unknown key added at the top and in data[nested]."""
    data["added_later"] = {"any": "value"}
    data[nested]["added_later"] = 1
    path.write_text(json.dumps(data))


class TestLoadIgnoresUnknownKeys:
    """Results written by a newer DVSim with added fields still load."""

    @staticmethod
    def test_flow_results(tmp_path: Path) -> None:
        """SimFlowResults.load ignores unknown keys, at the top and nested."""
        results = _flow_results()
        path = tmp_path / "test_ip.json"
        _write_with_unknown_keys(path, results.model_dump(mode="json"), "block")

        assert_that(SimFlowResults.load(path), equal_to(results))

    @staticmethod
    def test_flow_summary(tmp_path: Path) -> None:
        """SimFlowSummary.load ignores unknown keys, at the top and nested."""
        summary = _flow_results().summary()
        path = tmp_path / "test_ip.json"
        _write_with_unknown_keys(path, summary.model_dump(mode="json"), "block")

        assert_that(SimFlowSummary.load(path), equal_to(summary))

    @staticmethod
    def test_results_summary(tmp_path: Path) -> None:
        """SimResultsSummary.load ignores unknown keys, at the top and nested."""
        summary = _summary()
        data = summary.model_dump(mode="json")
        data["flow_results"]["test_ip"]["added_later"] = True
        path = tmp_path / "index.json"
        _write_with_unknown_keys(path, data, "top")

        assert_that(SimResultsSummary.load(path), equal_to(summary))


class TestBuildingRejectsUnknownFields:
    """Building results in code still rejects unknown fields, to catch typos."""

    @staticmethod
    def test_ip_meta() -> None:
        """An unknown field is an error when building a model directly."""
        with pytest.raises(ValidationError):
            IPMeta(**{**IP.model_dump(), "added_later": 1})

    @staticmethod
    def test_model_validate() -> None:
        """model_validate (not load) keeps the models' strictness."""
        data = _flow_results().model_dump(mode="json")
        data["added_later"] = 1
        with pytest.raises(ValidationError):
            SimFlowResults.model_validate(data)
