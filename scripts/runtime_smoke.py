#!/usr/bin/env python3
"""Runtime smoke test: run Claude Code with the plugin and compare each role's effective model and effort with its frontmatter.

Evidence comes from Claude Code itself: SubagentStop/Stop hook input reports the effort level in effect, and the
session transcripts record the model of every assistant message. Each run makes real (paid) model calls.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from install import PLUGIN, frontmatter

ROLES = ("explorer", "researcher", "worker", "tester", "reviewer")
TASK = "Reply with the single word OK. Do not use any tools."
READ_ONLY = ("explorer", "researcher")  # no write tools in frontmatter
NO_WRITE_BY_INSTRUCTION = ("reviewer",)  # keeps Bash; its no-write rule is behavioral
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"}
HOOK = "import sys\nwith open(sys.argv[1], 'a', encoding='utf-8') as f:\n    f.write(sys.stdin.read().strip() + '\\n')\n"
HOOK_EVENTS = ("PreToolUse", "SubagentStop", "Stop", "InstructionsLoaded")
RULE = Path(__file__).resolve().parent / "default-orchestration-rule.md"
RULE_FILE = "claude-orchestration.md"  # name of the installed rule file, also used for the bundled copy
# --default-rule: an unfamiliar codebase where each subsystem's value is reached through a five-module call chain,
# next to retired legacy modules holding a decoy value. (subsystem, entry function, constant, value, decoy)
FLOWS = (("orders", "create_order", "TABLE", '"orders_v2"', '"orders_v1"'),
         ("billing", "invoice", "VAT_RATE", "0.19", "0.16"),
         ("notify", "send", "MAX_RETRIES", "13", "5"))
STEPS = ("api", "service", "rules", "adapter", "config")
MAP_TASK = ("I am new to this repository. Answer three independent questions and cite the files on each path; the legacy "
            "modules are not on these paths. (1) Starting at orders/api.py create_order, which TABLE value is used? "
            "(2) Starting at billing/api.py invoice, which VAT_RATE applies? (3) Starting at notify/api.py send, what is MAX_RETRIES?")
LOOKUP_TASK = "What is VAT_RATE in billing/config.py? Reply with the number only."
CHANGE_TASK = ("Add an optional currency argument, default \"EUR\", that billing/api.py invoice passes along its whole call chain so "
               "that the dict returned at the end contains it; add a test under tests/ and run it. Report when it is done.")
RESEARCH_TASK = ("Before we add an HTTP client dependency: from the projects' official sources, compare the current stable releases of "
                 "httpx and requests, their supported Python versions, and their maintenance status, and recommend one for Python 3.11+.")
NO_SUBAGENTS = "# Project rules\n\nDo all work in the main session. Do not use subagents or the Agent tool in this repository.\n"
# (name, task, project CLAUDE.md, expected): None = no Agent call; otherwise only orchestration roles, including these.
RULE_CASES = (("map", MAP_TASK, None, frozenset()), ("lookup", LOOKUP_TASK, None, None), ("project forbids", MAP_TASK, NO_SUBAGENTS, None),
              ("change", CHANGE_TASK, None, frozenset({"orchestration:reviewer"})), ("research", RESEARCH_TASK, None, frozenset({"orchestration:researcher"})))
ANSWERS = {"map": [value.strip('"') for *_, value, _ in FLOWS], "lookup": ["0.19"], "project forbids": [value.strip('"') for *_, value, _ in FLOWS]}


def transcript_models(path: str) -> list[str]:
    models = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        model = (json.loads(line).get("message") or {}).get("model") if line.strip() else None
        if model and not model.startswith("<"):
            models.append(model)
    return models


def load_events(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()] if log.exists() else []


def verdict(name: str, want: dict, effort: str | None, models: list[str]) -> dict:
    ok = effort == want.get("effort") and bool(models) and all(want.get("model", "?") in m for m in models)
    return {"name": name, "want": f"{want.get('model')}/{want.get('effort')}", "seen": f"{','.join(sorted(set(models))) or '-'}/{effort or '-'}", "ok": ok}


def check_roles(events: list[dict], plugin_dir: Path, roles=ROLES) -> list[dict]:
    stops = {e.get("agent_type"): e for e in events if e.get("hook_event_name") == "SubagentStop"}
    results = []
    for role in roles:
        want = frontmatter(plugin_dir / "agents" / f"{role}.md")
        event = stops.get(f"orchestration:{role}")
        if event is None:
            results.append({"name": role, "want": f"{want.get('model')}/{want.get('effort')}", "seen": "not dispatched", "ok": False})
            continue
        results.append(verdict(role, want, (event.get("effort") or {}).get("level"), transcript_models(event["agent_transcript_path"])))
    return results


def last_session_turn(events: list[dict]) -> tuple[str | None, list[str]] | None:
    """Effort of the main session's last Stop event and the model of its last assistant message."""
    stops = [e for e in events if e.get("hook_event_name") == "Stop" and "agent_id" not in e]
    if not stops:
        return None
    return (stops[-1].get("effort") or {}).get("level"), transcript_models(stops[-1]["transcript_path"])[-1:]


def check_skill(events: list[dict], plugin_dir: Path) -> dict:
    want = frontmatter(plugin_dir / "skills/orchestrate/SKILL.md")
    turn = last_session_turn(events)
    if turn is None:
        return {"name": "orchestrate skill", "want": f"{want.get('model')}/{want.get('effort')}", "seen": "no Stop event", "ok": False}
    return verdict("orchestrate skill", want, *turn)


def check_agent_session(events: list[dict], want: dict, role: str) -> dict:
    """`claude --agent` documents only the agent's model and tools for the main session, so effort is reported, not required."""
    turn = last_session_turn(events)
    effort, models = turn if turn else (None, [])
    return {"name": f"{role} --agent", "want": f"{want.get('model')} (effort not applied)",
            "seen": f"{','.join(models) or '-'}/{effort or '-'}", "ok": bool(models) and want.get("model", "?") in models[0]}


def check_read_only(events: list[dict], work: Path, roles=READ_ONLY, label="read-only") -> list[dict]:
    results = []
    for role in roles:
        dispatched = any(e.get("agent_type") == f"orchestration:{role}" for e in events if e.get("hook_event_name") == "SubagentStop")
        writes = sorted({e.get("tool_name") for e in events if e.get("hook_event_name") == "PreToolUse"
                         and e.get("agent_type") == f"orchestration:{role}" and e.get("tool_name") in WRITE_TOOLS})
        created = (work / f"probe-{role}.txt").exists()
        seen = "not dispatched" if not dispatched else f"write tools {writes or 'none'}, file {'created' if created else 'absent'}"
        results.append({"name": f"{role} {label}", "want": "no write", "seen": seen, "ok": dispatched and not writes and not created})
    return results


def forget_sessions(events: list[dict]) -> int:
    """Delete the session transcripts these runs left under Claude Code's projects directory; return how many.

    Only `<projects>/<project>/<session>.jsonl`, its `<session>/` directory, and the project folder once it holds
    nothing but empty directories are removed.
    """
    projects = (Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser() / "projects").resolve()
    removed = 0
    for path in {Path(e["transcript_path"]).resolve() for e in events if e.get("transcript_path") and "agent_id" not in e}:
        if path.suffix != ".jsonl" or path.parent.parent != projects:
            continue
        for item in (path, path.with_suffix("")):  # <session>.jsonl and <session>/ with subagent transcripts
            if item.is_symlink() or item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        removed += 1
        if all(i.is_dir() and not i.is_symlink() and not any(i.iterdir()) for i in path.parent.iterdir()):  # e.g. an empty memory/
            shutil.rmtree(path.parent)
    return removed


def write_settings(work: Path, extra: dict | None = None) -> Path:
    log, hook = work / "hooks.jsonl", work / "hook.py"
    hook.write_text(HOOK, encoding="utf-8")
    command = [{"type": "command", "command": f'"{sys.executable}" "{hook}" "{log}"'}]
    settings = work / "settings.json"
    settings.write_text(json.dumps({**(extra or {}), "hooks": {event: [{"hooks": command}] for event in HOOK_EVENTS}}), encoding="utf-8")
    return settings


def helpers(sub: str, part: int, count: int) -> list[str]:
    lines = []
    for k in range(count):
        lines += [f"def {sub}_helper_{part}_{k}(items, factor={k + 1}):", f'    """Scale the {sub} items that are not multiples of {k + 2}."""',
                  f"    return [x * factor for x in items if x % {k + 2}]", "", ""]
    return lines


def write_fixture(root: Path) -> None:
    """About 4,000 lines in 72 modules: per subsystem, the call chain hides among helper functions and modules."""
    for sub, entry, const, value, decoy in FLOWS:
        pkg = root / sub
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        for i, step in enumerate(STEPS):
            name = entry if i == 0 else f"{step}_{sub}"
            if i + 1 < len(STEPS):
                nxt = STEPS[i + 1]
                head, call = [f"from {sub} import {nxt}", "", ""], f"    return {nxt}.{nxt}_{sub}(dict(payload, step={step!r}))"
            else:
                head, call = [f"{const} = {value}", "", ""], f"    return dict(payload, {const.lower()}={const})"
            body = head + helpers(sub, 100 + i, 3) + [f"def {name}(payload):", call, "", ""] + helpers(sub, 200 + i, 3)
            (pkg / f"{step}.py").write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")
        for i in range(14):
            (pkg / f"util_{i}.py").write_text("\n".join(helpers(sub, i, 20)).rstrip() + "\n", encoding="utf-8")
        for i in range(4):
            (pkg / f"legacy_{i}.py").write_text(f"{const} = {decoy}  # retired\n\n\ndef config_{sub}_v{i}(payload):\n    return dict(payload, {const.lower()}={const})\n", encoding="utf-8")


def agent_calls(events: list[dict]) -> list[dict]:
    """Agent tool inputs issued by the main session (calls made inside a subagent carry agent_id)."""
    return [e.get("tool_input") or {} for e in events if e.get("hook_event_name") == "PreToolUse" and e.get("tool_name") == "Agent" and "agent_id" not in e]


def rule_run(events: list[dict], expect: frozenset | None) -> tuple[bool, str]:
    """Judge one --default-rule run. The rule must be loaded; then, with expect None, no Agent call at all; otherwise
    only orchestration roles, including every role in expect, dispatched without model/effort overrides."""
    if not any(Path(e.get("file_path", "")).name == RULE_FILE for e in events if e.get("hook_event_name") == "InstructionsLoaded"):
        return False, "rule not loaded"
    calls = agent_calls(events)
    types = [c.get("subagent_type") or "general-purpose" for c in calls]
    roles = [c for c, t in zip(calls, types) if t.startswith("orchestration:")]
    overrides = sorted({k for c in roles for k in ("model", "effort") if c.get(k)})
    ok = not calls if expect is None else len(roles) == len(calls) > 0 and expect <= set(types) and not overrides
    return ok, (",".join(t.removeprefix("orchestration:") for t in types) or "no Agent call") + (f" (overrides {','.join(overrides)})" if overrides else "")


def check_rule_case(name: str, runs: list[tuple[bool, str]], expect: frozenset | None) -> dict:
    """A case passes when at least 2/3 of its runs follow the rule (delegating is a model decision), or every run
    when the rule says not to delegate."""
    passed = sum(ok for ok, _ in runs)
    ok = bool(runs) and (passed == len(runs) if expect is None else 3 * passed >= 2 * len(runs))
    want = "no Agent call" if expect is None else "roles only" + "".join(f" +{r.removeprefix('orchestration:')}" for r in sorted(expect))
    return {"name": f"default rule: {name}", "want": want, "seen": f"{passed}/{len(runs)} [" + " | ".join(seen for _, seen in runs) + "]", "ok": ok}


def settle(transcript: Path, timeout: float = 15) -> None:
    """Wait until the TUI has flushed an assistant message to the transcript and the file stops growing."""
    deadline, size = time.monotonic() + timeout, -1
    while time.monotonic() < deadline:
        current = transcript.stat().st_size if transcript.exists() else -1
        if current == size and transcript_models(str(transcript)):
            return
        size = current
        time.sleep(1)


def run_interactive(claude: str, steps: list[tuple[str, object]], plugin_dir: Path | None, work: Path, model: str, timeout: float = 600) -> list[list[dict]]:
    """Drive a real interactive session in tmux; each step sends a prompt and waits until done(events) is true.

    Returns the events seen by the end of each step, with the main transcript snapshotted at that moment,
    because later steps keep appending to the same session transcript.

    Runs in the current directory, which must already be trusted by Claude Code (a trust prompt would block input).
    """
    if not shutil.which("tmux"):
        raise RuntimeError("--interactive needs tmux")
    session, log = f"orchestration-smoke-{work.parent.name[-8:]}", work / "hooks.jsonl"
    plugin_arg = f' --plugin-dir "{plugin_dir}"' if plugin_dir else ""
    command = f'{claude}{plugin_arg} --settings "{write_settings(work)}" --model {model}'
    subprocess.run(["tmux", "new-session", "-d", "-s", session, "-x", "200", "-y", "50", command], check=True)
    snapshots = []
    try:
        for i, (prompt, done) in enumerate(steps):
            time.sleep(5)  # let the TUI accept input
            subprocess.run(["tmux", "send-keys", "-t", session, "-l", prompt], check=True)
            subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], check=True)
            deadline = time.monotonic() + timeout
            while not done(load_events(log)):
                if time.monotonic() > deadline:
                    raise RuntimeError(f"interactive step timed out: {prompt[:60]}")
                time.sleep(2)
            events = load_events(log)
            for e in events:
                if e.get("hook_event_name") == "Stop" and "agent_id" not in e:
                    settle(Path(e["transcript_path"]))
                    snapshot = work / f"transcript-{i}.jsonl"
                    shutil.copyfile(e["transcript_path"], snapshot)
                    e["transcript_path"] = str(snapshot)
            snapshots.append(events)
    finally:
        # Exit cleanly so Claude Code finishes writing its transcript before forget_sessions removes it.
        subprocess.run(["tmux", "send-keys", "-t", session, "-l", "/exit"], capture_output=True)
        subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], capture_output=True)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and subprocess.run(["tmux", "has-session", "-t", session], capture_output=True).returncode == 0:
            time.sleep(1)
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
    return snapshots


def run_claude(claude: str, prompt: str, plugin_dir: Path | None, work: Path, budget: float, model: str | None, extra: tuple = (),
               settings: dict | None = None, env: dict | None = None, cwd: Path | None = None) -> dict:
    """Run one headless session (hooks log to work/, cwd defaults to work) and return its JSON result."""
    args = [claude, "-p", prompt, *(["--plugin-dir", str(plugin_dir)] if plugin_dir else []), "--settings", str(write_settings(work, settings)), "--output-format", "json", "--max-budget-usd", str(budget)]
    if model:
        args += ["--model", model]
    args += list(extra)
    proc = subprocess.run(args, cwd=cwd or work, capture_output=True, text=True, timeout=900, env={**os.environ, **(env or {})})
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}")
    return json.loads(proc.stdout)


def cost_of(out: dict) -> float:
    return float(out.get("total_cost_usd") or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plugin-dir", type=Path, default=PLUGIN, help="plugin directory to test (default: bundled plugin/)")
    parser.add_argument("--use-installed", action="store_true", help="test the plugin Claude Code already has installed (no --plugin-dir); --plugin-dir then names its files for the expected values")
    parser.add_argument("--roles", default=",".join(ROLES), help="comma-separated roles to dispatch")
    parser.add_argument("--skill", action="store_true", help="also invoke /orchestration:orchestrate and check its model/effort")
    parser.add_argument("--tool-surface", action="store_true", help="also ask read-only roles to create a file and check they cannot")
    parser.add_argument("--agent-path", action="store_true", help="also start each role as the session agent (claude --agent) and check its model/effort")
    parser.add_argument("--interactive", action="store_true", help="also repeat the role and skill checks in an interactive session driven through tmux (run from a trusted folder; cost is not reported)")
    parser.add_argument("--default-rule", action="store_true", help="also check that the default-orchestration rule makes a session delegate to the roles in an unfamiliar repository, and not for a one-file lookup or when the project forbids subagents (bundled rule via --add-dir; with --use-installed, the user's installed rule)")
    parser.add_argument("--runs", type=int, default=3, help="runs per --default-rule case")
    parser.add_argument("--rule-cases", type=lambda v: [c.strip() for c in v.split(",") if c.strip()], default=[], help=f"comma-separated --default-rule cases (default: all of {', '.join(c[0] for c in RULE_CASES)})")
    parser.add_argument("--rule-model", default="opus", help="session model for --default-rule (the main model users work with)")
    parser.add_argument("--coordinator-model", default="haiku", help="session model; it differs from the skill's so a working override is visible")
    parser.add_argument("--keep-sessions", action="store_true", help="keep the session transcripts the runs leave in Claude Code's projects directory")
    parser.add_argument("--budget", type=float, default=2.0, help="maximum USD per claude run")
    parser.add_argument("--claude", default="claude")
    args = parser.parse_args()
    plugin_dir, roles = args.plugin_dir.expanduser().resolve(), [r for r in args.roles.split(",") if r]
    load_dir = None if args.use_installed else plugin_dir
    unknown = set(roles) - set(ROLES)
    if unknown:
        parser.error(f"unknown roles: {sorted(unknown)}")
    results, cost = [], 0.0
    with tempfile.TemporaryDirectory(prefix="orchestration-smoke-") as td:
        try:
            if roles:
                work = Path(td) / "roles"; work.mkdir()
                names = ", ".join(f"orchestration:{r}" for r in roles)
                prompt = f"Dispatch these subagents one at a time, giving each exactly this task: '{TASK}' Subagents: {names}. Do nothing else; after all of them return, reply DONE."
                cost += cost_of(run_claude(args.claude, prompt, load_dir, work, args.budget, args.coordinator_model))
                results += check_roles(load_events(work / "hooks.jsonl"), plugin_dir, roles)
            if args.skill:
                work = Path(td) / "skill"; work.mkdir()
                cost += cost_of(run_claude(args.claude, f"/orchestration:orchestrate Economy mode. {TASK} Do not delegate.", load_dir, work, args.budget, args.coordinator_model))
                results.append(check_skill(load_events(work / "hooks.jsonl"), plugin_dir))
            if args.tool_surface:
                work = Path(td) / "tools"; work.mkdir()
                tasks = " ".join(f"Give orchestration:{r} exactly this task: 'Create the file {work / f'probe-{r}.txt'} containing OK. If no available tool can create files, reply CANNOT.'" for r in READ_ONLY + NO_WRITE_BY_INSTRUCTION)
                cost += cost_of(run_claude(args.claude, f"Dispatch these subagents one at a time and do nothing else yourself. {tasks} Then reply DONE.", load_dir, work, args.budget, args.coordinator_model))
                events = load_events(work / "hooks.jsonl")
                results += check_read_only(events, work) + check_read_only(events, work, NO_WRITE_BY_INSTRUCTION, "no-write (instruction)")
            if args.agent_path:
                for role in roles:
                    work = Path(td) / f"agent-{role}"; work.mkdir()
                    cost += cost_of(run_claude(args.claude, TASK, load_dir, work, args.budget, None, ("--agent", f"orchestration:{role}")))
                    results.append(check_agent_session(load_events(work / "hooks.jsonl"), frontmatter(plugin_dir / "agents" / f"{role}.md"), role))
            if args.default_rule:
                cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser().resolve()
                extra, settings, env = (), None, None
                if not args.use_installed:  # bundled rule through --add-dir; the user's own instructions are left out
                    rules = Path(td) / "user-rules" / ".claude/rules"
                    rules.mkdir(parents=True)
                    shutil.copyfile(RULE, rules / RULE_FILE)
                    extra, env = ("--add-dir", str(rules.parents[1])), {"CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD": "1"}
                    settings = {"claudeMdExcludes": [str(cfg / "CLAUDE.md"), str(cfg / "rules") + "/**"]}
                for name, task, project_rules, expect in RULE_CASES:
                    if args.rule_cases and name not in args.rule_cases:
                        continue
                    runs = []
                    for i in range(args.runs):
                        work = Path(td) / f"rule-{name.replace(' ', '-')}-{i}"
                        repo = work / "repo"
                        write_fixture(repo)
                        if project_rules:
                            (repo / "CLAUDE.md").write_text(project_rules, encoding="utf-8")
                        try:
                            out = run_claude(args.claude, task, load_dir, work, args.budget, args.rule_model, extra, settings, env, repo)
                        except (RuntimeError, subprocess.TimeoutExpired) as e:
                            runs.append((False, f"error: {str(e)[:80]}"))
                            continue
                        cost += cost_of(out)
                        ok, seen = rule_run(load_events(work / "hooks.jsonl"), expect)
                        if name in ANSWERS:
                            seen += f", answer {'right' if all(a in str(out.get('result', '')) for a in ANSWERS[name]) else 'wrong'}"
                        runs.append((ok, f"{seen}, ${cost_of(out):.2f}"))
                    if runs:
                        results.append(check_rule_case(name, runs, expect))
            if args.interactive:
                work = Path(td) / "interactive"; work.mkdir()
                names = ", ".join(f"orchestration:{r}" for r in roles)
                stops = lambda n: (lambda ev: sum(e.get("hook_event_name") == "Stop" for e in ev) >= n)
                role_stops = lambda ev: len({e.get("agent_type") for e in ev if e.get("hook_event_name") == "SubagentStop"} & {f"orchestration:{r}" for r in roles}) == len(roles)
                steps = [(f"/orchestration:orchestrate Economy mode. {TASK} Do not delegate.", stops(1))]
                if roles:  # interactive sessions may run subagents in the background over several turns
                    steps.append((f"Dispatch these subagents, giving each exactly this task: '{TASK}' Subagents: {names}. Do nothing else; when all have returned, reply DONE.", role_stops))
                snapshots = run_interactive(args.claude, steps, load_dir, work, args.coordinator_model)
                checks = [check_skill(snapshots[0], plugin_dir), *(check_roles(snapshots[-1], plugin_dir, roles) if roles else [])]
                results += [dict(r, name=f"{r['name']} (interactive)") for r in checks]
        finally:
            if not args.keep_sessions:
                for work in Path(td).iterdir():
                    forget_sessions(load_events(work / "hooks.jsonl"))
    width = max(len(r["name"]) for r in results)
    for r in results:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['name']:<{width}}  expected {r['want']:<14}  seen {r['seen']}")
    print(f"cost: ${cost:.4f}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
