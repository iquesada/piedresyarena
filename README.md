# piedres y arena

Source of [piedresyarena.com](https://www.piedresyarena.com), a blog about bicycle trips around the world.

This is a static site built with [Astro](https://astro.build) and published on GitHub Pages. There is no backend, database or admin panel: the site is edited by changing files in this repository and pushing to `main`.

The site content is in Spanish and English. Everything else in the repository is in English.

See [ADR 0001](docs/adr/0001-migrate-to-static-site.md) for the migration from WordPress and the reasoning behind it, and [ADR 0002](docs/adr/0002-english-version.md) for the English version.

## Requirements

- Node.js 22 and npm
- Python 3, for the post-build check, the migration script and the tests in `tools/`

## Development

```sh
npm install
npm run dev       # local server at http://localhost:4321
npm run build     # build the site into dist/
npm run preview   # serve dist/ locally
npm run check     # type-check, build, then check dist/ (pages, links, redirects, images)
npm test          # tests for the Python tools in tools/ (needs the Python setup below)
```

## Project structure

```
docs/adr/                   Architecture decision records
src/content/trips.yaml      The trips: name, year, country and map colour
src/content/stages/es/      One folder per stage: index.md and its images
src/content/stages/en/      English stages: index.md only, the images stay in Spanish
src/content/pages/es/       Standalone pages ("Sobre mí")
src/content/pages/en/       English pages ("About")
src/content.config.ts       Content schemas
src/redirects.json          Old WordPress URLs -> new URLs
src/assets/                 Original logo (the site uses a vector redraw in src/components/LogoIcon.astro)
src/i18n/                   Interface text per language (es.ts, en.ts) and the englishPublic setting
src/lib/                    Content helpers and Markdown plugins (including the one that finds English images)
src/components/             Astro components (map, stage navigation, and TripPage, StagePage and AboutPage, shared by both languages)
src/layouts/                Page layout
src/pages/                  Routes (Spanish at the root, English under en/)
public/                     Static files served as-is (CNAME, favicons)
tools/                      Migration script, post-build check and their tests
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

- **Add a stage:** create a new folder with its `index.md` and images, then push. The folder's trip must match the `trip:` field, and `translationKey` must be `<trip>/<folder>`, or the build fails. The map, the trip page and the previous/next links update automatically. Stages are ordered by `date`; two stages on the same day are ordered by their folder name.
- **Add a trip:** add an entry to `src/content/trips.yaml` and use its `id` as the stages' `trip`.
- **Add images:** put them next to `index.md` and reference them with a relative path (`./photo.jpg`), each in its own paragraph. A title in quotes becomes the caption. Astro resizes and optimizes them at build time.
- **Line breaks:** a single newline inside a paragraph is a line break (as in WordPress), so don't hard-wrap paragraphs. Leave a blank line between paragraphs.
- **Catch mistakes:** the build fails if a stage is missing a required field, such as its coordinates, or points to a trip or image that doesn't exist.
- **Change interface text** (labels, buttons, date formats): edit `src/i18n/es.ts` and `src/i18n/en.ts`, not the components. A key missing from `en.ts` fails the type check.

### English content

An English stage is a folder in `src/content/stages/en/<trip>/<english-stage>/` with only an `index.md`. Its front matter holds only the text that changes with the language, plus the `translationKey` of the Spanish stage:

```md
---
title: "Georgia 2, from Zhinvali to Atabe"
description: "Into the Caucasus"
translationKey: "georgia-2019/2-de-zhinvali-a-atabe"
---

Stage text…

![Alt text](./P1110429.jpg "Optional caption")
```

- **Everything else comes from Spanish:** date, trip, coordinates and cover image. Change them once, in the Spanish stage. `seoTitle` and `seoDescription` are optional, as in Spanish.
- **Images** are written exactly as in the Spanish stage (`./P1110429.jpg`). Don't copy them: a remark plugin finds them in the Spanish folder named by the `translationKey`.
- **Folder and slug:** the trip folder must be the Spanish stage's trip. The stage folder is the English slug, used in the URL.
- **Whole trips:** the build fails if a trip has some English stages but not all of them, if a `translationKey` matches no Spanish stage, or if two English stages share one. Trips without English stages don't appear on the English site.
- **The about page** is `src/content/pages/en/about/index.md`, with `translationKey: "sobre-mi"`. Its cover photo comes from the Spanish page.
- **Trip names:** each trip in `trips.yaml` has an `en:` entry with its English `name` and `country`.
- **Style:** follow "Translation style" in [ADR 0002](docs/adr/0002-english-version.md).

### Making English public

`englishPublic` in `src/i18n/index.ts` controls whether the English version is announced. While it is `false`, English pages have `noindex` and no page has a language switcher or `hreflang` tags: the English pages are only reachable by typing their URL. Setting it to `true` adds the switcher (in the header) and `hreflang` tags to every page that exists in both languages, and removes `noindex`. From then on, a new stage needs an English version, or the post-build check fails.

## URLs

| Content | Spanish | English |
|---|---|---|
| Home | `/` | `/en/` |
| Trip | `/viajes/<trip>/` | `/en/trips/<trip>/` |
| Stage | `/viajes/<trip>/<stage>/` | `/en/trips/<trip>/<english-stage>/` |
| About | `/sobre-mi/` | `/en/about/` |

Trip slugs are the same in both languages. The 404 page is Spanish only.

The old WordPress URLs (`/listing/…`, `/listing_type/…`, `/listing_location/…`, `/a-los-pedales/`) redirect to the new ones. The mapping is in `src/redirects.json`.

## Post-build check

`npm run check` runs `tools/check_build.py` over `dist/` after the build. It checks that every expected page exists (Spanish and English), that links, redirects and images work, that every image went through Astro, and that `<html lang>` is `en` under `/en/` and `es` elsewhere. Links on English pages must stay in English, apart from the switcher and `hreflang` links.

It reads `englishPublic` and checks more in each mode:

- **Hidden** (`false`): every English page is `noindex`, and no page has a switcher or `hreflang`.
- **Public** (`true`): every Spanish stage has an English version, and the `hreflang` and switcher links point to existing pages and match in both directions.

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

> **Warning:** `--force` deletes `src/content/stages/es/`, `src/content/pages/es/`, `src/content/trips.yaml` and `src/redirects.json` before writing them again. Any edit made to those files since the migration is lost, including the English trip names (`en:` in `trips.yaml`). `src/content/stages/en/` and `src/content/pages/en/` are not touched. Without `--force`, the script refuses to run if they exist.
