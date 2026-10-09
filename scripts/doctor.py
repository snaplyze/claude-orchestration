#!/usr/bin/env python3
"""Static validation of the distribution: manifest, plugin frontmatter, and profiles."""
from pathlib import Path
import json, re, sys
from install import frontmatter

R = Path(__file__).resolve().parents[1]
AGENTS = {"explorer", "researcher", "worker", "tester", "reviewer"}
MODELS = {"haiku", "sonnet", "opus"}
ROOT_MODELS = {"sonnet", "opus"}
EFFORTS = {"low", "medium", "high", "xhigh"}
RESERVED = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")
PROFILE_COUNT = 8
MARKETPLACE_PROFILE = "pro-balanced"
ROLE_ORDER = ("explorer", "researcher", "worker", "tester", "reviewer")


def pair_errors(where: str, model, effort, models=MODELS) -> list[str]:
    errors = []
    if model not in models: errors.append(f"{where}: unsupported model {model!r}")
    if effort not in EFFORTS: errors.append(f"{where}: invalid/missing effort {effort!r}")
    return errors


def check(root: Path = R) -> list[str]:
    errors = []
    try:
        name = json.loads((root / "plugin/.claude-plugin/plugin.json").read_text(encoding="utf-8")).get("name", "")
        if name != "orchestration": errors.append("plugin name must be orchestration")
        if name.startswith(RESERVED): errors.append("plugin uses reserved prefix")
    except Exception as e: errors.append(f"manifest: {e}")

    shipped, turns, documented = {}, {}, {}
    agent_files = {p.stem: p for p in (root / "plugin/agents").glob("*.md")}
    if set(agent_files) != AGENTS: errors.append(f"plugin agents must be exactly {sorted(AGENTS)}")
    for key, path in [("skill", root / "plugin/skills/orchestrate/SKILL.md"), *agent_files.items()]:
        try: d = frontmatter(path)
        except Exception as e: errors.append(f"{path.name}: {e}"); continue
        errors += pair_errors(path.name, d.get("model"), d.get("effort"), ROOT_MODELS if key == "skill" else MODELS)
        shipped[key] = [d.get("model"), d.get("effort")]
        turns[key] = d.get("maxTurns", "session-owned")

    profiles = sorted((root / "profiles").glob("*.json"))
    if len(profiles) != PROFILE_COUNT: errors.append(f"expected {PROFILE_COUNT} profiles, found {len(profiles)}")
    for p in profiles:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if set(d) != {"settings", "skill", "agents"}: errors.append(f"{p.name}: invalid schema"); continue
            if set(d["agents"]) != AGENTS: errors.append(f"{p.name}: incomplete agents")
            errors += pair_errors(f"{p.name} settings", d["settings"].get("model"), d["settings"].get("effortLevel"), ROOT_MODELS)
            errors += pair_errors(f"{p.name} skill", d["skill"].get("model"), d["skill"].get("effort"), ROOT_MODELS)
            for agent, pair in d["agents"].items():
                if not isinstance(pair, list) or len(pair) != 2: errors.append(f"{p.name} {agent}: expected [model, effort]"); continue
                errors += pair_errors(f"{p.name} {agent}", *pair)
            documented[p.stem] = [[d["skill"].get("model"), d["skill"].get("effort")], *(d["agents"].get(a, [None, None]) for a in ROLE_ORDER)]
            if p.stem == MARKETPLACE_PROFILE:
                expected = {"skill": [d["skill"].get("model"), d["skill"].get("effort")], **d["agents"]}
                if shipped != expected: errors.append(f"plugin frontmatter must match {p.name}")
        except Exception as e: errors.append(f"{p.name}: {e}")
    return errors + doc_errors(root, documented, shipped, turns)


def table_rows(path: Path, first_cell: str) -> dict[str, list[str]]:
    """Map the first cell of each Markdown table row matching first_cell (a regex) to its remaining cells."""
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if cells and re.fullmatch(first_cell, cells[0]): rows[cells[0].strip("`")] = cells[1:]
    return rows


def doc_errors(root: Path, documented: dict, shipped: dict, turns: dict) -> list[str]:
    """The topology tables in the docs are derived data: they must match the profiles and plugin frontmatter."""
    errors = []
    profile_rows = table_rows(root / "docs/models-and-plans.md", r"`[a-z0-9-]+`")
    for name, pairs in documented.items():
        want = [f"{str(model).capitalize()} {effort}" for model, effort in pairs]
        if profile_rows.get(name) != want: errors.append(f"docs/models-and-plans.md: row {name} must be {want}, found {profile_rows.get(name)}")
    component_rows = table_rows(root / "docs/architecture.md", "orchestrator skill|" + "|".join(ROLE_ORDER))
    for key in ("skill", *ROLE_ORDER):
        want = [*shipped.get(key, ["?", "?"]), str(turns.get(key))]
        found = component_rows.get("orchestrator skill" if key == "skill" else key, [])[:3]
        if found != want: errors.append(f"docs/architecture.md: row {key} must start with {want}, found {found}")
    return errors


if __name__ == "__main__":
    errors = check()
    if errors:
        print("\n".join("ERROR: " + e for e in errors)); sys.exit(1)
    print("doctor: OK")
