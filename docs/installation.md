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

## User scope (all projects) with a profile

The GitHub marketplace ships the balanced topology. To use another profile in
every project, build a local marketplace whose plugin already carries the
profile and install it at user scope:

```bash
python scripts/install.py --user --profile max-20x-thorough --default-rule
claude plugin marketplace add ~/.claude-orchestration
claude plugin install orchestration@orchestration-local --scope user
```

- `--user` writes `~/.claude-orchestration` (`--marketplace-dir` to change it):
  `.claude-plugin/marketplace.json` (marketplace `orchestration-local`) and the
  plugin with the profile's model/effort in every frontmatter. Claude Code
  loads a plugin from a local-path marketplace in place, so rerunning the
  command (for example with another `--profile`) updates the installed plugin;
  restart sessions to pick it up.
- `--default-rule` adds a managed block to your user `CLAUDE.md`
  (`$CLAUDE_CONFIG_DIR/CLAUDE.md` or `~/.claude/CLAUDE.md`), marked
  `claude-orchestration:managed`, that makes the plugin's roles the default way
  to delegate unless project instructions say otherwise. Rerunning replaces the
  block; your other text is kept. The text is `scripts/default-orchestration-rule.md`.
- Root `model`/`effortLevel` are not written in user mode: the skill and each
  role carry their own, and your global defaults stay yours.
- Do not install `orchestration@snaplyze-orchestration` at the same time; both
  register the `orchestration` plugin.

Remove:

```bash
claude plugin uninstall orchestration@orchestration-local
claude plugin marketplace remove orchestration-local
python scripts/install.py --user --uninstall --default-rule
```

Verify the installed copy with
`python scripts/runtime_smoke.py --use-installed --plugin-dir ~/.claude-orchestration/plugin --skill`.
