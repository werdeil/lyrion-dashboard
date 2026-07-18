<!--
Thanks for contributing! Keep this short — describe the change and confirm the
checks. Delete any checklist line that doesn't apply to your PR.
See CLAUDE.md for the project's conventions and how to reproduce each CI gate.
-->

## What & why

<!-- What does this change and why? Link any related issue (e.g. Closes #123). -->

## How it was tested

<!-- Commands run, manual steps, screenshots for UI changes (before/after). -->

## Checklist

- [ ] `python -m unittest discover` passes, with tests added/updated for the change
- [ ] `python -m compileall .` and `pylint app.py config.py i18n.py routes services scripts tests` are clean
- [ ] Security still clean: `pip-audit` and `bandit -r . -x ./tests` (any accepted finding carries an inline `# nosec` with justification)
- [ ] Frontend/shell touched → `npx --yes eslint@9 static/*.js` and `shellcheck scripts/*.sh` pass
- [ ] New/changed UI strings exist in **both** `fr` and `en` (`i18n.py` and, for the app, `res/values*/strings.xml`)
- [ ] `README.md` and `README.fr.md` kept in lockstep if user-facing behaviour changed
- [ ] No authentication / public-exposure feature added (the app is LAN-only by design — see CLAUDE.md)
