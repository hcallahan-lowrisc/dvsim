# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the job data models."""

import json
from pathlib import Path

from hamcrest import assert_that, equal_to, has_item, is_not

from dvsim.job.data import DeployDump
from tests.test_scheduler import job_spec_factory

__all__ = ()


class TestDeployDump:
    """The deploy_<branch>_<timestamp>.json dump."""

    @staticmethod
    def test_dump(tmp_path: Path) -> None:
        """The dump is the marker and the jobs, which are as they were in version 1.0.0."""
        jobs = [job_spec_factory(tmp_path, name=name) for name in ("a", "b")]

        data = json.loads(DeployDump(jobs=jobs).model_dump_json())

        assert_that(
            list(data),
            equal_to(["kind", "schema_version", "jobs"]),
        )
        assert_that(data["kind"], equal_to("dvsim.deploy"))
        assert_that(data["schema_version"], equal_to("2.0.0"))
        # Version 1.0.0 was a list of these, with the callbacks left out
        assert_that(
            data["jobs"],
            equal_to(
                [j.model_dump(exclude={"pre_launch", "post_finish"}, mode="json") for j in jobs]
            ),
        )
        assert_that(data["jobs"][0], is_not(has_item("pre_launch")))
