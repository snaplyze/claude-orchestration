# Security

- Delegation never expands user authorization.
- Read-only roles omit edit/write tools.
- Plugin agents do not claim `permissionMode` isolation because Claude Code ignores that field for plugin subagents.
- One writer owns each file/subsystem at a time.
- No hook, MCP server, background monitor, network daemon, credential, or telemetry is bundled.
- Installer changes only `.claude/plugins/orchestration` plus explicitly managed profile keys in `.claude/settings.json`.
- Symlink plugin destinations are rejected.
- No profile enables bypass permissions, auto mode, Agent Teams, Ultracode, usage credits, or API credentials.

Claude Code's active permission mode can still affect subagents. Inspect effective runtime permissions when the boundary matters.
