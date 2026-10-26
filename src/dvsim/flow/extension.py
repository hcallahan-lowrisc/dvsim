# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Cfg extensions: hjson files merged into a named flow cfg (--cfg-extend).

An extension adds to a cfg that dvsim loads from the project tree, without
editing that tree. It is named on the command line as NAME=PATH, where NAME is
the ``name`` of the cfg to extend. That cfg may be the one dvsim was pointed at
or a child of a primary cfg: the extension reaches it either way.

The extension is loaded with its own ``import_cfgs`` and merged into the cfg
after the cfg's own files, with the usual rules: lists concatenate (so the
extension's entries follow the cfg's own), and a conflicting scalar is an
error. To change a scalar, an extension uses ``overrides``, which join the
cfg's own.

By default an extension that can't be loaded, merged or overridden stops the
run. With --on-cfg-extend-error skip, it is left out instead: the cfg runs as
if it had not been named, and its reports say that it was skipped and why.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dvsim.flow.hjson import load_hjson

__all__ = (
    "CfgExtension",
    "CfgExtensionSkip",
    "check_cfg_extension_overrides",
    "check_cfg_extensions_used",
    "load_cfg_extension",
    "override_names",
)


@dataclass(frozen=True)
class CfgExtension:
    """An extension file, and the name of the cfg it extends."""

    cfg_name: str
    path: Path

    @classmethod
    def parse(cls, value: str) -> "CfgExtension":
        """Parse NAME=PATH, as given to --cfg-extend.

        A relative PATH is taken from the current directory.
        """
        name, sep, path = value.partition("=")
        name, path = name.strip(), path.strip()
        if not sep or not name or not path:
            msg = f"Invalid cfg extension {value!r}: expected NAME=PATH."
            raise ValueError(msg)
        return cls(name, Path(path).resolve())


@dataclass(frozen=True)
class CfgExtensionSkip:
    """Why an extension was left out (--on-cfg-extend-error skip).

    A cfg holds this object rather than the bare reason, so that the cfg's
    wildcard expansion leaves the reason (which may quote a wildcard) as it is.
    """

    reason: str


def load_cfg_extension(
    ext: CfgExtension, initial_values: Mapping[str, object], arg_keys: Iterable[str]
) -> dict:
    """Load an extension file and its imports.

    initial_values holds what is needed to resolve the names of imported files,
    and arg_keys those of its keys that came from the command line (as for
    load_hjson). The returned data holds only what the extension sets.

    Raises a RuntimeError if the file can't be loaded or isn't allowed. Its
    message gives the reason only: the caller names the extension.
    """
    if not ext.path.is_file():
        msg = "it is not a file."
        raise RuntimeError(msg)

    try:
        data = load_hjson(str(ext.path), initial_values, set(arg_keys))
    except SystemExit as err:
        # parse_hjson logs why a file can't be parsed and exits.
        msg = "it, or a file it imports, can't be parsed (see above)."
        raise RuntimeError(msg) from err
    except ValueError as err:
        # An import_cfgs entry with a wildcard that can't be resolved.
        msg = f"it can't resolve the name of a file it imports: {err}"
        raise RuntimeError(msg) from err

    if "use_cfgs" in data:
        msg = "it sets use_cfgs: an extension can't add child cfgs."
        raise RuntimeError(msg)

    # Drop the initial values that the extension didn't set itself. One that it
    # did set, even to an equal value, is a different object and is kept, so
    # that a conflict with the cfg is reported.
    for key, value in initial_values.items():
        if data.get(key) is value:
            del data[key]

    return data


def check_cfg_extensions_used(
    extensions: Iterable[CfgExtension],
    used: Iterable[CfgExtension],
    cfg_names: Iterable[str],
    primary_name: str | None,
) -> list[str]:
    """Check that every extension was used by a loaded cfg.

    used are the extensions that some cfg matched. cfg_names are the names that
    the cfgs that can be extended had when they matched them (before any
    overrides); a primary cfg can't be extended, so its name is passed
    separately to give a clearer message. Returns a list of error messages
    (empty if all is well).
    """
    used = set(used)
    names = set(cfg_names)
    errors = []
    for ext in extensions:
        if ext in used:
            continue
        if ext.cfg_name == primary_name:
            errors.append(
                f"Cfg extension {ext.path} names the primary cfg {ext.cfg_name!r}: "
                "only a cfg that runs jobs (a child, or a cfg run on its own) can be extended."
            )
        else:
            known = ", ".join(sorted(names)) or "none"
            errors.append(
                f"Cfg extension {ext.path} names {ext.cfg_name!r}, but no loaded cfg has "
                f"that name (loaded: {known})."
            )
    return errors


def override_names(overrides: object) -> set[str]:
    """Return the names of the keys that an ``overrides`` list sets."""
    if not isinstance(overrides, list):
        return set()
    return {o["name"] for o in overrides if isinstance(o, dict) and isinstance(o.get("name"), str)}


def check_cfg_extension_overrides(overrides: object, cfg: object, taken: Iterable[str]) -> None:
    """Check an extension's overrides as the cfg will apply them.

    The cfg processes overrides only once every file is merged (see
    FlowCfg._process_overrides, whose checks these mirror). Checking an
    extension's own here, against the cfg it has just been merged into, lets
    a broken one (most often, a key that the cfg no longer has) be reported
    as that extension's fault. So an extension can only override keys that
    the cfg or an earlier extension define. taken are the keys already
    overridden before this extension.

    Raises a RuntimeError for the first problem found (its message gives the reason only).
    """
    if not isinstance(overrides, list):
        msg = "its 'overrides' must be a list."
        raise RuntimeError(msg)
    taken = set(taken)
    for item in overrides:
        if not (isinstance(item, dict) and set(item) == {"name", "value"}):
            msg = f"each of its overrides needs a name and a value, not {item!r}."
            raise RuntimeError(msg)
        name, value = item["name"], item["value"]
        if not isinstance(name, str):
            msg = f"each of its overrides needs a key name, not {name!r}."
            raise RuntimeError(msg)
        if name in taken:
            msg = f"it overrides {name!r}, which is already overridden."
            raise RuntimeError(msg)
        if not hasattr(cfg, name):
            msg = f"it overrides {name!r}, which the cfg doesn't have."
            raise RuntimeError(msg)
        old = getattr(cfg, name)
        if not isinstance(value, type(old)):
            msg = (
                f"it overrides {name!r} with {value!r}, "
                f"which doesn't match the type of its value {old!r}."
            )
            raise RuntimeError(msg)
        taken.add(name)
