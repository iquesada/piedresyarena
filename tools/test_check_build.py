"""Unit tests for tools/check_build.py, over minimal dist/ and src/content trees built in tmp_path."""
import html
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_build  # noqa: E402

SITE = 'https://www.piedresyarena.com'

# One trip, "t", with one stage in each language. Spanish path -> English path.
PAIRS = {
    '/': '/en/',
    '/sobre-mi/': '/en/about/',
    '/viajes/t/': '/en/trips/t/',
    '/viajes/t/1-uno/': '/en/trips/t/1-one/',
}
OTHER = {**PAIRS, **{en: es for es, en in PAIRS.items()}}  # either path -> its other-language path


def page(path, public=False, body='', head='', lang=None, robots=True, alternate=True, alternates=None):
    """A built page as Base.astro renders it: lang, title, canonical, noindex while hidden,
    and hreflang plus switcher to its other-language version when public.

    alternates: hreflang -> path, replacing the default es/en/x-default triple; the switcher follows it.
    """
    english = path.startswith('/en/')
    lang = lang or ('en' if english else 'es')
    other_lang = 'es' if english else 'en'
    head += f'<title>x</title><link rel="canonical" href="{SITE}{path}">'
    if english and not public and robots:
        head += '<meta name="robots" content="noindex">'
    if alternates is None and path in OTHER:
        es, en = (OTHER[path], path) if english else (path, OTHER[path])
        alternates = {'es': es, 'en': en, 'x-default': es}
    if public and alternate and alternates:
        head += ''.join(f'<link rel="alternate" hreflang="{l}" href="{SITE}{u}">' for l, u in alternates.items())
        body = f'<a href="{alternates[other_lang]}" hreflang="{other_lang}">switch</a>' + body
    return f'<!doctype html><html lang="{lang}"><head>{head}</head><body>{body}</body></html>'


def map_div(trips):
    return f'<div data-trips="{html.escape(json.dumps(trips))}"></div>'


def run(tmp_path, public=False, pages=None, es_stages=('t/1-uno',), en_stages=None):
    """Writes the fixture trees and returns check()'s errors.

    pages: URL path -> HTML overriding the default page (None removes it); `/x/` is written as x/index.html, `/x.html` as is.
    en_stages: English folder (`<trip>/<slug>`) -> translationKey; default: t/1-one -> t/1-uno.
    """
    en_stages = {'t/1-one': 't/1-uno'} if en_stages is None else en_stages
    content, dist = tmp_path / 'src' / 'content', tmp_path / 'dist'
    content.mkdir(parents=True)
    (content / 'trips.yaml').write_text('- id: "t"\n  name: "T"\n- id: "empty"\n  name: "Sin etapas"\n')
    (content.parent / 'redirects.json').write_text('{}')
    for key in es_stages:
        f = content / 'stages' / 'es' / key / 'index.md'
        f.parent.mkdir(parents=True)
        f.write_text(f'---\ntitle: "x"\ntranslationKey: "{key}"\n---\n')
    for folder, key in en_stages.items():
        f = content / 'stages' / 'en' / folder / 'index.md'
        f.parent.mkdir(parents=True)
        f.write_text(f'---\ntitle: "x"\ntranslationKey: "{key}"\n---\n')

    built = {p: page(p, public) for pair in PAIRS.items() for p in pair}
    built.update(pages or {})
    for path, text in built.items():
        if text is None:
            continue
        f = dist / path.lstrip('/')
        f = f if f.suffix == '.html' else f / 'index.html'
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    return check_build.check(dist, content, public)


# --- A consistent site ------------------------------------------------------------

@pytest.mark.parametrize('public', [False, True])
def test_consistent_site_has_no_errors(tmp_path, public):
    assert run(tmp_path, public) == []


# --- Expected English pages ---------------------------------------------------------

class TestExpectedPages:
    @pytest.mark.parametrize('path', ['/en/trips/t/1-one/', '/en/trips/t/', '/en/', '/en/about/'])
    def test_missing_english_page(self, tmp_path, path):
        assert f'missing page {path}' in run(tmp_path, pages={path: None})

    def test_english_trip_page_expected_only_when_it_has_english_stages(self, tmp_path):
        errors = run(tmp_path, en_stages={}, pages={'/en/trips/t/': None, '/en/trips/t/1-one/': None})
        assert errors == []


# --- lang ---------------------------------------------------------------------------

class TestLang:
    def test_english_page_with_spanish_lang(self, tmp_path):
        errors = run(tmp_path, pages={'/en/about/': page('/en/about/', lang='es')})
        assert errors == ["/en/about/index.html: lang='es'"]

    def test_spanish_page_with_english_lang(self, tmp_path):
        errors = run(tmp_path, pages={'/sobre-mi/': page('/sobre-mi/', lang='en')})
        assert errors == ["/sobre-mi/index.html: lang='en'"]


# --- Links out of English -------------------------------------------------------------

class TestEnglishLinks:
    def test_english_page_linking_to_spanish_page(self, tmp_path):
        errors = run(tmp_path, pages={'/en/': page('/en/', body='<a href="/sobre-mi/">About</a>')})
        assert errors == ['/en/index.html: link out of English /sobre-mi/']

    def test_english_page_with_relative_link_out_of_english(self, tmp_path):
        errors = run(tmp_path, pages={'/en/': page('/en/', body='<a href="../viajes/t/">Trip</a>')})
        assert errors == ['/en/index.html: link out of English ../viajes/t/']

    def test_english_page_with_relative_link_within_english(self, tmp_path):
        body = '<a href="../../../about/">About</a><a href="./">Here</a><a href="../">Up</a>'
        assert run(tmp_path, pages={'/en/trips/t/1-one/': page('/en/trips/t/1-one/', body=body)}) == []

    def test_english_page_with_absolute_site_url_out_of_english(self, tmp_path):
        errors = run(tmp_path, pages={'/en/': page('/en/', body=f'<a href="{SITE}/viajes/t/">Trip</a>')})
        assert errors == [f'/en/index.html: link out of English {SITE}/viajes/t/']

    def test_english_page_linking_within_english_and_outside_the_site(self, tmp_path):
        body = '<a href="/en/about/">About</a><a href="https://en.wikipedia.org/wiki/Georgia">Wiki</a>'
        assert run(tmp_path, pages={'/en/': page('/en/', body=body)}) == []

    def test_spanish_page_may_link_anywhere(self, tmp_path):
        errors = run(tmp_path, pages={'/': page('/', body='<a href="/viajes/t/">x</a><a href="/sobre-mi/">y</a>')})
        assert errors == []

    def test_hreflang_elements_are_exempt_from_the_english_only_rule(self, tmp_path):
        # Public mode: the default English pages carry <a hreflang> and <link hreflang> to Spanish pages.
        errors = run(tmp_path, public=True)
        assert not [e for e in errors if 'link out of English' in e]


# --- Map data-trips -------------------------------------------------------------------

class TestMapData:
    def test_map_with_broken_url(self, tmp_path):
        trips = [{'url': '/en/trips/t/', 'stages': [{'url': '/en/trips/t/nope/'}]}]
        errors = run(tmp_path, pages={'/en/': page('/en/', body=map_div(trips))})
        assert errors == ['/en/index.html: broken link /en/trips/t/nope/']

    def test_map_with_spanish_url_on_english_page(self, tmp_path):
        trips = [{'url': '/viajes/t/', 'stages': [{'url': '/en/trips/t/1-one/'}]}]
        errors = run(tmp_path, pages={'/en/': page('/en/', body=map_div(trips))})
        assert errors == ['/en/index.html: link out of English /viajes/t/']

    def test_map_with_spanish_stage_url_on_english_page(self, tmp_path):
        trips = [{'url': '/en/trips/t/', 'stages': [{'url': '/viajes/t/1-uno/'}]}]
        errors = run(tmp_path, pages={'/en/': page('/en/', body=map_div(trips))})
        assert errors == ['/en/index.html: link out of English /viajes/t/1-uno/']

    def test_map_with_valid_urls(self, tmp_path):
        trips = [{'url': '/viajes/t/', 'stages': [{'url': '/viajes/t/1-uno/'}]}]
        assert run(tmp_path, pages={'/': page('/', body=map_div(trips))}) == []


# --- Hidden mode ----------------------------------------------------------------------

class TestHiddenMode:
    def test_english_page_without_noindex(self, tmp_path):
        errors = run(tmp_path, pages={'/en/trips/t/': page('/en/trips/t/', robots=False)})
        assert errors == ['/en/trips/t/index.html: not noindex while English is hidden']

    @pytest.mark.parametrize('path', ['/', '/en/'])
    @pytest.mark.parametrize('element', [
        '<link rel="alternate" hreflang="en" href="/en/">',
        '<link rel="alternate" hreflang="x-default" href="/">',
    ])
    def test_link_hreflang_on_any_page(self, tmp_path, path, element):
        errors = run(tmp_path, pages={path: page(path, head=element)})
        assert errors == [f'{path}index.html: hreflang while English is hidden']

    @pytest.mark.parametrize('path', ['/sobre-mi/', '/en/about/'])
    def test_switcher_on_any_page(self, tmp_path, path):
        errors = run(tmp_path, pages={path: page(path, body=f'<a href="{OTHER[path]}" hreflang="xx">switch</a>')})
        assert errors == [f'{path}index.html: hreflang while English is hidden']


# --- Public mode ----------------------------------------------------------------------

class TestPublicMode:
    def test_spanish_stage_without_english_version(self, tmp_path):
        errors = run(tmp_path, public=True, es_stages=('t/1-uno', 't/2-dos'),
                     pages={'/viajes/t/2-dos/': page('/viajes/t/2-dos/', True)})
        assert errors == ['no English version of stage t/2-dos', '/viajes/t/2-dos/: no hreflang alternates or switcher']

    def test_spanish_stage_without_english_version_is_fine_while_hidden(self, tmp_path):
        errors = run(tmp_path, es_stages=('t/1-uno', 't/2-dos'), pages={'/viajes/t/2-dos/': page('/viajes/t/2-dos/')})
        assert errors == []

    def test_hreflang_on_one_side_only(self, tmp_path):
        errors = run(tmp_path, public=True, pages={'/sobre-mi/': page('/sobre-mi/', True, alternate=False)})
        assert sorted(errors) == ["/en/about/: hreflang alternates not symmetrical: "
                                  f"{{'es': '{SITE}/sobre-mi/', 'en': '{SITE}/en/about/', 'x-default': '{SITE}/sobre-mi/'}}",
                                  '/sobre-mi/: no hreflang alternates or switcher']

    def test_hreflang_missing_on_both_sides(self, tmp_path):
        pages = {p: page(p, True, alternate=False) for p in ('/sobre-mi/', '/en/about/')}
        errors = run(tmp_path, public=True, pages=pages)
        assert sorted(errors) == ['/en/about/: no hreflang alternates or switcher',
                                  '/sobre-mi/: no hreflang alternates or switcher']

    def test_404_needs_no_hreflang(self, tmp_path):
        assert run(tmp_path, public=True, pages={'/404.html': page('/404.html', True)}) == []

    def test_other_html_file_needs_hreflang(self, tmp_path):
        errors = run(tmp_path, public=True, pages={'/otra.html': page('/otra.html', True)})
        assert errors == ['/otra.html: no hreflang alternates or switcher']

    def test_hreflang_pointing_to_another_page(self, tmp_path):
        alternates = {'es': '/', 'en': '/en/trips/t/', 'x-default': '/'}
        errors = run(tmp_path, public=True, pages={'/': page('/', True, alternates=alternates)})
        assert sorted(errors) == [
            f"/: hreflang alternates not symmetrical: {{'es': '{SITE}/', 'en': '{SITE}/en/trips/t/', 'x-default': '{SITE}/'}}",
            f"/en/: hreflang alternates not symmetrical: {{'es': '{SITE}/', 'en': '{SITE}/en/', 'x-default': '{SITE}/'}}",
        ]

    def test_x_default_not_spanish(self, tmp_path):
        alternates = {'es': '/', 'en': '/en/', 'x-default': '/en/'}
        errors = run(tmp_path, public=True, pages={p: page(p, True, alternates=alternates) for p in ('/', '/en/')})
        assert sorted(errors) == ['/: x-default is not the Spanish page', '/en/: x-default is not the Spanish page']

    def test_switcher_to_the_wrong_page(self, tmp_path):
        good = page('/sobre-mi/', True)
        errors = run(tmp_path, public=True, pages={'/sobre-mi/': good.replace('<a href="/en/about/"', '<a href="/en/"')})
        assert errors == ["/sobre-mi/: switcher '/en/' does not match hreflang en"]

    def test_missing_switcher(self, tmp_path):
        good = page('/en/about/', True)
        errors = run(tmp_path, public=True, pages={'/en/about/': good.replace(' hreflang="es">switch', '>switch')})
        # Without hreflang, the link to Spanish is an ordinary link out of English too.
        assert errors == ['/en/about/index.html: link out of English /sobre-mi/',
                          '/en/about/: switcher None does not match hreflang es']

    def test_switcher_to_missing_page(self, tmp_path):
        good = page('/viajes/t/', True)
        bad = good.replace('<a href="/en/trips/t/"', '<a href="/en/trips/nope/"')
        errors = run(tmp_path, public=True, pages={'/viajes/t/': bad})
        assert '/viajes/t/index.html: broken link /en/trips/nope/' in errors
        assert "/viajes/t/: switcher '/en/trips/nope/' does not match hreflang en" in errors

    def test_hreflang_to_missing_page(self, tmp_path):
        good = page('/viajes/t/1-uno/', True)
        bad = good.replace(f'hreflang="en" href="{SITE}/en/trips/t/1-one/"', f'hreflang="en" href="{SITE}/en/trips/t/gone/"')
        errors = run(tmp_path, public=True, pages={'/viajes/t/1-uno/': bad})
        assert f'/viajes/t/1-uno/index.html: broken link {SITE}/en/trips/t/gone/' in errors
        assert any(e.startswith('/viajes/t/1-uno/: hreflang alternates not symmetrical') for e in errors)


# --- english_public -------------------------------------------------------------------

class TestEnglishPublic:
    @pytest.mark.parametrize('value, expected', [('true', True), ('false', False)])
    def test_true_and_false(self, tmp_path, value, expected):
        f = tmp_path / 'index.ts'
        f.write_text(f"import x from './es';\n\n/** doc */\nexport const englishPublic = {value};\n")
        assert check_build.english_public(f) is expected

    def test_missing_setting(self, tmp_path):
        f = tmp_path / 'index.ts'
        f.write_text('export const somethingElse = true;\n')
        with pytest.raises(SystemExit, match='englishPublic not found'):
            check_build.english_public(f)

    def test_matches_the_real_file(self):
        assert check_build.english_public(check_build.ROOT / 'src' / 'i18n' / 'index.ts') in (True, False)


# --- Page -----------------------------------------------------------------------------

class TestPage:
    def test_hreflang_elements_are_not_links(self):
        p = check_build.Page('<link rel="alternate" hreflang="es" href="/a/"><a href="/b/" hreflang="es">ES</a>'
                             '<a href="/c/">c</a>')
        assert p.links == ['/c/']
        assert p.alternates == {'es': '/a/'}
        assert p.switcher == '/b/'

    def test_hreflang_urls_are_still_checked_for_existence(self):
        p = check_build.Page('<link rel="alternate" hreflang="es" href="/a/"><a href="/b/" hreflang="es">ES</a>')
        assert set(p.urls) == {'/a/', '/b/'}

    def test_lang_and_robots(self):
        p = check_build.Page('<html lang="en"><head><meta name="robots" content="noindex"></head></html>')
        assert (p.lang, p.robots) == ('en', 'noindex')

    def test_map_urls_are_links(self):
        trips = [{'url': '/en/trips/a/', 'stages': [{'url': '/en/trips/a/1/'}, {'url': '/en/trips/a/2/'}]}]
        p = check_build.Page(map_div(trips))
        assert p.links == ['/en/trips/a/', '/en/trips/a/1/', '/en/trips/a/2/']
        assert p.urls == p.links

    def test_no_hreflang(self):
        p = check_build.Page('<html lang="es"><a href="/x/">x</a></html>')
        assert p.alternates == {} and p.switcher is None
