#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'map_pool' / 'appraisal'
TILE_CACHE = ROOT / '.cache' / 'osm_tiles'
TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
USER_AGENT = 'dataFatory-cleanroom-map-asset-prep/0.1 (+local synthetic document QA)'

# Small hand-picked domestic places. These are not intended to represent a real
# appraised property; they are cleanroom visual map backgrounds for fictional docs.
MAPS = [
    {
        'id': 'kr_wonju_ganhyeon_osm_z15',
        'label': '원주시 지정면 간현리 일대',
        'lat': 37.3666,
        'lon': 127.8288,
        'zoom': 15,
        'grid': (4, 4),
    },
    {
        'id': 'kr_paju_munsan_osm_z15',
        'label': '파주시 문산읍 일대',
        'lat': 37.8590,
        'lon': 126.7855,
        'zoom': 15,
        'grid': (4, 4),
    },
    {
        'id': 'kr_gimhae_jinyeong_osm_z15',
        'label': '김해시 진영읍 일대',
        'lat': 35.3065,
        'lon': 128.7314,
        'zoom': 15,
        'grid': (4, 4),
    },
]


def latlon_to_tile(lat: float, lon: float, z: int) -> tuple[float, float]:
    lat_rad = math.radians(lat)
    n = 2.0 ** z
    xtile = (lon + 180.0) / 360.0 * n
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile


def fetch_tile(z: int, x: int, y: int) -> Image.Image:
    TILE_CACHE.mkdir(parents=True, exist_ok=True)
    p = TILE_CACHE / str(z) / str(x) / f'{y}.png'
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        return Image.open(p).convert('RGB')
    url = TILE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    p.write_bytes(data)
    # Be gentle to the public tile service during one-time asset preparation.
    time.sleep(0.25)
    return Image.open(BytesIO(data)).convert('RGB')


def font(size: int):
    for fp in [ROOT/'fonts'/'malgun.ttf', ROOT/'fonts'/'gulim.ttc']:
        if fp.exists():
            return ImageFont.truetype(str(fp), size=size)
    return ImageFont.load_default()


def make_map(spec: dict) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    z = int(spec['zoom'])
    gx, gy = spec['grid']
    cx, cy = latlon_to_tile(float(spec['lat']), float(spec['lon']), z)
    left = math.floor(cx - gx / 2)
    top = math.floor(cy - gy / 2)
    canvas = Image.new('RGB', (gx * 256, gy * 256), 'white')
    tile_urls = []
    for ix in range(gx):
        for iy in range(gy):
            x, y = left + ix, top + iy
            canvas.paste(fetch_tile(z, x, y), (ix * 256, iy * 256))
            tile_urls.append(TILE_URL.format(z=z, x=x, y=y))

    # Fit the appraisal page map area and make it a touch more scan-like.
    target = (935, 980)
    canvas = canvas.resize(target, Image.Resampling.LANCZOS)
    canvas = canvas.filter(ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=3))
    d = ImageDraw.Draw(canvas, 'RGBA')
    # Subtle cleanroom overlay: fictional parcel area and leader labels.
    px = [(420, 515), (525, 465), (662, 515), (720, 642), (655, 765), (455, 735)]
    d.polygon(px, fill=(255, 230, 205, 115), outline=(190, 42, 42, 230))
    d.line(px + [px[0]], fill=(190, 42, 42, 230), width=5)
    f = font(24)
    d.text((515, 575), '기호 1\n128-4', font=f, fill=(170, 35, 35, 255))
    d.line([(520, 470), (455, 360)], fill=(180, 35, 35, 220), width=3)
    d.text((410, 315), '기호 2', font=f, fill=(170, 35, 35, 255))
    d.line([(650, 505), (735, 395)], fill=(180, 35, 35, 220), width=3)
    d.text((718, 350), '기호 3', font=f, fill=(170, 35, 35, 255))
    # Attribution must be visible on the map image.
    attr = '© OpenStreetMap contributors / ODbL'
    af = font(18)
    bbox = d.textbbox((0, 0), attr, font=af)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    d.rounded_rectangle([target[0]-tw-22, target[1]-th-18, target[0]-8, target[1]-5], radius=4, fill=(255,255,255,205))
    d.text((target[0]-tw-15, target[1]-th-15), attr, font=af, fill=(40,40,40,255))

    png = OUT / f"{spec['id']}.png"
    canvas.save(png)
    meta = {
        'id': spec['id'],
        'label': spec['label'],
        'path': str(png.relative_to(ROOT)),
        'source': 'OpenStreetMap standard raster tiles',
        'source_url': 'https://www.openstreetmap.org/',
        'copyright_url': 'https://www.openstreetmap.org/copyright',
        'tile_usage_policy_url': 'https://operations.osmfoundation.org/policies/tiles/',
        'license_summary': 'OpenStreetMap data is ODbL. Visible attribution is embedded in the image. Public OSM tiles were fetched once with a clear User-Agent and cached locally; do not bulk prefetch for production.',
        'attribution': '© OpenStreetMap contributors / ODbL',
        'center': {'lat': spec['lat'], 'lon': spec['lon']},
        'zoom': z,
        'tile_urls': tile_urls,
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    (OUT / f"{spec['id']}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return meta


def main() -> None:
    metas = [make_map(s) for s in MAPS]
    index = {
        'purpose': 'Cleanroom appraisal report map-image pool for fictional domestic documents.',
        'selection_policy': 'Use local files only in renderers; keep OSM attribution visible; replace with self-hosted/provider-permitted maps before high-volume generation.',
        'maps': metas,
    }
    (OUT / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'created': [m['path'] for m in metas]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
