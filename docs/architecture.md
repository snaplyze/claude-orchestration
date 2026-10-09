# Architecture

The main Claude Code session owns the user conversation. Invoking `/orchestration:orchestrate` activates a skill with its own explicit model and effort; that skill coordinates five plugin-scoped subagents.

The marketplace distribution uses the balanced topology:

| Component | Model alias | Effort | Turn cap | Intent |
|---|---|---:|---:|---|
| orchestrator skill | opus | high | session-owned | decomposition, routing, integration |
| explorer | haiku | low | 12 | focused repository mapping |
| researcher | sonnet | medium | 16 | primary-source research |
| worker | sonnet | high | 30 | bounded implementation |
| tester | sonnet | medium | 22 | reproduction and verification |
| reviewer | opus | high | 18 | independent material-risk review |

Local installer profiles replace the model/effort pairs while keeping role behavior and bounded turn caps. The orchestrator adapts **routing**, not effort: root-only vs delegation, role selection, parallel read-only work, serialization of writers, and whether a larger Claude Code mechanism is warranted.

## Why this shape

- Subagents have isolated context and return summaries, which protects the main context from exploration noise.
- One writer owns a file/subsystem at a time. Read-only investigation can run in parallel.
- `maxTurns` bounds runaway delegated loops without pretending to be a token budget.
- `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` is a runtime ceiling for parallel read-only tools/subagents (currently defaults to 10); the plugin does not override it or try to fill it.
- Agent Teams remain an explicit escalation when independent sessions need peer-to-peer communication.
- Dynamic workflows and `/batch` are useful for large repeatable or worktree-isolated jobs, but are not silently substituted for normal delegation.

## Permission boundary

Plugin subagents cannot enforce `permissionMode`, `hooks`, or `mcpServers` in their own frontmatter; Claude Code ignores those fields for plugin-provided agents. This distribution therefore does not claim per-agent sandbox isolation. Tool lists and instructions narrow intent, while the active session/organization permission policy remains authoritative.

Read-only roles omit Edit/Write. `reviewer` retains Bash for repository evidence such as diffs/tests, so its no-write rule is an instruction boundary rather than a filesystem sandbox. Use Claude Code's session sandbox/permission policy when hard isolation is required.
