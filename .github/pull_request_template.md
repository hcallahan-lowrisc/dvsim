## Description

<!-- Describe what this PR does and why. -->

## Checklist

- [ ] All commits are signed off (`git commit -s`), indicating acceptance of the CLA
- [ ] Commit messages follow the [conventional commit format](https://www.conventionalcommits.org) (`<type>[(<scope>)][!]: <description>`)
  - [ ] The commit type correctly reflects the semver impact of the change
  - [ ] Breaking changes are marked with `!` or a `BREAKING CHANGE:` footer
- [ ] New behaviour is covered by tests

<details>
<summary>Commit type reference</summary>

Each commit merged from this PR drives an automatic release — the type determines the version bump.
See [doc/releasing.md](doc/releasing.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

| Type | Semver impact | Use when… |
|------|--------------|-----------|
| `feat` | minor bump | adding new user-facing behaviour or CLI options |
| `fix` | patch bump | correcting a bug in existing behaviour |
| `perf` | patch bump | improving performance without changing behaviour |
| `refactor` | patch bump | restructuring code without changing behaviour |
| `docs` | no release | documentation-only changes |
| `test` | no release | adding or fixing tests |
| `ci` | no release | CI workflow changes |
| `chore` | no release | maintenance (deps, tooling, config) |
| `build` | no release | build system changes |
| `revert` | patch bump | reverting a previous commit |

**Breaking changes → major bump:** append `!` to the type (e.g. `feat!: remove --legacy-flag`) or add a `BREAKING CHANGE: <description>` footer.

**Format:**
```
<type>[(<scope>)][!]: <short description>   # 100 chars max
<blank line>
<optional body>
<blank line>
Signed-off-by: Name <email>                 # required; use git commit -s
```

**Examples:**
```
feat(scheduler): add --max-jobs CLI flag
fix: handle empty testplan gracefully
feat!: remove Python 3.9 support
```

</details>
