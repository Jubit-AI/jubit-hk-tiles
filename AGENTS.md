# jubit-hk-tiles

This repo generates **soft-stylised isometric tiles of Hong Kong** from the Lands Department's 3D open data. It is a fork of [`cannoneyed/isometric-nyc`](https://github.com/cannoneyed/isometric-nyc), retargeted from New York City to Hong Kong.

> **Governance + project rules**: see [`CLAUDE.md`](./CLAUDE.md) — it carries the Jubit 12-Rule Template and the HK-adaptation context. The per-week status lives in [`docs/HK-ADAPTATION-PLAN.md`](./docs/HK-ADAPTATION-PLAN.md); licensing rules in [`docs/legal/attribution.md`](./docs/legal/attribution.md); the remaining NYC→HK retargeting map in [`docs/research/nyc-to-hk-coupling-checklist.md`](./docs/research/nyc-to-hk-coupling-checklist.md).
>
> **Naming note**: the Python package dir is still `src/isometric_nyc/` — a deferred rename to `src/isometric_hk/` (Week 7, atomic commit) per the coupling checklist. Until then, imports reference `isometric_nyc` as shown below.

The tech-stack / tooling guidance below is unchanged from upstream and still accurate (uv / pytest / ruff).

## Technology Stack

  * **Language:** Python (Version specified in `pyproject.toml`)
  * **Package Manager:** `uv` (Strictly used for all dependency management and environment handling)
  * **Testing:** `pytest`
  * **Linting/Formatting:** `ruff`

## Environment & Dependency Management (`uv`)

**Crucial:** Do not use `pip`, `poetry`, or `conda`. This project relies entirely on `uv`.

### Setup

To initialize the environment and install dependencies:

```bash
uv sync
```

*This creates the virtual environment automatically in `.venv`.*

### Managing Dependencies

  * **Add a package:** `uv add <package_name>`
  * **Add a dev dependency:** `uv add --dev <package_name>`
  * **Remove a package:** `uv remove <package_name>`
  * **Update lockfile:** `uv lock`

### Running Code

Always execute commands within the project's context using `uv run`. Do not manually activate the virtual environment.

  * **Run a script:** `uv run python src/main.py`
  * **Run a module:** `uv run python -m my_module`
  * **Run arbitrary tools:** `uv run <command>`

## Common Tasks & Commands

| Task | Command |
| :--- | :--- |
| **Run Tests** | `uv run pytest` |
| **Format Code** | `uv run ruff format .` (Adjust if using different tool) |
| **Lint Code** | `uv run ruff check .` (Adjust if using different tool) |
| **Run Application** | `uv run python src/app.py` |

## Directory Structure

```text
.
├── .venv/               # Managed by uv (do not touch)
├── src/                 # Source code
│   └── isometric_nyc/   # Main package
├── tests/               # Test suite
├── tasks/               # Task files, which are markdown files that defined new
│                        # tasks for a coding agent to execute (see below)
├── pyproject.toml       # Project configuration & dependencies
├── uv.lock              # Exact dependency versions (do not edit manually)
├── .python-version      # Target Python version
└── README.md            # Human-readable documentation
```

## Coding Standards

1.  **Type Hints:** All function signatures must include Python type hints.
2.  **Imports:** Use absolute imports for project modules (e.g., `from isometric_nyc.utils import helper`).
3.  **Configuration:** All project metadata and tool configuration must reside in `pyproject.toml`.
4.  **Lockfile:** Never ignore `uv.lock`. If `pyproject.toml` changes, run `uv lock` or `uv sync` to update it.

## Task Files

Task files are markdown files that define new tasks for the agent to execute. They are located in the `tasks` directory. These files may be edited by the agent to clarify instructions or to add new tasks, but the use must specify invoking any specific task.

-----
