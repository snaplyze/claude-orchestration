#!/usr/bin/env python3
"""Safely install/update Claude Orchestration and materialize a selected model/effort profile."""
from __future__ import annotations
import argparse, json, os, shutil, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
MARKER = "claude-orchestration"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".claude-orchestration-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def profile_data(name: str) -> dict:
    path = ROOT / "profiles" / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"unknown profile: {name}")
    data = load_json(path)
    if not all(k in data for k in ("settings", "skill", "agents")):
        raise ValueError(f"invalid profile schema: {name}")
    return data


def patch_frontmatter(path: Path, values: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError(f"missing YAML frontmatter: {path}")
    lines = parts[1].strip("\n").splitlines()
    output, seen = [], set()
    for line in lines:
        key = line.split(":", 1)[0].strip() if ":" in line else ""
        if key in values:
            output.append(f"{key}: {values[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in seen:
            output.append(f"{key}: {value}")
    path.write_text("---\n" + "\n".join(output) + "\n---" + parts[2], encoding="utf-8")


def materialize_profile(stage: Path, profile: dict) -> None:
    patch_frontmatter(stage / "skills/orchestrate/SKILL.md", profile["skill"])
    for name, config in profile["agents"].items():
        if not isinstance(config, list) or len(config) != 2:
            raise ValueError(f"invalid agent profile: {name}")
        patch_frontmatter(stage / "agents" / f"{name}.md", {"model": config[0], "effort": config[1]})


def apply_settings(settings: dict, name: str, profile: dict) -> None:
    old = settings.get(MARKER)
    if isinstance(old, dict):
        for key in old.get("managedKeys", []):
            settings.pop(key, None)
    fragment = profile["settings"]
    settings.update(fragment)
    settings[MARKER] = {"profile": name, "managedKeys": sorted(fragment)}


def install(target: Path, profile_name: str | None = None) -> Path:
    target = target.resolve()
    if not target.is_dir():
        raise ValueError("target must be an existing directory")
    if target == ROOT.resolve() or ROOT.resolve() in target.parents:
        raise ValueError("target must be outside the distribution checkout")

    dest = target / ".claude/plugins/orchestration"
    if dest.is_symlink():
        raise ValueError("refusing to replace symlink plugin destination")
    settings_path = target / ".claude/settings.json"
    old_settings = settings_path.read_bytes() if settings_path.exists() else None
    backup_root = Path(tempfile.mkdtemp(prefix="claude-orchestration-backup-"))
    stage_root = Path(tempfile.mkdtemp(prefix="claude-orchestration-stage-"))
    backup, stage = backup_root / "orchestration", stage_root / "orchestration"

    try:
        if dest.exists():
            if not dest.is_dir():
                raise ValueError("plugin destination is not a directory")
            shutil.copytree(dest, backup)
        shutil.copytree(PLUGIN, stage)
        if profile_name:
            profile = profile_data(profile_name)
            materialize_profile(stage, profile)
            settings = load_json(settings_path)
            apply_settings(settings, profile_name, profile)
            atomic_write(settings_path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(stage, dest)
    except Exception:
        if dest.exists():
            shutil.rmtree(dest)
        if backup.exists():
            shutil.copytree(backup, dest)
        if old_settings is None:
            settings_path.unlink(missing_ok=True)
        else:
            atomic_write(settings_path, old_settings.decode("utf-8"))
        raise
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
        shutil.rmtree(backup_root, ignore_errors=True)
    return dest


def uninstall(target: Path) -> None:
    target = target.resolve()
    dest = target / ".claude/plugins/orchestration"
    if dest.is_symlink():
        raise ValueError("refusing to remove symlink plugin destination")
    if dest.exists():
        shutil.rmtree(dest)
    settings_path = target / ".claude/settings.json"
    if settings_path.exists():
        settings = load_json(settings_path)
        marker = settings.pop(MARKER, None)
        if isinstance(marker, dict):
            for key in marker.get("managedKeys", []):
                settings.pop(key, None)
        atomic_write(settings_path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


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
