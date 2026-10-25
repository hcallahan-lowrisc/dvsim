# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for loading hjson cfg files."""

from pathlib import Path

import pytest

from dvsim.flow.hjson import load_hjson


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A scratch directory."""
    return tmp_path


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestFileDir:
    def test_each_file_sees_its_own_directory(self, root: Path) -> None:
        """{file_dir} names the directory of the file it is written in."""
        top = _write(
            root / "top.hjson",
            """{
              import_cfgs: ["{proj_root}/overlay/sub/ext.hjson"]
              top_file: "{file_dir}/top.txt"
              opts: ["{file_dir}/a.f"]
            }""",
        )
        _write(
            root / "overlay" / "sub" / "ext.hjson",
            """{
              import_cfgs: ["{file_dir}/../more.hjson"]
              opts: ["+incdir+{file_dir}"]
              modes: [{name: "m", build_opts: ["-f {file_dir}/m.f"]}]
            }""",
        )
        _write(root / "overlay" / "more.hjson", '{opts: ["{file_dir}/more.f"]}')

        data = load_hjson(str(top), {"proj_root": str(root)})

        sub = root / "overlay" / "sub"
        assert data["top_file"] == f"{root}/top.txt"
        assert data["opts"] == [
            f"{root}/a.f",
            f"+incdir+{sub}",
            f"{root}/overlay/more.f",
        ]
        assert data["modes"] == [{"name": "m", "build_opts": [f"-f {sub}/m.f"]}]

    def test_relative_path_gives_absolute_dir(self, root: Path, monkeypatch) -> None:
        """A cfg named by a relative path still gets an absolute {file_dir}."""
        _write(root / "cfg" / "top.hjson", '{dir: "{file_dir}"}')
        monkeypatch.chdir(root)

        data = load_hjson("cfg/top.hjson", {})

        assert data["dir"] == str(root / "cfg")

    def test_symlinks_are_kept(self, root: Path) -> None:
        """{file_dir} spells a directory reached through a symlink as {proj_root} does."""
        _write(root / "real" / "top.hjson", '{dir: "{file_dir}"}')
        (root / "link").symlink_to(root / "real")

        data = load_hjson(str(root / "link" / "top.hjson"), {})

        assert data["dir"] == str(root / "link")

    def test_only_strings_change(self, root: Path) -> None:
        """Numbers and booleans pass through; strings in overrides are expanded too."""
        top = _write(
            root / "top.hjson",
            '{n: 3, b: true, overrides: [{name: "x", value: "{file_dir}/x"}]}',
        )

        data = load_hjson(str(top), {})

        assert (data["n"], data["b"]) == (3, True)
        assert data["overrides"] == [{"name": "x", "value": f"{root}/x"}]

    def test_other_wildcards_are_left_alone(self, root: Path) -> None:
        """Only {file_dir} is expanded at load time; the rest wait for the flow."""
        top = _write(root / "top.hjson", '{x: "{self_dir}/{file_dir}/{build_mode}"}')

        data = load_hjson(str(top), {})

        assert data["x"] == f"{{self_dir}}/{root}/{{build_mode}}"
