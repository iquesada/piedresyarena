import { visit } from 'unist-util-visit';

// Gives every Markdown image a `sizes` attribute matching where it is displayed, so the
// srcset Astro generates (image.layout: 'constrained') is picked at display size.
// Galleries are raw `<div class="gallery">` … `</div>` nodes around top-level paragraphs
// (see tools/migrate.py), so they are tracked while walking the root's children.
export function rehypeImageSizes({ content, gallery }) {
  return () => (tree) => {
    let inGallery = false;
    for (const node of tree.children) {
      if (node.type === 'raw' && /<div class="gallery">/.test(node.value)) inGallery = true;
      else if (node.type === 'raw' && /<\/div>/.test(node.value)) inGallery = false;
      visit(node, 'element', (el) => {
        if (el.tagName === 'img') el.properties.sizes = inGallery ? gallery : content;
      });
    }
  };
}
