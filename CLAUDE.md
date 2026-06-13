# jubit-hk-tiles (forked from cannoneyed/isometric-nyc)

This repo is the Hong Kong adaptation of [`cannoneyed/isometric-nyc`](https://github.com/cannoneyed/isometric-nyc). The upstream pipeline (PyVista + Gemini + fine-tuned Qwen + DZI viewer) is reused; the data source is swapped from NYC OpenData + Google 3D Tiles to the **Hong Kong Lands Department territory-wide 3D Visualisation Map** ([data.map.gov.hk](https://data.map.gov.hk/)). See `docs/HK-ADAPTATION-PLAN.md`.

## Project Rules — 12-Rule Template

> These rules apply to every task in this project unless explicitly overridden.
> Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.
>
> This is a portable template — copy this whole section into the root `CLAUDE.md` of any project to apply the same rules.

### Rule 1 — Think Before Coding
State assumptions explicitly. If uncertain, ask rather than guess. Present multiple interpretations when ambiguity exists. Push back when a simpler approach exists. Stop when confused. Name what's unclear.

### Rule 2 — Simplicity First
Minimum code that solves the problem. Nothing speculative. No features beyond what was asked. No abstractions for single-use code. Test: would a senior engineer say this is overcomplicated? If yes, simplify.

### Rule 3 — Surgical Changes
Touch only what you must. Clean up only your own mess. Don't "improve" adjacent code, comments, or formatting. Don't refactor what isn't broken. Match existing style.

### Rule 4 — Goal-Driven Execution
Define success criteria. Loop until verified. Don't follow steps — define success and iterate. Strong success criteria let you loop independently.

### Rule 5 — Use the model only for judgment calls
Use the model for: classification, drafting, summarization, extraction. Do NOT use the model for: routing, retries, deterministic transforms. If code can answer, code answers.

### Rule 6 — Token budgets are not advisory
Per-task: 4,000 tokens. Per-session: 30,000 tokens. If approaching budget, summarize and start fresh. Surface the breach. Do not silently overrun.

### Rule 7 — Surface conflicts, don't average them
If two patterns contradict, pick one (more recent / more tested). Explain why. Flag the other for cleanup. Don't blend conflicting patterns.

### Rule 8 — Read before you write
Before adding code, read exports, immediate callers, shared utilities. "Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.

### Rule 9 — Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does. A test that can't fail when business logic changes is wrong.

### Rule 10 — Checkpoint after every significant step
Summarize what was done, what's verified, what's left. Don't continue from a state you can't describe back. If you lose track, stop and restate.

### Rule 11 — Match the codebase's conventions, even if you disagree
Conformance > taste inside the codebase. If you genuinely think a convention is harmful, surface it. Don't fork silently.

### Rule 12 — Fail loud
"Completed" is wrong if anything was skipped silently. "Tests pass" is wrong if any were skipped. Default to surfacing uncertainty, not hiding it.

## Upstream context — preserved verbatim below

The upstream NYC repo's CLAUDE.md follows. We keep it because the tech stack (uv / pytest / ruff) and pipeline structure are unchanged in this fork.

---

## Technology Stack

  * **Language:** Python (Version specified in `.python-version` or `pyproject.toml`)
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
├── tasks/               # Task files, which are markdown files that define new
│                        # tasks for the agent to execute (see below)
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
