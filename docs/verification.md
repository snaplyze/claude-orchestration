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
python scripts/runtime_smoke.py --skill --tool-surface --agent-path   # bundled plugin, headless
python scripts/runtime_smoke.py --interactive                         # same checks in a TUI session (tmux)
python scripts/runtime_smoke.py --skill --plugin-dir <project>/.claude/plugins/orchestration
```

`runtime_smoke.py` runs Claude Code with the plugin and a temporary `--settings`
file whose `PreToolUse`/`SubagentStop`/`Stop` hooks record the effort level in
effect and the tools used; each model comes from the session transcripts. Every
check compares against the frontmatter of the tested plugin directory, so an
installed profile is checked against its own values. Modes:

- default: dispatch each `orchestration:*` role by name with a one-word task;
- `--skill`: start on another model (`haiku` by default) and invoke
  `/orchestration:orchestrate`, so a working model/effort override is visible;
- `--tool-surface`: ask explorer and researcher (no write tools) and reviewer
  (Bash, no-write by instruction) to create a file; pass only if no write tool
  ran and no file appeared. The same probe against `worker` fails, which shows
  it detects writes;
- `--agent-path`: start each role as the session agent (`claude --agent`);
  the agent's model is required, its effort is reported only (see below);
- `--use-installed`: test the plugin Claude Code already has installed (no
  `--plugin-dir`), with `--plugin-dir` naming its files for the expected
  values, for example `~/.claude-orchestration/plugin` after a user install;
- `--interactive`: repeat the role and skill checks in a real interactive
  session driven through tmux, run from a folder Claude Code already trusts.

Runs use whatever account `claude` is logged in with — locally, your
subscription; usage counts against its limits, and the printed cost is
Claude Code's estimate (about $0.05–0.15 per mode). `--budget` caps each run.

### Runtime smoke in CI

`.github/workflows/runtime-smoke.yml` runs the headless modes on GitHub-hosted
Ubuntu with Claude Code pinned to 2.1.295: on manual dispatch and on
same-repository PRs that touch `plugin/`, `profiles/`, the installer, or the
smoke script. It authenticates with the owner's subscription through the
repository secret `CLAUDE_CODE_OAUTH_TOKEN`, created once with:

```bash
claude setup-token                                   # browser sign-in; prints a one-year token
gh secret set CLAUDE_CODE_OAUTH_TOKEN -R snaplyze/claude-orchestration   # paste the token when asked
```

The token can only make model requests. It is the owner's personal
subscription, and Anthropic's Consumer Terms forbid sharing account access, so
the job runs only when the repository owner both authored the event and
started or re-ran the run; other collaborators' PRs skip it, and fork PRs never
receive the secret. Without the secret the job is skipped. Interactive mode is
not run in CI. A shared team CI needs a Claude Console API key instead.

### Results

On 2026-10-09, Claude Code 2.1.295 (local, subscription):

| Check | Result |
|---|---|
| Five roles, headless and interactive | PASS: explorer `claude-haiku-5-5`/low; researcher and tester `claude-sonnet-5-5`/medium; worker `claude-sonnet-5-5`/high; reviewer `claude-opus-5-5`/high |
| Skill, headless and interactive | PASS: a Haiku session switches to `claude-opus-5-5`/high |
| Installed `max-20x-thorough` | PASS 6/6, including `xhigh` for reviewer and skill |
| Read-only roles; reviewer no-write instruction | PASS: no write tool, no file |
| `--agent` session | Model applied for all roles; effort stays at the session level (medium) instead of frontmatter |
| Default permission mode (as in CI) | PASS for a role and the skill |
| Marketplace install in an isolated `CLAUDE_CONFIG_DIR` | PASS: 1.2.0 from `main` installed and enabled |
| `runtime-smoke.yml` on GitHub-hosted Ubuntu with the owner's subscription token | PASS 20/20 (run 37912677050): bundled plugin incl. `--agent` and read-only probes, and installed `max-20x-thorough` |
| User-scope install (`install.py --user --profile max-20x-thorough --default-rule`, local marketplace loaded in place), checked with `--use-installed` | PASS 20/20: skill and reviewer `claude-opus-5-5`/xhigh, researcher/worker/tester `claude-sonnet-5-5`/high, explorer `claude-haiku-5-5`/low, headless and interactive; read-only and `--agent` as above |
| Default-orchestration rule in the user `CLAUDE.md` | Loaded in a folder without project instructions. A task with three independent workstreams was delegated to `orchestration:explorer`, `orchestration:researcher`, and `orchestration:reviewer` (not built-in agents); a trivial task and a small four-file read were done directly; with a project `CLAUDE.md` forbidding subagents, nothing was delegated |

The reviewer result shows behavior, not a guarantee: subagent frontmatter can
list only whole tools, and `Bash(...)` in `disallowedTools` removes Bash
entirely, so a plugin cannot limit the reviewer's Bash to read-only commands.
Use a session `permissions.deny` rule when a hard limit is needed.

## Current upstream caveats

Claude Code documentation supports `effort` in skill and subagent frontmatter, but upstream issue reports show path-specific inconsistencies (checked 2026-10-09). On Claude Code 2.1.295, `runtime_smoke.py` found Agent-tool dispatch and `/orchestration:orchestrate` (headless and interactive) applying frontmatter model and effort, and `claude --agent` applying the model but not the effort:

- ordinary Agent-tool subagent dispatch runs at the subagent's `effort`: reporters' observations in [#82259](https://github.com/anthropics/claude-code/issues/82259) and [#83252](https://github.com/anthropics/claude-code/issues/83252) (v2.1.220; the latter found only a display defect), not a maintainer confirmation;
- `claude -p --agent <name>` ignored agent frontmatter effort in [#82259](https://github.com/anthropics/claude-code/issues/82259) (v2.1.220), closed 2026-10-08 as inactive rather than fixed;
- inline skill execution can stay at session effort ([#69267](https://github.com/anthropics/claude-code/issues/69267), open), and adding `effort` to a skill with `model` can drop the model override ([#81618](https://github.com/anthropics/claude-code/issues/81618), open, v2.1.220).

For that reason, the project installer also writes the selected **root** model and effort into project `.claude/settings.json`; it does not rely solely on skill frontmatter for coordinator effort. The orchestration skill is manual-only (`disable-model-invocation: true`) so normal use starts at a user-invoked turn boundary. Subagents are intended to run through normal foreground delegation, not as `--agent` personas or experimental teammates when exact effort is part of acceptance. To run a role as the session anyway, pass its effort explicitly, for example `claude --agent orchestration:reviewer --effort high`.

Do not claim effective effort from static YAML alone. When a Claude Code release changes these paths, repeat the runtime smoke matrix and record the client version.
