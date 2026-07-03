#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from PIL import Image, ImageChops, ImageDraw, ImageFont

from datafactory.authoring import render_authoring_preview
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_DIR = ROOT / 'workbench' / 'documents' / '주주명부__ID-03'
AUTHORING = DOC_DIR / 'authoring'
SCHEMA_PATH = AUTHORING / 'schema.json'
STYLE_PATH = AUTHORING / 'stylesheet.json'
FAKER_PATH = AUTHORING / 'faker_profile.json'
OUT = ROOT / 'outputs' / 'style_calibration' / 'ID-03_주주명부'
ORIGINAL = DOC_DIR / 'samples' / 'original' / '4_page_001.jpg'
INPAINTED = DOC_DIR / 'inpaint' / 'original_4_page_001' / 'lama' / 'inpainted_lama.png'
FONT = ROOT / 'fonts' / 'malgun.ttf'

ORIGINAL_RECORD = {
    'list_date': '2023년  5월  8일',
    'list_date_suffix': '현재',
    'issue_date': '2023년  5월  8일',
    'company_name': '주식회사 엔식품',
    'company_address': '경기도 하남시 대성로 69번길 48',
    'representative_name': '김 영 기',
    'total_issued_shares': '10,000주',
    'attendance_total': '',
    'approval_total': '',
    'notarization_total': '',
    'par_value': '5,000원',
    'capital_amount': '50,000,000원',
}
for r in range(1, 10):
    for c in ['name', 'share_count', 'attendance_shares', 'approval_shares', 'notarization_shares', 'note']:
        ORIGINAL_RECORD[f'shareholder_{r}_{c}'] = ''
ORIGINAL_RECORD.update({
    'shareholder_1_name': '김영기',
    'shareholder_1_share_count': '10,000',
})

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data: dict) -> None:
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def temp_faker() -> Path:
    faker = load_json(FAKER_PATH)
    faker = dict(faker)
    pools = dict(faker.get('data_pools') or {})
    pools['id03_registry_profiles'] = [ORIGINAL_RECORD]
    faker['data_pools'] = pools
    path = OUT / 'calibration_faker_profile.json'
    write_json(path, faker)
    return path


def render_calibration() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    fake = temp_faker()
    result = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, fake, out_dir=OUT / 'render', seed=1, sample_id='calibration_original_values')
    return result.image


def fit_same_size(a: Image.Image, b: Image.Image) -> tuple[Image.Image, Image.Image]:
    a = a.convert('RGB')
    b = b.convert('RGB')
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.BICUBIC)
    return a, b


def make_full_comparison(rendered_path: Path) -> None:
    orig, rend = fit_same_size(Image.open(ORIGINAL), Image.open(rendered_path))
    inp = Image.open(INPAINTED).convert('RGB').resize(orig.size, Image.Resampling.BICUBIC)
    diff = ImageChops.difference(orig, rend)
    # amplify useful visual differences
    diff_amp = diff.point(lambda v: min(255, v * 3))
    blend = Image.blend(orig, rend, 0.5)
    labels = [('original', orig), ('inpainted', inp), ('calibration render', rend), ('amplified diff', diff_amp), ('50% overlay', blend)]
    scale_w = 430
    thumbs=[]
    for label, im in labels:
        t=im.copy(); t.thumbnail((scale_w, 610)); thumbs.append((label,t))
    font=ImageFont.truetype(str(FONT), 20) if FONT.exists() else ImageFont.load_default()
    sheet=Image.new('RGB',(scale_w*len(thumbs)+20*(len(thumbs)+1), 680),(245,245,242))
    d=ImageDraw.Draw(sheet)
    for i,(label,t) in enumerate(thumbs):
        x=20+i*(scale_w+20)
        d.text((x,18),label,font=font,fill=(20,20,20))
        sheet.paste(t,(x,52)); d.rectangle([x,52,x+t.width,52+t.height],outline=(150,150,150))
    sheet.save(OUT / 'full_comparison.jpg', quality=92)
    diff.save(OUT / 'full_diff.png')
    blend.save(OUT / 'full_overlay_50.png')


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    rendered=render_calibration()
    make_full_comparison(rendered)
    print('calibration', rendered)
    print('full', OUT / 'full_comparison.jpg')


if __name__ == '__main__':
    main()
