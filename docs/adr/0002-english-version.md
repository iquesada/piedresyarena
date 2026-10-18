# ADR 0002: Add an English version of the site

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

The site is live at www.piedresyarena.com, in Spanish only. ADR 0001 prepared it for an English version without building one:

- Astro i18n is configured with `defaultLocale: 'es'`, `locales: ['es', 'en']` and `prefixDefaultLocale: false`.
- Content is stored per locale (`src/content/stages/es/…`, `src/content/pages/es/…`).
- Every stage and page has a `translationKey` shared by its translations.
- Interface text comes from `src/i18n/es.ts`, and `<html lang>` follows the current locale.

ADR 0001 left four questions open: the English pages, the language switcher, the translated trip names and map popups, and the policy for untranslated content. This ADR answers them.

The content to translate:

- 64 stages in 12 trips, about 35,000 words, with 243 body images, 64 cover images and 7 YouTube embeds;
- the about page ("Sobre mí");
- the trip names and countries in `src/content/trips.yaml`;
- about 25 interface strings in `src/i18n/es.ts`.

Claude translates the content and the owner reviews it.

## Decision

### URLs

English pages live under `/en/`. The Spanish URLs do not change.

| Content | Spanish | English |
|---|---|---|
| Home | `/` | `/en/` |
| Trip | `/viajes/<trip>/` | `/en/trips/<trip>/` |
| Stage | `/viajes/<trip>/<stage>/` | `/en/trips/<trip>/<english-stage>/` |
| About | `/sobre-mi/` | `/en/about/` |

- **Stage slugs are translated**, as ADR 0001 planned: `/en/trips/georgia-2019/2-from-zhinvali-to-atabe/`.
- **Trip slugs are not translated.** The trip id is both the URL segment and the key that stages reference, so it stays the same in both languages: `/en/trips/jordania-2011/`. Translating trip slugs would need a per-locale slug map for 12 trips that are mostly place names. The cost is a few Spanish words in English URLs.
- **The 404 page stays Spanish.** GitHub Pages serves a single `/404.html` for every missing path. An English 404 would need client-side detection of the `/en/` prefix and isn't worth it for now.

### Content model

English stages live in `src/content/stages/en/<trip>/<english-stage>/index.md`. They hold **only the text that changes with the language**:

```md
---
title: "Georgia 2, from Zhinvali to Atabe"
description: "Into the Caucasus"
translationKey: "georgia-2019/2-de-zhinvali-a-atabe"
---

Stage text…

![Alt text](./P1110429.jpg "Optional caption")
```

- `date`, `trip`, `lat`, `lng` and `image` come from the Spanish stage with the same `translationKey`. They are written once, so the two versions can't disagree on where or when a stage happened. `address` isn't rendered anywhere and isn't carried over.
- `seoTitle` and `seoDescription` are optional, as in Spanish.
- English stages are a separate collection (`stageTranslations`, loaded from `stages/en/`), with their own, smaller schema. The Spanish `stages` collection only loads `stages/es/`. This removes the `es/` filter that `allStages()` needs today.
- The trip folder of an English stage must match the trip of its Spanish stage. The build fails if a `translationKey` has no Spanish stage, if two English stages share one, or if the trip folders don't match.
- The about page follows the same pattern: `src/content/pages/en/about/index.md` with `title`, `translationKey` and optional SEO fields. The cover image comes from the Spanish page.

### Images are not duplicated

The English folder has no images. In an English stage, a body image is written exactly as in Spanish (`./P1110429.jpg`). A small remark plugin, `src/lib/remark-translation-images.mjs`, rewrites it to a path into the Spanish stage's folder (`src/content/stages/es/<translationKey>/P1110429.jpg`). It computes that path from the English file's location and its `translationKey`. Astro then optimizes the image as usual, and the post-build check still verifies that every image went through Astro.

The plugin relies on the `translationKey` naming the Spanish folder. The build enforces it: it fails if a Spanish stage's `translationKey` differs from its folder (`<trip>/<stage>`). The about page works the same way, with the key `sobre-mi`.

This keeps the English Markdown identical in structure to the Spanish one, so the two are easy to compare side by side. It also keeps the repository from growing by another 70 MB.

The plugin runs as a user remark plugin, which Astro applies before it collects the Markdown images. Writing explicit relative paths in the English files (`../../../es/georgia-2019/2-de-zhinvali-a-atabe/P1110429.jpg`) would also work without a plugin, but it is more verbose and easier to get wrong by hand.

### Trips

`trips.yaml` keeps `name` and `country` in Spanish and gains an English translation per trip:

```yaml
- id: "jordania-2011"
  name: "Jordania, de Madaba a Áqaba"
  year: 2011
  country: "Jordania"
  color: "#f28e2b"
  en:
    name: "Jordan, from Madaba to Aqaba"
    country: "Jordan"
```

A helper returns the name and country for a locale. Components never read `trip.data.name` directly.

### Interface text

`src/i18n/en.ts` mirrors `es.ts` and is typed against its keys, so a missing English string fails the type check. Dates use the same format options with the `en-GB` locale ("14 August 2019"). `<html lang>` stays `en`.

The site name, "piedres y arena", is not translated. It's Asturian ("stones and sand") and part of the brand.

### Pages and components

The routes under `src/pages/en/` reuse the same components as the Spanish routes. The helpers in `src/lib/content.ts` become locale-aware:

- `tripPath`, `stagePath` and the about path take the locale;
- `allStages` and `stagesOf` return the stages of one locale, with their text in that language and their order and coordinates from Spanish;
- previous and next links stay within the same language.

The home map, its popups, the trip tiles and the stage counters all read from these helpers, so the English home shows English titles and links to English pages.

### Language switcher and `hreflang`

- **Switcher.** The header gets a link to the same page in the other language: "EN" on Spanish pages and "ES" on English pages. It uses `hreflang` and `lang` attributes. The other language's version is found by `translationKey`, and for the home page and trip pages by route.
- **`hreflang` tags.** Every page that exists in both languages declares both versions with `<link rel="alternate" hreflang="…">`, plus `x-default` pointing to Spanish. This is what lets search engines send English searchers to the English page.
- **No automatic redirect or language notice.** The browser language is never used to redirect or prompt readers. A JavaScript redirect would get in the way of readers who want Spanish with an English browser.

### Rollout: batches, with English hidden until complete

The translation is delivered in several pull requests, so that each one can be reviewed comfortably:

1. **The infrastructure, Georgia 2019 and the about page.** This includes everything in this ADR, `en.ts`, the English trip names for all 12 trips, the README and post-build check updates, and the six Georgia stages.
2. **The other trips, newest first,** one or two trips per pull request (about 4,000–6,000 words each).
3. **The last pull request** makes English public.

Until the last pull request, English is deployed but hidden. One setting in `src/i18n/index.ts` (`englishPublic = false`) controls this:

- every English page has `<meta name="robots" content="noindex">`;
- no page, Spanish or English, has a switcher or `hreflang` tags. Both appear when `englishPublic` becomes `true`;
- the English pages are reachable only by typing their URL, for reviewing on the live site.

**Untranslated content.** A trip is translated whole or not at all: the build fails if a trip has some English stages but not all of them. The English home, map and trip tiles only show trips that are translated. This only matters while the batches are in progress. Once `englishPublic` is `true`, the post-build check requires every Spanish stage to have an English version, so new stages must be added in both languages.

### Translation style

The translation is natural English, not word for word:

- It keeps the author's voice: first person, humour, asides, exclamations and the mix of past and present tense the original uses.
- Spanish idioms are adapted, not translated literally: "quien algo quiere, algo le cuesta" becomes "no pain, no gain", or whatever fits the sentence best.
- Typos and slips in the original are not carried over. They are fixed in the Spanish too, with minimal edits.
- **Place names** use the established English form when there is one: Tbilisi, Aqaba, Ljubljana, Ethiopia, the Dead Sea. Otherwise they stay as written.
- **Proper names that are Spanish by nature** stay in Spanish, with a short gloss the first time if needed: Camino de Santiago, Camino Primitivo, Ruta de la Plata.
- **Measurements** stay metric. Distances, heights and temperatures are not converted.
- **Image alt texts and captions** are translated. YouTube embeds and raw HTML are kept exactly as they are.
- **Short descriptions** stay short and in the same tone as the Spanish ones. When the Spanish one is already in English ("Magic!"), it is kept.
- **Spelling** is British: metres, tyres, lorries.
- **Apostrophes and quotes** are typographic (’ “ ”) in English text, front matter included. Never in URLs, HTML attributes, embeds or code.
- **Links to pages in another language** are switched to their English equivalent when one exists, for example English Wikipedia instead of Spanish.

The owner reviews each batch in its pull request. Corrections to the style are added here, so later batches follow them.

### Checks

`tools/check_build.py` is extended to:

- expect an English page for every English stage, for every trip with English stages, and for `/en/` and `/en/about/`;
- check `lang="en"` under `/en/` and `lang="es"` everywhere else;
- check that every internal link on an English page stays in English, apart from the switcher and `hreflang` links;
- check that the `hreflang` and switcher links point to existing pages and are symmetrical;
- check that English pages are `noindex` and that no page has `hreflang` while English is hidden, and that it has no gaps once it's public.

## Alternatives considered

### Content model

- **English stages as full copies of the front matter.** This works with the existing schema, but every date, coordinate and cover image would be written twice and could drift apart. Rejected.
- **Both languages in one Markdown file.** Rejected: very long files, and Astro's content collections expect one body per entry.

### Images

- **Copy the images into the English folders.** It is the simplest to implement, but it doubles the image weight of the repository. Rejected.
- **Move all images to a shared folder.** It would change every Spanish stage, and the Spanish URLs and editing workflow work well as they are. Rejected.

### Reaching the English version

- **A switcher plus a notice for non-Spanish browsers.** It helps readers who follow a link to a Spanish page, but it adds a dismissible element and code to remember the dismissal. It can be added later if needed.
- **An automatic redirect.** Rejected for the reason above.

### Rollout

- **Batches, with English public from the start.** The progress would be visible, but the English home would be incomplete for weeks and would need a policy for links to untranslated trips. Rejected.
- **One pull request with everything.** About 35,000 words would be too much to review in one go. Rejected.

### Trip slugs

- **Translated trip slugs** (`/en/trips/jordan-2011/`). These are nicer URLs, but they need a slug map and break the rule that one id names one trip everywhere. Rejected for now. It could still be added before English goes public without breaking any link.

## Consequences

- **Editing:** fixing a typo in Spanish doesn't touch English. Changing a stage's date, coordinates or cover image is done once, in Spanish. Once English is public, a new stage needs an English version or the check fails.
- **Repository:** it grows by about 35,000 words of Markdown and no images.
- **ADR 0001:** its "Repository language" rule now reads: the website content is in Spanish and English, and everything else stays in English. The README is updated to match.
- **SEO:** the English pages are invisible to search engines until the last batch. After that, `hreflang` links both versions.
- **Build time:** the English pages reuse the optimized Spanish images, so image processing doesn't double. Only the page count does.

## Out of scope

- An English 404 page.
- Translated trip slugs (see above).
- A language notice or automatic redirect.
- Introductory texts per trip, GPX tracks and the visual redesign, as in ADR 0001.
