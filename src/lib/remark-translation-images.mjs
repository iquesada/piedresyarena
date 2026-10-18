import fs from 'node:fs';
import path from 'node:path';
import { visit } from 'unist-util-visit';

// English Markdown (`src/content/<collection>/en/…`) writes body images exactly as its Spanish original
// (`./P1110429.jpg`), and the files live only in the Spanish folder, `<collection>/es/<translationKey>/`.
// Rewrites those relative URLs to point there. Must run before Astro's remark-collect-images, which it
// does as a user remark plugin.
export function remarkTranslationImages() {
  return (tree, file) => {
    const root = file.path?.match(/^(.*\/content\/[^/]+)\/en\//)?.[1];
    if (!root) return;
    const key = file.data.astro?.frontmatter?.translationKey;
    if (!key) throw new Error(`${file.path}: no translationKey to find its images`);
    const es = path.join(root, 'es', key);
    if (!fs.existsSync(es)) throw new Error(`${file.path}: translationKey "${key}" matches no Spanish entry`);
    const dir = path.dirname(file.path);
    visit(tree, 'image', (node) => {
      if (URL.canParse(node.url) || node.url.startsWith('/') || node.url.startsWith('#')) return;
      node.url = path.relative(dir, path.join(es, node.url));
    });
  };
}
