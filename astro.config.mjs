import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import remarkBreaks from 'remark-breaks';
import redirects from './src/redirects.json';
import { rehypeFigure } from './src/lib/rehype-figure.mjs';
import { rehypeImageSizes } from './src/lib/rehype-image-sizes.mjs';

// Displayed image widths. Keep in sync with --content-width (760px) and the .gallery
// grid (minmax(220px, 1fr), ~3 columns in the column) in src/layouts/Base.astro.
const sizes = {
  content: '(min-width: 760px) 760px, 100vw',
  gallery: '(min-width: 760px) 250px, (min-width: 480px) 50vw, 100vw',
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
