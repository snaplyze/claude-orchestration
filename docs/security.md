# Security

- Delegation never expands user authorization.
- Read-only roles omit edit/write tools.
- Plugin agents do not claim `permissionMode` isolation because Claude Code ignores that field for plugin subagents.
- One writer owns each file/subsystem at a time.
- No hook, MCP server, background monitor, network daemon, credential, or telemetry is bundled.
- Installer changes only `.claude/plugins/orchestration` plus explicitly managed profile keys in `.claude/settings.json`, and restores the prior values of those keys on uninstall.
- In user mode (`--user`) the installer writes only the marketplace directory (`~/.claude-orchestration` by default), which must be new, empty, or built by it, and with `--default-rule` one file, `rules/claude-orchestration.md` in the Claude config directory; it removes a pre-1.5 `claude-orchestration:managed` block from the user `CLAUDE.md`, keeping the rest of the file. Uninstall deletes only what it built.
- `runtime_smoke.py` makes real model calls under the current login and deletes the session transcripts it creates; the CI workflow uses the owner's subscription token only for runs the owner authored and started.
- Symlinks and Windows junctions at `.claude`, `.claude/plugins`, or `.claude/plugins/orchestration`, at the marketplace directory and its entries, and at the rule file are rejected, and `--profile` accepts only bundled profile names.
- No profile enables bypass permissions, auto mode, Agent Teams, Ultracode, usage credits, or API credentials.

Claude Code's active permission mode can still affect subagents. Inspect effective runtime permissions when the boundary matters.
