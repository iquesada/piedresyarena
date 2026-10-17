# piedres y arena

Source of [piedresyarena.com](https://www.piedresyarena.com), a blog about bicycle trips around the world.

This is a static site built with [Astro](https://astro.build) and published on GitHub Pages. There is no backend, database or admin panel: the site is edited by changing files in this repository and pushing to `main`.

The site content is in Spanish. Everything else in the repository is in English. The structure is ready for a future English version of the site.

See [ADR 0001](docs/adr/0001-migrate-to-static-site.md) for the migration from WordPress and the reasoning behind it.

## Requirements

- Node.js 22 and npm
- Python 3, only for the migration script and its tests

## Development

```sh
npm install
npm run dev       # local server at http://localhost:4321
npm run build     # build the site into dist/
npm run preview   # serve dist/ locally
npm run check     # type-check, build, then check dist/ (pages, links, redirects, images)
npm test          # unit tests for tools/migrate.py (needs the Python setup below)
```

## Project structure

```
docs/adr/                   Architecture decision records
src/content/trips.yaml      The trips: name, year, country and map colour
src/content/stages/es/      One folder per stage: index.md and its images
src/content/pages/es/       Standalone pages ("Sobre mí")
src/content.config.ts       Content schemas
src/redirects.json          Old WordPress URLs -> new URLs
src/assets/                 Original logo (the site uses a vector redraw in src/components/LogoIcon.astro)
src/i18n/                   Interface text per language (es.ts)
src/lib/                    Content helpers and Markdown plugins
src/components/             Astro components (map, logo icon, stage navigation)
src/layouts/                Page layout
src/pages/                  Routes
public/                     Static files served as-is (CNAME, favicons)
tools/                      Migration script, its tests and the post-build check
.github/workflows/          Build and deploy to GitHub Pages
```

## Editing content

Each stage is a folder in `src/content/stages/es/<trip>/<stage>/`, with an `index.md` and the stage's images next to it. The metadata goes in the front matter and the text goes below it:

```md
---
title: "Georgia 2, de Zhinvali a Atabe"
date: 2019-08-14
trip: "georgia-2019"
lat: 42.12370237322097
lng: 44.77512403305043
address: "Zhinvali"
description: "Adentrándome en el Cáucaso"
image: "./atabe.jpg"
translationKey: "georgia-2019/2-de-zhinvali-a-atabe"
---

Stage text…

![Alt text](./photo.jpg "Optional caption")
```

- **Add a stage:** create a new folder with its `index.md` and images, then push. The folder's trip must match the `trip:` field, or the build fails. The map, the trip page and the previous/next links update automatically. Stages are ordered by `date`; two stages on the same day are ordered by their folder name.
- **Add a trip:** add an entry to `src/content/trips.yaml` and use its `id` as the stages' `trip`.
- **Add images:** put them next to `index.md` and reference them with a relative path (`./photo.jpg`), each in its own paragraph. A title in quotes becomes the caption. Astro resizes and optimizes them at build time.
- **Line breaks:** a single newline inside a paragraph is a line break (as in WordPress), so don't hard-wrap paragraphs. Leave a blank line between paragraphs.
- **Catch mistakes:** the build fails if a stage is missing a required field, such as its coordinates, or points to a trip or image that doesn't exist.
- **Change interface text** (labels, buttons, date formats): edit `src/i18n/es.ts`, not the components.

## URLs

| Content | URL |
|---|---|
| Home | `/` |
| Trip | `/viajes/<trip>/` |
| Stage | `/viajes/<trip>/<stage>/` |
| About | `/sobre-mi/` |

The old WordPress URLs (`/listing/…`, `/listing_type/…`, `/listing_location/…`, `/a-los-pedales/`) redirect to the new ones. The mapping is in `src/redirects.json`.

A future English version would live under `/en/`. The Spanish URLs will not change.

## Deployment

Every push to `main` runs a GitHub Actions workflow (`.github/workflows/deploy.yml`) that builds the site and publishes it to GitHub Pages. There is no preview deployment: check changes locally with `npm run build` and `npm run preview` (or `npm run check`) before pushing.

### Going live

One-time steps after the first deployment:

1. In the repository settings, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
2. Set the custom domain to `www.piedresyarena.com` (it matches `public/CNAME`).
3. At the DNS provider of `piedresyarena.com`:
   - apex `A` records: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`;
   - apex `AAAA` records: `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`;
   - a `CNAME` record for `www` pointing to `iquesada.github.io`;
   - keep any existing `MX` (email) records.
4. Once the certificate is issued, enable **Enforce HTTPS**.

## Migration from WordPress

`old/` holds the WordPress database dump and the uploads backup. It is not committed to the repository.

`tools/migrate.py` reads the dump and generates:
- `src/content/trips.yaml`;
- the stage folders and their images (downscaled to 1600 px, without EXIF data);
- the about page;
- `src/redirects.json`.

Python setup (a virtual environment is recommended):

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r tools/requirements.txt
```

The migration has already been run, and its output is committed. Re-run it only to regenerate everything from the dump:

```sh
python3 tools/migrate.py --force
```

> **Warning:** `--force` deletes `src/content/stages/es/`, `src/content/pages/es/`, `src/content/trips.yaml` and `src/redirects.json` before writing them again. Any edit made to those files since the migration is lost. Without `--force`, the script refuses to run if they exist.
