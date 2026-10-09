#!/usr/bin/env python3
"""Runtime smoke test: run Claude Code with the plugin and compare each role's effective model and effort with its frontmatter.

Evidence comes from Claude Code itself: SubagentStop/Stop hook input reports the effort level in effect, and the
session transcripts record the model of every assistant message. Each run makes real (paid) model calls.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from install import PLUGIN, frontmatter

ROLES = ("explorer", "researcher", "worker", "tester", "reviewer")
TASK = "Reply with the single word OK. Do not use any tools."
READ_ONLY = ("explorer", "researcher")  # no write tools in frontmatter
NO_WRITE_BY_INSTRUCTION = ("reviewer",)  # keeps Bash; its no-write rule is behavioral
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"}
HOOK = "import sys\nwith open(sys.argv[1], 'a', encoding='utf-8') as f:\n    f.write(sys.stdin.read().strip() + '\\n')\n"


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


def write_settings(work: Path) -> Path:
    log, hook = work / "hooks.jsonl", work / "hook.py"
    hook.write_text(HOOK, encoding="utf-8")
    command = [{"type": "command", "command": f'"{sys.executable}" "{hook}" "{log}"'}]
    settings = work / "settings.json"
    settings.write_text(json.dumps({"hooks": {event: [{"hooks": command}] for event in ("PreToolUse", "SubagentStop", "Stop")}}), encoding="utf-8")
    return settings


def run_interactive(claude: str, steps: list[tuple[str, object]], plugin_dir: Path, work: Path, model: str, timeout: float = 600) -> list[list[dict]]:
    """Drive a real interactive session in tmux; each step sends a prompt and waits until done(events) is true.

    Returns the events seen by the end of each step, with the main transcript snapshotted at that moment,
    because later steps keep appending to the same session transcript.

    Runs in the current directory, which must already be trusted by Claude Code (a trust prompt would block input).
    """
    if not shutil.which("tmux"):
        raise RuntimeError("--interactive needs tmux")
    session, log = f"orchestration-smoke-{work.parent.name[-8:]}", work / "hooks.jsonl"
    command = f'{claude} --plugin-dir "{plugin_dir}" --settings "{write_settings(work)}" --model {model}'
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
                    snapshot = work / f"transcript-{i}.jsonl"
                    shutil.copyfile(e["transcript_path"], snapshot)
                    e["transcript_path"] = str(snapshot)
            snapshots.append(events)
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
    return snapshots


def run_claude(claude: str, prompt: str, plugin_dir: Path, work: Path, budget: float, model: str | None, extra: tuple = ()) -> float:
    args = [claude, "-p", prompt, "--plugin-dir", str(plugin_dir), "--settings", str(write_settings(work)), "--output-format", "json", "--max-budget-usd", str(budget)]
    if model:
        args += ["--model", model]
    args += list(extra)
    proc = subprocess.run(args, cwd=work, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}")
    return float(json.loads(proc.stdout).get("total_cost_usd") or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plugin-dir", type=Path, default=PLUGIN, help="plugin directory to test (default: bundled plugin/)")
    parser.add_argument("--roles", default=",".join(ROLES), help="comma-separated roles to dispatch")
    parser.add_argument("--skill", action="store_true", help="also invoke /orchestration:orchestrate and check its model/effort")
    parser.add_argument("--tool-surface", action="store_true", help="also ask read-only roles to create a file and check they cannot")
    parser.add_argument("--agent-path", action="store_true", help="also start each role as the session agent (claude --agent) and check its model/effort")
    parser.add_argument("--interactive", action="store_true", help="also repeat the role and skill checks in an interactive session driven through tmux (run from a trusted folder; cost is not reported)")
    parser.add_argument("--coordinator-model", default="haiku", help="session model; it differs from the skill's so a working override is visible")
    parser.add_argument("--budget", type=float, default=2.0, help="maximum USD per claude run")
    parser.add_argument("--claude", default="claude")
    args = parser.parse_args()
    plugin_dir, roles = args.plugin_dir.resolve(), [r for r in args.roles.split(",") if r]
    unknown = set(roles) - set(ROLES)
    if unknown:
        parser.error(f"unknown roles: {sorted(unknown)}")
    results, cost = [], 0.0
    with tempfile.TemporaryDirectory(prefix="orchestration-smoke-") as td:
        if roles:
            work = Path(td) / "roles"; work.mkdir()
            names = ", ".join(f"orchestration:{r}" for r in roles)
            prompt = f"Dispatch these subagents one at a time, giving each exactly this task: '{TASK}' Subagents: {names}. Do nothing else; after all of them return, reply DONE."
            cost += run_claude(args.claude, prompt, plugin_dir, work, args.budget, args.coordinator_model)
            results += check_roles(load_events(work / "hooks.jsonl"), plugin_dir, roles)
        if args.skill:
            work = Path(td) / "skill"; work.mkdir()
            cost += run_claude(args.claude, f"/orchestration:orchestrate Economy mode. {TASK} Do not delegate.", plugin_dir, work, args.budget, args.coordinator_model)
            results.append(check_skill(load_events(work / "hooks.jsonl"), plugin_dir))
        if args.tool_surface:
            work = Path(td) / "tools"; work.mkdir()
            tasks = " ".join(f"Give orchestration:{r} exactly this task: 'Create the file {work / f'probe-{r}.txt'} containing OK. If no available tool can create files, reply CANNOT.'" for r in READ_ONLY + NO_WRITE_BY_INSTRUCTION)
            cost += run_claude(args.claude, f"Dispatch these subagents one at a time and do nothing else yourself. {tasks} Then reply DONE.", plugin_dir, work, args.budget, args.coordinator_model)
            events = load_events(work / "hooks.jsonl")
            results += check_read_only(events, work) + check_read_only(events, work, NO_WRITE_BY_INSTRUCTION, "no-write (instruction)")
        if args.agent_path:
            for role in roles:
                work = Path(td) / f"agent-{role}"; work.mkdir()
                cost += run_claude(args.claude, TASK, plugin_dir, work, args.budget, None, ("--agent", f"orchestration:{role}"))
                results.append(check_agent_session(load_events(work / "hooks.jsonl"), frontmatter(plugin_dir / "agents" / f"{role}.md"), role))
        if args.interactive:
            work = Path(td) / "interactive"; work.mkdir()
            names = ", ".join(f"orchestration:{r}" for r in roles)
            stops = lambda n: (lambda ev: sum(e.get("hook_event_name") == "Stop" for e in ev) >= n)
            role_stops = lambda ev: len({e.get("agent_type") for e in ev if e.get("hook_event_name") == "SubagentStop"} & {f"orchestration:{r}" for r in roles}) == len(roles)
            steps = [(f"/orchestration:orchestrate Economy mode. {TASK} Do not delegate.", stops(1))]
            if roles:  # interactive sessions may run subagents in the background over several turns
                steps.append((f"Dispatch these subagents, giving each exactly this task: '{TASK}' Subagents: {names}. Do nothing else; when all have returned, reply DONE.", role_stops))
            snapshots = run_interactive(args.claude, steps, plugin_dir, work, args.coordinator_model)
            checks = [check_skill(snapshots[0], plugin_dir), *(check_roles(snapshots[-1], plugin_dir, roles) if roles else [])]
            results += [dict(r, name=f"{r['name']} (interactive)") for r in checks]
    width = max(len(r["name"]) for r in results)
    for r in results:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['name']:<{width}}  expected {r['want']:<14}  seen {r['seen']}")
    print(f"cost: ${cost:.4f}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
