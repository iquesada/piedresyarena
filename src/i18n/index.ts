import es, { dateFormat as esDateFormat } from './es';

export type Key = keyof typeof es;

const dictionaries: Record<string, Record<Key, string>> = { es };
const dateFormats: Record<string, Intl.DateTimeFormatOptions> = { es: esDateFormat };

export function t(locale: string | undefined, key: Key, params: Record<string, string | number> = {}): string {
  const text = (dictionaries[locale ?? 'es'] ?? es)[key];
  return text.replace(/\{(\w+)\}/g, (m, p) => (p in params ? String(params[p]) : m));
}

export function formatDate(locale: string | undefined, date: Date): string {
  const l = locale ?? 'es';
  return new Intl.DateTimeFormat(l, { ...(dateFormats[l] ?? esDateFormat), timeZone: 'UTC' }).format(date);
}

export function stageCount(locale: string | undefined, n: number): string {
  return n === 1 ? t(locale, 'trip.stage') : t(locale, 'trip.stages', { n });
}
