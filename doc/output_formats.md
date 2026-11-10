<!--
# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
-->

# Output formats: markers, schemas and compatibility

DVSim writes JSON files that other tools read: the results of a regression,
the scheduler's metrics, and the list of jobs it deployed. This page says
which files those are, how each one says what format it is, what DVSim
promises about how the formats change, and how to check a tool that reads
them.

If you only want the rules for a tool that reads these files, go to
[Writing a reader](#writing-a-reader). If you change one of DVSim's models,
go to [Changing a format](#changing-a-format).

## Why the formats have a contract

Several tools read DVSim's output:

- `dvsim-admin report gen` rebuilds the HTML report from `index.json` and
  the per-block files, and `dvsim-admin dashboard gen` builds a dashboard
  from `index.json`.
- Dashboards and metrics services load the results of nightly regressions
  into a database.
- CI scripts check pass rates or coverage, or archive the files.

These tools are often a different version from the DVSim that wrote the
files: a dashboard reads the results of many runs, written over months by
whichever DVSim each project used at the time. Before the files had a
contract, three problems followed:

1. **Adding a field broke readers.** DVSim's own readers rejected any field
   they didn't know. A file written by a newer DVSim that had gained a field
   could not be read by an older `dvsim-admin`. To stay readable, a new field
   had to be left out of the file whenever it was empty, which only moved
   the problem to the first run where it wasn't.
2. **Readers had to guess what a file was.** Nothing in a file named its
   format. Readers told an `index.json` from a per-block file by which keys
   it had, and broke if those keys changed.
3. **Format changes were not announced.** DVSim's version says when its
   command line or Python API breaks, but nothing said when an output file
   changed. A reader learned about a change by failing on it.

The contract fixes these:

- Every file names its format and that format's version
  ([format markers](#format-markers)).
- The version follows semantic versioning, and DVSim releases follow it: a
  breaking format change is a breaking DVSim change
  ([compatibility guarantees](#compatibility-guarantees)).
- Readers ignore fields they don't know, so adding a field is safe.
- Each format has a JSON Schema that ships with DVSim, so a reader can check
  what it may rely on ([schemas](#schemas)).

## The files

| Format (`kind`) | File | Written by | Version |
|---|---|---|---|
| `dvsim.sim.summary` | `<scratch>/reports/index.json` | `dvsim` sim flow, at the end of a run | 1.0.0 |
| `dvsim.sim.summary` | `<output_dir>/dashboard.json` | `dvsim-admin dashboard gen` | 1.0.0 |
| `dvsim.sim.flow` | `<scratch>/reports/<block>.json`, or `<block>_<variant>.json` for a block with a variant | `dvsim` sim flow, one per block | 1.0.0 |
| `dvsim.instrumentation` | `<scratch>/reports/metrics.json` | `dvsim --instrument ...` | 1.0.0 |
| `dvsim.deploy` | `<scratch_root>/deploy_<branch>_<timestamp>.json` | `dvsim`, before it runs the jobs | 2.0.0 |

`<scratch>` is the top-level config's `scratch_base_path`, which the project
config sets: OpenTitan's is `{scratch_root}/{branch}`.

- `dvsim.sim.summary` is the run as a whole: the top-level config, the DVSim
  version, the time stamp and a summary per block (pass counts and
  coverage). Read the per-block files for the details.
- `dvsim.sim.flow` is one block's results: test stages and testpoints with
  pass counts, coverage, and the failed jobs grouped by error message.
- `dvsim.instrumentation` is the scheduler's own measurements: run time, and
  per-job timing and resource use, depending on which `--instrument` types
  were chosen (`meta`, `timing`, `compute` or `all`).
- `dvsim.deploy` is every job DVSim was about to run, as it was configured:
  command, paths, dependencies, seeds and so on. It is for debugging a run,
  and DVSim doesn't read it back.

The formats are defined by the Pydantic models that write them:

| Format | Model |
|---|---|
| `dvsim.sim.summary` | `dvsim.sim.data.SimResultsSummary` |
| `dvsim.sim.flow` | `dvsim.sim.data.SimFlowResults` |
| `dvsim.instrumentation` | `dvsim.instrumentation.records.InstrumentationResults` |
| `dvsim.deploy` | `dvsim.job.data.DeployDump` |

### Not covered

These files are not part of this contract yet:

- The `results.hjson` files that the external result parsers of the formal,
  synthesis, CDC and lint flows write for DVSim to read. Their fields are
  described in those flows' docstrings only.
- DVSim's inputs: flow configs, testplans and mode definitions.
- The HTML reports, badges and console output. They are for people, and may
  change in any release.

## Format markers

Each file starts with two fields:

```json
{
  "kind": "dvsim.sim.summary",
  "schema_version": "1.0.0",
  "top": { "...": "..." },
  "flow_results": { "...": "..." }
}
```

- `kind` names the format. A reader should check it rather than guess from
  the other keys.
- `schema_version` is the version of that format, as `MAJOR.MINOR.PATCH`.
  Each format has its own version, independent of DVSim's own version and
  of the other formats.

The version changes like this:

| Change to the format | Version bump | Example |
|---|---|---|
| A field is removed or renamed, changes type or meaning, or may now be missing or `null` where it was always there | **major** | `1.4.0` → `2.0.0` |
| A field is added, or a field that could be missing or `null` is now always there | minor | `1.4.0` → `1.5.0` |
| No field changes: a clearer description, say | patch | `1.4.0` → `1.4.1` |

A field "changes meaning" if a reader that kept using it as before would get
a wrong answer: a percentage that becomes a fraction, a count that starts
including skipped tests, a path that becomes relative to somewhere else.

### Files without a marker

Files written before DVSim added the markers have neither field. They are
version 1.0.0 of their format: the formats were the same, apart from the
marker. DVSim reads them as such, and other readers should too.

The one exception is the deploy dump. Before the markers it was a JSON list
of jobs, which has nowhere to put a marker, so it became an object with the
list under `jobs`. That changed its shape, so the list is version 1.0.0 and
the object is 2.0.0:

```json
{
  "kind": "dvsim.deploy",
  "schema_version": "2.0.0",
  "jobs": [ { "name": "uart_smoke", "...": "..." } ]
}
```

A reader of the deploy dump that must handle both can check the type of the
top-level value: a list is 1.0.0, and the entries are the same in both
versions.

## Compatibility guarantees

### What DVSim promises about the files it writes

- Within one major version of a format, every field keeps its name, its type
  and its meaning, and a field that was always present, and never `null`,
  stays so. Fields are only added.
- A field that may be `null` is shown as such in the schema. A reader must
  handle `null` for such a field even if it has never seen one.
- A change to a format's major version is a breaking change to DVSim, and is
  released as a major DVSim release with a `BREAKING CHANGE` note in the
  changelog (see [Releasing DVSim](./releasing.md)). A minor or patch change to
  a format comes in a minor or patch DVSim release.
- The schema of each format, as of each release, ships in that release (see
  [Schemas](#schemas)).

Nothing promises the order of fields, apart from the marker coming first, or
the order of entries in a mapping. Whitespace and number formatting may also
change.

### What DVSim's own readers do

`dvsim-admin` and anything else that loads these files through the models'
`load()` method behave like this:

| The file is... | DVSim... |
|---|---|
| unmarked | reads it as version 1.0.0 |
| the same major version, any minor or patch | reads it. Fields it doesn't know, at any depth, are ignored |
| a newer major version, or a version it can't parse | logs a warning naming the file, its version and the version this DVSim reads, then tries to read it anyway. This works if the fields this DVSim needs kept their meaning. Otherwise reading fails with a validation error: use a newer DVSim |
| another `kind` | fails with an error naming both kinds |

So an older DVSim reads files from a newer one of the same major version,
and a newer DVSim reads unmarked files from before the markers.

Two limits:

- DVSim 1.59.1 and older reject any field they don't know, including the
  markers. They can't read files from a DVSim that writes markers. Use the
  same or a newer DVSim to read them.
- `metrics.json` is read with its models' own settings, so that the metrics
  an instrumentation plugin adds are kept rather than dropped. Some of its
  models still reject unknown fields, so a field added to them will not
  load in an older DVSim.

Building the models in Python is stricter than loading a file: passing a
field a model doesn't have is an error, so a misspelt field fails where the
results are made rather than producing a file without it.

## Schemas

Each format has a [JSON Schema](https://json-schema.org/) (draft 2020-12),
generated from its model. The schemas are in the `dvsim/schemas/` directory
of the installed package, named after the format's `kind`:

```text
dvsim/schemas/dvsim.sim.summary.json
dvsim/schemas/dvsim.sim.flow.json
dvsim/schemas/dvsim.instrumentation.json
dvsim/schemas/dvsim.deploy.json
```

To find them in an installed DVSim:

```sh
python -c 'from dvsim.schemas import SCHEMA_DIR; print(SCHEMA_DIR)'
```

In the source tree they are at `src/dvsim/schemas/`, so each release tag
from their introduction on has the schemas of that release.

What a schema says:

- Every field a file of that format can have, with its type, and the
  definitions of nested objects under `$defs`.
- Which fields are always present (`required`). Fields that are not required
  may be missing.
- Which fields may be `null` (an `anyOf` with `"type": "null"`).
- `kind` as a constant, and the current `schema_version` as the default of
  that field.

What a schema allows on purpose:

- **Fields it doesn't list.** Readers must ignore unknown fields, so the
  schemas don't forbid them: a file of a newer minor version, with fields
  added since, still validates against the older schema.
- **A missing `kind` or `schema_version`.** Files from before the markers
  have neither, and are still version 1.0.0.

The schemas describe the files as written, not the Python models: the
models' Python properties (such as the coverage averages) and the fields left
out when writing (such as a job's callbacks) are not in them.

## Writing a reader

These rules let a tool read files from DVSim versions older and newer than
the one it was written against:

1. **Check `kind`**, and treat a missing `kind` as the format you expected.
   Don't tell formats apart by their other keys.
2. **Check the major version.** Treat a missing `schema_version` as `1.0.0`.
   Read any version with the major version you know. For a newer major
   version, either refuse with a clear message or warn and carry on, which
   is what DVSim does; don't fail somewhere later with an unrelated error.
3. **Ignore fields you don't know**, at every level. Don't turn on "reject
   unknown fields" in your parser.
4. **Only rely on fields the schema marks as required**, and handle `null`
   wherever the schema allows it.
5. **Don't rely on order**, of fields or of mapping entries.

In Python, without DVSim:

```python
import json
from pathlib import Path

KNOWN_MAJOR = 1


def load_summary(path: Path) -> dict:
    data = json.loads(path.read_text())
    kind = data.get("kind", "dvsim.sim.summary")
    if kind != "dvsim.sim.summary":
        raise ValueError(f"{path} is a {kind!r} file, not a DVSim results summary")
    version = data.get("schema_version", "1.0.0")
    if int(version.split(".")[0]) != KNOWN_MAJOR:
        raise ValueError(f"{path} is summary format {version}; this tool reads {KNOWN_MAJOR}.x")
    return data
```

In Python with DVSim installed, use the models; they apply all the rules
above:

```python
from pathlib import Path

from dvsim.sim.data import SimResultsSummary

summary = SimResultsSummary.load(Path("reports/index.json"))
flows = summary.load_flow_results(base_path=Path("reports"))
```

In Rust with `serde`, unknown fields are ignored unless a struct asks
otherwise. Don't add `#[serde(deny_unknown_fields)]`, and give the marker
fields defaults:

```rust
#[derive(serde::Deserialize)]
struct Summary {
    #[serde(default = "summary_kind")]
    kind: String,
    #[serde(default = "unmarked_version")]
    schema_version: String,
    flow_results: std::collections::BTreeMap<String, FlowSummary>,
    // ...only the fields this tool uses
}

fn summary_kind() -> String { "dvsim.sim.summary".into() }
fn unmarked_version() -> String { "1.0.0".into() }
```

With `jq`, read the marker the same way:

```sh
jq -r '[.kind // "dvsim.sim.summary", .schema_version // "1.0.0"] | @tsv' reports/index.json
```

## Checking a reader against the schemas

The schemas let you check, in your tool's own CI, that it reads what DVSim
writes and that it will notice when that changes.

### Validate the files you test with

If your tool's tests use DVSim output files as fixtures, validate them
against the schema of the DVSim version you support. That catches fixtures
written by hand that DVSim would never produce. With
[`check-jsonschema`](https://check-jsonschema.readthedocs.io/):

```sh
SCHEMAS=$(python -c 'from dvsim.schemas import SCHEMA_DIR; print(SCHEMA_DIR)')
check-jsonschema --schemafile "$SCHEMAS/dvsim.sim.summary.json" tests/fixtures/index.json
check-jsonschema --schemafile "$SCHEMAS/dvsim.sim.flow.json" tests/fixtures/uart.json
```

Or in Python with [`jsonschema`](https://python-jsonschema.readthedocs.io/):

```python
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from dvsim.schemas import SCHEMA_DIR

schema = json.loads((SCHEMA_DIR / "dvsim.sim.summary.json").read_text())
Draft202012Validator(schema).validate(json.loads(Path("tests/fixtures/index.json").read_text()))
```

### Generate real files without a simulator

`dvsim --fake` runs a regression with a fake launcher that makes up results
instead of running any tools, and writes the same files as a real run. That
gives your CI real output from the DVSim version it pins, with no EDA tools
or licences:

```sh
dvsim path/to/foo_sim_cfg.hjson --proj-root path/to/project -i foo_smoke --fake \
    -t vcs --scratch-root /tmp/dvsim-fake
# reports in /tmp/dvsim-fake/<branch>/reports/
```

The run exits with an error when the made-up results include failures. That
is expected: check the files, not the exit code.

### Check the fields you rely on

A schema lists every field. Your tool uses some of them. List those fields
in your tests and check that the schema still has each one, with the type you
expect, and as required if you don't handle its absence. A test like that
fails on the DVSim upgrade that would have broken your tool, instead of on
the next nightly run.

### Compare two DVSim versions

To see how the formats changed between two DVSim releases, compare their
schemas:

```sh
git -C path/to/dvsim diff <old-tag> <new-tag> -- src/dvsim/schemas/
```

A field that disappears, changes type, leaves a `required` list or becomes
nullable is a breaking change, and the format's major version will have
changed with it. A new property, or a field joining a `required` list, is an
addition.

## How it works

This section is for DVSim developers.

### Markers and loading

`dvsim.formats.MarkedFormat` is the base class of every model that is
written to a file. A subclass declares the marker as its first two fields:

```python
class SimResultsSummary(MarkedFormat):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["dvsim.sim.summary"] = "dvsim.sim.summary"
    schema_version: str = "1.0.0"
    ...
```

DVSim checks the declaration when the class is defined, and fails if
either field or its default is missing. Because they are the first fields,
they are written first. Built in code, a model gets the current marker from
the defaults.

`MarkedFormat.load(path)` reads a file. It passes pydantic two settings for
that one call:

- `extra="ignore"`, so unknown fields are dropped at every level, even in
  models that forbid them. The models keep `extra="forbid"` for everything
  else, which is how building one with a misspelt field still fails. A
  format sets `load_extra = None` to use its models' own settings instead;
  `metrics.json` does this to keep the extra metrics its `extra="allow"`
  models hold, which `extra="ignore"` would drop.
- A validation context holding the path. A model validator on
  `MarkedFormat` runs only when that context is there, so it checks the
  marker of files and nothing else: it fills in a missing marker as 1.0.0,
  warns about a newer major version, and fails on another `kind`.

This needs pydantic 2.12 or newer, the first version that takes `extra` per
call.

### Schemas

`dvsim.schemas` generates each format's schema from its model, in
serialization mode, so that it describes the files as written. It removes
the `"additionalProperties": false` that pydantic adds for models that
forbid extra fields, so that the schemas allow unknown fields like the
readers do.

`dvsim.schemas.formats()` lists the formats. A test
(`tests/test_schemas.py`) fails if a committed schema differs from the one
its model generates, or if a committed schema belongs to no format, so a
model change can't land without its schema.

### Changing a format

1. Change the model.
2. Decide the bump with the table in
   [Format markers](#format-markers). If in doubt, it is major.
3. Change the default of the model's `schema_version` to the new version.
4. Regenerate the schemas, from the source tree:

   ```sh
   python -m dvsim.schemas
   ```

5. Commit the model, the new version and the schemas together. For a major
   bump, mark the commit as breaking (`feat!:` or a `BREAKING CHANGE:`
   footer) and say in the footer what readers must change. The schema
   diff in review shows exactly what changed.

To add a format: subclass `MarkedFormat`, add the model to
`dvsim.schemas.formats()`, regenerate, and add it to the tables on this
page.

## Known gaps

- Nothing checks automatically yet that a schema change between releases
  comes with the right version bump; review does.
- No test yet loads files written by past DVSim releases.
- The schemas don't carry the fields' descriptions; the models' docstrings
  have them.
- `metrics.json` is not fully tolerant of added fields; see
  [What DVSim's own readers do](#what-dvsims-own-readers-do).
- The formats in [Not covered](#not-covered) have no marker or schema.
