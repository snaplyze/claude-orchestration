## Summary

## Scope

## Verification

- [ ] Diff is limited to the intended scope; docs match the implementation.
- [ ] `python -m unittest discover -v`
- [ ] `python scripts/doctor.py`
- [ ] `sh -n setup.sh`
- [ ] `claude plugin validate --strict ./plugin` (when Claude Code is available)
- [ ] `python scripts/runtime_smoke.py --skill --tool-surface` when the plugin, profiles, or installer change (or the `Runtime smoke` check)
- [ ] `CHANGELOG.md` updated under `Unreleased` for user-visible changes
