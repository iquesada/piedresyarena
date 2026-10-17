import { visit } from 'unist-util-visit';

// Gives every Markdown image a `sizes` attribute matching where it is displayed, so the
// srcset Astro generates (image.layout: 'constrained') is picked at display size.
// Galleries are raw `<div class="gallery">` (or `gallery strip`) … `</div>` nodes around top-level paragraphs
// (see tools/migrate.py), so they are tracked while walking the root's children.
export function rehypeImageSizes({ content, gallery, strip }) {
  return () => (tree) => {
    let current = content;
    for (const node of tree.children) {
      const open = node.type === 'raw' && node.value.match(/<div class="gallery( strip)?">/);
      if (open) current = open[1] ? strip : gallery;
      else if (node.type === 'raw' && /<\/div>/.test(node.value)) current = content;
      visit(node, 'element', (el) => {
        if (el.tagName === 'img') el.properties.sizes = current;
      });
    }
  };
}
