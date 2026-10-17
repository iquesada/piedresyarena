import { visit } from 'unist-util-visit';

const isBlank = (n) => n.type === 'text' && !n.value.trim();

// Turns a paragraph whose only content is an <img title="…"> into
// <figure><img><figcaption>…</figcaption></figure>. Must run before Astro's
// rehype-images, which picks up the img (minus its title) for optimization.
export function rehypeFigure() {
  return (tree) => {
    visit(tree, 'element', (node, index, parent) => {
      if (node.tagName !== 'p' || !parent || index === undefined) return;
      const kids = node.children.filter((c) => !isBlank(c));
      const [img] = kids;
      if (kids.length !== 1 || img.type !== 'element' || img.tagName !== 'img') return;
      const caption = img.properties?.title;
      if (!caption) return;
      delete img.properties.title;
      parent.children[index] = {
        type: 'element',
        tagName: 'figure',
        properties: {},
        children: [img, { type: 'element', tagName: 'figcaption', properties: {}, children: [{ type: 'text', value: String(caption) }] }],
      };
    });
  };
}
