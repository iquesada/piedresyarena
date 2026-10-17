import { getCollection, getEntry, type CollectionEntry } from 'astro:content';

export type Stage = CollectionEntry<'stages'>;
export type Trip = CollectionEntry<'trips'>;

const slugOf = (stage: Stage) => stage.id.split('/').at(-1)!;
const byDateThenSlug = (a: Stage, b: Stage) =>
  a.data.date.getTime() - b.data.date.getTime() || slugOf(a).localeCompare(slugOf(b));

/** Spanish stages only: future `en/` entries must not generate pages under /viajes/. */
export const allStages = async () => (await getCollection('stages', (s) => s.id.startsWith('es/'))).sort(byDateThenSlug);

export const stagesOf = async (tripId: string) => (await allStages()).filter((s) => s.data.trip.id === tripId);

export const tripPath = (trip: Trip) => `/viajes/${trip.id}/`;

export const stagePath = (stage: Stage) => `/viajes/${stage.data.trip.id}/${slugOf(stage)}/`;

export const tripOf = async (stage: Stage) => (await getEntry(stage.data.trip))!;

export async function prevNext(stage: Stage) {
  const stages = await stagesOf(stage.data.trip.id);
  const i = stages.findIndex((s) => s.id === stage.id);
  return { prev: stages[i - 1], next: stages[i + 1] };
}
