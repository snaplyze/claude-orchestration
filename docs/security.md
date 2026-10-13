# Security

- Delegation never expands user authorization.
- Read-only roles omit edit/write tools.
- Plugin agents do not claim `permissionMode` isolation because Claude Code ignores that field for plugin subagents.
- One writer owns each file/subsystem at a time.
- No hook, MCP server, background monitor, network daemon, credential, or telemetry is bundled.
- A project install changes only `.claude/plugins/orchestration` plus the managed profile keys and the `claude-orchestration` marker in `.claude/settings.json`, which is re-serialized as a whole (two-space indent, UTF-8 without BOM, LF), plus `.claude/.orchestration.lock` while it runs; the prior values of the managed keys come back on uninstall unless you changed them after installing, and a rerun without `--profile` keeps such a changed value. Uninstall removes the settings file, `plugins/` and `.claude` only when they are left empty.
- In user mode (`--user`) the installer writes only the marketplace directory (`~/.claude-orchestration` by default), which must be new, empty, or built by it, and with `--default-rule` one file, `rules/claude-orchestration.md` in the Claude config directory, and holds `.orchestration.lock` in each directory it changes while it runs. `--register` and `--uninstall --register` change your Claude Code user configuration through the `claude` CLI (`claude plugin marketplace add|remove`, `claude plugin install|uninstall|enable --scope user`), which records the marketplace and the plugin in your user settings. Uninstall deletes only what it built: the `plugin/` tree (including anything placed inside it) and the manifest; other entries in the directory are kept and listed.
- `runtime_smoke.py` makes real model calls under the current login and deletes the session transcripts it creates; headless modes run in a temporary working directory, while `--interactive` drives a real TUI session in the current directory under your real permission mode and dispatches subagents, so run it from a folder you already trust. The CI workflow uses the owner's subscription token only for runs the owner authored and started.
- Symlinks and Windows junctions at `.claude`, `.claude/plugins`, `.claude/plugins/orchestration`, or `.claude/settings.json`, at the marketplace directory and its entries, and at the rule file are rejected, and `--profile` accepts only bundled profile names.
- No profile enables bypass permissions, auto mode, Agent Teams, Ultracode, usage credits, or API credentials.

Claude Code's active permission mode can still affect subagents. Inspect effective runtime permissions when the boundary matters.
