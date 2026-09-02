<!--
Thanks for contributing! Keep this short — describe the change and confirm the
checks. Delete any checklist line that doesn't apply to your PR.
See CLAUDE.md for the project's conventions and how to reproduce each CI gate.
-->

## Problem

<!-- What is broken, missing or needed — the state of things without this PR.
     Link any related issue (e.g. Closes #123). -->

## Solution

<!-- What this PR does about it, and anything a reviewer would be surprised by. -->

## How it was tested

<!-- Commands run, manual steps, screenshots for UI changes (before/after). -->

## Checklist

- [ ] Title and body re-read against `git diff origin/master...HEAD`: they describe the branch as it now stands, not a first attempt, and the three sections are under 200 words
- [ ] `python -m unittest discover` passes, with tests added/updated for the change
- [ ] `python -m compileall .` and `pylint app.py config.py i18n.py routes services scripts tests` are clean
- [ ] Security still clean: `pip-audit` and `bandit -r . -x ./tests` (any accepted finding carries an inline `# nosec` with justification)
- [ ] Frontend/shell touched → `npx --yes eslint@9 static/*.js` and `shellcheck scripts/*.sh` pass
- [ ] New/changed UI strings exist in **both** `fr` and `en` (`i18n.py` and, for the app, `res/values*/strings.xml`)
- [ ] Documentation kept in lockstep if user-facing behaviour changed — each edited page in **both** languages (`README.md` / `README.fr.md`, `docs/*.md` / `docs/*.fr.md`) — and any `.claude/skills/` page describing what this PR changed updated with it
- [ ] No authentication / public-exposure feature added (the app is LAN-only by design — see CLAUDE.md)
