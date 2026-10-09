# Installation

Requirements: Python 3.11+ (CI covers 3.11 on Linux and 3.12/3.13 on Linux, macOS, and Windows), an existing target project, and Claude Code for runtime use.

```bash
./setup.sh /workspace/project --profile pro-balanced
```

The plugin is copied to `.claude/plugins/orchestration`; selected profile keys are merged into `.claude/settings.json`. Unrelated settings are preserved. The installer records under `claude-orchestration` the profile, the keys it owns, and their values before installation; uninstall and profile switches restore those prior values. Rerunning setup without `--profile` refreshes the plugin and keeps the installed profile.

Run it explicitly:

```bash
claude --plugin-dir .claude/plugins/orchestration
```

This explicit loading is deliberate: it is easy to audit and does not silently mutate user-level plugin marketplaces. For distribution through a marketplace, install the same `plugin/` directory using Claude Code's plugin commands.

Switch profile by rerunning setup with another `--profile`. Remove managed plugin/settings with:

```bash
./setup.sh /workspace/project --uninstall
```

The installer refuses symlinks at `.claude`, `.claude/plugins`, or `.claude/plugins/orchestration` (so writes cannot leave the target), accepts only profile names from `profiles/`, stages the new copy next to the destination, and swaps it in with a rename. On ordinary failures it restores the previous plugin directory and the exact previous `settings.json` bytes. It is not a crash-consistent filesystem transaction across power loss or hostile races; a crash can leave a `.claude/plugins/.orchestration-*` work directory. If restoring the previous plugin itself fails, the installer keeps that directory and prints where the previous copy is; otherwise the work directory is safe to delete.
