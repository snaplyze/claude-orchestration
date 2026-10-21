# Default orchestration (claude-orchestration)

For the main session only; a subagent reading this ignores it. It applies in every repository, including ones without agent rules. Project instructions (CLAUDE.md, AGENTS.md, .claude/rules) win only where they conflict, for example when they forbid subagents or prescribe their own orchestration.

Delegate to the `orchestration` plugin roles when a trigger fits:

- `orchestration:explorer`: answering needs code you have not read, across several files or modules (locating code, tracing a call or data flow, mapping a subsystem). Run one per independent area, in parallel.
- `orchestration:researcher`: the answer depends on current external facts, such as releases, versions, APIs, vendor or model documentation, or a comparison across official sources.
- `orchestration:worker`: two or more independent implementation units, or a fully specified change that would flood your context. Give each worker its own files.
- `orchestration:tester`: reproducing a reported failure, or verification beyond one quick command.
- `orchestration:reviewer`: before you report a material change as done (several files, a public interface, security, data, concurrency, or migrations), an independent review of the actual diff.

Work directly on a single file, a quick lookup, or strictly sequential steps, because each delegate costs time and tokens.

How to delegate:

- Use these roles instead of the built-in Explore, Plan, or general-purpose agents for the same job; fall back to built-ins only when the roles are unavailable.
- Always set `subagent_type` to the role. Never pass `model` or `effort`, and never fork for a role: either bypasses the installed profile.
- Brief each delegate with the objective, relevant paths, allowed reads, writes, and external actions, acceptance checks, and a stop condition, sized so one delegate can finish it. Delegation never expands authority.
- Keep one writer per file. Wait for every delegate you depend on, then inspect the final diff and run the checks yourself; report only what actually ran.
- `/orchestration:orchestrate` is started by the user. When a message begins with it, follow its routing; never imitate invoking it.
