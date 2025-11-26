# Repository Guidelines

## Project Structure & Module Organization
Agent logic sits in `src/eagent`. `graph.py` wires the LangGraph flow, `nodes/` contains worker and aggregator code, and `config.py`, `state.py`, plus `utils/` centralize settings and helpers. CLI entry points (`main.py`, `runner.py`) load `.env` before bootstrapping. Prompts stay in `prompts.py`, telemetry hooks in `telemetry.py`. Tests live in `tests/`, and LangSmith evaluation helpers in `evals/`. Co-locate new prompts, assets, or fixtures with their consuming module.

## Build, Test, and Development Commands
- `uv sync` — install runtime and optional test dependencies from `pyproject.toml`; always run this on a fresh checkout.
- `uv run eagent --model openai:gpt-4o --temperature 0.0` — execute the CLI agent end-to-end; adjust flags but keep the `uv run` prefix for reproducibility.
- `uv run eagent -h` — show CLI help (short flag enabled via Typer context settings) to discover available subcommands and options.
- `uv run eagent --version` — print the installed application version (sourced dynamically from package metadata) and exit; useful for debugging environments.
- `uv run pytest` — run the async-aware test suite configured via `[tool.pytest.ini_options]`.
- `uv run python tests/eval.py` — trigger LangSmith dataset evaluations once credentials are present.

## Coding Style & Naming Conventions
Target Python 3.13 with type hints and 4-space indentation. Follow PEP 8 naming (`snake_case` modules/functions, `CamelCase` classes) and keep LangGraph node IDs descriptive (`worker_synthesizer`, `report_aggregator`). Use Pydantic models for validation and `TypedDict`/dataclasses for transient state. Add short docstrings to complex nodes and keep prompts versioned beside their callers.

## Testing Guidelines
Tests live under `tests/` and rely on `pytest` + `pytest-asyncio`. Mirror the source tree when naming modules (`tests/test_nodes_worker.py` for `src/eagent/nodes/worker.py`). Prefer deterministic fakes over live LLM calls by injecting mocks via `llm.get_default_llm`. Run `uv run pytest -k <pattern>` for focused checks. When adding LangSmith datasets, document them in `tests/eval.py` and keep failover branches (retries, interrupts) covered.

## Commit & Pull Request Guidelines
Commits follow an emoji-flavored Conventional Commit style (`✨feat: 重构文献分析流程…`). Use one imperative sentence after the emoji/prefix; expand details in the body when needed. Pull requests should link issues, describe behavioral impact, attach screenshots or LangSmith trace URLs when UX changes, and list new env vars with reproduction steps beginning `uv sync && uv run eagent …`.

## Security & Configuration Tips
Copy `.env.example` to `.env`, then set `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`, and `LANGSMITH_TRACING=true` before running `uv run eagent`. Never commit secrets; document required keys inside the PR description instead. For shared LangSmith workspaces, create contributor-specific project names so evaluations do not overwrite each other.
