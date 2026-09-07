# Repository Guidelines

## Project Structure & Module Organization

- `pa_agent/` contains the application package. `main.py` starts the GUI; `data/` implements market-data sources, `ai/` contains prompt assembly, model clients, validation, and routing, `orchestrator/` coordinates the two-stage analysis, and `gui/` contains PyQt6 windows and widgets.
- `tests/` is organized by `unit/`, `property/`, `integration/`, and `e2e/`; shared fixtures live in `tests/fixtures/`.
- `prompt_engineering/` holds runtime strategy prompts. `tradingview/` contains embedded chart assets. User/runtime state belongs in `config/`, `logs/`, `records/`, `experience/`, and `trade_records/` and is normally ignored by Git.

## Build, Test, and Development Commands

Create an environment and install development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
python -m pip install -e "[dev]"
```

- `python -m pa_agent.main` (or `python run.py`) launches the desktop app.
- `pytest -q` runs the complete test suite; `pytest -m "not e2e"` skips end-to-end tests.
- `QT_QPA_PLATFORM=offscreen pytest -q tests/unit` runs GUI-capable tests headlessly.
- `make lint` runs `ruff check .` and `black --check .`; use `ruff check pa_agent tests` for a focused check.

## Coding Style & Naming Conventions

Use Python 3.11+, four-space indentation, type hints, and focused modules. Black and Ruff target a 100-character line length; imports are organized by Ruff (`I`). Use `snake_case` for files, functions, and variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Keep shared paths in `pa_agent/config/paths.py` rather than hard-coding them.

## Testing Guidelines

Name files `test_<behavior>.py` and tests `test_<expected_result>`. Mark tests with `unit`, `property`, `integration`, `e2e`, or `live` as appropriate. There is no fixed coverage threshold; every behavior change should include or update deterministic tests, with network-dependent tests opt-in only.

## Commit & Pull Request Guidelines

Follow the existing Conventional Commit-style prefixes, e.g. `feat: add data source`, `fix: mask API key`, `test: cover validator`, or `docs: update setup`. Keep each commit and PR focused on one concern. PRs should explain motivation, notable design choices, and validation commands; link the relevant issue. Include screenshots or recordings for GUI changes and update tests when changing schemas, prompts, or routing.

## Security & Configuration Tips

Copy `config/settings.example.json` to create local settings, but never commit `config/settings.json`, API keys, `.env` files, logs, or runtime records. Use the system credential store and run `make setup-secrets` (PowerShell on Windows) to enable the repository's secret-scanning hook.
