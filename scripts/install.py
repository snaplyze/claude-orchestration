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
RULE_FILE = "claude-orchestration.md"
RULE_HEADER = b"<!-- Managed by claude-orchestration (scripts/install.py): rewritten on install, removed on uninstall. -->\n"
# Before 1.5 the rule was a block between these lines in the user CLAUDE.md; rule installs and removals take it out.
LEGACY_BEGIN, LEGACY_END = b"<!-- BEGIN claude-orchestration:managed -->", b"<!-- END claude-orchestration:managed -->"
JUNCTION = 0xA0000003  # IO_REPARSE_TAG_MOUNT_POINT


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def is_link(path: Path) -> bool:
    """A symlink, or a Windows junction, which is_symlink() does not report."""
    try:
        return path.is_symlink() or getattr(os.lstat(path), "st_reparse_tag", 0) == JUNCTION
    except OSError:
        return False


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


def put(path: Path, data: bytes | None) -> None:
    """Write data atomically, or remove the file when data is None."""
    if data is None:
        path.unlink(missing_ok=True)
    else:
        atomic_write(path, data)


def missing_dirs(paths) -> list[Path]:
    """The given directories and their ancestors that do not exist yet, deepest first."""
    missing = set()
    for path in paths:
        while not path.exists() and path not in missing:
            missing.add(path)
            path = path.parent
    return sorted(missing, key=lambda p: len(p.parts), reverse=True)


def remove_empty(dirs) -> None:
    for path in dirs:
        try:
            path.rmdir()
        except OSError:
            pass


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
    """Return the managed plugin path, refusing links anywhere between the target and it."""
    path = target
    for part in (".claude", "plugins", "orchestration"):
        path = path / part
        if is_link(path):
            raise ValueError(f"refusing symlink in plugin destination: {path}")
    return path


def transaction(writes: dict[Path, bytes | None], dest: Path | None = None, profile: dict | None = None) -> None:
    """Apply file writes (None removes a file) and, with dest, stage the plugin (with profile) beside dest and swap it in.

    On failure every file gets its previous bytes back, directories created here are removed again, and the previous
    plugin directory is restored.
    """
    before = {path: path.read_bytes() if path.exists() else None for path in writes}
    created = missing_dirs([*(path.parent for path in writes), *([dest.parent] if dest else [])])
    work = stage = previous = None
    done = False
    try:
        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            work = Path(tempfile.mkdtemp(prefix=".orchestration-", dir=dest.parent))
            stage, previous = work / "stage", work / "previous"
            shutil.copytree(PLUGIN, stage)
            if profile:
                materialize_profile(stage, profile)
        for path, data in writes.items():
            if data != before[path]:
                put(path, data)
        if dest:
            if dest.exists():
                os.replace(dest, previous)
            os.replace(stage, dest)
        done = True
    except BaseException:
        for path, data in before.items():
            if (path.read_bytes() if path.exists() else None) != data:
                put(path, data)
        if previous and previous.exists():
            if dest.exists():
                shutil.rmtree(dest)
            os.replace(previous, dest)
        raise
    finally:
        if previous and previous.exists() and not done:  # the restore itself failed: keep the only copy of the old plugin
            shutil.rmtree(stage, ignore_errors=True)
            print(f"Previous plugin kept at {previous}; move it back to {dest}", file=sys.stderr)
        else:
            if work:
                shutil.rmtree(work, ignore_errors=True)
            if not done:
                remove_empty(created)


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
    transaction({settings_path: dump_settings(settings)} if profile else {}, dest, profile)
    return dest


def uninstall(target: Path) -> None:
    target = target.resolve()
    dest = plugin_destination(target)
    settings_path = target / ".claude/settings.json"
    settings = load_json(settings_path)
    if dest.exists():
        shutil.rmtree(dest)
    if release_settings(settings):
        atomic_write(settings_path, dump_settings(settings))


def without_legacy_block(data: bytes, path: Path) -> bytes | None:
    """CLAUDE.md bytes without the pre-1.5 managed block and the blank line set before it; None when there is no block."""
    lines = data.splitlines(keepends=True)
    begins = [i for i, line in enumerate(lines) if line.strip() == LEGACY_BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == LEGACY_END]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0] > ends[0]:
        raise ValueError(f"{path}: malformed claude-orchestration:managed markers; remove the old block by hand, then rerun")
    start, end = begins[0], ends[0] + 1
    if start and not lines[start - 1].strip():
        start -= 1
    elif end < len(lines) and not lines[end].strip():
        end += 1
    return b"".join(lines[:start] + lines[end:])


def rule_path(config_dir: Path) -> Path:
    return config_dir / "rules" / RULE_FILE


def rule_writes(config_dir: Path, enable: bool) -> dict[Path, bytes | None]:
    """File changes that install (enable) or remove the default rule, taking any pre-1.5 block out of CLAUDE.md."""
    rule, legacy = rule_path(config_dir), config_dir / "CLAUDE.md"
    if is_link(rule):
        raise ValueError(f"refusing symlink: {rule}")
    if rule.exists() and not rule.read_bytes().startswith(RULE_HEADER):
        raise ValueError(f"{rule} was not written by this installer; move it away, then rerun")
    writes = {rule: RULE_HEADER + RULE_TEMPLATE.read_bytes() if enable else None}
    stripped = without_legacy_block(legacy.read_bytes(), legacy) if legacy.exists() else None
    if stripped is not None:
        if is_link(legacy):
            raise ValueError(f"{legacy} is a symlink holding the old managed block; remove the block by hand, then rerun")
        writes[legacy] = stripped if stripped.strip() else None
    return writes


def marketplace_dir(root: Path) -> Path:
    """Resolve the local marketplace directory: absent, empty, or one this installer built; never a link."""
    root = root.expanduser()
    if is_link(root):
        raise ValueError(f"refusing symlink as marketplace directory: {root}")
    root = root.resolve()
    if root == ROOT or ROOT in root.parents:
        raise ValueError("marketplace directory must be outside the distribution checkout")
    for path in (root / ".claude-plugin", root / ".claude-plugin/marketplace.json", root / "plugin"):
        if is_link(path):
            raise ValueError(f"refusing symlink in marketplace directory: {path}")
    if root.exists() and not (root.is_dir() and (not any(root.iterdir()) or built_here(root))):
        raise ValueError(f"{root} is neither empty nor an {LOCAL_MARKETPLACE} marketplace; pass another --marketplace-dir")
    return root


def built_here(root: Path) -> bool:
    try:
        return json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")).get("name") == LOCAL_MARKETPLACE
    except (OSError, ValueError, AttributeError):
        return False


def install_user(root: Path, profile_name: str, config_dir: Path | None = None) -> Path:
    """Build a local marketplace whose plugin carries the profile; with config_dir, also install the default rule there."""
    root = marketplace_dir(root)
    profile = profile_data(profile_name)
    manifest = {"name": LOCAL_MARKETPLACE, "description": f"Local Claude Orchestration build ({profile_name} profile)", "owner": {"name": "local"}, "plugins": [{"name": "orchestration", "source": "./plugin",
                "description": f"Claude Orchestration with the {profile_name} profile"}]}
    writes = {root / ".claude-plugin/marketplace.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8")}
    if config_dir:
        writes |= rule_writes(config_dir, True)
    transaction(writes, root / "plugin", profile)
    return root / "plugin"


def uninstall_user(root: Path, config_dir: Path | None = None) -> list[Path]:
    """Remove what install_user built (the directory too once empty) and, with config_dir, the default rule.

    Returns the entries left in the marketplace directory because this installer did not create them.
    """
    root = marketplace_dir(root)
    if config_dir:
        transaction(rule_writes(config_dir, False))
        remove_empty([rule_path(config_dir).parent])
    if not root.exists():
        return []
    if (root / "plugin").exists():
        shutil.rmtree(root / "plugin")
    (root / ".claude-plugin/marketplace.json").unlink(missing_ok=True)
    for work in root.glob(".orchestration-*"):
        shutil.rmtree(work, ignore_errors=True)
    remove_empty([root / ".claude-plugin", root])
    return sorted(root.iterdir()) if root.exists() else []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path, nargs="?", help="project directory (omit with --user)")
    parser.add_argument("--profile")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--user", action="store_true", help="build a local marketplace for a user-scope install instead of a project install")
    parser.add_argument("--marketplace-dir", type=Path, default=Path("~/.claude-orchestration"), help="local marketplace directory for --user")
    parser.add_argument("--default-rule", action="store_true", help=f"with --user: also install (or remove) the default-orchestration rule as rules/{RULE_FILE} in the Claude config directory")
    args = parser.parse_args()
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser() if args.default_rule else None
    if args.user:
        if args.target:
            parser.error("--user takes no target directory")
        if args.uninstall:
            left = uninstall_user(args.marketplace_dir, config_dir)
            print(f"Removed the local marketplace build" + (f" and {rule_path(config_dir)}" if config_dir else ""))
            if left:
                print(f"Kept {args.marketplace_dir.expanduser()}: it also holds {', '.join(p.name for p in left)}")
            print(f"Also run: claude plugin uninstall orchestration@{LOCAL_MARKETPLACE} && claude plugin marketplace remove {LOCAL_MARKETPLACE}")
            return
        if not args.profile:
            parser.error("--user needs --profile")
        dest = install_user(args.marketplace_dir, args.profile, config_dir)
        print(f"Built local marketplace {LOCAL_MARKETPLACE} with plugin at {dest}" + (f"; default rule in {rule_path(config_dir)}" if config_dir else ""))
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
