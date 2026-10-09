# Contributing

Keep changes bounded and evidence-driven: fix the cause, remove what the change replaces, and update the docs when behavior changes. Do not add secrets, raw private session logs, generated caches, or user-specific settings.

## Checks

```bash
python -m unittest discover -v
python scripts/doctor.py
sh -n setup.sh
claude plugin validate --strict ./plugin                    # when Claude Code is installed
python scripts/runtime_smoke.py --skill --tool-surface      # plugin, profile, or installer changes
```

`runtime_smoke.py` makes real model calls under your Claude login. In CI the `Runtime smoke` workflow runs it only for runs the repository owner authored and started, because it uses the owner's subscription token.

## Pull requests

Open an issue first for anything beyond a small fix, then a PR against `main` using the template. CI must pass on Linux, macOS, and Windows. Note user-visible changes under `Unreleased` in `CHANGELOG.md`.

## Releases

1. Bump `version` in `plugin/.claude-plugin/plugin.json` and rename `Unreleased` in `CHANGELOG.md` to the version and date.
2. Merge the release PR after CI and the runtime smoke pass.
3. Tag the merge commit `vX.Y.Z` and publish a GitHub Release with the changelog section.
