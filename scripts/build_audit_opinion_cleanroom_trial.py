#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import shutil
from datetime import datetime
from pathlib import Path

import fitz
from datafactory.supersample import (
    DEFAULT_RENDER_SCALE,
    ScaledDraw,
    finish_supersampled_page,
    new_supersampled_page,
)
from datafactory.cleanroom_assets import paste_asset_center, paste_cleanroom_asset
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'cleanroom_trials' / 'FIN-11_감사보고서·결산보고서'
PAGES = OUT / 'pages'
QA = OUT / 'qa'
WB = ROOT / 'workbench' / 'documents' / '감사보고서·결산보고서__FIN-11'
PROGRESS = ROOT / 'docs/reports/cleanroom/20260702_audit_opinion_cleanup.md'
FONTS = ROOT / 'fonts'

W, H = 1191, 1684  # matches source raster page size closely
RENDER_SCALE = DEFAULT_RENDER_SCALE
PAGE_PT = (595, 842)
INK = (30, 30, 30)
BLUE = (25, 72, 157)
PALE_BLUE = (233, 240, 250)
GRAY = (105, 105, 105)
LIGHT_GRAY = (228, 228, 228)
RED = (190, 38, 51)


def font(name: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = {
        'serif': ['batang.ttc', 'NanumMyeongjo.ttf', 'malgun.ttf'],
        'sans': ['malgunbd.ttf' if bold else 'malgun.ttf', 'gulim.ttc'],
        'gothic': ['gulim.ttc', 'malgun.ttf'],
        'mono': ['NGULIM.TTF', 'malgun.ttf'],
    }
    for file in candidates.get(name, candidates['serif']):
        path = FONTS / file
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()

F = {
    'cover_small': font('serif', 21),
    'cover_title': font('serif', 41),
    'cover_blue': font('serif', 44),
    'h1': font('serif', 31),
    'h2': font('serif', 24),
    'body': font('serif', 21),
    'body_small': font('serif', 18),
    'table': font('serif', 16),
    'tiny': font('serif', 13),
    'sans': font('sans', 18),
    'seal': font('serif', 20),
    'sign': font('sans', 25, True),
}

CONTENT = {
    'target_doc': '감사보고서·결산보고서 / 감사의견서',
    'company': '라온그린에너지 주식회사',
    'recipient': '주주 및 이사회 귀중',
    'auditor': '한빛회계법인',
    'audit_partner': '공인회계사 민 서 우',
    'period_current': '2025년 1월 1일부터 2025년 12월 31일까지',
    'period_prior': '2024년 1월 1일부터 2024년 12월 31일까지',
    'date': '2026년 3월 24일',
    'address': '서울특별시 영등포구 국제금융로 32',
    'phone': '02-782-4100',
    'opinion': '우리의 의견으로는 별첨된 재무제표는 라온그린에너지 주식회사의 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태와 동일로 종료되는 양 보고기간의 재무성과 및 현금흐름을 한국채택국제회계기준에 따라 중요성의 관점에서 공정하게 표시하고 있습니다.',
}

SECTIONS = [
    ('감사의견', [
        '우리는 라온그린에너지 주식회사(이하 “회사”)의 재무제표를 감사하였습니다. 해당 재무제표는 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태표, 동일로 종료되는 양 보고기간의 포괄손익계산서, 자본변동표 및 현금흐름표 그리고 유의적 회계정책의 요약을 포함한 재무제표의 주석으로 구성되어 있습니다.',
        CONTENT['opinion'],
    ]),
    ('감사의견근거', [
        '우리는 대한민국의 회계감사기준에 따라 감사를 수행하였습니다. 이 기준에 따른 우리의 책임은 이 감사보고서의 재무제표감사에 대한 감사인의 책임 단락에 기술되어 있습니다.',
        '우리는 재무제표감사와 관련된 대한민국의 윤리적 요구사항에 따라 회사로부터 독립적이며, 그러한 요구사항에 따른 기타 윤리적 책임들을 이행하였습니다. 우리가 입수한 감사증거가 감사의견을 위한 근거로서 충분하고 적합하다고 우리는 믿습니다.',
    ]),
    ('핵심감사사항', [
        '핵심감사사항은 우리의 전문가적 판단에 따라 당기 재무제표감사에서 가장 유의적인 사항입니다. 우리는 수익인식의 기간귀속, 장기공급계약의 회수가능성 및 재고자산 평가충당금 산정과 관련한 경영진의 판단을 핵심감사사항으로 식별하였습니다.',
        '우리는 계약별 검수조건, 매출인식 시점, 주요 고객의 채권 회수 이력 및 기말 이후 입금 내역을 대사하였고, 표본으로 선정한 거래에 대하여 원천증빙과 회계처리의 일관성을 확인하였습니다.',
    ]),
    ('재무제표에 대한 경영진과 지배기구의 책임', [
        '경영진은 한국채택국제회계기준에 따라 재무제표를 작성하고 공정하게 표시할 책임이 있으며, 부정이나 오류로 인한 중요한 왜곡표시가 없는 재무제표를 작성하는 데 필요하다고 결정한 내부통제에 대해서도 책임이 있습니다.',
        '지배기구는 회사의 재무보고절차의 감시에 대한 책임이 있습니다.',
    ]),
    ('재무제표감사에 대한 감사인의 책임', [
        '우리의 목적은 회사의 재무제표에 전체적으로 부정이나 오류로 인한 중요한 왜곡표시가 없는지에 대하여 합리적인 확신을 얻어 우리의 의견이 포함된 감사보고서를 발행하는 데 있습니다.',
        '감사기준에 따른 감사의 일부로서 우리는 감사의 전 과정에 걸쳐 전문가적 판단을 수행하고 전문가적 의구심을 유지합니다. 또한 부정이나 오류로 인한 중요한 왜곡표시위험을 식별하고 평가하며, 그러한 위험에 대응하는 감사절차를 설계하고 수행합니다.',
        '우리는 감사 중 식별된 유의적 내부통제 미비점, 계획된 감사범위와 시기, 감사 중 발견한 주요 사항을 지배기구와 커뮤니케이션합니다.',
    ]),
]

SUMMARY_ROWS = [
    ('유동자산', '42,615,902,000', '39,871,444,000'),
    ('비유동자산', '31,804,118,000', '29,116,230,000'),
    ('자산총계', '74,420,020,000', '68,987,674,000'),
    ('유동부채', '18,240,772,000', '17,982,501,000'),
    ('비유동부채', '9,115,340,000', '8,540,730,000'),
    ('자본총계', '47,063,908,000', '42,464,443,000'),
    ('매출액', '96,317,550,000', '88,904,882,000'),
    ('영업이익', '7,846,120,000', '6,420,050,000'),
    ('당기순이익', '5,182,904,000', '4,113,288,000'),
]


def clean_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    (path / 'pages').mkdir(parents=True, exist_ok=True)
    (path / 'qa' / 'pdf_rendered_pages').mkdir(parents=True, exist_ok=True)


def new_page(scanned=True):
    im, d = new_supersampled_page(W, H, (255, 255, 253), RENDER_SCALE)
    if scanned:
        rng = random.Random(20260702)
        for _ in range(70):
            x, y = rng.randrange(55, W - 55), rng.randrange(55, H - 55)
            c = rng.randrange(218, 245)
            r = rng.choice([1, 1, 2])
            d.ellipse([x-r, y-r, x+r, y+r], fill=(c, c, c))
    return im, d


def tw(d, text, fnt):
    return d.textlength(str(text), font=fnt)


def center(d, y, text, fnt, fill=INK, x1=0, x2=W):
    d.text(((x1 + x2 - tw(d, text, fnt)) / 2, y), text, font=fnt, fill=fill)


def wrap(d, text, fnt, width):
    lines = []
    for para in str(text).split('\n'):
        if not para.strip():
            lines.append('')
            continue
        buf = ''
        for ch in para:
            if tw(d, buf + ch, fnt) <= width:
                buf += ch
            else:
                if buf:
                    lines.append(buf)
                buf = ch
        if buf:
            lines.append(buf)
    return lines


def paragraph(d, x, y, text, fnt=None, width=840, leading=1.65, first_indent=0):
    fnt = fnt or F['body']
    for pi, para in enumerate(str(text).split('\n')):
        if not para.strip():
            y += int(fnt.size * leading * 0.7)
            continue
        lines = wrap(d, para, fnt, width - (first_indent if pi == 0 else 0))
        for li, line in enumerate(lines):
            xx = x + (first_indent if li == 0 and pi == 0 else 0)
            d.text((xx, y), line, font=fnt, fill=INK)
            y += int(fnt.size * leading)
    return y


def page_no(d, n):
    center(d, H - 72, f'- {n} -', F['tiny'], fill=GRAY)


def round_stamp(d, cx, cy, text='인', size=58):
    paste_asset_center(d, 'stamp', 1, cx, cy, size * 1.12, opacity=0.82, rotate=-1.5)
    center(d, cy - 13, text, F['seal'], fill=RED, x1=cx-size//2, x2=cx+size//2)


def square_seal(d, cx, cy, label='한빛', size=82):
    paste_asset_center(d, 'stamp', 7, cx, cy, size * 1.12, opacity=0.82, rotate=1.5)
    center(d, cy - 11, label, F['seal'], fill=RED, x1=cx-size//2, x2=cx+size//2)


def signature(d, x, y):
    paste_cleanroom_asset(d, 'signature', 1, (x - 12, y - 24, x + 270, y + 82), opacity=0.90, rotate=-1.0)


def draw_logo(d, x, y, scale=1.0):
    paste_asset_center(d, 'logo', 3, x + 34*scale, y + 33*scale, 72*scale, opacity=0.95)
    d.text((x-12*scale, y+66*scale), 'HANBIT', font=F['tiny'], fill=BLUE)


def table_pillow(d, x, y, headers, rows, widths, row_h=35):
    cx = x
    for h, w in zip(headers, widths):
        d.rectangle([cx, y, cx+w, y+row_h], outline=INK, width=1, fill=(245, 247, 250))
        center(d, y+9, h, F['table'], x1=cx, x2=cx+w)
        cx += w
    y += row_h
    for idx, row in enumerate(rows):
        cx = x
        fill = (255, 255, 253) if idx % 2 == 0 else (249, 249, 248)
        for val, w in zip(row, widths):
            d.rectangle([cx, y, cx+w, y+row_h], outline=LIGHT_GRAY, width=1, fill=fill)
            if val and val[0].isdigit():
                d.text((cx+w-tw(d, val, F['table'])-10, y+9), val, font=F['table'], fill=INK)
            else:
                d.text((cx+10, y+9), val, font=F['table'], fill=INK)
            cx += w
        y += row_h
    return y


def a_cover():
    im, d = new_page()
    center(d, 155, CONTENT['company'], F['cover_small'])
    center(d, 345, '재 무 제 표 에 대 한', F['cover_title'], fill=INK)
    center(d, 425, '감 사 의 견 서', F['cover_blue'], fill=BLUE)
    d.line([365, 505, 825, 505], fill=BLUE, width=2)
    center(d, 610, '제 9 기', F['h2'])
    center(d, 660, CONTENT['period_current'], F['body_small'])
    center(d, 750, '제 8 기', F['h2'])
    center(d, 800, CONTENT['period_prior'], F['body_small'])
    center(d, 1210, CONTENT['auditor'], F['h2'])
    draw_logo(d, 535, 1280, 0.9)
    return im


def a_toc():
    im, d = new_page()
    center(d, 170, '목              차', F['h1'], fill=BLUE)
    entries = [('독립된 감사인의 감사의견서', '1'), ('요약 재무정보', '4'), ('감사인의 확인 및 날인', '5')]
    y = 410
    for title, no in entries:
        d.text((275, y), title, font=F['body'], fill=INK)
        d.line([560, y+20, 875, y+20], fill=LIGHT_GRAY, width=1)
        d.text((900, y), no, font=F['body'], fill=INK)
        y += 115
    return im


def a_opinion_page_1():
    im, d = new_page()
    d.text((145, 110), CONTENT['auditor'], font=F['body_small'], fill=INK)
    d.text((145, 138), CONTENT['address'], font=F['tiny'], fill=GRAY)
    draw_logo(d, 995, 105, 0.9)
    center(d, 255, '독립된 감사인의 감사의견서', F['h1'], fill=BLUE)
    d.text((145, 360), CONTENT['company'], font=F['body'], fill=INK)
    d.text((145, 395), CONTENT['recipient'], font=F['body'], fill=INK)
    y = 495
    for heading, paras in SECTIONS[:2]:
        d.text((145, y), heading, font=F['h2'], fill=INK)
        y += 48
        for p in paras:
            y = paragraph(d, 145, y, p, F['body_small'], 900, 1.65, first_indent=18)
            y += 22
        y += 10
    page_no(d, 1)
    return im


def a_opinion_page_2():
    im, d = new_page()
    y = 120
    for heading, paras in SECTIONS[2:4]:
        d.text((145, y), heading, font=F['h2'], fill=INK)
        y += 48
        if heading == '핵심감사사항':
            d.rectangle([145, y, 1045, y+108], outline=(170, 188, 215), width=1, fill=PALE_BLUE)
            d.text((170, y+18), '식별한 핵심감사사항', font=F['body_small'], fill=BLUE)
            d.text((170, y+55), '① 수익인식의 기간귀속   ② 장기공급계약 회수가능성   ③ 재고자산 평가', font=F['body_small'], fill=INK)
            y += 140
        for p in paras:
            y = paragraph(d, 145, y, p, F['body_small'], 900, 1.65, first_indent=18)
            y += 22
        y += 12
    page_no(d, 2)
    return im


def a_opinion_page_3():
    im, d = new_page()
    y = 120
    heading, paras = SECTIONS[4]
    d.text((145, y), heading, font=F['h2'], fill=INK)
    y += 48
    for p in paras:
        y = paragraph(d, 145, y, p, F['body_small'], 900, 1.65, first_indent=18)
        y += 22
    y += 55
    center(d, y, CONTENT['date'], F['body'])
    y += 100
    d.text((450, y), CONTENT['auditor'], font=F['h2'], fill=INK)
    square_seal(d, 760, y+17, '한빛', 70)
    y += 95
    d.text((405, y), CONTENT['audit_partner'], font=F['body'], fill=INK)
    signature(d, 670, y-20)
    round_stamp(d, 870, y+12, '인', 60)
    y += 130
    d.rectangle([145, y, 1045, y+120], outline=LIGHT_GRAY, width=1, fill=(250,250,248))
    paragraph(d, 165, y+18, '이 감사의견서는 감사보고서일 현재로 유효한 것입니다. 감사보고서일 이후 열람일까지 회사의 재무제표에 중대한 영향을 미칠 수 있는 사건이나 상황이 발생할 수 있습니다.', F['tiny'], 860, 1.55)
    page_no(d, 3)
    return im


def a_summary_page():
    im, d = new_page()
    center(d, 140, '요 약 재 무 정 보', F['h1'], fill=BLUE)
    center(d, 195, CONTENT['company'], F['body_small'])
    d.text((145, 270), '(단위 : 원)', font=F['tiny'], fill=GRAY)
    table_pillow(d, 145, 310, ['과                        목', '제 9(당) 기', '제 8(전) 기'], SUMMARY_ROWS, [380, 260, 260], 41)
    paragraph(d, 145, 760, '위 요약 재무정보는 감사의견서 비교 산출을 위한 대표 항목만을 표시한 것이며, 재무제표 전체의 표시와 공시를 대체하지 않습니다.', F['body_small'], 900, 1.7)
    page_no(d, 4)
    return im


def a_confirm_page():
    im, d = new_page()
    center(d, 180, '감사인의 확인', F['h1'], fill=INK)
    paragraph(d, 210, 350, '본인은 라온그린에너지 주식회사의 제9기 재무제표에 대한 감사절차를 수행하였으며, 감사기준에 따른 충분하고 적합한 감사증거를 입수하였습니다.', F['body'], 780, 1.75, first_indent=30)
    paragraph(d, 210, 540, '감사의견의 형성 과정에서 회사의 회계정책, 추정의 합리성, 재무제표 표시 및 주석 공시의 적정성을 검토하였습니다.', F['body'], 780, 1.75, first_indent=30)
    center(d, 850, CONTENT['date'], F['body'])
    d.text((395, 1030), CONTENT['auditor'], font=F['h2'], fill=INK)
    square_seal(d, 705, 1050, '한빛', 84)
    d.text((370, 1135), CONTENT['audit_partner'], font=F['body'], fill=INK)
    signature(d, 645, 1115)
    round_stamp(d, 875, 1150, '인', 64)
    page_no(d, 5)
    return im


def save_a_pages():
    pages = [a_cover(), a_toc(), a_opinion_page_1(), a_opinion_page_2(), a_opinion_page_3(), a_summary_page(), a_confirm_page()]
    paths = []
    for i, im in enumerate(pages, 1):
        im = im.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=4))
        im = finish_supersampled_page(im, (W, H), RENDER_SCALE)
        p = PAGES / f'page_{i:03d}.png'
        im.save(p)
        paths.append(p)
    return paths


def images_to_pdf(paths, pdf_path):
    doc = fitz.open()
    for p in paths:
        page = doc.new_page(width=PAGE_PT[0], height=PAGE_PT[1])
        page.insert_image(fitz.Rect(0, 0, PAGE_PT[0], PAGE_PT[1]), filename=str(p))
    doc.save(pdf_path)
    doc.close()


def render_pdf(pdf_path: Path, out_dir: Path):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        p = out_dir / f'rendered_{i:03d}.png'
        pix.save(p)
        paths.append(p)
    doc.close()
    return paths



def make_contact_sheet(paths, out, title, cols=4):
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = (len(paths) + cols - 1) // cols
    cell_w, cell_h = 300, 435
    sheet = Image.new('RGB', (cols * cell_w, rows * cell_h + 58), 'white')
    d = ImageDraw.Draw(sheet)
    d.text((16, 14), title, font=F['body'], fill=INK)
    for i, p in enumerate(paths):
        im = Image.open(p).convert('RGB')
        im.thumbnail((cell_w - 25, cell_h - 55))
        x = (i % cols) * cell_w + 12
        y = (i // cols) * cell_h + 58
        d.text((x, y), p.stem, font=F['tiny'], fill=INK)
        sheet.paste(im, (x, y + 22))
    sheet.save(out, quality=92)
    return out

def clean() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    PAGES.mkdir(parents=True, exist_ok=True)
    (QA / 'pdf_rendered_pages').mkdir(parents=True, exist_ok=True)


def promote(pdf: Path, page_paths: list[Path], rendered: list[Path], contact: Path) -> None:
    dst = WB / 'samples' / 'cleanroom'
    if dst.exists():
        shutil.rmtree(dst)
    (dst / 'pages').mkdir(parents=True, exist_ok=True)
    (dst / 'qa' / 'pdf_rendered_pages').mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf, dst / 'audit_opinion_cleanroom_pillow.pdf')
    shutil.copy2(OUT / 'manifest.json', dst / 'manifest.json')
    for p in page_paths:
        shutil.copy2(p, dst / 'pages' / p.name)
    for p in rendered:
        shutil.copy2(p, dst / 'qa' / 'pdf_rendered_pages' / p.name)
    shutil.copy2(contact, dst / 'qa' / 'contact_sheet.jpg')
    mp = WB / 'manifest.json'
    man = json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else {}
    files = []
    for p in [dst/'audit_opinion_cleanroom_pillow.pdf', dst/'manifest.json'] + sorted((dst/'pages').glob('page_*.png')) + [dst/'qa'/'contact_sheet.jpg'] + sorted((dst/'qa/pdf_rendered_pages').glob('rendered_*.png')):
        files.append({'path': str(p), 'kind': 'cleanroom_trial', 'source': str(OUT)})
    man['status'] = 'cleanroom_sample_ready'
    man['cleanroom_samples'] = files
    man.setdefault('artifacts', {})['cleanroom'] = {
        'pdf': str(dst / 'audit_opinion_cleanroom_pillow.pdf'),
        'contact_sheet': str(dst / 'qa' / 'contact_sheet.jpg'),
        'pages_dir': str(dst / 'pages'),
        'rendered_pages_dir': str(dst / 'qa' / 'pdf_rendered_pages'),
        'trial_manifest': str(dst / 'manifest.json'),
        'quality_judgement': 'accepted_for_workbench_cleanroom_reference',
        'render_scale': RENDER_SCALE,
    }
    man['updated_at'] = datetime.now().astimezone().isoformat()
    mp.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding='utf-8')


def write_manifest(pdf: Path, pages: list[Path], rendered: list[Path], contact: Path) -> None:
    (OUT / 'manifest.json').write_text(json.dumps({
        'schema_version': 1,
        'doc_id': 'FIN-11',
        'title': '감사보고서·결산보고서 / 감사의견서 클린룸 대표본',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'method': 'Pillow direct drawing with external-font supersampling',
        'render_scale': RENDER_SCALE,
        'status': 'cleanroom_trial_ready',
        'deliverables': {
            'pdf': str(pdf.relative_to(OUT)),
            'pages': [str(p.relative_to(OUT)) for p in pages],
            'rendered_pages': [str(p.relative_to(OUT)) for p in rendered],
            'contact_sheet': str(contact.relative_to(OUT)),
        },
        'policy': 'cleanroom fictional company/accounting firm; no copied source names, prose, logos, stamps, or page images',
    }, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    clean()
    pages = save_a_pages()
    pdf = OUT / 'audit_opinion_cleanroom_pillow.pdf'
    images_to_pdf(pages, pdf)
    rendered = render_pdf(pdf, QA / 'pdf_rendered_pages')
    contact = make_contact_sheet(rendered, QA / 'contact_sheet.jpg', 'FIN-11 cleanroom PDF render QA')
    write_manifest(pdf, pages, rendered, contact)
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(
        f"# FIN-11 감사보고서·결산보고서 클린룸 산출물 정리\n\n"
        f"- PDF: `{pdf}`\n"
        f"- Render QA: `{contact}`\n"
        f"- render_scale: `{RENDER_SCALE}`\n"
        "- HTML/B 트랙은 폐기하고 Pillow 직접 드로잉 트랙만 정식 산출물로 유지한다.\n",
        encoding='utf-8',
    )
    promote(pdf, pages, rendered, contact)
    print(pdf)
    print(contact)
    print(f'pages={len(pages)} rendered={len(rendered)} render_scale={RENDER_SCALE}')


if __name__ == '__main__':
    main()
