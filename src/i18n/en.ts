import type es from './es';

export default {
  'site.title': 'piedres y arena',
  'site.description': 'A blog about cycling trips around the world.',
  'nav.trips': 'Trips',
  'nav.about': 'About',
  'lang.switch': 'Read this page in English',
  'social.instagram': 'Follow me on Instagram',
  'stage.prev': 'Previous stage',
  'stage.next': 'Next stage',
  'trip.stages': '{n} stages',
  'trip.stage': '1 stage',
  'map.label': 'Map of stages',
  'home.title': 'An atlas of cycling trips',
  'home.summary': '{trips} trips and {stages} stages, from the Sahara to the Caucasus. Tap a trip on the map to see its stages.',
  'trips.label': 'Trips',
  'trip.stages.label': 'Stages of the trip',
  'stage.number': 'Stage {n}',
  'stage.position': 'stage {n} of {total}',
  'gallery.prev': 'Previous photo',
  'gallery.next': 'Next photo',
  'map.attribution': '© OpenStreetMap contributors',
  'notFound.title': 'Page not found',
  'notFound.heading': 'You’re lost',
  'notFound.where': '0° N, 0° E',
  'notFound.text': 'You’re on Null Island, the spot in the Gulf of Guinea where places without coordinates end up. The page you’re looking for doesn’t exist or has moved.',
  'notFound.home': 'Back to the map',
  'notFound.random': 'Take me to a random stage',
} as const satisfies Record<keyof typeof es, string>;

export const dateFormat: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long', year: 'numeric' };
