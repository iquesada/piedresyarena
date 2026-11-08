---
name: garmin-stages
description: Fill a trip's stages from the rides recorded in Garmin Connect - stage place (start of the ride), distance, elevation gain, villages on the way and a simplified track.json for the map. Use when the user asks to get, download or update stages, tracks, km or desnivel from Garmin.
---

# Garmin stages

Garmin has no API for personal accounts. `tools/garmin_stages.py` uses
[python-garminconnect](https://github.com/cyberjunky/python-garminconnect), which logs in as the
Garmin Connect app does. It is unofficial: if Garmin changes its login, update the pinned version
in `tools/requirements-garmin.txt` (check the project's releases first).

Run everything from the repo root with the project's `.venv`.

## 1. Setup and login (the user, once)

```sh
.venv/bin/pip install -r tools/requirements-garmin.txt
.venv/bin/python tools/garmin_stages.py login
```

`login` asks for email, password and, if the account has it, the MFA code, so the **user runs it in
their own terminal**: never ask for or handle the password. Tokens go to `~/.garminconnect`
(outside the repo) and refresh themselves; login again only when a command says so.

## 2. Look before writing

```sh
.venv/bin/python tools/garmin_stages.py fetch <trip>
```

`<trip>` is the folder under `src/content/stages/es/`. For each stage it finds the cycling
activities started that day (local time), and prints activity ids, km, m+, start and end points and
the villages on the way (OpenStreetMap Nominatim, one request a second, cached). GPX and Nominatim
answers are cached in `.cache/garmin/` (git-ignored).

Show the user the report. Check:
- stages with no ride: older trips (before Ardennes 2022) are probably not in Garmin;
- days with two rides (merged) or a ride that crosses midnight;
- start points far from the stage's current `address`.

## 3. Write, when the user agrees

```sh
.venv/bin/python tools/garmin_stages.py fetch <trip> --write [--trim-start M] [--trim-end M]
```

Per stage, this:
- sets `lat`/`lng` to the start of the ride (the stage place, see GLOSSARY.md), `distance` (km) and
  `elevation` (m+) in the front matter;
- puts `<!-- Pueblos en ruta (Garmin): … -->` at the top of the body, for the user to use in the
  text (replaced on each run);
- writes `track.json` next to `index.md`: the ride as `[[lat, lng], …]`, simplified to ~8 m.

`--trim-start`/`--trim-end` leave the first/last metres out of `track.json` (not out of the
figures). Ask the user whether to use them whenever a ride starts or ends at home, around 500 m.

`address` is not touched: if the start moved to another place, tell the user.

## Raw API calls (the "curl")

```sh
.venv/bin/python tools/garmin_stages.py get '/activitylist-service/activities/search/activities?startDate=2023-11-11&endDate=2023-11-15'
.venv/bin/python tools/garmin_stages.py get '/activity-service/activity/<activityId>'
```

Paths are relative to `https://connectapi.garmin.com`. GPX export is
`/download-service/export/gpx/activity/<activityId>` (binary: the script downloads it, `get` does
not). A plain `curl` with the bearer token is not used on purpose: Garmin's Cloudflare front blocks
clients that do not look like the app, and the library handles that and the token refresh.
