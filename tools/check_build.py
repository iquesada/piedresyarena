#!/usr/bin/env python3
"""Post-build checks over dist/. Expected pages come from the sources, never hardcoded.

Usage: python3 tools/check_build.py   (after `astro build`)
"""
import json
import posixpath
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE_HOSTS = {'www.piedresyarena.com', 'piedresyarena.com'}
SHORTCODES = ('[button', '[caption', '[tabs', '[easingslider', '[imagetab')


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.lang = self.refresh = self.canonical = self.robots = None
        self.title = False
        self.urls, self.imgs = [], []
        self.links = []  # hrefs to follow, without the hreflang ones (switcher and alternates)
        self.alternates, self.switcher = {}, None  # hreflang -> href of <link rel=alternate>; <a hreflang> href
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
        elif tag == 'meta' and a.get('name') == 'robots':
            self.robots = a.get('content')
        if 'hreflang' in a:
            if tag == 'a':
                self.switcher = a.get('href')
            else:
                self.alternates[a['hreflang']] = a.get('href')
        elif a.get('href'):
            self.links.append(a['href'])
        if a.get('data-trips'):  # the home map: trip and stage links built in the browser
            urls = [u for trip in json.loads(a['data-trips']) for u in [trip['url']] + [s['url'] for s in trip['stages']]]
            self.links += urls
            self.urls += urls
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


def target(dist, path):
    """dist file served for an internal URL path, or None."""
    p = dist / unquote(path).lstrip('/')
    if p.is_file():
        return p
    return p / 'index.html' if (p / 'index.html').is_file() else None


def internal(dist, url, f):
    """Normalised URL path of an internal URL found in dist file f, or None for external ones."""
    u = urlsplit(url)
    if not u.path or ((u.scheme or u.netloc) and u.netloc not in SITE_HOSTS):
        return None
    path = u.path if u.path.startswith('/') else '/' + str(f.parent.relative_to(dist) / u.path)
    norm = posixpath.normpath(path)
    return norm + '/' if path.endswith('/') and norm != '/' else norm


def english_public(i18n_path):
    """Value of `englishPublic` in src/i18n/index.ts."""
    m = re.search(r'^export const englishPublic = (true|false);', i18n_path.read_text(), re.M)
    if not m:
        sys.exit(f'englishPublic not found in {i18n_path}')
    return m[1] == 'true'


def check(dist: Path, content: Path, public: bool) -> list[str]:
    """Errors in the built site `dist`, built from `content` (src/content, with src/redirects.json next to it).
    Prints a one-line summary."""
    stages_es, stages_en = content / 'stages' / 'es', content / 'stages' / 'en'
    errors = []

    expected = ['/', '/sobre-mi/', '/en/', '/en/about/']
    trips = re.findall(r'^- id: "?([^"\n]+)"?$', (content / 'trips.yaml').read_text(), re.M)
    for prefix, stages in (('/viajes', stages_es), ('/en/trips', stages_en)):
        expected += [f'{prefix}/{t}/' for t in trips if any((stages / t).glob('*/index.md'))]  # trips without stages get no page
        expected += [f'{prefix}/{p.parent.parent.name}/{p.parent.name}/' for p in stages.glob('*/*/index.md')]
    errors += [f'missing page {p}' for p in expected if not target(dist, p)]

    redirects = json.loads((content.parent / 'redirects.json').read_text())
    redirect_files = set()
    for old, new in redirects.items():
        f = target(dist, old)
        if not f:
            errors.append(f'missing redirect page {old}')
            continue
        redirect_files.add(f)
        dest = Page(f.read_text()).refresh
        if dest != new or not target(dist, new):
            errors.append(f'redirect {old} -> {dest!r}, expected existing {new}')

    if public:
        translated = {re.search(r'^translationKey: "?([^"\n]+)"?$', p.read_text(), re.M)[1] for p in stages_en.glob('*/*/index.md')}
        errors += [f'no English version of stage {k}' for k in sorted({f'{p.parent.parent.name}/{p.parent.name}' for p in stages_es.glob('*/*/index.md')} - translated)]

    pages = [p for p in dist.rglob('*.html') if p not in redirect_files]
    parsed = {}  # URL path -> Page
    for f in pages:
        rel = '/' + str(f.relative_to(dist))
        text = f.read_text()
        page = parsed[rel.removesuffix('index.html')] = Page(text)
        english = rel.startswith('/en/')
        if page.lang != ('en' if english else 'es'):
            errors.append(f'{rel}: lang={page.lang!r}')
        if english and not public and page.robots != 'noindex':
            errors.append(f'{rel}: not noindex while English is hidden')
        if not public and (page.alternates or page.switcher):
            errors.append(f'{rel}: hreflang while English is hidden')
        if english:
            for url in page.links:
                path = internal(dist, url, f)
                dest = path and target(dist, path)
                if dest and dest.suffix == '.html' and not path.startswith('/en/'):
                    errors.append(f'{rel}: link out of English {url}')
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
            path = internal(dist, url, f)
            if path and not target(dist, path):
                errors.append(f'{rel}: broken link {url}')

    # Public: every page but the 404 exists in both languages. Both versions name each other the same way,
    # and the switcher goes to the other one.
    for path, page in parsed.items():
        if not public or path == '/404.html':
            continue
        if not page.alternates and not page.switcher:
            errors.append(f'{path}: no hreflang alternates or switcher')
            continue
        own, other = ('en', 'es') if path.startswith('/en/') else ('es', 'en')
        alt = {l: urlsplit(u).path for l, u in page.alternates.items()}
        back = parsed.get(alt.get(other))
        if alt.get(own) != path or not back or {l: urlsplit(u).path for l, u in back.alternates.items()} != alt:
            errors.append(f'{path}: hreflang alternates not symmetrical: {page.alternates}')
        elif alt.get('x-default') != alt['es']:
            errors.append(f'{path}: x-default is not the Spanish page')
        if not page.switcher or urlsplit(page.switcher).path != alt.get(other):
            errors.append(f'{path}: switcher {page.switcher!r} does not match hreflang {other}')

    print(f'Checked {len(pages)} pages, {len(redirects)} redirects, {len(expected)} expected pages.')
    return errors


def main():
    dist = ROOT / 'dist'
    if not dist.is_dir():
        sys.exit('dist/ not found: run `astro build` first')
    errors = check(dist, ROOT / 'src' / 'content', english_public(ROOT / 'src' / 'i18n' / 'index.ts'))
    for e in errors:
        print(f'  {e}')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
