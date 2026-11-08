import type { APIRoute, GetStaticPaths } from 'astro';

// Tracks written next to each Spanish stage (src/content/stages/es/<trip>/<stage>/track.json): the ride as [[lat, lng], …].
const files = import.meta.glob<number[][]>('/src/content/stages/es/*/*/track.json', { eager: true, import: 'default' });

/** <trip> -> { <stage key>: track }. Shared by both locales. */
export const tracks: Record<string, Record<string, number[][]>> = {};
for (const [path, track] of Object.entries(files)) {
  const [trip, stage] = path.split('/').slice(-3, -1);
  (tracks[trip] ??= {})[`${trip}/${stage}`] = track;
}

export const getStaticPaths = (() => Object.keys(tracks).map((trip) => ({ params: { trip } }))) satisfies GetStaticPaths;

/** One file per trip, fetched by the map only when it shows stages. */
export const GET: APIRoute = ({ params }) => Response.json(tracks[params.trip!]);
