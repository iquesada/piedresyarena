#!/usr/bin/env python3
"""Post-build checks over dist/. Expected pages come from the sources, never hardcoded.

Usage: python3 tools/check_build.py   (after `astro build`)
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
STAGES = ROOT / 'src' / 'content' / 'stages' / 'es'
TRIPS = ROOT / 'src' / 'content' / 'trips.yaml'
REDIRECTS = ROOT / 'src' / 'redirects.json'
SITE_HOSTS = {'www.piedresyarena.com', 'piedresyarena.com'}
SHORTCODES = ('[button', '[caption', '[tabs', '[easingslider', '[imagetab')


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.lang = self.refresh = self.canonical = None
        self.title = False
        self.urls, self.imgs = [], []
        self.divs, self.embeds, self.nested_embeds = [], [], 0  # open <div>s (True = .embed), iframes per .embed
        self.feed(text)

    def handle_endtag(self, tag):
        if tag == 'div' and self.divs:
            self.divs.pop()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'html':
            self.lang = a.get('lang')
        elif tag == 'title':
            self.title = True
        elif tag == 'meta' and a.get('http-equiv') == 'refresh':
            self.refresh = a.get('content', '').split('url=', 1)[-1]
        elif tag == 'link' and a.get('rel') == 'canonical':
            self.canonical = a.get('href')
        if tag == 'div':
            is_embed = 'embed' in (a.get('class') or '').split()
            if is_embed:
                self.nested_embeds += any(self.divs)
                self.embeds.append(0)
            self.divs.append(is_embed)
        elif tag == 'iframe' and any(self.divs):
            self.embeds[-1] += 1
        if tag == 'img':
            self.imgs.append(a.get('src') or '')
        for key in ('href', 'src'):
            if a.get(key):
                self.urls.append(a[key])
        if a.get('srcset'):
            self.urls += [c.split()[0] for c in a['srcset'].split(',') if c.strip()]


def target(path):
    """dist file served for an internal URL path, or None."""
    p = DIST / unquote(path).lstrip('/')
    if p.is_file():
        return p
    return p / 'index.html' if (p / 'index.html').is_file() else None


def main():
    if not DIST.is_dir():
        sys.exit('dist/ not found: run `astro build` first')
    errors = []

    expected = ['/', '/sobre-mi/']
    trips = re.findall(r'^- id: "?([^"\n]+)"?$', TRIPS.read_text(), re.M)
    expected += [f'/viajes/{t}/' for t in trips if any((STAGES / t).glob('*/index.md'))]  # trips without stages get no page
    expected += [f'/viajes/{p.parent.parent.name}/{p.parent.name}/' for p in STAGES.glob('*/*/index.md')]
    errors += [f'missing page {p}' for p in expected if not target(p)]

    redirects = json.loads(REDIRECTS.read_text())
    redirect_files = set()
    for old, new in redirects.items():
        f = target(old)
        if not f:
            errors.append(f'missing redirect page {old}')
            continue
        redirect_files.add(f)
        dest = Page(f.read_text()).refresh
        if dest != new or not target(new):
            errors.append(f'redirect {old} -> {dest!r}, expected existing {new}')

    pages = [p for p in DIST.rglob('*.html') if p not in redirect_files]
    for f in pages:
        rel = '/' + str(f.relative_to(DIST))
        text = f.read_text()
        page = Page(text)
        if page.lang != 'es':
            errors.append(f'{rel}: lang={page.lang!r}')
        if not page.title:
            errors.append(f'{rel}: no <title>')
        if not page.canonical and rel != '/404.html':
            errors.append(f'{rel}: no canonical link')
        errors += [f'{rel}: leftover {s}' for s in SHORTCODES if s in text]
        if page.nested_embeds:
            errors.append(f'{rel}: .embed nested inside another .embed')
        errors += [f'{rel}: .embed with {n} iframes' for n in page.embeds if n != 1]
        if '![' in text:
            errors.append(f'{rel}: literal ![')
        errors += [f'{rel}: image not optimized: {src}' for src in page.imgs if not src.startswith('/_astro/')]
        for url in page.urls:
            u = urlsplit(url)
            if not u.path or ((u.scheme or u.netloc) and u.netloc not in SITE_HOSTS):
                continue
            path = u.path if u.path.startswith('/') else '/' + str(f.parent.relative_to(DIST) / u.path)
            if not target(path):
                errors.append(f'{rel}: broken link {url}')

    print(f'Checked {len(pages)} pages, {len(redirects)} redirects, {len(expected)} expected pages.')
    for e in errors:
        print(f'  {e}')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
