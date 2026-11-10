# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Regenerate the committed JSON Schemas: `python -m dvsim.schemas`."""

from dvsim.schemas import write_schemas

for path in write_schemas():
    print(path)  # noqa: T201
