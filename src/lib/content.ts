import { getCollection, getEntry, type CollectionEntry } from 'astro:content';
import type { Locale } from '../i18n';

export type Trip = CollectionEntry<'trips'>;
type SpanishData = CollectionEntry<'stages'>['data'];

/** A stage in one locale. Text comes from that locale; date, place, trip and cover always from Spanish. */
export type Stage = {
  locale: Locale;
  /** translationKey, shared by both versions: `<trip>/<Spanish slug>`. */
  key: string;
  slug: string;
  /** For render(). */
  entry: CollectionEntry<'stages'> | CollectionEntry<'stageTranslations'>;
  data: Pick<SpanishData, 'title' | 'description' | 'seoTitle' | 'seoDescription' | 'date' | 'trip' | 'lat' | 'lng' | 'image'>;
};

// Both locales are in Spanish order.
const byDateThenKey = (a: Stage, b: Stage) => a.data.date.getTime() - b.data.date.getTime() || a.key.localeCompare(b.key);

async function spanishStages(): Promise<Stage[]> {
  return (await getCollection('stages')).map((entry): Stage => {
    const [folderTrip, slug] = entry.id.split('/');
    if (folderTrip !== entry.data.trip.id) {
      throw new Error(`src/content/stages/es/${entry.id}/index.md: front matter trip "${entry.data.trip.id}" does not match its folder "${folderTrip}"`);
    }
    // English stages find their images in the folder their translationKey names.
    if (entry.data.translationKey !== entry.id) {
      throw new Error(`src/content/stages/es/${entry.id}/index.md: translationKey "${entry.data.translationKey}" does not match its folder "${entry.id}"`);
    }
    return { locale: 'es', key: entry.id, slug, entry, data: entry.data };
  });
}

/** A trip is translated whole or not at all. */
async function englishStages(): Promise<Stage[]> {
  const spanish = new Map((await spanishStages()).map((s) => [s.key, s]));
  const seen = new Set<string>();
  const stages = (await getCollection('stageTranslations')).map((entry): Stage => {
    const { title, description, seoTitle, seoDescription, translationKey: key } = entry.data;
    const file = `src/content/stages/en/${entry.id}/index.md`;
    const es = spanish.get(key);
    if (!es) throw new Error(`${file}: translationKey "${key}" matches no Spanish stage`);
    if (seen.has(key)) throw new Error(`${file}: translationKey "${key}" is already used by another English stage`);
    seen.add(key);
    const [folderTrip, slug] = entry.id.split('/');
    const { date, trip, lat, lng, image } = es.data;
    if (folderTrip !== trip.id) throw new Error(`${file}: trip folder "${folderTrip}" does not match the Spanish stage's trip "${trip.id}"`);
    return { locale: 'en', key, slug, entry, data: { title, description, seoTitle, seoDescription, date, trip, lat, lng, image } };
  });
  for (const trip of new Set(stages.map((s) => s.data.trip.id))) {
    const missing = [...spanish.values()].filter((s) => s.data.trip.id === trip && !seen.has(s.key)).map((s) => s.key);
    if (missing.length) throw new Error(`Trip "${trip}" is partly translated: no English stage for ${missing.join(', ')}`);
  }
  return stages;
}

export const allStages = async (locale: Locale) => (await (locale === 'en' ? englishStages() : spanishStages())).sort(byDateThenKey);

export const stagesOf = async (locale: Locale, tripId: string) => (await allStages(locale)).filter((s) => s.data.trip.id === tripId);

export const homePath = (locale: Locale) => (locale === 'en' ? '/en/' : '/');

export const aboutPath = (locale: Locale) => (locale === 'en' ? '/en/about/' : '/sobre-mi/');

export const tripPath = (locale: Locale, trip: { id: string }) => (locale === 'en' ? `/en/trips/${trip.id}/` : `/viajes/${trip.id}/`);

export const stagePath = (stage: Stage) => `${tripPath(stage.locale, stage.data.trip)}${stage.slug}/`;

export const tripText = (locale: Locale, trip: Trip) => (locale === 'en' ? trip.data.en : { name: trip.data.name, country: trip.data.country });

export const tripOf = async (stage: Stage) => (await getEntry(stage.data.trip))!;

export async function prevNext(stage: Stage) {
  const stages = await stagesOf(stage.locale, stage.data.trip.id);
  const i = stages.findIndex((s) => s.key === stage.key);
  return { prev: stages[i - 1], next: stages[i + 1] };
}

/** The about page in one locale. Its cover photo always comes from the Spanish page. */
export async function aboutPage(locale: Locale) {
  const es = (await getEntry('pages', 'es/sobre-mi'))!;
  const entry = locale === 'en' ? (await getEntry('pages', 'en/about'))! : es;
  if (entry.data.translationKey !== 'sobre-mi') {
    throw new Error(`src/content/pages/${entry.id}/index.md: translationKey "${entry.data.translationKey}" should be "sobre-mi"`);
  }
  const { title, seoTitle, seoDescription } = entry.data;
  return { entry, title, seoTitle, seoDescription, image: es.data.image };
}
