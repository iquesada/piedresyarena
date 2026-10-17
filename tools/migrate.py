#!/usr/bin/env python3
"""One-off migration of the WordPress dump in old/ into Astro content.

Usage: python3 tools/migrate.py [--force]

Reads old/piedresy_piedresyarena.sql and old/uploads/, and writes:
  src/content/trips.yaml
  src/content/stages/es/<trip>/<stage>/index.md (+ images)
  src/content/pages/es/sobre-mi/index.md (+ images)
  src/redirects.json
"""
import argparse
import html
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DUMP = ROOT / 'old' / 'piedresy_piedresyarena.sql'
UPLOADS = ROOT / 'old' / 'uploads'
STAGES_DIR = ROOT / 'src' / 'content' / 'stages' / 'es'
PAGES_DIR = ROOT / 'src' / 'content' / 'pages' / 'es'
TRIPS_FILE = ROOT / 'src' / 'content' / 'trips.yaml'
REDIRECTS_FILE = ROOT / 'src' / 'redirects.json'
TABLES = ('pya_posts', 'pya_postmeta', 'pya_terms', 'pya_term_taxonomy', 'pya_term_relationships')
ABOUT_ID = '169'
SLIDER_ID = '700'
MAX_EDGE = 1600

# (slug, name, year, country, map colour)
TRIPS = [
    ('raid-al-magrib-2003', 'Raid Al Magrib', 2003, 'Marruecos', '#e6194b'),
    ('mongolia-bike-challenge-2010', 'Mongolia Bike Challenge', 2010, 'Mongolia', '#3cb44b'),
    ('jordania-2011', 'Jordania, de Madaba a Áqaba', 2011, 'Jordania', '#4363d8'),
    ('etiopia-wild-bike-2012', 'Etiopía Wild Bike', 2012, 'Etiopía', '#f58231'),
    ('camino-de-santiago-2013', 'Camino de Santiago con Planeta Bike', 2013, 'España', '#911eb4'),
    ('namibia-2015', 'Namibia', 2015, 'Namibia', '#42d4f4'),
    ('camino-primitivo-2016', 'Camino Primitivo', 2016, 'España', '#f032e6'),
    ('ruta-de-la-plata-2016', 'Ruta de la Plata', 2016, 'España', '#9a6324'),
    ('tanzania-2017', 'Tanzania', 2017, 'Tanzania', '#469990'),
    ('eslovenia-2018', 'Eslovenia', 2018, 'Eslovenia', '#808000'),
    ('georgia-2019', 'Georgia', 2019, 'Georgia', '#000075'),
    ('ardennes-arbalete-2022', 'Ardennes Arbalète', 2022, 'Bélgica', '#800000'),
]

# old WordPress post_name -> (trip slug, new stage slug)
STAGES = {
    'raid-al-magrib': ('raid-al-magrib-2003', 'relato'),
    'mongolia-bike-challenge-2010-primera-etapa': ('mongolia-bike-challenge-2010', 'etapa-1'),
    'mongolia-bike-challenge-2010-segunda-etapa': ('mongolia-bike-challenge-2010', 'etapa-2'),
    'mongolia-bike-challenge-2010-tercera-y-cuarta-etapas': ('mongolia-bike-challenge-2010', 'etapas-3-y-4'),
    'mongolia-bike-challenge-2010-quina-etapa': ('mongolia-bike-challenge-2010', 'etapa-5'),
    'mongolia-bike-challenge-2010-sexta-etapa': ('mongolia-bike-challenge-2010', 'etapa-6'),
    'mongolia-bike-challenge-2010-septima-etapa': ('mongolia-bike-challenge-2010', 'etapa-7'),
    'mongolia-bike-challenge-2010-octava-etapa': ('mongolia-bike-challenge-2010', 'etapa-8'),
    'mongolia-bike-challenge-2010-novena-etapa': ('mongolia-bike-challenge-2010', 'etapa-9'),
    'mongolia-bike-challenge-2010-decima-etapa': ('mongolia-bike-challenge-2010', 'etapa-10'),
    'jordania-de-madaba-a-aqaba-1': ('jordania-2011', 'etapa-1'),
    'jordania-de-madaba-a-aqaba-2': ('jordania-2011', 'etapa-2'),
    'jordania-de-madaba-a-aqaba-3': ('jordania-2011', 'etapa-3'),
    'jordania-de-madaba-a-aqaba-4': ('jordania-2011', 'etapa-4'),
    'jordania-de-madaba-a-aqaba-5': ('jordania-2011', 'etapa-5'),
    'jordania-de-madaba-a-aqaba-6': ('jordania-2011', 'etapa-6'),
    'etiopia-wild-bike-1': ('etiopia-wild-bike-2012', 'etapa-1'),
    'etiopia-wild-bike-2': ('etiopia-wild-bike-2012', 'etapa-2'),
    'etiopia-wild-bike-3': ('etiopia-wild-bike-2012', 'etapa-3'),
    'etiopia-wild-bike-4': ('etiopia-wild-bike-2012', 'etapa-4'),
    'etiopia-wild-bike-5': ('etiopia-wild-bike-2012', 'etapa-5'),
    'etiopia-wild-bike-6': ('etiopia-wild-bike-2012', 'etapa-6'),
    'etiopia-wild-bike-7': ('etiopia-wild-bike-2012', 'etapa-7'),
    'etiopia-wild-bike-8': ('etiopia-wild-bike-2012', 'etapa-8'),
    'etiopia-wild-bike-9': ('etiopia-wild-bike-2012', 'etapa-9'),
    'camino-de-santiago-planeta-bike': ('camino-de-santiago-2013', 'relato'),
    'namibia-1-de-otjiwarongo-a-outjo': ('namibia-2015', '1-de-otjiwarongo-a-outjo'),
    'namibia-2-de-outjo-a-khorixas': ('namibia-2015', '2-de-outjo-a-khorixas'),
    'namibia-3-de-khorixas-al-monte-brandberg': ('namibia-2015', '3-de-khorixas-al-monte-brandberg'),
    'namibia-4-del-monte-brandberg-a-uis': ('namibia-2015', '4-del-monte-brandberg-a-uis'),
    'namibia-5-de-uis-a-henties-bay': ('namibia-2015', '5-de-uis-a-henties-bay'),
    'namibia-6-de-henties-bay-a-swakopmund': ('namibia-2015', '6-de-henties-bay-a-swakopmund'),
    'namibia-7-de-swakopmund-a-walvis-bay': ('namibia-2015', '7-de-swakopmund-a-walvis-bay'),
    'namibia-8-daan-viljoen-game-reserve': ('namibia-2015', '8-daan-viljoen-game-reserve'),
    'camino-de-santiago-primitivo-de-oviedo-a-campiello': ('camino-primitivo-2016', '1-de-oviedo-a-campiello'),
    'camino-de-santiago-primitivo-de-campiello-a-fonsagrada': ('camino-primitivo-2016', '2-de-campiello-a-fonsagrada'),
    'camino-de-santiago-primitivo-de-fonsagrada-a-melide': ('camino-primitivo-2016', '3-de-fonsagrada-a-melide'),
    'camino-de-santiago-primitivo-de-melide-a-santiago-de-compostela': ('camino-primitivo-2016', '4-de-melide-a-santiago-de-compostela'),
    'ruta-la-plata-bejar-salamanca': ('ruta-de-la-plata-2016', '1-de-bejar-a-salamanca'),
    'ruta-la-plata-salamanca-granja-la-moreruela': ('ruta-de-la-plata-2016', '2-de-salamanca-a-granja-de-moreruela'),
    'ruta-la-plata-granja-la-moreruela-hospital-orbigo': ('ruta-de-la-plata-2016', '3-de-granja-de-moreruela-a-hospital-de-orbigo'),
    'ruta-de-la-plata-de-hospital-de-orbigo-a-poladura-de-la-tercia': ('ruta-de-la-plata-2016', '4-de-hospital-de-orbigo-a-poladura-de-la-tercia'),
    'tanzania-1-moshi-lake-chala': ('tanzania-2017', '1-moshi-lake-chala'),
    'tanzania-2-lake-chala-kamwanga': ('tanzania-2017', '2-lake-chala-kamwanga'),
    'tanzania-3-de-kamwanga-a-olpopongi': ('tanzania-2017', '3-de-kamwanga-a-olpopongi'),
    'tanzania-4-de-olpopongi-a-kikuletwa-hot-spring': ('tanzania-2017', '4-de-olpopongi-a-kikuletwa-hot-spring'),
    'tanzania-5-de-kikuletwa-hot-spring-a-arusha': ('tanzania-2017', '5-de-kikuletwa-hot-spring-a-arusha'),
    'eslovenia-1-de-ljubliana-al-lago-bled': ('eslovenia-2018', '1-de-ljubliana-al-lago-bled'),
    'eslovenia-2-de-bled-a-finkenstein': ('eslovenia-2018', '2-de-bled-a-finkenstein'),
    'eslovenia-3-de-finkestein-a-bovec': ('eslovenia-2018', '3-de-finkestein-a-bovec'),
    'eslovenia-4-de-bovec-a-kanal': ('eslovenia-2018', '4-de-bovec-a-kanal'),
    'eslovenia-5-de-kanal-a-postojna': ('eslovenia-2018', '5-de-kanal-a-postojna'),
    'eslovenia-6-de-postojna-a-ljubliana': ('eslovenia-2018', '6-de-postojna-a-ljubliana'),
    'georgia-1-de-tblisi-a-zhinvali': ('georgia-2019', '1-de-tblisi-a-zhinvali'),
    'georgia-2-de-zhinvali-a-atabe': ('georgia-2019', '2-de-zhinvali-a-atabe'),
    'georgia-3-de-atabe-a-shatili': ('georgia-2019', '3-de-atabe-a-shatili'),
    'georgia-4-shatili': ('georgia-2019', '4-shatili'),
    'georgia-5-de-shatili-a-zhinvali': ('georgia-2019', '5-de-shatili-a-zhinvali'),
    'georgia-6-de-zhinvali-a-telavi': ('georgia-2019', '6-de-zhinvali-a-telavi'),
    'ardennes-arbalete-1': ('ardennes-arbalete-2022', 'etapa-1'),
    'ardennes-arbalete-2': ('ardennes-arbalete-2022', 'etapa-2'),
    'ardennes-arbalete-3': ('ardennes-arbalete-2022', 'etapa-3'),
    'ardennes-arbalete-4': ('ardennes-arbalete-2022', 'etapa-4'),
    'ardennes-arbalete-5': ('ardennes-arbalete-2022', 'etapa-5'),
}


# --- SQL dump -----------------------------------------------------------------

SQL_ESCAPES = {'0': '\0', 'b': '\b', 'n': '\n', 'r': '\r', 't': '\t', 'Z': '\x1a'}
INSERT = re.compile(r'INSERT INTO `(\w+)` \(([^)]*)\) VALUES')
BARE = re.compile(r'[^,)\s]+')


def parse_tuples(s, i=0):
    """Parse `(…), (…);` starting at s[i]. Returns (rows, index after the `;`)."""
    rows, row = [], None
    while i < len(s):
        c = s[i]
        if c == '(':
            row, i = [], i + 1
        elif c == ')':
            rows.append(row)
            row, i = None, i + 1
        elif c == ';' and row is None:
            return rows, i + 1
        elif c in ', \t\r\n':
            i += 1
        elif c == "'":
            buf, i = [], i + 1
            while True:
                c = s[i]
                if c == '\\':
                    buf.append(SQL_ESCAPES.get(s[i + 1], s[i + 1]))
                    i += 2
                elif c == "'" and s[i + 1:i + 2] == "'":
                    buf.append("'")
                    i += 2
                elif c == "'":
                    i += 1
                    break
                else:
                    buf.append(c)
                    i += 1
            row.append(''.join(buf))
        else:
            m = BARE.match(s, i)
            row.append(None if m.group() == 'NULL' else m.group())
            i = m.end()
    return rows, i


def load_dump(text, tables=TABLES):
    out = {t: [] for t in tables}
    for m in INSERT.finditer(text):
        if m.group(1) not in out:
            continue
        cols = [c.strip(' `') for c in m.group(2).split(',')]
        rows, _ = parse_tuples(text, m.end())
        out[m.group(1)] += [dict(zip(cols, r)) for r in rows]
    return out


# --- YAML / Markdown ------------------------------------------------------------

def yaml_value(v):
    # JSON strings are valid YAML double-quoted scalars.
    return str(v) if isinstance(v, (int, float)) else json.dumps(v, ensure_ascii=False)


def front_matter(fields):
    lines = [f'{k}: {v if k == "date" else yaml_value(v)}' for k, v in fields.items() if v is not None]
    return '---\n' + '\n'.join(lines) + '\n---\n'


def clean_text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s))).strip()


def md_image(path, alt='', title=''):
    alt = re.sub(r'([\\\[\]])', r'\\\1', clean_text(alt))
    title = clean_text(title).replace('\\', '\\\\').replace('"', '\\"')
    return f'\n\n![{alt}]({path}' + (f' "{title}"' if title else '') + ')\n\n'


def gallery(images):
    return '\n\n<div class="gallery">\n\n' + ''.join(images) + '\n\n</div>\n\n'


def embed(src):
    return f'\n\n<div class="embed"><iframe src="{src}" title="YouTube" loading="lazy" allowfullscreen></iframe></div>\n\n'


def attr(tag, name):
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return html.unescape(m.group(1)) if m else ''


IMG = re.compile(r'<img\b[^>]*>')
YOUTUBE = re.compile(r'^[ \t]*https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)\S*[ \t]*$', re.M)


def convert_body(content, image, slider=()):
    """WordPress post_content -> Markdown. `image(url)` returns the local path ('./x.jpg') or None if missing."""

    def img_md(tag, caption=''):
        path = image(attr(tag, 'src'))
        return md_image(path, attr(tag, 'alt'), caption) if path else ''

    def caption(m):
        tag = IMG.search(m.group(1))
        if not tag:
            return m.group(0)
        return img_md(tag.group(), m.group(1)[tag.end():])  # md_image strips the closing </a>

    def tabs(m):
        urls = re.findall(r'\[imagetab[^\]]*\]\s*(\S+?)\s*\[/imagetab\]', m.group(1))
        return gallery([md_image(p) for p in map(image, urls) if p])

    s = content.replace('\r\n', '\n').replace('<!--more-->', '')
    s = re.sub(r'\[button[^\]]*\].*?\[/button\]', '', s, flags=re.S)
    s = re.sub(r'^<div>(.*?)</div>', r'\1', s, flags=re.S | re.M)
    s = re.sub(r'^<p(?: [^>]*)?>(.*?)</p>', r'\1', s, flags=re.S | re.M)
    s = re.sub(r'\[caption[^\]]*\](.*?)\[/caption\]', caption, s, flags=re.S)
    s = re.sub(r'<a\b[^>]*>\s*(<img\b[^>]*>)\s*</a>', r'\1', s)
    s = IMG.sub(lambda m: img_md(m.group()), s)
    s = re.sub(r'\[tabs[^\]]*\](.*?)\[/tabs\]', tabs, s, flags=re.S)
    s = re.sub(r'\[easingslider[^\]]*\]', lambda m: gallery([md_image(p, alt) for p, alt in slider]), s)
    # Existing iframes first: the bare-URL embeds below contain an iframe that must not be wrapped again.
    s = re.sub(r'<iframe\b[^>]*>\s*</iframe>', lambda m: embed(attr(m.group(), 'src')), s)
    s = YOUTUBE.sub(lambda m: embed(f'https://www.youtube-nocookie.com/embed/{m.group(1)}'), s)
    s = re.sub(r'<span style="text-decoration: line-through;">(.*?)</span>', r'~~\1~~', s)
    s = re.sub(r'<del>(.*?)</del>', r'~~\1~~', s)
    s = re.sub(r'<span style="[^"]*">(.*?)</span>', r'\1', s, flags=re.S)
    s = re.sub(r'(<\w+) style="[^"]*"', r'\1', s)
    s = re.sub(r'^[ \t]*(&nbsp;|\xa0)[ \t]*$', '', s, flags=re.M)
    s = re.sub(r'[ \t]+$|^[ \t]+', '', s, flags=re.M)
    return re.sub(r'\n{3,}', '\n\n', s).strip() + '\n'


# --- Images ---------------------------------------------------------------------

def original_upload(rel, uploads=UPLOADS):
    """Prefer the original over WordPress's -WxH / -scaled derivatives when it exists."""
    orig = re.sub(r'(?:-scaled)?(?:-\d+x\d+)?(?=\.\w+$)', '', rel)
    return orig if (uploads / orig).is_file() else rel


def save_image(src, dst):
    """Copy with orientation applied, long edge <= MAX_EDGE, and no EXIF."""
    with Image.open(src) as im:
        fmt = im.format
        out = ImageOps.exif_transpose(im)
        out.thumbnail((MAX_EDGE, MAX_EDGE))
        if fmt in ('JPEG', 'MPO'):  # MPO: camera multi-picture JPEG, first frame is the photo
            out.convert('RGB').save(dst, 'JPEG', quality=85, optimize=True, icc_profile=im.info.get('icc_profile'))
        elif fmt == 'PNG':
            out.save(dst, 'PNG', optimize=True)
        else:
            raise ValueError(f'unsupported image format {fmt}: {src}')


class Folder:
    """Copies uploads into one content folder, once per source file."""

    def __init__(self, path, report):
        self.path, self.report, self.copied = path, report, {}

    def add(self, rel):
        rel = original_upload(unquote(rel).lstrip('/'))
        if rel in self.copied:
            return self.copied[rel]
        if not (UPLOADS / rel).is_file():
            self.report['missing'].append(f'{self.path.relative_to(ROOT)}: {rel}')
            return None
        ascii_name = unicodedata.normalize('NFKD', Path(rel).name).encode('ascii', 'ignore').decode()  # iñaki -> inaki
        name = re.sub(r'[^A-Za-z0-9_.-]+', '-', ascii_name)
        if any(p == f'./{name}' for p in self.copied.values()):
            name = '-'.join(Path(rel).parent.parts) + '-' + name
        self.path.mkdir(parents=True, exist_ok=True)
        save_image(UPLOADS / rel, self.path / name)
        self.report['images'] += 1
        self.copied[rel] = f'./{name}'
        return self.copied[rel]

    def url(self, url):
        if '/wp-content/uploads/' not in url:
            self.report['unmapped'].append(f'{self.path.relative_to(ROOT)}: {url}')
            return None
        return self.add(url.split('/wp-content/uploads/', 1)[1])


# --- Main -----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--force', action='store_true', help='delete previous output and regenerate it')
    args = ap.parse_args()

    targets = [STAGES_DIR, PAGES_DIR, TRIPS_FILE, REDIRECTS_FILE]
    existing = [t for t in targets if t.exists()]
    if existing and not args.force:
        sys.exit('Refusing to overwrite (use --force): ' + ', '.join(str(t.relative_to(ROOT)) for t in existing))
    for t in existing:
        shutil.rmtree(t) if t.is_dir() else t.unlink()

    db = load_dump(DUMP.read_text(encoding='utf-8'))
    posts = {p['ID']: p for p in db['pya_posts']}
    meta = defaultdict(dict)
    for m in db['pya_postmeta']:
        meta[m['post_id']][m['meta_key']] = m['meta_value']
    attached = lambda att_id: meta[str(att_id)].get('_wp_attached_file')

    listings = {p['post_name']: p for p in posts.values() if p['post_type'] == 'listing' and p['post_status'] == 'publish'}
    unknown, stale = sorted(set(listings) - set(STAGES)), sorted(set(STAGES) - set(listings))
    if unknown or stale:
        sys.exit(f'STAGES out of sync with the dump. Not in STAGES: {unknown}. Not published: {stale}')
    trip_ids = {t[0] for t in TRIPS}
    if bad := {t for t, _ in STAGES.values()} ^ trip_ids:
        sys.exit(f'TRIPS and STAGES disagree on: {sorted(bad)}')
    if len(set(STAGES.values())) != len(STAGES):
        sys.exit('Duplicate stage slugs in STAGES')

    report = {'images': 0, 'missing': [], 'unmapped': [], 'leftovers': []}

    def check(path, body):
        rel = path.relative_to(ROOT)
        without_images = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', body)
        report['leftovers'] += [f'{rel}: {m}' for m in re.findall(r'\[/?[a-z_]+\b[^\]]*\]', without_images)]
        report['leftovers'] += [f'{rel}: raw <img>' for _ in IMG.findall(body)]
        report['unmapped'] += [f'{rel}: {m}' for m in re.findall(r'\S*piedresyarena\.com\S*', body)]

    def seo(m):
        return {'seoTitle': clean_text(m.get('_yoast_wpseo_title', '')) or None,
                'seoDescription': clean_text(m.get('_yoast_wpseo_metadesc', '')) or None}

    TRIPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRIPS_FILE.write_text(''.join(
        f'- id: {yaml_value(s)}\n  name: {yaml_value(n)}\n  year: {y}\n  country: {yaml_value(c)}\n  color: {yaml_value(col)}\n'
        for s, n, y, c, col in TRIPS), encoding='utf-8')

    for old, post in listings.items():
        trip, slug = STAGES[old]
        m = meta[post['ID']]
        folder = Folder(STAGES_DIR / trip / slug, report)
        cover = folder.add(attached(m.get('_thumbnail_id')) or f'missing-thumbnail-of-{old}')
        body = convert_body(post['post_content'], folder.url)
        fields = {
            'title': clean_text(post['post_title']),
            'date': post['post_date'][:10],
            'trip': trip,
            'lat': float(m['_et_listing_lat']),
            'lng': float(m['_et_listing_lng']),
            'address': clean_text(m.get('_et_listing_custom_address', '')) or None,
            'description': clean_text(m.get('_et_listing_description', '')),
            'image': cover,
            **seo(m),
            'translationKey': f'{trip}/{slug}',
        }
        (folder.path / 'index.md').write_text(front_matter(fields) + '\n' + body, encoding='utf-8')
        check(folder.path / 'index.md', body)

    about = posts[ABOUT_ID]
    folder = Folder(PAGES_DIR / 'sobre-mi', report)
    slides_meta = meta[SLIDER_ID].get('_easingslider', '')
    slides = re.findall(r'"attachment_id";i:(\d+);.*?"alt";s:\d+:"(.*?)";', slides_meta)
    slider = [(p, alt) for p, alt in ((folder.add(attached(i) or f'missing-attachment-{i}'), alt) for i, alt in slides) if p]
    body = convert_body(about['post_content'], folder.url, slider)
    fields = {'title': clean_text(about['post_title']), **seo(meta[ABOUT_ID]), 'translationKey': 'sobre-mi'}
    folder.path.mkdir(parents=True, exist_ok=True)
    (folder.path / 'index.md').write_text(front_matter(fields) + '\n' + body, encoding='utf-8')
    check(folder.path / 'index.md', body)

    # Redirects: every old stage, every taxonomy term with published stages, and the about page.
    redirects = {f'/listing/{old}/': f'/viajes/{t}/{s}/' for old, (t, s) in STAGES.items()}
    terms = {t['term_id']: t['slug'] for t in db['pya_terms']}
    taxonomy = {t['term_taxonomy_id']: (t['taxonomy'], terms[t['term_id']]) for t in db['pya_term_taxonomy']}
    by_id = {p['ID']: STAGES[name][0] for name, p in listings.items()}
    term_trips = defaultdict(set)
    for r in db['pya_term_relationships']:
        tax = taxonomy.get(r['term_taxonomy_id'])
        if tax and tax[0] in ('listing_type', 'listing_location') and r['object_id'] in by_id:
            term_trips[tax].add(by_id[r['object_id']])
    ids = {p['ID']: name for name, p in listings.items()}
    for m in db['pya_postmeta']:
        if m['meta_key'] == '_wp_old_slug' and m['post_id'] in ids:
            redirects.setdefault(f'/listing/{m["meta_value"]}/', redirects[f'/listing/{ids[m["post_id"]]}/'])
    for (tax, slug), trips in sorted(term_trips.items()):
        redirects[f'/{tax}/{slug}/'] = f'/viajes/{next(iter(trips))}/' if len(trips) == 1 else '/'
    redirects['/a-los-pedales/'] = '/sobre-mi/'
    REDIRECTS_FILE.write_text(json.dumps(redirects, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print(f'Trips:      {len(TRIPS)}')
    print(f'Stages:     {len(listings)}')
    print('Pages:      1 (sobre-mi)')
    print(f'Images:     {report["images"]}')
    print(f'Redirects:  {len(redirects)}')
    problems = 0
    for key, label in (('missing', 'Missing images'), ('leftovers', 'Unconverted shortcodes/HTML'), ('unmapped', 'Unmapped internal links')):
        print(f'{label}: {len(report[key])}')
        for line in report[key]:
            print(f'  {line}')
        problems += len(report[key])
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
