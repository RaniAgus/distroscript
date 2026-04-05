# AGENTS.md

## What this repo is

A single-file Python CLI (`src/distroscript.py`) that reads a declarative YAML config and generates
a Bash installation script for a target Linux distro. `schema.json` must stay co-located in `src/`.

## Commands

```bash
# Run (stdout is the generated script)
python3 src/distroscript.py <config.yml> --os <fedora|ubuntu|popos|mint> [--out output.sh]

# Typecheck (only linter enforced in CI)
mypy ./src/distroscript.py

# Run all tests (must be run from repo root)
python3 ./tests/run_tests.py
```

Install dev dependencies (runtime + mypy + stubs) via the `[dev]` extra:

```bash
pip install -e ".[dev]"
```

To build a distributable:

```bash
pip install hatch
hatch build          # produces dist/
pip install dist/distroscript-*.whl   # installs `distroscript` CLI command
```

## Testing

- **No pytest.** Custom snapshot runner at `tests/run_tests.py`.
- Tests are golden-file comparisons: each `tests/inputs/NN-name.yml` is run against each OS and
  diffed against `tests/outputs/{os}/NN-name.sh`.
- If no expected file exists for an OS, the test is silently skipped (tests 05, 06, 16 are
  Fedora-only).
- To manually check one case:
  ```bash
  python3 src/distroscript.py tests/inputs/05-flags.yml --os fedora > /tmp/out.sh
  git diff --no-index tests/outputs/fedora/05-flags.sh /tmp/out.sh
  ```
- To update a golden file after an intentional change: regenerate with `--out` and overwrite the
  file in `tests/outputs/`.
- To add a new test: add `NN-name.yml` to `tests/inputs/` and the matching `.sh` files to
  `tests/outputs/{os}/`.

## CI

`.github/workflows/python.yml` runs on push/PR touching `src/**`, `tests/**`, or the workflow file:

1. `pip install -e ".[dev]"`
2. `mypy ./src/distroscript.py`
3. `python3 ./tests/run_tests.py`

## Architecture

Pipeline in `main()`:

```
YAML load → JSON Schema validate → load_packages() → resolve_packages()
         → merge_packages() → calculate_transitive_dependencies() → print
```

`Package` and `Command` are abstract frozen dataclasses. Subclasses self-register via
`__init_subclass__` using a `type=` keyword in the class definition (e.g.,
`class DnfPackage(Package, type='dnf')`). Do not break this pattern when adding new types.

## Key non-obvious behaviors

- **First-match wins for OS selection:** `load_package_list()` returns the first alternative list
  that resolves to at least one package. Order of alternatives in YAML matters.
- **`UndefinedPackage` is intentional:** unresolved `depends_on` references render as `# TODO:`
  comments in output rather than erroring.
- **Merge requires same type AND same flags** and is blocked when one package depends on another
  (ordering preserved).
- **`ShellPackage` runs with `-i`** (interactive shell) to source `.bashrc`/`.zshrc` — intentional.
- **`AppImagePackage` bakes post-install steps** (desktop entry, icon extraction) into its
  constructor, not in `print_package()`.
- **Ubuntu has 14 test cases, Fedora has 17.** Tests 05/06/16 have no Ubuntu counterpart.
- Python 3.10+ required (uses `match`/structural pattern matching syntax in type hints).
