#!/usr/bin/env python3
"""Safely install/update Claude Orchestration and materialize a selected model/effort profile."""
from __future__ import annotations
import argparse, json, os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
PROFILES = ROOT / "profiles"
MARKER = "claude-orchestration"
LOCAL_MARKETPLACE = "orchestration-local"
RULE_TEMPLATE = Path(__file__).resolve().parent / "default-orchestration-rule.md"
RULE_BEGIN, RULE_END = "<!-- BEGIN claude-orchestration:managed -->", "<!-- END claude-orchestration:managed -->"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".claude-orchestration-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def dump_settings(settings: dict) -> bytes:
    return (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def profile_data(name: str) -> dict:
    if name not in {p.stem for p in PROFILES.glob("*.json")}:
        raise ValueError(f"unknown profile: {name}; pass --profile with a name from {PROFILES}")
    data = load_json(PROFILES / f"{name}.json")
    if not all(k in data for k in ("settings", "skill", "agents")):
        raise ValueError(f"invalid profile schema: {name}")
    return data


def split_frontmatter(text: str, path: Path) -> tuple[list[str], str]:
    """Return the YAML frontmatter lines and the body that follows the closing delimiter."""
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError(f"missing YAML frontmatter: {path}")
    return parts[1].strip("\n").splitlines(), parts[2]


def frontmatter(path: Path) -> dict[str, str]:
    lines, _ = split_frontmatter(path.read_text(encoding="utf-8"), path)
    return {k.strip(): v.strip() for k, v in (line.split(":", 1) for line in lines if ":" in line)}


def patch_frontmatter(path: Path, values: dict[str, str]) -> None:
    lines, body = split_frontmatter(path.read_text(encoding="utf-8"), path)
    output, seen = [], set()
    for line in lines:
        key = line.split(":", 1)[0].strip() if ":" in line else ""
        if key in values:
            output.append(f"{key}: {values[key]}")
            seen.add(key)
        else:
            output.append(line)
    output += [f"{key}: {value}" for key, value in values.items() if key not in seen]
    path.write_text("---\n" + "\n".join(output) + "\n---" + body, encoding="utf-8")


def materialize_profile(stage: Path, profile: dict) -> None:
    patch_frontmatter(stage / "skills/orchestrate/SKILL.md", profile["skill"])
    for name, config in profile["agents"].items():
        if not isinstance(config, list) or len(config) != 2:
            raise ValueError(f"invalid agent profile: {name}")
        patch_frontmatter(stage / "agents" / f"{name}.md", {"model": config[0], "effort": config[1]})


def release_settings(settings: dict) -> bool:
    """Remove the marker and give managed keys back their pre-install values. Return True if a marker was present."""
    marker = settings.pop(MARKER, None)
    if not isinstance(marker, dict):
        return marker is not None
    previous = marker.get("previous", {})
    for key in marker.get("managedKeys", []):
        if key in previous:
            settings[key] = previous[key]
        else:
            settings.pop(key, None)
    return True


def apply_settings(settings: dict, name: str, profile: dict) -> None:
    release_settings(settings)
    fragment = profile["settings"]
    previous = {key: settings[key] for key in fragment if key in settings}
    settings.update(fragment)
    settings[MARKER] = {"profile": name, "managedKeys": sorted(fragment), "previous": previous}


def plugin_destination(target: Path) -> Path:
    """Return the managed plugin path, refusing symlinks anywhere between the target and it."""
    path = target
    for part in (".claude", "plugins", "orchestration"):
        path = path / part
        if path.is_symlink():
            raise ValueError(f"refusing symlink in plugin destination: {path}")
    return path


def swap_in(dest: Path, profile: dict | None, path: Path | None = None, data: bytes | None = None) -> Path:
    """Stage the plugin (with profile) beside dest, optionally write one file, and swap the plugin in.

    On failure the file's previous bytes and the previous plugin directory are restored.
    """
    old = path.read_bytes() if path and path.exists() else None
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".orchestration-", dir=dest.parent))
    stage, previous = work / "stage", work / "previous"
    swapped = False
    try:
        shutil.copytree(PLUGIN, stage)
        if profile:
            materialize_profile(stage, profile)
        if path and data is not None and data != old:
            atomic_write(path, data)
        if dest.exists():
            os.replace(dest, previous)
        os.replace(stage, dest)
        swapped = True
    except BaseException:
        if path:
            current = path.read_bytes() if path.exists() else None
            if current != old:
                if old is None:
                    path.unlink()
                else:
                    atomic_write(path, old)
        if previous.exists():
            if dest.exists():
                shutil.rmtree(dest)
            os.replace(previous, dest)
        raise
    finally:
        if previous.exists() and not swapped:  # the restore itself failed: keep the only copy of the old plugin
            shutil.rmtree(stage, ignore_errors=True)
            print(f"Previous plugin kept at {previous}; move it back to {dest}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)
    return dest


def install(target: Path, profile_name: str | None = None) -> Path:
    target = target.resolve()
    if not target.is_dir():
        raise ValueError("target must be an existing directory")
    if target == ROOT or ROOT in target.parents:
        raise ValueError("target must be outside the distribution checkout")
    dest = plugin_destination(target)
    if dest.exists() and not dest.is_dir():
        raise ValueError("plugin destination is not a directory")

    settings_path = target / ".claude/settings.json"
    settings = load_json(settings_path)
    if profile_name is None and isinstance(settings.get(MARKER), dict):
        profile_name = settings[MARKER].get("profile")
    profile = profile_data(profile_name) if profile_name else None
    if profile:
        apply_settings(settings, profile_name, profile)
    return swap_in(dest, profile, settings_path, dump_settings(settings) if profile else None)


def uninstall(target: Path) -> None:
    target = target.resolve()
    dest = plugin_destination(target)
    settings_path = target / ".claude/settings.json"
    settings = load_json(settings_path)
    if dest.exists():
        shutil.rmtree(dest)
    if release_settings(settings):
        atomic_write(settings_path, dump_settings(settings))


def with_rule(text: str, block: str | None) -> str:
    """Replace, append, or (block=None) remove the managed default-orchestration block in a CLAUDE.md text."""
    start, end = text.find(RULE_BEGIN), text.find(RULE_END)
    if start != -1 and end != -1:
        text = (text[:start].rstrip("\n") + "\n\n" + text[end + len(RULE_END):].lstrip("\n")).strip("\n")
    if block:
        text = (text + "\n\n" if text else "") + f"{RULE_BEGIN}\n{block.strip()}\n{RULE_END}"
    return text + "\n" if text else ""


def user_paths(root: Path) -> tuple[Path, Path]:
    root = root.expanduser().resolve()
    for path in (root, root / ".claude-plugin", root / "plugin"):
        if path.is_symlink():
            raise ValueError(f"refusing symlink in marketplace directory: {path}")
    if root == ROOT or ROOT in root.parents:
        raise ValueError("marketplace directory must be outside the distribution checkout")
    return root, root / "plugin"


def install_user(root: Path, profile_name: str, rule_path: Path | None = None) -> Path:
    """Build a local marketplace whose plugin carries the profile, for a user-scope install with `claude plugin`."""
    root, dest = user_paths(root)
    profile = profile_data(profile_name)
    manifest = {"name": LOCAL_MARKETPLACE, "description": f"Local Claude Orchestration build ({profile_name} profile)", "owner": {"name": "local"}, "plugins": [{"name": "orchestration", "source": "./plugin",
                "description": f"Claude Orchestration with the {profile_name} profile"}]}
    atomic_write(root / ".claude-plugin/marketplace.json", (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    data = None
    if rule_path:
        current = rule_path.read_text(encoding="utf-8") if rule_path.exists() else ""
        data = with_rule(current, RULE_TEMPLATE.read_text(encoding="utf-8")).encode("utf-8")
    return swap_in(dest, profile, rule_path, data)


def uninstall_user(root: Path, rule_path: Path | None = None) -> None:
    root, _ = user_paths(root)
    if rule_path and rule_path.exists():
        text = with_rule(rule_path.read_text(encoding="utf-8"), None)
        if text:
            atomic_write(rule_path, text.encode("utf-8"))
        else:
            rule_path.unlink()
    if root.exists():
        shutil.rmtree(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path, nargs="?", help="project directory (omit with --user)")
    parser.add_argument("--profile")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--user", action="store_true", help="build a local marketplace for a user-scope install instead of a project install")
    parser.add_argument("--marketplace-dir", type=Path, default=Path("~/.claude-orchestration"), help="local marketplace directory for --user")
    parser.add_argument("--default-rule", action="store_true", help="with --user: add (or remove) the managed default-orchestration block in the user CLAUDE.md")
    args = parser.parse_args()
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser()
    rule_path = config_dir / "CLAUDE.md" if args.default_rule else None
    if args.user:
        if args.target:
            parser.error("--user takes no target directory")
        if args.uninstall:
            uninstall_user(args.marketplace_dir, rule_path)
            print(f"Removed {args.marketplace_dir}" + (f" and the managed block in {rule_path}" if rule_path else ""))
            print(f"Also run: claude plugin uninstall orchestration@{LOCAL_MARKETPLACE} && claude plugin marketplace remove {LOCAL_MARKETPLACE}")
            return
        if not args.profile:
            parser.error("--user needs --profile")
        dest = install_user(args.marketplace_dir, args.profile, rule_path)
        print(f"Built local marketplace {LOCAL_MARKETPLACE} with plugin at {dest}" + (f"; default rule in {rule_path}" if rule_path else ""))
        print(f"First time: claude plugin marketplace add {dest.parent} && claude plugin install orchestration@{LOCAL_MARKETPLACE} --scope user")
        print("Later runs update the plugin in place; restart Claude Code sessions to pick it up.")
        return
    if args.target is None or args.default_rule:
        parser.error("a project install needs a target directory; --default-rule needs --user")
    if args.uninstall:
        uninstall(args.target)
        print("Uninstalled orchestration plugin")
        return
    dest = install(args.target, args.profile)
    print(f"Installed plugin at {dest}")
    print(f"Launch: claude --plugin-dir {dest}")


if __name__ == "__main__":
    main()
