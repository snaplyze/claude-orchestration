# Verification

## Static acceptance

```bash
python -m unittest discover -v
python scripts/doctor.py
sh -n setup.sh
```

`scripts/doctor.py` is the single static validator: plugin namespace, the exact five-agent set, supported model/effort pairs in the plugin and in all eight profiles, and plugin frontmatter equal to `pro-balanced` (the marketplace topology). The tests run it once, check that it rejects a broken copy, and verify installer behavior: per-profile materialization, round trip of prior settings through install, profile switch, and uninstall, reinstall without `--profile`, byte-identical settings on a no-marker uninstall, rollback after an early (invalid profile) and a late (plugin swap) failure, and rejection of symlinks and unknown profile names.

## GitHub Actions

CI uses only standard GitHub-hosted runners. It runs the same unittest and doctor commands on `ubuntu-latest`, `macos-latest`,
and `windows-latest`, with Python 3.12 and 3.13, plus Python 3.11 on Ubuntu.
The Windows/3.13 job also installs and uninstalls through `setup.ps1`, and a
separate Ubuntu job checks `setup.sh` syntax and runs the same smoke test. Python is provided by SHA-pinned `actions/setup-python`.

Triggers are pushes to `main`, pull requests, and manual dispatch. PR branch
pushes do not also create a separate push run. Superseded runs for the same ref
are cancelled; test jobs have a 15-minute timeout and the shell job 5 minutes.
The token has `contents: read`, checkout does not persist credentials, and all
external contributors require approval before their fork PR workflows run.

For agents, the project runner mode is `github-hosted` (the `CI-раннеры` line
in `AGENTS.md`; rules in §14–15). CI status is tracked as A-01 in the
[plan](plan.md).
Local Linux tests do not establish Windows/macOS acceptance or Claude Code
runtime behavior.

## Claude Code runtime acceptance

When Claude Code is installed and authenticated, run:

```bash
claude plugin validate --strict ./plugin
python scripts/runtime_smoke.py --skill --tool-surface        # bundled plugin
python scripts/runtime_smoke.py --skill --plugin-dir <project>/.claude/plugins/orchestration
```

`runtime_smoke.py` starts headless Claude Code with the plugin and a temporary
`--settings` file whose `SubagentStop`/`Stop` hooks record the effort level in
effect. It dispatches each `orchestration:*` role by name with a one-word task
and reads each subagent's model from its session transcript. With `--skill` it
starts a session on another model (`haiku` by default) and invokes
`/orchestration:orchestrate`, so a working model/effort override is visible.
With `--tool-surface` it asks the read-only roles (explorer, researcher) to
create a file and passes only if no write tool ran and the file is absent; the
same probe against `worker` fails, which confirms it detects writes.
Every check compares against the frontmatter of the tested plugin directory, so
an installed profile is checked against its own values. Each run makes real,
paid model calls (about $0.05–0.15; `--budget` caps each run) and is not part
of CI, which has no Claude credentials.

Covered: the skill is invocable, the five roles are discoverable by name, both
use their declared model and effort, and explorer/researcher cannot write.
Not covered: reviewer's no-write rule (it keeps Bash, so the rule is an
instruction, not a tool limit) and interactive or `--agent` paths.

Results on 2026-10-09, Claude Code 2.1.295: bundled plugin — 5/5 roles and the
skill PASS (explorer `claude-haiku-5-5`/low; researcher and tester
`claude-sonnet-5-5`/medium; worker `claude-sonnet-5-5`/high; reviewer and skill
`claude-opus-5-5`/high, the skill switching a Haiku session); installed
`max-20x-thorough` — 6/6 PASS including `xhigh` for reviewer and skill; read-only
probe 2/2 PASS. Marketplace path: in an isolated `CLAUDE_CONFIG_DIR`,
`/plugin marketplace add snaplyze/claude-orchestration` and
`/plugin install orchestration@snaplyze-orchestration` installed and enabled
1.2.0 from `main`.

## Current upstream caveats

Claude Code documentation supports `effort` in skill and subagent frontmatter, but upstream issue reports show path-specific inconsistencies (checked 2026-10-09). On Claude Code 2.1.295, `runtime_smoke.py` found the first and third behaviors working for this plugin's paths — Agent-tool dispatch and a headless `/orchestration:orchestrate` invocation both applied frontmatter model and effort; `--agent` was not tested:

- ordinary Agent-tool subagent dispatch runs at the subagent's `effort`: reporters' observations in [#82259](https://github.com/anthropics/claude-code/issues/82259) and [#83252](https://github.com/anthropics/claude-code/issues/83252) (v2.1.220; the latter found only a display defect), not a maintainer confirmation;
- `claude -p --agent <name>` ignored agent frontmatter effort in [#82259](https://github.com/anthropics/claude-code/issues/82259) (v2.1.220), closed 2026-10-08 as inactive rather than fixed;
- inline skill execution can stay at session effort ([#69267](https://github.com/anthropics/claude-code/issues/69267), open), and adding `effort` to a skill with `model` can drop the model override ([#81618](https://github.com/anthropics/claude-code/issues/81618), open, v2.1.220).

For that reason, the project installer also writes the selected **root** model and effort into project `.claude/settings.json`; it does not rely solely on skill frontmatter for coordinator effort. The orchestration skill is manual-only (`disable-model-invocation: true`) so normal use starts at a user-invoked turn boundary. Subagents are intended to run through normal foreground delegation, not as `--agent` personas or experimental teammates when exact effort is part of acceptance.

Do not claim effective effort from static YAML alone. When a Claude Code release changes these paths, repeat the runtime smoke matrix and record the client version.
