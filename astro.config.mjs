import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import remarkBreaks from 'remark-breaks';
import redirects from './src/redirects.json';
import { rehypeFigure } from './src/lib/rehype-figure.mjs';
import { rehypeImageSizes } from './src/lib/rehype-image-sizes.mjs';

// Displayed image widths. Keep in sync with --wide (64rem = 1024px, figures break out to it)
// and the .gallery grid (2 columns, 4 from 760px) and .gallery.strip (85% wide, at most 40rem) in src/layouts/Base.astro.
const sizes = {
  content: '(min-width: 1024px) 1024px, 100vw',
  gallery: '(min-width: 1024px) 256px, (min-width: 760px) 25vw, 50vw',
  strip: '(min-width: 760px) 640px, 85vw',
};

export default defineConfig({
  site: 'https://www.piedresyarena.com',
  trailingSlash: 'always',
  i18n: { defaultLocale: 'es', locales: ['es', 'en'], routing: { prefixDefaultLocale: false } },
  redirects,
  image: { layout: 'constrained', responsiveStyles: true, breakpoints: [480, 760, 1080] },
  markdown: {
    processor: unified({
      remarkPlugins: [remarkBreaks],
      rehypePlugins: [rehypeFigure, rehypeImageSizes(sizes)],
    }),
  },
});
