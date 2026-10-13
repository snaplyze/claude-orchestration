# Installation

Requirements: Python 3.11+ (the CI matrix is in [verification](verification.md)), an existing target project, and Claude Code for runtime use.

```bash
./setup.sh /workspace/project --profile pro-balanced
```

The plugin is copied to `.claude/plugins/orchestration`; selected profile keys are merged into `.claude/settings.json`. Unrelated settings are preserved. The installer records under `claude-orchestration` the profile, the keys it owns, their values before installation, and the values it applied; uninstall and profile switches restore the prior values, except for a key you changed after installing, which keeps your value. Rerunning setup without `--profile` refreshes the plugin and keeps the installed profile.

Run it explicitly:

```bash
claude --plugin-dir .claude/plugins/orchestration
```

A project install writes nothing outside `<project>/.claude`; for an install that applies to every project, see the user-scope section below or the README.

Switch profile by rerunning setup with another `--profile`. Remove managed plugin/settings with:

```bash
./setup.sh /workspace/project --uninstall
```

The installer refuses symlinks and Windows junctions in the destination chain (the list is in [security](security.md), so writes cannot leave the target or replace a link), accepts only profile names from `profiles/`, stages the new copy next to the destination, and swaps it in with a rename. On ordinary failures it restores the previous plugin directory and the exact previous `settings.json` bytes. It is not a crash-consistent filesystem transaction across power loss or hostile races; a crash can leave a `.claude/plugins/.orchestration-*` work directory. If restoring the previous plugin itself fails, the installer keeps that directory and prints where the previous copy is; otherwise the work directory is safe to delete.

## User scope (all projects) with a profile

The GitHub marketplace ships the balanced topology. To use another profile in
every project, build a local marketplace whose plugin already carries the
profile and install it at user scope:

```bash
python scripts/install.py --user --profile max-20x-thorough --default-rule --register
python scripts/install.py --status
```

On Windows run `.\setup.ps1 -User -Profile max-20x-thorough -DefaultRule -Register`
and `.\setup.ps1 -Status` (`-MarketplaceDir` overrides the directory);
`./setup.sh --user …` works the same on macOS and Linux.

- `--user` writes `~/.claude-orchestration` (`--marketplace-dir` to change it):
  `.claude-plugin/marketplace.json` (marketplace `orchestration-local`) and the
  plugin with the profile's model/effort in every frontmatter. Claude Code
  loads a plugin from a local-path marketplace in place, so rerunning the
  command (for example with another `--profile`) updates the installed plugin;
  restart sessions to pick it up. The directory must be new, empty, or one the
  installer built (its manifest is named `orchestration-local`); anything else,
  and any symlink or junction there, is refused. Uninstall removes only what
  the installer built and keeps the directory if other files remain in it.
- `--default-rule` installs the rule as its own file,
  `rules/claude-orchestration.md` in the Claude config directory
  (`$CLAUDE_CONFIG_DIR` or `~/.claude`). User rules apply to every project, so
  the plugin's roles become the default way to delegate wherever project
  instructions do not say otherwise. The installer owns that file whole
  (rewritten on install, deleted on uninstall) and refuses to overwrite a file
  of that name it did not write. The text is `scripts/default-orchestration-rule.md`.
  Installers before 1.5 kept the rule as a `claude-orchestration:managed` block
  in the user `CLAUDE.md`; installing or removing the rule takes that block out,
  with the blank lines the old installer put before it, and leaves the rest of
  the file alone, or refuses without writing if the markers are damaged.
- `--register` runs `claude plugin marketplace add` and
  `claude plugin install orchestration@orchestration-local --scope user`
  (or `enable`) only when needed, so a rerun changes nothing, and then checks
  that the plugin is enabled and loads from the marketplace `plugin/`. It
  refuses when `orchestration-local` is already registered from another
  directory or another enabled plugin is named `orchestration` (for example
  `orchestration@snaplyze-orchestration`): both register the same plugin.
  Without `--register`, run those two commands yourself.
- `--status` prints one line per requirement, OK or TODO: the rule file is
  current, no pre-1.5 block is left in `CLAUDE.md`, and an orchestration plugin
  is enabled. With a local build, the build must match what this checkout
  would write (file by file) and the plugin must be enabled from it with no
  other `orchestration` plugin enabled; without one, exactly one enabled
  `orchestration` plugin from any marketplace counts. It exits 1 while
  anything is TODO.
- `--user --uninstall --register` removes the registration only when it points
  at this marketplace directory.
- `--default-rule` alone (no `--user`) installs or, with `--uninstall`, removes
  only the rule, for example next to the GitHub marketplace plugin.
- Root `model`/`effortLevel` are not written in user mode: the skill and each
  role carry their own, and your global defaults stay yours.

Remove:

```bash
python scripts/install.py --user --uninstall --default-rule --register
```

Verify the installed copy with
`python scripts/runtime_smoke.py --use-installed --plugin-dir ~/.claude-orchestration/plugin --skill --default-rule`;
the `--default-rule` cases then use your installed rule file.
