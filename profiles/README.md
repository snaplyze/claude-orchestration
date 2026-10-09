# Profiles

Profiles materialize a complete **model + effort** topology for the orchestrator and all five subagents. They also merge the root `model` and `effortLevel` keys into the target `.claude/settings.json` while preserving unrelated settings.

Use `python scripts/install.py <project> --profile <name>` for one project, or `python scripts/install.py --user --profile <name>` for a user-scope install in all projects (see [installation](../docs/installation.md)); user mode materializes the frontmatter but leaves your global `model`/`effortLevel` alone. The GitHub marketplace plugin ships the `pro-balanced` topology because marketplace installation has no profile-selection prompt.

See [models and plans](../docs/models-and-plans.md) for the exact matrix and runtime precedence. Profile names do not grant model access.
