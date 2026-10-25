# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the retry settings of build modes, run modes and tests, and their reports."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from dvsim.job.deploy import Deploy
from dvsim.modes import DEFAULT_RETRY_DELAY_SECS, BuildMode, RetrySettings, RunMode
from dvsim.regression import Regression
from dvsim.report.data import IPMeta, ToolMeta
from dvsim.sim import data
from dvsim.sim.report import HtmlReportRenderer, MarkdownReportRenderer
from dvsim.sim_results import BucketedFailures
from dvsim.test import Test as DvsimTest

LIC = r"licen[cs]e checkout failed"


class TestRetrySettings:
    """Parsing and checking retry_patterns and max_retries."""

    def test_defaults(self) -> None:
        mode = BuildMode({"name": "default"})
        assert (mode.retry_patterns, mode.max_retries, mode.retry_delay_secs) == ([], None, None)

    @pytest.mark.parametrize("cls", [BuildMode, RunMode, DvsimTest])
    def test_set(self, cls) -> None:
        mode = cls(
            {"name": "m", "retry_patterns": [LIC], "max_retries": 2, "retry_delay_secs": 1.5}
        )
        assert (mode.retry_patterns, mode.max_retries, mode.retry_delay_secs) == ([LIC], 2, 1.5)

    @pytest.mark.parametrize(
        "settings",
        [
            {"retry_patterns": LIC},
            {"retry_patterns": ["(unclosed"]},
            {"max_retries": -1},
            {"max_retries": "2"},
            {"max_retries": True},
            {"retry_delay_secs": -1},
            {"retry_delay_secs": "10"},
        ],
    )
    def test_invalid(self, settings) -> None:
        with pytest.raises(SystemExit):
            BuildMode({"name": "m", **settings})

    def test_merge_two_files(self) -> None:
        """A mode defined in two files gets the patterns of both."""
        mode = BuildMode({"name": "m", "retry_patterns": ["a"]})
        mode.merge_mode(BuildMode({"name": "m", "retry_patterns": ["b"], "max_retries": 1}))
        assert (mode.retry_patterns, mode.max_retries) == (["a", "b"], 1)


class TestInheritance:
    """A test takes the retry settings of its build mode."""

    @staticmethod
    def _create(test: dict, build: dict):
        sim_cfg = SimpleNamespace(
            build_modes=[BuildMode({"name": "b", **build})],
            run_modes=[],
            en_run_modes=[],
        )
        (obj,) = DvsimTest.create_tests([{"name": "t", "build_mode": "b", **test}], sim_cfg)
        return obj

    def test_from_build_mode(self) -> None:
        test = self._create({}, {"retry_patterns": [LIC], "max_retries": 2})
        assert (test.retry_patterns, test.max_retries) == ([LIC], 2)

    def test_own_settings_win(self) -> None:
        test = self._create(
            {"retry_patterns": ["timeout", LIC], "max_retries": 1},
            {"retry_patterns": [LIC], "max_retries": 3, "retry_delay_secs": 5},
        )
        # The patterns of both, once each; the test's own count, and the build mode's delay.
        assert (test.retry_patterns, test.max_retries, test.retry_delay_secs) == (
            ["timeout", LIC],
            1,
            5,
        )


class TestJobSettings:
    """The settings a job gets from its mode or test."""

    @staticmethod
    def _job(**settings: object) -> SimpleNamespace:
        job = SimpleNamespace(retry_patterns=[], max_retries=0, retry_delay_secs=0)
        mode = SimpleNamespace(
            **{"retry_patterns": [], "max_retries": None, "retry_delay_secs": None, **settings}
        )
        Deploy._set_retries(job, mode)
        return job

    def test_no_patterns_no_retries(self) -> None:
        assert self._job(max_retries=3).max_retries == 0

    def test_defaults_with_patterns(self) -> None:
        """Patterns alone give one retry, after the default delay."""
        job = self._job(retry_patterns=[LIC])
        assert (job.max_retries, job.retry_delay_secs) == (1, DEFAULT_RETRY_DELAY_SECS)

    def test_given(self) -> None:
        job = self._job(retry_patterns=[LIC], max_retries=0, retry_delay_secs=0)
        assert (job.max_retries, job.retry_delay_secs) == (0, 0)


def _sim_cfg(**kwargs: object) -> SimpleNamespace:
    """A sim cfg with a sim mode and a run mode that each give retry settings."""
    build_modes = BuildMode.create_modes(
        [
            {"name": "default"},
            {"name": "lic", "is_sim_mode": 1, "retry_patterns": ["b"], "max_retries": 2},
        ]
    )
    run_modes = RunMode.create_modes([{"name": "slow", "retry_patterns": ["r"]}])
    cfg = SimpleNamespace(
        build_modes=build_modes, run_modes=run_modes, en_build_modes=[], en_run_modes=[]
    )
    cfg.__dict__.update(kwargs)
    cfg.tests = DvsimTest.create_tests([{"name": "t", "build_mode": "default"}], cfg)
    return cfg


class TestEnabledForTheRun:
    """Modes enabled for a whole run or regression pass their retry settings on."""

    def test_global_modes(self) -> None:
        cfg = _sim_cfg()
        build = RetrySettings(retry_patterns=["b"], max_retries=2)
        run = RetrySettings(retry_patterns=["b", "r"], max_retries=2)
        DvsimTest.merge_global_opts(cfg.tests, *[[]] * 9, {}, {}, build, run)
        (test,) = cfg.tests
        assert (test.build_mode.retry_patterns, test.build_mode.max_retries) == (["b"], 2)
        assert (test.retry_patterns, test.max_retries) == (["b", "r"], 2)

    def test_regression_modes(self) -> None:
        cfg = _sim_cfg()
        (regr,) = Regression.create_regressions(
            [{"name": "r", "en_sim_modes": ["lic"], "en_run_modes": ["slow"]}], cfg, cfg.tests
        )
        regr.merge_regression_opts()
        (test,) = regr.tests
        assert (test.build_mode.retry_patterns, test.build_mode.max_retries) == (["b"], 2)
        assert (test.retry_patterns, test.max_retries) == (["b", "r"], 2)


BLOCK = IPMeta(
    name="blk", commit="c0ffee", commit_short="c0f", branch="main", url=None, revision_info=None
)
TIMESTAMP = datetime(2026, 10, 25, tzinfo=timezone.utc)


def _flow(retried: dict[str, int]) -> data.SimFlowResults:
    return data.SimFlowResults(
        block=BLOCK,
        tool=ToolMeta(name="vcs", version="1"),
        timestamp=TIMESTAMP,
        build_seed=None,
        testplan_ref=None,
        stages={},
        coverage=None,
        cov_report_page=None,
        vplan_report_page=None,
        failed_jobs=BucketedFailures(buckets={}),
        passed=0,
        total=0,
        percent=0.0,
        retried_jobs=retried,
    )


class TestRetryReports:
    """Retried jobs are listed in the block reports, and only when there are some."""

    def test_markdown(self) -> None:
        md = MarkdownReportRenderer(None).render_block(_flow({"0.ok": 1, "build": 2}))["report.md"]
        assert "## Retried Jobs" in md
        assert "* `0.ok`: 1 retry" in md
        assert "* `build`: 2 retries" in md

    def test_markdown_none(self) -> None:
        md = MarkdownReportRenderer(None).render_block(_flow({}))["report.md"]
        assert "Retried Jobs" not in md

    def test_html(self) -> None:
        flow = _flow({"0.ok": 1})
        summary = data.SimResultsSummary(
            top=None,
            version=None,
            timestamp=TIMESTAMP,
            build_seed=None,
            flow_results={"blk": flow.summary()},
            report_path=Path("/scratch/reports"),
        )
        block = HtmlReportRenderer().render(summary, {"blk": flow})["blk.html"]
        assert "Retried Jobs" in block
        assert "<td>0.ok</td><td>1</td>" in block
