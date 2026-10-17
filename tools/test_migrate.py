"""Unit tests for the pure parts of tools/migrate.py. They never read old/."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import migrate  # noqa: E402

UP = 'https://www.piedresyarena.com/wp-content/uploads/'


def fake_image(url):
    """Stand-in for Folder.url: maps upload URLs to './<basename>', anything else to None."""
    if '/wp-content/uploads/' not in url:
        return None
    return './' + url.rsplit('/', 1)[1]


def convert(content, **kw):
    return migrate.convert_body(content, fake_image, **kw)


def paragraphs(md):
    return [p for p in md.strip().split('\n\n') if p]


# --- SQL tuple tokenizer ----------------------------------------------------------

class TestParseTuples:
    def test_numbers_strings_and_null(self):
        rows, end = migrate.parse_tuples("(1, 'a', NULL, 2.5), (2, '', NULL, -3);rest")
        assert rows == [['1', 'a', None, '2.5'], ['2', '', None, '-3']]
        assert end == len("(1, 'a', NULL, 2.5), (2, '', NULL, -3);")

    def test_backslash_escapes(self):
        rows, _ = migrate.parse_tuples(r"('it\'s', 'a\"b', 'x\\y', 'l1\nl2\r\tz', '\0\Z');")
        assert rows == [["it's", 'a"b', 'x\\y', 'l1\nl2\r\tz', '\0\x1a']]

    def test_unknown_escape_keeps_the_character(self):
        rows, _ = migrate.parse_tuples(r"('100\%', 'a\_b');")
        assert rows == [['100%', 'a_b']]

    def test_doubled_quote(self):
        rows, _ = migrate.parse_tuples("('it''s', '''');")
        assert rows == [["it's", "'"]]

    def test_structural_characters_inside_strings(self):
        rows, _ = migrate.parse_tuples("('a, (b); c)', 'NULL');")
        assert rows == [['a, (b); c)', 'NULL']]

    def test_starts_at_offset_and_tolerates_newlines(self):
        s = "VALUES\n(1,'x'),\n(2,'y');\nINSERT"
        rows, end = migrate.parse_tuples(s, s.index('('))
        assert rows == [['1', 'x'], ['2', 'y']]
        assert s[end:] == '\nINSERT'

    def test_real_wordpress_row(self):
        # Shape of a pya_posts row from the dump (escaped quotes, \r\n, NULLs).
        s = (r"(1103, 1, '2020-05-10 10:00:00', 'Hoy hemos <span style=\"text-decoration: line-through;\">"
             r"disfrutado</span> sufrido.\r\n\r\n[caption id=\"attachment_1\"]x[/caption]', NULL, 'publish');")
        rows, _ = migrate.parse_tuples(s)
        assert rows[0][3] == ('Hoy hemos <span style="text-decoration: line-through;">disfrutado</span> sufrido.'
                              '\r\n\r\n[caption id="attachment_1"]x[/caption]')
        assert rows[0][4] is None and rows[0][5] == 'publish'


def test_load_dump_maps_columns_and_skips_other_tables():
    text = (
        "INSERT INTO `pya_other` (`a`) VALUES ('ignored');\n"
        "INSERT INTO `pya_terms` (`term_id`, `name`, `slug`) VALUES (1, 'Mongolia', 'mongolia'), (2, 'Ruta ''x''', NULL);\n"
        "INSERT INTO `pya_terms` (`term_id`, `name`, `slug`) VALUES (3, 'c', 'c');\n"
    )
    db = migrate.load_dump(text, tables=('pya_terms',))
    assert db == {'pya_terms': [
        {'term_id': '1', 'name': 'Mongolia', 'slug': 'mongolia'},
        {'term_id': '2', 'name': "Ruta 'x'", 'slug': None},
        {'term_id': '3', 'name': 'c', 'slug': 'c'},
    ]}


# --- Markdown / YAML escaping -----------------------------------------------------

class TestMdImage:
    def test_alt_and_title(self):
        assert migrate.md_image('./a.jpg', 'Carretera', 'Embalse') == '\n\n![Carretera](./a.jpg "Embalse")\n\n'

    def test_no_title(self):
        assert migrate.md_image('./a.jpg', 'x') == '\n\n![x](./a.jpg)\n\n'

    def test_title_quotes_and_backslashes_escaped(self):
        out = migrate.md_image('./a.jpg', '', 'El "Gran" C:\\dir')
        assert out.strip() == r'![](./a.jpg "El \"Gran\" C:\\dir")'

    def test_alt_brackets_and_backslash_escaped(self):
        out = migrate.md_image('./a.jpg', 'a [b] c\\d')
        assert out.strip() == r'![a \[b\] c\\d](./a.jpg)'

    def test_html_entities_tags_and_whitespace_cleaned(self):
        out = migrate.md_image('./a.jpg', 'Lago&nbsp;de\n  Bled', '<em>Áqaba</em> &amp; Wadi Rum')
        assert out.strip() == '![Lago de Bled](./a.jpg "Áqaba & Wadi Rum")'


class TestYaml:
    @pytest.mark.parametrize('value', [
        'Jordania, de Madaba a Áqaba', 'a: b', '"quoted"', "it's", 'back\\slash', '#e6194b', '- dash', 'line\nbreak', '',
    ])
    def test_strings_round_trip_as_json_scalars(self, value):
        out = migrate.yaml_value(value)
        assert out.startswith('"') and json.loads(out) == value

    def test_non_ascii_kept_literal(self):
        assert migrate.yaml_value('Etiopía') == '"Etiopía"'

    def test_numbers_unquoted(self):
        assert migrate.yaml_value(2010) == '2010'
        assert migrate.yaml_value(43.25) == '43.25'

    def test_front_matter_skips_none_and_leaves_date_bare(self):
        fm = migrate.front_matter({'title': 'Etapa: 1', 'date': '2010-08-01', 'lat': 47.5, 'address': None})
        assert fm == '---\ntitle: "Etapa: 1"\ndate: 2010-08-01\nlat: 47.5\n---\n'


# --- Body conversion ---------------------------------------------------------------

class TestCaptions:
    def test_caption_becomes_titled_image_in_own_paragraph(self):
        # Real snippet (Georgia).
        src = ('Texto antes.[caption id="attachment_1103" align="aligncenter" width="1024"]<img class="size-full wp-image-1103" '
               f'src="{UP}2020/05/zhinvali_dam.jpg" alt="" width="1024" height="684" /> Embalse de Zhinvali[/caption]Texto después.')
        assert paragraphs(convert(src)) == [
            'Texto antes.', '![](./zhinvali_dam.jpg "Embalse de Zhinvali")', 'Texto después.']

    def test_caption_with_lightbox_link(self):
        # Real snippet (Namibia).
        src = (f'[caption id="attachment_511" align="alignleft" width="1024"]<a href="{UP}2015/09/outjo.jpg">'
               f'<img class="wp-image-511 size-full" src="{UP}2015/09/outjo.jpg" alt="Carretera a Outjo" width="1024" '
               'height="768" /></a> Carretera a Outjo[/caption]')
        assert convert(src) == '![Carretera a Outjo](./outjo.jpg "Carretera a Outjo")\n'

    def test_caption_with_quotes_in_text(self):
        src = f'[caption]<img src="{UP}a.jpg" alt="" /> El &quot;Gran&quot; Rift[/caption]'
        assert convert(src) == '![](./a.jpg "El \\"Gran\\" Rift")\n'

    def test_caption_with_missing_image_is_dropped(self):
        out = migrate.convert_body(f'A\n\n[caption]<img src="{UP}gone.jpg" /> x[/caption]\n\nB', lambda u: None)
        assert out == 'A\n\nB\n'


class TestImages:
    def test_bare_img(self):
        assert convert(f'<img class="aligncenter" src="{UP}2003/03/IMG_0043.jpg" alt="marruecos pueblo" />') == \
            '![marruecos pueblo](./IMG_0043.jpg)\n'

    def test_lightbox_link_unwrapped(self):
        src = f'<a href="{UP}x.jpg" rel="lightbox"> <img src="{UP}x.jpg" alt="y" /> </a>'
        assert convert(src) == '![y](./x.jpg)\n'

    def test_inline_alignleft_image_splits_paragraph(self):
        # Real snippet (Raid Al Magrib).
        src = (f'<p>Primera frase. <a href="{UP}2003/03/IMG_0063.jpg"><img class="alignleft size-full wp-image-320" '
               f'alt="marruecos nieve" src="{UP}2003/03/IMG_0063.jpg" width="1024" height="768" /></a>Comenzamos la subida '
               'por una pista embarrada.</p>')
        assert paragraphs(convert(src)) == [
            'Primera frase.', '![marruecos nieve](./IMG_0063.jpg)', 'Comenzamos la subida por una pista embarrada.']

    def test_img_with_unmapped_src_removed(self):
        out = convert('Hola <img src="http://www.cosasdelperro.com/smile.png" /> adiós')
        assert '<img' not in out and out.split() == ['Hola', 'adiós']

    def test_alt_with_entities(self):
        assert convert(f'<img src="{UP}a.jpg" alt="Tom &amp; Jerry [1]" />') == r'![Tom & Jerry \[1\]](./a.jpg)' + '\n'


class TestShortcodes:
    def test_button_removed(self):
        src = ('Fin.\r\n\r\n[button link="https://www.piedresyarena.com/listing/mongolia-bike-challenge-2010-primera-etapa/" '
               'color="orange"]Etapa anterior[/button] [button link="x"]Siguiente[/button]')
        assert convert(src) == 'Fin.\n'

    def test_tabs_imagetab_become_gallery(self):
        # Real snippet (Camino de Santiago), relative and absolute imagetab URLs.
        src = ('[tabs slidertype="images" auto="yes"] [imagetab width="960" height="720"]/wp-content/uploads/2013/07/IMG_0136.jpg'
               '[/imagetab] [imagetab width="960" height="720"]/wp-content/uploads/2013/07/img_2483.jpg[/imagetab]'
               f'[imagetab width="960" height="720"]{UP}2013/07/DSCN2684.jpg[/imagetab][/tabs]')
        assert paragraphs(convert(src)) == [
            '<div class="gallery">', '![](./IMG_0136.jpg)', '![](./img_2483.jpg)', '![](./DSCN2684.jpg)', '</div>']

    def test_tabs_skip_missing_images(self):
        src = '[tabs][imagetab]/wp-content/uploads/a.jpg[/imagetab][imagetab]/elsewhere/b.jpg[/imagetab][/tabs]'
        assert paragraphs(convert(src)) == ['<div class="gallery">', '![](./a.jpg)', '</div>']

    @pytest.mark.parametrize('code', ['[easingslider id="700"]', '[easingsliderlite]', '[easingsliderlite id="700"]'])
    def test_easingslider_becomes_gallery(self, code):
        slider = [('./s1.jpg', 'Bike dog'), ('./s2.jpg', '')]
        assert paragraphs(convert(f'Intro\n\n{code}\n\nFin', slider=slider)) == [
            'Intro', '<div class="gallery">', '![Bike dog](./s1.jpg)', '![](./s2.jpg)', '</div>', 'Fin']

    def test_twelve_slides_one_per_paragraph(self):
        slider = [(f'./s{i}.jpg', f'alt {i}') for i in range(12)]
        ps = paragraphs(convert('[easingslider id="700"]', slider=slider))
        assert ps[0] == '<div class="gallery">' and ps[-1] == '</div>'
        assert ps[1:-1] == [f'![alt {i}](./s{i}.jpg)' for i in range(12)]


class TestEmbeds:
    NOCOOKIE = '<div class="embed"><iframe src="https://www.youtube-nocookie.com/embed/{}" title="YouTube" loading="lazy" allowfullscreen></iframe></div>'

    @pytest.mark.parametrize('url', [
        'http://www.youtube.com/watch?v=H5fAcNsIfoQ',
        'https://youtube.com/watch?v=H5fAcNsIfoQ&feature=youtu.be',
        'https://youtu.be/H5fAcNsIfoQ',
        '  https://www.youtube.com/watch?v=H5fAcNsIfoQ  ',
    ])
    def test_bare_youtube_url_on_own_line(self, url):
        # Real snippet (Mongolia).
        src = f'Podéis verme, brevemente, en el 3:40!!\r\n\r\n{url}\r\n\r\nFin'
        assert paragraphs(convert(src)) == ['Podéis verme, brevemente, en el 3:40!!', self.NOCOOKIE.format('H5fAcNsIfoQ'), 'Fin']

    def test_youtube_url_inside_text_untouched(self):
        src = 'Mira http://www.youtube.com/watch?v=H5fAcNsIfoQ ahora'
        assert convert(src) == src + '\n'

    def test_youtube_link_untouched(self):
        src = '<a href="http://www.youtube.com/watch?v=H5fAcNsIfoQ">Video resumen</a>'
        assert convert(src) == src + '\n'

    def test_iframe_keeps_src(self):
        src = ('<iframe width="520" height="293" src="https://www.youtube.com/embed/H5fAcNsIfoQ?feature=oembed" '
               'frameborder="0" allowfullscreen></iframe>')
        assert convert(src) == ('<div class="embed"><iframe src="https://www.youtube.com/embed/H5fAcNsIfoQ?feature=oembed" '
                                'title="YouTube" loading="lazy" allowfullscreen></iframe></div>\n')


class TestInlineCleanup:
    def test_line_through_span_becomes_strikethrough(self):
        # Real snippet (Tanzania).
        src = 'Hoy hemos <span style="text-decoration: line-through;">disfrutado</span> sufrido una noche complicada.'
        assert convert(src) == 'Hoy hemos ~~disfrutado~~ sufrido una noche complicada.\n'

    def test_del_becomes_strikethrough(self):
        # Real snippet (Camino de Santiago).
        assert convert('Fueron dos <del>fríos</del> grandes días') == 'Fueron dos ~~fríos~~ grandes días\n'

    @pytest.mark.parametrize('style', ['font-size: 13px; line-height: 19px;', 'font-size: 13px;line-height: 19px',
                                       'line-height: 12.997159004211426px'])
    def test_style_spans_stripped(self, style):
        assert convert(f'a <span style="{style}">b\nc</span> d') == 'a b\nc d\n'

    def test_style_attribute_removed_from_other_tags(self):
        assert convert('<strong style="color: red;">x</strong>') == '<strong>x</strong>\n'

    def test_more_tag_and_nbsp_lines_removed(self):
        src = 'Uno<!--more-->\r\n\r\n&nbsp;\r\n\r\n\xa0\r\n\r\n\r\n\r\nDos'
        assert convert(src) == 'Uno\n\nDos\n'

    def test_paragraph_and_div_wrappers_removed(self):
        assert convert('<p>Uno</p>\n\n<p class="x">Dos</p>\n<div>Tres</div>') == 'Uno\n\nDos\nTres\n'

    def test_trailing_and_leading_whitespace_trimmed(self):
        assert convert('  a  \n\tb\t') == 'a\nb\n'


# --- Images ------------------------------------------------------------------------

def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'')
    return path


class TestOriginalUpload:
    @pytest.mark.parametrize('derived', [
        '2013/07/IMG_0136-1024x768.jpg', '2020/05/IMG_0136-scaled.jpg', '2020/05/IMG_0136-scaled-300x225.jpg'])
    def test_prefers_existing_original(self, tmp_path, derived):
        folder = derived.rsplit('/', 1)[0]
        touch(tmp_path / folder / 'IMG_0136.jpg')
        assert migrate.original_upload(derived, tmp_path) == f'{folder}/IMG_0136.jpg'

    def test_falls_back_to_referenced_file(self, tmp_path):
        touch(tmp_path / '2020/05/IMG_20190814_163521-scaled.jpg')
        assert migrate.original_upload('2020/05/IMG_20190814_163521-scaled.jpg', tmp_path) == \
            '2020/05/IMG_20190814_163521-scaled.jpg'

    def test_plain_name_unchanged(self, tmp_path):
        assert migrate.original_upload('2013/06/capsule-512.png', tmp_path) == '2013/06/capsule-512.png'

    def test_only_strips_suffix_before_extension(self, tmp_path):
        touch(tmp_path / 'a-300x300-b.jpg')
        assert migrate.original_upload('a-300x300-b.jpg', tmp_path) == 'a-300x300-b.jpg'


def make_jpeg(path, size, orientation=None):
    im = Image.new('RGB', size, 'red')
    im.paste('blue', (0, 0, size[0] // 2, size[1] // 4))
    exif = Image.Exif()
    exif[0x010F] = 'Canon'  # Make
    if orientation:
        exif[0x0112] = orientation
    im.save(path, 'JPEG', exif=exif)
    return path


class TestSaveImage:
    def test_downscales_long_edge_to_cap(self, tmp_path):
        src = make_jpeg(tmp_path / 'big.jpg', (3200, 2000))
        migrate.save_image(src, tmp_path / 'out.jpg')
        with Image.open(tmp_path / 'out.jpg') as out:
            assert out.size == (1600, 1000)
            assert out.format == 'JPEG'

    def test_portrait_downscale(self, tmp_path):
        src = make_jpeg(tmp_path / 'tall.jpg', (1200, 2400))
        migrate.save_image(src, tmp_path / 'out.jpg')
        with Image.open(tmp_path / 'out.jpg') as out:
            assert out.size == (800, 1600)

    def test_no_upscaling(self, tmp_path):
        src = make_jpeg(tmp_path / 'small.jpg', (300, 200))
        migrate.save_image(src, tmp_path / 'out.jpg')
        with Image.open(tmp_path / 'out.jpg') as out:
            assert out.size == (300, 200)

    def test_exif_orientation_applied_and_exif_stripped(self, tmp_path):
        src = make_jpeg(tmp_path / 'rot.jpg', (400, 200), orientation=6)  # 6 = rotate 90° CW to display
        migrate.save_image(src, tmp_path / 'out.jpg')
        with Image.open(tmp_path / 'out.jpg') as out:
            assert out.size == (200, 400)
            assert 'exif' not in out.info
            assert dict(out.getexif()) == {}

    def test_rotated_large_image_capped_after_transpose(self, tmp_path):
        src = make_jpeg(tmp_path / 'rot.jpg', (3200, 2000), orientation=8)
        migrate.save_image(src, tmp_path / 'out.jpg')
        with Image.open(tmp_path / 'out.jpg') as out:
            assert out.size == (1000, 1600)

    def test_png_stays_png_without_exif(self, tmp_path):
        src = tmp_path / 'a.png'
        exif = Image.Exif()
        exif[0x010F] = 'Canon'
        Image.new('RGBA', (2000, 100), (0, 0, 0, 0)).save(src, 'PNG', exif=exif)
        migrate.save_image(src, tmp_path / 'out.png')
        with Image.open(tmp_path / 'out.png') as out:
            assert out.format == 'PNG' and out.mode == 'RGBA' and out.size == (1600, 80)
            assert dict(out.getexif()) == {}

    def test_unsupported_format_raises(self, tmp_path):
        src = tmp_path / 'a.gif'
        Image.new('P', (10, 10)).save(src, 'GIF')
        with pytest.raises(ValueError, match='unsupported image format GIF'):
            migrate.save_image(src, tmp_path / 'out.gif')


class TestFolder:
    @pytest.fixture
    def env(self, tmp_path, monkeypatch):
        uploads = tmp_path / 'uploads'
        monkeypatch.setattr(migrate, 'ROOT', tmp_path)
        monkeypatch.setattr(migrate, 'UPLOADS', uploads)
        # original_upload binds UPLOADS as a default argument at import time.
        monkeypatch.setattr(migrate.original_upload, '__defaults__', (uploads,))
        report = defaultdict(list, images=0)
        return uploads, migrate.Folder(tmp_path / 'out', report), report

    def test_copies_original_once_and_returns_relative_path(self, env):
        uploads, folder, report = env
        make_jpeg(touch(uploads / '2015/09/outjo.jpg'), (50, 40))
        assert folder.url(f'{UP}2015/09/outjo-300x225.jpg') == './outjo.jpg'
        assert folder.url(f'{UP}2015/09/outjo.jpg') == './outjo.jpg'
        assert report['images'] == 1
        assert (folder.path / 'outjo.jpg').is_file()

    def test_sanitizes_and_unquotes_filenames(self, env):
        uploads, folder, _ = env
        make_jpeg(touch(uploads / '2019/08/Foto (1) "Tbilisi".jpg'), (10, 10))
        assert folder.add('/2019/08/Foto%20(1)%20%22Tbilisi%22.jpg') == './Foto-1-Tbilisi-.jpg'

    def test_transliterates_filenames_to_ascii_but_not_alt_text(self, env):
        uploads, folder, _ = env
        make_jpeg(touch(uploads / '2022/07/iñaki-Áqaba ß.jpg'), (10, 10))
        body = migrate.convert_body(f'<img src="{UP}2022/07/i%C3%B1aki-%C3%81qaba%20%C3%9F.jpg" alt="Iñaki en Áqaba" />',
                                    folder.url)
        assert body == '![Iñaki en Áqaba](./inaki-Aqaba-.jpg)\n'
        assert (folder.path / 'inaki-Aqaba-.jpg').is_file()

    def test_same_name_in_different_months_disambiguated(self, env):
        uploads, folder, _ = env
        make_jpeg(touch(uploads / '2013/07/IMG_1.jpg'), (10, 10))
        make_jpeg(touch(uploads / '2013/08/IMG_1.jpg'), (10, 10))
        assert folder.add('2013/07/IMG_1.jpg') == './IMG_1.jpg'
        assert folder.add('2013/08/IMG_1.jpg') == './2013-08-IMG_1.jpg'

    def test_missing_and_unmapped_are_reported(self, env):
        _, folder, report = env
        assert folder.url(f'{UP}2010/01/gone.jpg') is None
        assert folder.url('http://www.cosasdelperro.com/smile.png') is None
        assert report['missing'] == ['out: 2010/01/gone.jpg']
        assert report['unmapped'] == ['out: http://www.cosasdelperro.com/smile.png']
