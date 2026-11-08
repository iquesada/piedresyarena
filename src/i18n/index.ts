import es, { dateFormat as esDateFormat } from './es';
import en, { dateFormat as enDateFormat } from './en';

export type Key = keyof typeof es;
export type Locale = 'es' | 'en';

/** While false, English pages are noindex and no page links to its other-language version (switcher, hreflang). */
export const englishPublic = true;

export const toLocale = (value: string | undefined): Locale => (value === 'en' ? 'en' : 'es');

const dictionaries: Record<Locale, Record<Key, string>> = { es, en };
const dateFormats: Record<Locale, Intl.DateTimeFormatOptions> = { es: esDateFormat, en: enDateFormat };
const intlTags: Record<Locale, string> = { es: 'es', en: 'en-GB' };

export function t(locale: string | undefined, key: Key, params: Record<string, string | number> = {}): string {
  const text = dictionaries[toLocale(locale)][key];
  return text.replace(/\{(\w+)\}/g, (m, p) => (p in params ? String(params[p]) : m));
}

export function formatDate(locale: string | undefined, date: Date): string {
  const l = toLocale(locale);
  return new Intl.DateTimeFormat(intlTags[l], { ...dateFormats[l], timeZone: 'UTC' }).format(date);
}

/** "92 km · 1.450 m+": the stage figures that are known, in the locale's number format. */
export function stageFigures(locale: string | undefined, distance?: number, elevation?: number): string[] {
  const n = new Intl.NumberFormat(intlTags[toLocale(locale)], { maximumFractionDigits: 0, useGrouping: 'always' });
  return [distance !== undefined && `${n.format(distance)} km`, elevation !== undefined && `${n.format(elevation)} m+`].filter((s) => s !== false);
}

export function stageCount(locale: string | undefined, n: number): string {
  return n === 1 ? t(locale, 'trip.stage') : t(locale, 'trip.stages', { n });
}
