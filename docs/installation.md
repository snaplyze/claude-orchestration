# Installation

Requirements: Python 3.11+ (stated minimum, untested: the CI matrix lists 3.12/3.13; see plan A-11), an existing target project, and Claude Code for runtime use.

```bash
./setup.sh /workspace/project --profile pro-balanced
```

The plugin is copied to `.claude/plugins/orchestration`; selected profile keys are merged into `.claude/settings.json`. Unrelated settings are preserved and the installer records exactly which keys it owns under `claude-orchestration`. Known gaps (see [plan](plan.md)): a pre-existing `model`/`effortLevel` is overwritten and removed on uninstall (A-03); rerunning without `--profile` resets agent frontmatter to the balanced topology while settings keep the previous profile (A-04).

Run it explicitly:

```bash
claude --plugin-dir .claude/plugins/orchestration
```

This explicit loading is deliberate: it is easy to audit and does not silently mutate user-level plugin marketplaces. For distribution through a marketplace, install the same `plugin/` directory using Claude Code's plugin commands.

Switch profile by rerunning setup with another `--profile`. Remove managed plugin/settings with:

```bash
./setup.sh /workspace/project --uninstall
```

The installer refuses a symlink at the managed plugin destination and rolls back plugin/settings state on ordinary failures. It is not a crash-consistent filesystem transaction across power loss or hostile races.
