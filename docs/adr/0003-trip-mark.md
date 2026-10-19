# ADR 0003: Mark trips with the rider instead of a dot

- **Status:** Accepted
- **Date:** 2026-10-19

## Context

- Over the photos, a trip is marked by a coloured circle (`.dot` in `src/layouts/Base.astro`). It appears in the home and about tiles (`TripTiles.astro`), the trip opener kicker (`TripPage.astro`) and the trip link in the stage opener (`StagePage.astro`).
- The map (`Map.astro`) marks trips differently: the logo's rider (stone, two wheels, head) in the trip colour, on a white tag with a pointer.
- The dot is small and gets lost over the darkened photos.

## Decision

- **The rider replaces the dot** in those three places. It sits on a white rounded tag, without the map pin's pointer.
- **The map popup keeps its dot** (`.pop-dot`).
- **One drawing.** The map pin and the trip mark share the rider from `src/lib/rider.ts`, drawn in `currentColor`. The trip colour is the only value interpolated, as `color` in a `style` attribute: Astro escapes it in the trip mark, and in the map's divIcon string it comes from `trips.yaml`, as before.

## Alternatives considered

- **The map pin, pointer included.** Rejected: it points at nothing outside a map.
- **The rider with no tag.** Rejected: the darker trip colours get lost over the darkened photos.
- **Two copies of the drawing.** Rejected: LogoIcon shows that copies drift.

## Consequences

- **Map:** the pin and the trip mark change together; the pin's tag and pointer stay in `Map.astro`.
- **Layout:** the mark is about three times wider than the dot, so the kicker lines can wrap differently.
- **Logo:** `LogoIcon.astro` stays a separate two-tone redraw with slightly different geometry (head radius 1.9 against 2), so it can drift from the shared drawing.
