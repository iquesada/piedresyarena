import { defineCollection, reference } from 'astro:content';
import { file, glob } from 'astro/loaders';
import { z } from 'astro/zod';

// `<trip>/<stage>/index.md` -> `<trip>/<stage>`, `es/sobre-mi/index.md` -> `es/sobre-mi`
const folderId = ({ entry }: { entry: string }) => entry.replace(/\/index\.md$/, '');

const trips = defineCollection({
  loader: file('src/content/trips.yaml'),
  schema: z.object({
    name: z.string(),
    year: z.number().int(),
    country: z.string(),
    color: z.string(),
    en: z.object({ name: z.string(), country: z.string() }),
  }),
});

// Spanish stages. The id (`<trip>/<stage>`) is also their translationKey.
const stages = defineCollection({
  loader: glob({ pattern: '**/index.md', base: 'src/content/stages/es', generateId: folderId }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      date: z.coerce.date(),
      trip: reference('trips'),
      lat: z.number(),
      lng: z.number(),
      address: z.string().optional(),
      description: z.string(),
      image: image(),
      seoTitle: z.string().optional(),
      seoDescription: z.string().optional(),
      translationKey: z.string(),
    }),
});

// English stages hold only their text: the rest comes from the Spanish stage named by translationKey.
const stageTranslations = defineCollection({
  loader: glob({ pattern: '**/index.md', base: 'src/content/stages/en', generateId: folderId }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    seoTitle: z.string().optional(),
    seoDescription: z.string().optional(),
    translationKey: z.string(),
  }),
});

const pages = defineCollection({
  loader: glob({ pattern: '**/index.md', base: 'src/content/pages', generateId: folderId }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      image: image().optional(),
      seoTitle: z.string().optional(),
      seoDescription: z.string().optional(),
      translationKey: z.string(),
    }),
});

export const collections = { trips, stages, stageTranslations, pages };
