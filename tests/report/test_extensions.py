# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test how reports show the cfg extensions (--cfg-extend) of a flow."""

from datetime import datetime, timezone
from pathlib import Path

from dvsim.report.data import CfgExtensionMeta, GitRevisionMeta, IPMeta, ToolMeta
from dvsim.sim.data import SimFlowResults, SimResultsSummary
from dvsim.sim.report import HtmlReportRenderer, MarkdownReportRenderer
from dvsim.sim_results import BucketedFailures

__all__ = ()

TS = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _results(*extensions: CfgExtensionMeta) -> SimFlowResults:
    return SimFlowResults(
        block=IPMeta(
            name="blk",
            commit="c" * 40,
            commit_short="c" * 7,
            branch="b",
            url=None,
            revision_info=None,
        ),
        tool=ToolMeta(name="vcs", version="1"),
        timestamp=TS,
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
        extensions=extensions,
    )


def _summary(results: SimFlowResults) -> SimResultsSummary:
    return SimResultsSummary(
        top=None,
        version=None,
        timestamp=TS,
        build_seed=None,
        flow_results={"blk": results.summary()},
        report_path=Path("/reports"),
    )


MERGED = CfgExtensionMeta(path="/overlay/ok.hjson")
SKIPPED = CfgExtensionMeta(path="/overlay/broken.hjson", skipped="key 'x' not found")


class TestExtensionsInReports:
    def test_summary_keeps_extensions(self) -> None:
        assert _results(MERGED, SKIPPED).summary().extensions == (MERGED, SKIPPED)

    def test_json_round_trip(self) -> None:
        results = _results(MERGED, SKIPPED)
        assert SimFlowResults.model_validate_json(results.model_dump_json()) == results

    def test_markdown_names_skipped_extensions(self) -> None:
        results = _results(MERGED, SKIPPED)
        renderer = MarkdownReportRenderer()

        block = renderer.render_block(results)["report.md"]
        summary = renderer.render_summary(_summary(results))["report.md"]

        assert (
            "**Warning:** cfg extension `/overlay/broken.hjson` skipped: key 'x' not found" in block
        )
        # Merged extensions are listed, without a warning.
        assert "* `/overlay/ok.hjson`" in block
        assert "`/overlay/ok.hjson` skipped" not in block
        assert "BLK (1 extension skipped)" in summary

    def test_markdown_without_skipped_extensions(self) -> None:
        results = _results(MERGED)
        renderer = MarkdownReportRenderer()

        assert "skipped" not in renderer.render_block(results)["report.md"]
        assert "skipped" not in renderer.render_summary(_summary(results))["report.md"]

    def test_html_names_skipped_extensions(self) -> None:
        results = _results(MERGED, SKIPPED)

        pages = HtmlReportRenderer().render(_summary(results), {"blk": results})

        assert (
            "/overlay/broken.hjson</code> skipped: key &#39;x&#39; not found" in pages["blk.html"]
        )
        assert "1 extension skipped" in pages["index.html"]

    def test_html_without_skipped_extensions(self) -> None:
        results = _results(MERGED)

        pages = HtmlReportRenderer().render(_summary(results), {"blk": results})

        assert "skipped" not in pages["blk.html"]
        assert "extension skipped" not in pages["index.html"]


TRACKED = CfgExtensionMeta(
    path="/overlay/dv/ext.hjson",
    revision=GitRevisionMeta(
        origin="git@example.com:org/overlay.git",
        commit="a" * 40,
        commit_short="aaaaaaa",
        dirty=True,
    ),
)


class TestExtensionRevisions:
    def test_markdown_gives_the_revision(self) -> None:
        block = MarkdownReportRenderer().render_block(_results(TRACKED, MERGED))["report.md"]

        assert (
            "### Cfg extensions:\n\n* `/overlay/dv/ext.hjson` (revision `aaaaaaa`, dirty, "
            "from git@example.com:org/overlay.git)\n* `/overlay/ok.hjson`\n" in block + "\n"
        )

    def test_skipped_gives_the_revision(self) -> None:
        skipped = TRACKED.model_copy(update={"skipped": "it is not a file."})

        block = MarkdownReportRenderer().render_block(_results(skipped))["report.md"]
        page = HtmlReportRenderer().render(_summary(_results(skipped)), {"blk": _results(skipped)})

        assert "(revision `aaaaaaa`, dirty, from git@example.com:org/overlay.git) skipped" in block
        assert "### Cfg extensions" not in block
        assert "(sha: aaaaaaa, dirty)" in page["blk.html"]

    def test_html_gives_the_revision(self) -> None:
        results = _results(TRACKED)

        page = HtmlReportRenderer().render(_summary(results), {"blk": results})["blk.html"]

        assert "Extension: ext.hjson sha: aaaaaaa (dirty)" in page
        assert "git@example.com:org/overlay.git" in page
        assert "a" * 40 in page
