# Starting armies

`generate_oob.py` writes `history/units/<TAG>_1945.txt` and `<TAG>_1950.txt` and keeps
each country history's `oob` line, starting techs and `1950.1.1 = { set_oob = ... }` block in sync.

1. Edit `countries.csv` (sizes per bookmark, role, family, experience).
2. Run `python tools/oob/generate_oob.py` (add `--dry-run` to preview).
3. `--init` rebuilds `countries.csv` from current history and **overwrites your edits**.

Roles: `superpower`, `soviet_subject` (local army + SOV garrison in the capital),
`us_occupation_zone` (US garrison only), `us_subject` (local army + 1 US garrison),
`us_state_of_union` (national guard), `independent`.

Per game version: `templates/<version>/american.txt`, `soviet.txt` and `techs/<version>.txt`.
Set `GAME_VERSION` at the top of the script when moving to a new version.
