#!/usr/bin/env python3
"""Static validation of the distribution: manifest, plugin frontmatter, and profiles."""
from pathlib import Path
import json, re, sys
from install import frontmatter, MODELS, ROOT_MODELS, EFFORTS  # the allowed names: the installer refuses anything else before writing

R = Path(__file__).resolve().parents[1]
AGENTS = {"explorer", "researcher", "worker", "tester", "reviewer"}
RESERVED = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")
RESERVED_NAMES = {"claude", "anthropic", "anthropics", "claude-code", "claude-mods"}
PROFILE_COUNT = 8
MARKETPLACE_PROFILE = "pro-balanced"
ROLE_ORDER = ("explorer", "researcher", "worker", "tester", "reviewer")
RULE_DOC, SKILL_DOC = "scripts/default-orchestration-rule.md", "plugin/skills/orchestrate/SKILL.md"
ROLE_LINE = re.compile(r"^- `orchestration:(?:explorer|researcher|worker|tester|reviewer)`: .*$", re.M)  # the rule's trigger lines
UNSAFE = re.compile("[\x00-\x08\x0b-\x1f\x85\u2028\u2029]")  # C0 controls except tab and LF, NEL, and the Unicode line/paragraph separators


def reserved_name(name: str) -> bool:
    """Whether `claude plugin validate` refuses the name as passing for one of Anthropic's own (research-sources 1):
    a reserved prefix or exact name, or `official` beside `claude`/`anthropic`; case ignored, a run of separators is one."""
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower()) if w]
    joined = "-".join(words)
    return joined.startswith(RESERVED) or joined in RESERVED_NAMES or any({a, b} == {"official", w} for a, b in zip(words, words[1:]) for w in ("claude", "anthropic"))


def pair_errors(where: str, model, effort, models=MODELS) -> list[str]:
    errors = []
    if model not in models: errors.append(f"{where}: unsupported model {model!r}")
    if effort not in EFFORTS: errors.append(f"{where}: invalid/missing effort {effort!r}")
    return errors


def check(root: Path = R) -> list[str]:
    errors, version = [], None
    try:
        manifest = json.loads((root / "plugin/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
        name, version = manifest.get("name", ""), manifest.get("version")
        if name != "orchestration": errors.append("plugin name must be orchestration")
        if reserved_name(name): errors.append(f"plugin name {name!r} is reserved")
        errors += changelog_errors(root, version)
    except Exception as e: errors.append(f"manifest: {e}")
    try:
        market = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        entries = [(p.get("name"), p.get("source")) for p in market.get("plugins", [])]
        if entries != [("orchestration", "./plugin")]: errors.append(f"marketplace.json must list only orchestration from ./plugin, found {entries}")
        if not market.get("name") or reserved_name(str(market["name"])): errors.append("marketplace.json: missing or reserved marketplace name")
    except Exception as e: errors.append(f"marketplace: {e}")

    shipped, turns, documented = {}, {}, {}
    agent_files = {p.stem: p for p in (root / "plugin/agents").glob("*.md")}
    if set(agent_files) != AGENTS: errors.append(f"plugin agents must be exactly {sorted(AGENTS)}")
    for key, path in [("skill", root / "plugin/skills/orchestrate/SKILL.md"), *agent_files.items()]:
        try: d = frontmatter(path)
        except Exception as e: errors.append(f"{path.name}: {e}"); continue
        errors += pair_errors(path.name, d.get("model"), d.get("effort"), ROOT_MODELS if key == "skill" else MODELS)
        errors += [f"{path.name}: control or separator character in {k}" for k, v in d.items() if UNSAFE.search(v)]
        shipped[key] = [d.get("model"), d.get("effort")]
        turns[key] = d.get("maxTurns", "session-owned")

    profiles = sorted((root / "profiles").glob("*.json"))
    if len(profiles) != PROFILE_COUNT: errors.append(f"expected {PROFILE_COUNT} profiles, found {len(profiles)}")
    for p in profiles:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if set(d) != {"skill", "agents"}: errors.append(f"{p.name}: invalid schema"); continue
            if set(d["agents"]) != AGENTS: errors.append(f"{p.name}: incomplete agents")
            errors += pair_errors(f"{p.name} skill", d["skill"].get("model"), d["skill"].get("effort"), ROOT_MODELS)
            if set(d["skill"]) != {"model", "effort"}: errors.append(f"{p.name} skill: keys must be model and effort")
            for agent, pair in d["agents"].items():
                if not isinstance(pair, list) or len(pair) != 2: errors.append(f"{p.name} {agent}: expected [model, effort]"); continue
                errors += pair_errors(f"{p.name} {agent}", *pair)
            documented[p.stem] = [[d["skill"].get("model"), d["skill"].get("effort")], *(d["agents"].get(a, [None, None]) for a in ROLE_ORDER)]
            if p.stem == MARKETPLACE_PROFILE:
                expected = {"skill": [d["skill"].get("model"), d["skill"].get("effort")], **d["agents"]}
                if shipped != expected: errors.append(f"plugin frontmatter must match {p.name}")
        except Exception as e: errors.append(f"{p.name}: {e}")
    try:
        rule = (root / RULE_DOC).read_text(encoding="utf-8")
        named = set(re.findall(r"`orchestration:(\w+)`", rule))
        if named != AGENTS: errors.append(f"default-orchestration-rule.md must name exactly the roles {sorted(AGENTS)}, found {sorted(named)}")
        if ROLE_LINE.findall(rule) != ROLE_LINE.findall((root / SKILL_DOC).read_text(encoding="utf-8")):
            errors.append(f"the five role lines (- `orchestration:<role>`: ...) of {RULE_DOC} and {SKILL_DOC} must be identical and in the same order")
    except OSError as e: errors.append(f"rule: {e}")
    return errors + doc_errors(root, documented, shipped, turns)


def changelog_errors(root: Path, version) -> list[str]:
    """CHANGELOG.md must carry the plugin.json version as its first released section, below at most an Unreleased one."""
    if not version: return ["plugin.json: missing version"]
    want = f"## {version} — "
    try: headings = [line for line in (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if line.startswith("## ")]
    except Exception as e: return [f"changelog: {e}"]
    above = headings[:next((i for i, h in enumerate(headings) if re.fullmatch(re.escape(want) + r"\d{4}-\d{2}-\d{2}", h)), len(headings))]
    if above == headings: return [f"CHANGELOG.md: no heading `{want}<YYYY-MM-DD>` for the plugin.json version"]
    if above not in ([], ["## Unreleased"]): return [f"CHANGELOG.md: only `## Unreleased` may precede `{want}<YYYY-MM-DD>`, found {above}"]
    return []


def table_rows(path: Path, first_cell: str, errors: list[str]) -> dict[str, list[str]]:
    """Map the first cell of each Markdown table row matching first_cell (a regex) to its remaining cells; a repeated
    first cell is an error, because one of the two rows would go unchecked."""
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if cells and re.fullmatch(first_cell, cells[0]):
            key = cells[0].strip("`")
            if key in rows: errors.append(f"{path.parent.name}/{path.name}: duplicate row {key}")
            rows[key] = cells[1:]
    return rows


def doc_errors(root: Path, documented: dict, shipped: dict, turns: dict) -> list[str]:
    """The topology tables in the docs are derived data: they must match the profiles and plugin frontmatter."""
    errors = []
    profile_rows = table_rows(root / "docs/models-and-plans.md", r"`[a-z0-9-]+`", errors)
    for name, pairs in documented.items():
        want = [f"{str(model).capitalize()} {effort}" for model, effort in pairs]
        if profile_rows.get(name) != want: errors.append(f"docs/models-and-plans.md: row {name} must be {want}, found {profile_rows.get(name)}")
    errors += [f"docs/models-and-plans.md: row {name} has no profile" for name in sorted(set(profile_rows) - set(documented))]
    component_rows = table_rows(root / "docs/architecture.md", "orchestrator skill|" + "|".join(ROLE_ORDER), errors)
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
