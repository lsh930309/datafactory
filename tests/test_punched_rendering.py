from PIL import Image, ImageChops, ImageDraw

from datafactory.rendering.punched import PunchedStyle, draw_punched_text, punched_text_size


def test_punched_text_draws_visible_marks():
    im = Image.new('RGB', (420, 120), (255, 255, 250))
    before = im.copy()
    d = ImageDraw.Draw(im)
    bbox = draw_punched_text(d, (20, 20), 'A042607-3025', PunchedStyle(scale=5, hole_radius=2.4, spacing=6, seed=7))
    diff = ImageChops.difference(im, before)
    assert bbox[2] > bbox[0]
    assert bbox[3] > bbox[1]
    assert diff.getbbox() is not None


def test_punched_text_size_is_positive():
    w, h = punched_text_size('NO.16', PunchedStyle(scale=6))
    assert w > 0
    assert h > 0
