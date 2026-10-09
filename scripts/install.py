#!/usr/bin/env python3
"""Safely install/update Claude Orchestration and materialize a selected model/effort profile."""
from __future__ import annotations
import argparse, json, os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
PROFILES = ROOT / "profiles"
MARKER = "claude-orchestration"


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
    old_settings = settings_path.read_bytes() if settings_path.exists() else None
    settings = load_json(settings_path)
    if profile_name is None and isinstance(settings.get(MARKER), dict):
        profile_name = settings[MARKER].get("profile")
    profile = profile_data(profile_name) if profile_name else None

    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".orchestration-", dir=dest.parent))
    stage, previous = work / "stage", work / "previous"
    try:
        shutil.copytree(PLUGIN, stage)
        if profile:
            materialize_profile(stage, profile)
            apply_settings(settings, profile_name, profile)
            atomic_write(settings_path, dump_settings(settings))
        if dest.exists():
            os.replace(dest, previous)
        os.replace(stage, dest)
    except BaseException:
        current = settings_path.read_bytes() if settings_path.exists() else None
        if current != old_settings:
            if old_settings is None:
                settings_path.unlink()
            else:
                atomic_write(settings_path, old_settings)
        if previous.exists():
            if dest.exists():
                shutil.rmtree(dest)
            os.replace(previous, dest)
        raise
    finally:
        if previous.exists():
            shutil.rmtree(stage, ignore_errors=True)
            print(f"Previous plugin kept at {previous}; move it back to {dest}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    if args.uninstall:
        uninstall(args.target)
        print("Uninstalled orchestration plugin")
        return
    dest = install(args.target, args.profile)
    print(f"Installed plugin at {dest}")
    print(f"Launch: claude --plugin-dir {dest}")


if __name__ == "__main__":
    main()
