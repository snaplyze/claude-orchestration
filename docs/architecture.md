# Architecture

The main Claude Code session owns the user conversation. Invoking `/orchestration:orchestrate` activates a skill with its own explicit model and effort; that skill coordinates five plugin-scoped subagents.

The marketplace distribution uses the balanced topology:

| Component | Model alias | Effort | Intent |
|---|---|---:|---|
| orchestrator skill | opus | high | decomposition, routing, integration, final judgment |
| explorer | haiku | low | focused repository mapping |
| researcher | sonnet | medium | primary-source research |
| worker | sonnet | high | bounded implementation |
| tester | sonnet | medium | reproduction and verification |
| reviewer | opus | high | independent material-risk review |

Local installer profiles replace the model/effort pairs while keeping role behavior. The orchestrator adapts **routing**, not effort: root-only vs delegation, role selection, parallel read-only work, serialization of writers, and whether a larger Claude Code mechanism is warranted.

## Why this shape

- Subagents have isolated context and return summaries, which protects the main context from exploration noise.
- One writer owns a file/subsystem at a time. Read-only investigation can run in parallel.
- No role sets `maxTurns`; the brief bounds the work. At the cap Claude Code stops a subagent without a warning or a closing turn and returns its last text marked as partial, so the coordinator has to resume it with `SendMessage` (`/en/sub-agents`; research-sources 18). Under the 1.6.0 caps (explorer 12, researcher 16, worker 30, tester 22, reviewer 18) the cap cut the first run in the middle of a tool call in half of 751 role runs on the owner's machine (`docs/verification.md`, results of 2026-10-21). The agents of Anthropic's `feature-dev` and `pr-review-toolkit` plugins set no cap either. Each role makes independent reads and searches in one turn, keeps to the brief, and ends with its report, or with what is done and what remains when the work outgrows the brief. A runaway delegate is stopped like any task (`x` in `/tasks`, or Claude's `TaskStop` tool); headless runs can add `--max-budget-usd`, which also stops background subagents still running.
- `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` is a runtime ceiling for parallel read-only tools/subagents (currently defaults to 10); the plugin does not override it or try to fill it.
- Agent Teams remain an explicit escalation when independent sessions need peer-to-peer communication.
- Dynamic workflows and `/batch` are useful for large repeatable or worktree-isolated jobs, but are not silently substituted for normal delegation.

## Permission boundary

Plugin subagents cannot enforce `permissionMode`, `hooks`, `mcpServers`, or `initialPrompt` in their own frontmatter; Claude Code ignores those fields for plugin-provided agents. This distribution therefore does not claim per-agent sandbox isolation. Tool lists and instructions narrow intent, while the active session/organization permission policy remains authoritative.

Read-only roles omit Edit/Write. `reviewer` retains Bash for repository evidence such as diffs/tests, so its no-write rule is an instruction boundary rather than a filesystem sandbox. Use Claude Code's session sandbox/permission policy when hard isolation is required.

Shell tools: `worker`, `tester`, and `reviewer` list both `Bash` and `PowerShell`. On native Windows without Git for Windows, Claude Code runs shell commands through the PowerShell tool (the Bash tool needs Git Bash); elsewhere PowerShell is opt-in, and a listed tool that is unavailable is simply not granted. On macOS, Linux, and WSL, Claude Code leaves `Glob` and `Grep` out of the default tool set and searches through Bash, but gives them back to a subagent that lists them without `Bash`. That is why `explorer` and `researcher` must not list `Bash`: it would cost them their search tools and give them a way to write.
