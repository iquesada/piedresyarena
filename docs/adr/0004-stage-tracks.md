# ADR 0004: Draw each stage's track, loaded per trip on demand

- **Status:** Accepted
- **Date:** 2026-11-08

## Context

- The map joined stage places with a dashed trip line (PR #18): it is not the road ridden, and the last stage's ride was not drawn.
- Most trips since 2010 have GPS rides in Garmin Connect. A personal tool, kept outside this repo on purpose, writes them next to each Spanish stage as `track.json` (`[[lat, lng], …]`, simplified to ~20 m) with the stage's `distance` and `elevation`.
- The map is on the home page, and its trip data is embedded in the page.

## Decision

- **Solid tracks, dashed fallback.** At stage zoom, a stage with a track is drawn as that track; a stage without one keeps its piece of dashed trip line to the next stage. One arrow per track or segment shows the way.
- **One file per trip, fetched on demand.** `src/pages/tracks/[trip].json.ts` builds `/tracks/<trip>.json` from the trip's `track.json` files. The map fetches it only at stage zoom and only for trips in view; the home page carries just its URL.
- **Pins stay on the named place.** A track can start a few km from its stage place (transfers, GPS switched on late); the pin is not moved to the ride's start on trips already published (decided for Jordan 2011).
- **Only the simplified track is published.** No GPX in the repo or on the site.

## Alternatives considered

- **Tracks embedded in the page.** Rejected: every trip's tracks would weigh on the home page, which shows only trip pins at first.
- **Pin at the ride's start.** Rejected for published trips: the pin would leave the place the stage is named after (Petra's pin ~17 km south of Petra).

## Consequences

- **Privacy:** a track that starts or ends at home shows the address; the tool can trim the ends, and the user decides per trip.
- **Size:** ~4 KB per stage; check it if a long or many-stage trip gets tracks.
- **Glossary:** "Track" is a term of its own; the trip line is now only the fallback.
