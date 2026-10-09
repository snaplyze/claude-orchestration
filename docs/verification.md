# Verification

## Static acceptance

```bash
python -m unittest discover -v
python scripts/doctor.py
sh -n setup.sh
```

`scripts/doctor.py` is the single static validator: plugin namespace, the exact five-agent set, supported model/effort pairs in the plugin and in all eight profiles, and plugin frontmatter equal to `pro-balanced` (the marketplace topology). The tests run it once, check that it rejects a broken copy, and verify installer behavior: per-profile materialization, round trip of prior settings through install, profile switch, and uninstall, reinstall without `--profile`, byte-identical settings on a no-marker uninstall, rollback after an early (invalid profile) and a late (plugin swap) failure, and rejection of symlinks and unknown profile names.

## GitHub Actions

The owner selected GitHub-hosted runners for this repository on 2026-10-09.
CI runs the same unittest and doctor commands on `ubuntu-latest`, `macos-latest`,
and `windows-latest`, with Python 3.12 and 3.13, plus Python 3.11 on Ubuntu.
The Windows/3.13 job also installs and uninstalls through `setup.ps1`, and a
separate Ubuntu job checks `setup.sh` syntax and runs the same smoke test. Python is provided by SHA-pinned `actions/setup-python`;
no local VM, private tool cache, or runner registration token is required.

Triggers are pushes to `main`, pull requests, and manual dispatch. PR branch
pushes do not also create a separate push run. Superseded runs for the same ref
are cancelled; test jobs have a 15-minute timeout and the shell job 5 minutes.
The token has `contents: read`, checkout does not persist credentials, and all
external contributors require approval before their fork PR workflows run.

This is an explicit project exception to the general self-hosted policy in
`AGENTS.md`; the hosted-run status is tracked as A-01 in the [plan](plan.md).
Local Linux tests do not establish Windows/macOS acceptance or Claude Code
runtime behavior.

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

Claude Code documentation supports `effort` in skill and subagent frontmatter, but upstream issue reports show path-specific inconsistencies (checked 2026-10-09; none was retested on Claude Code 2.1.295):

- ordinary Agent-tool subagent dispatch runs at the subagent's `effort`: reporters' observations in [#82259](https://github.com/anthropics/claude-code/issues/82259) and [#83252](https://github.com/anthropics/claude-code/issues/83252) (v2.1.220; the latter found only a display defect), not a maintainer confirmation;
- `claude -p --agent <name>` ignored agent frontmatter effort in [#82259](https://github.com/anthropics/claude-code/issues/82259) (v2.1.220), closed 2026-10-08 as inactive rather than fixed;
- inline skill execution can stay at session effort ([#69267](https://github.com/anthropics/claude-code/issues/69267), open), and adding `effort` to a skill with `model` can drop the model override ([#81618](https://github.com/anthropics/claude-code/issues/81618), open, v2.1.220).

For that reason, the project installer also writes the selected **root** model and effort into project `.claude/settings.json`; it does not rely solely on skill frontmatter for coordinator effort. The orchestration skill is manual-only (`disable-model-invocation: true`) so normal use starts at a user-invoked turn boundary. Subagents are intended to run through normal foreground delegation, not as `--agent` personas or experimental teammates when exact effort is part of acceptance.

Do not claim effective effort from static YAML alone. When a Claude Code release changes these paths, repeat the runtime smoke matrix and record the client version.
