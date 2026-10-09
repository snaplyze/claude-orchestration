# Verification

## Static acceptance

```bash
python -m unittest discover -v
python scripts/doctor.py
sh -n setup.sh
```

The tests verify namespace safety, the complete five-agent topology, supported fixed-effort model choices, all eight profile schemas, profile materialization, settings preservation, profile switching, uninstall, rollback after an early failure (invalid profile, before any write), and symlink rejection. Rollback after a late failure during the plugin swap is not exercised yet (see [plan](plan.md), A-07).

## GitHub Actions

The owner selected GitHub-hosted runners for this repository on 2026-10-09.
CI runs the same unittest and doctor commands on `ubuntu-latest`, `macos-latest`,
and `windows-latest`, with Python 3.12 and 3.13. A separate Ubuntu job checks
`setup.sh` syntax. Python is provided by SHA-pinned `actions/setup-python`;
no local VM, private tool cache, or runner registration token is required.

Triggers are pushes to `main`, pull requests, and manual dispatch. PR branch
pushes do not also create a separate push run. Superseded runs for the same ref
are cancelled; test jobs have a 15-minute timeout and the shell job 5 minutes.
The token has `contents: read`, checkout does not persist credentials, and all
external contributors require approval before their fork PR workflows run.

This is an explicit project exception to the general self-hosted policy in
`AGENTS.md`; the hosted-run status is tracked as A-01 in the [plan](plan.md).
Local Linux tests do not establish Windows/macOS acceptance, PowerShell
launcher coverage (A-11), or Claude Code runtime behavior.

## Claude Code runtime acceptance

When Claude Code is installed, run:

```bash
claude plugin validate --strict ./plugin
claude --plugin-dir ./plugin
```

Then verify:

1. `/orchestration:orchestrate` is visible.
2. The five `orchestration:*` agents are discoverable.
3. A direct `/orchestration:orchestrate ...` invocation uses the expected coordinator model/effort for the selected project profile.
4. Foreground Agent-tool dispatch of each specialist uses its declared model/effort.
5. Read-only and write-capable role behavior matches the documented tool surface.

## Current upstream caveats

Claude Code documentation supports `effort` in skill and subagent frontmatter, but recent upstream issue reports show path-specific inconsistencies:

- ordinary Agent/Task-tool subagent dispatch has been independently confirmed to honor subagent `effort`;
- `claude --agent <name>` still has an open report where agent frontmatter effort is ignored;
- skill effort has an open report where inline skill execution can remain at session effort, and Skill-tool/mid-turn invocation has additional model/effort gaps.

For that reason, the project installer also writes the selected **root** model and effort into project `.claude/settings.json`; it does not rely solely on skill frontmatter for coordinator effort. The orchestration skill is manual-only (`disable-model-invocation: true`) so normal use starts at a user-invoked turn boundary. Subagents are intended to run through normal foreground delegation, not as `--agent` personas or experimental teammates when exact effort is part of acceptance.

Do not claim effective effort from static YAML alone. When a Claude Code release changes these paths, repeat the runtime smoke matrix and record the client version.
