export default {
  'site.title': 'piedres y arena',
  'site.description': 'Blog de viajes en bicicleta por el mundo.',
  'nav.trips': 'Viajes',
  'nav.about': 'Sobre mí',
  'stage.prev': 'Etapa anterior',
  'stage.next': 'Siguiente etapa',
  'trip.stages': '{n} etapas',
  'trip.stage': '1 etapa',
  'map.label': 'Mapa de etapas',
  'map.attribution': '© colaboradores de OpenStreetMap',
  'notFound.title': 'Página no encontrada',
  'notFound.text': 'La página que buscas no existe o ha cambiado de sitio.',
  'notFound.home': 'Ir a la portada',
} as const;

export const dateFormat: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long', year: 'numeric' };
