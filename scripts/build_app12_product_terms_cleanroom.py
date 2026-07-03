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
    alpha_composite_logical,
    finish_supersampled_page,
    new_supersampled_page,
    paste_logical,
)
from datafactory.cleanroom_assets import paste_asset_center, paste_cleanroom_asset
from PIL import Image, ImageDraw, ImageFont, ImageFilter, JpegImagePlugin

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'cleanroom_trials' / 'APP-12_약관·상품설명서'
PAGES = OUT / 'pages'
QA = OUT / 'qa'
WB = ROOT / 'workbench' / 'documents' / '약관·상품설명서__APP-12'
SRC_DIR = WB / 'samples' / 'original'
PROGRESS = ROOT / 'docs/reports/cleanroom/20260702_app12_product_terms_cleanroom_trial.md'
FONTS = ROOT / 'fonts'
LOGO_SYMBOL = ROOT / 'assets' / 'logo_pool' / 'app12' / 'onyu_generated_symbol_v1.png'
SYSTEM_FONTS = [
    Path('/System/Library/Fonts/AppleSDGothicNeo.ttc'),
    Path('/System/Library/Fonts/Supplemental/AppleGothic.ttf'),
]

W, H = 1191, 1684
RENDER_SCALE = DEFAULT_RENDER_SCALE
INK = (26, 29, 32)
MUTED = (92, 96, 100)
LINE = (30, 34, 38)
GOLD = (231, 204, 119)
GOLD_DARK = (158, 122, 34)
CREAM = (250, 241, 202)
GREEN = (0, 137, 121)
GREEN_DARK = (0, 93, 86)
CYAN = (204, 246, 245)
ORANGE = (255, 207, 156)
ORANGE_2 = (255, 221, 184)
BLUE = (26, 103, 165)
GRAY_BG = (248, 249, 248)
RED = (190, 54, 52)


def font(name: str, size: int, bold: bool = False):
    candidates = {
        'sans': ['malgunbd.ttf' if bold else 'malgun.ttf', 'gulim.ttc'],
        'serif': ['batang.ttc', 'malgun.ttf'],
        'gothic': ['gulim.ttc', 'malgun.ttf'],
        'mono': ['NGULIM.TTF', 'malgun.ttf'],
        'display': [],
    }
    if name == 'display':
        for path in SYSTEM_FONTS:
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
    for filename in candidates.get(name, candidates['sans']):
        path = FONTS / filename
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


F = {
    'brand': font('display', 44, True),
    'title': font('sans', 46, True),
    'title2': font('display', 37, True),
    'title_main': font('display', 38, True),
    'title_side': font('display', 35, True),
    'sub': font('sans', 21),
    'body': font('gothic', 21),
    'body_bold': font('gothic', 22, True),
    'small': font('gothic', 17),
    'tiny': font('gothic', 14),
    'label': font('gothic', 20, True),
    'footer': font('gothic', 17),
    'stamp': font('serif', 20),
    'stamp_big': font('serif', 30),
}


def clean() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    PAGES.mkdir(parents=True, exist_ok=True)
    (QA / 'pdf_rendered_pages').mkdir(parents=True, exist_ok=True)


def new_page() -> tuple[Image.Image, ScaledDraw]:
    return new_supersampled_page(W, H, (255, 255, 252), RENDER_SCALE)


def tw(d: ImageDraw.ImageDraw, text: str, fnt) -> float:
    return d.textlength(str(text), font=fnt)


def wrap(d: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    out: list[str] = []
    for para in str(text).split('\n'):
        if not para.strip():
            out.append('')
            continue
        buf = ''
        for ch in para:
            if tw(d, buf + ch, fnt) <= width:
                buf += ch
            else:
                if buf:
                    out.append(buf)
                buf = ch
        if buf:
            out.append(buf)
    return out


def draw_wrapped(d, xy, text, fnt=None, width=800, fill=INK, leading=None, max_lines=None, align='left') -> int:
    fnt = fnt or F['body']
    leading = leading or int(fnt.size * 1.45)
    x, y = xy
    lines = wrap(d, text, fnt, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    for line in lines:
        if not line:
            y += int(leading * 0.75)
            continue
        xx = x
        if align == 'center':
            xx = x + (width - tw(d, line, fnt)) / 2
        elif align == 'right':
            xx = x + width - tw(d, line, fnt)
        d.text((xx, y), line, font=fnt, fill=fill)
        y += leading
    return y


def center(d, y, text, fnt, fill=INK, x1=0, x2=W) -> None:
    d.text(((x1 + x2 - tw(d, text, fnt)) / 2, y), text, font=fnt, fill=fill)


def logo(d, x, y, scale=1.0) -> None:
    # Generated cleanroom logo mark + deterministic wordmark text for Korean lettering.
    paste_asset_center(d, 'logo', 1, x + 30 * scale, y + 35 * scale, 64 * scale, opacity=0.96)
    d.text((x + 72 * scale, y - 2 * scale), '온유은행', font=F['brand'], fill=(28, 36, 40))
    d.text((x + 76 * scale, y + 50 * scale), 'ONYU BANK', font=F['tiny'], fill=GOLD_DARK)


def draw_header(d, title='생활든든 신용대출 상품설명서') -> None:
    d.rectangle([0, 0, W, 214], fill=CREAM)
    for yy in range(0, 214, 7):
        col = (250, 239 + yy // 35, 198)
        d.line([0, yy, W, yy], fill=col)
    logo(d, 58, 24, 1.05)
    d.text((612, 53), '준법감시인 심의필번호 : 제2026-상품-0418호', font=F['small'], fill=INK)
    d.text((781, 86), '( 2026.06.25 )', font=F['small'], fill=INK)
    d.rounded_rectangle([342, 119, 835, 186], radius=13, fill=(255, 255, 248), outline=(234, 222, 182), width=2)
    center(d, 132, '생활든든 신용대출', F['title_main'], x1=342, x2=835)
    d.text((872, 129), '상품설명서', font=F['title_side'], fill=GOLD_DARK)
    d.line([0, 208, W, 208], fill=(173, 162, 23), width=5)


def cell_text_center(d, box, text, fnt, fill=INK, leading=None) -> None:
    x1, y1, x2, y2 = box
    fitted = fnt
    fitted_leading = leading or int(fitted.size * 1.30)
    lines = wrap(d, text, fitted, x2 - x1 - 16)
    while lines and len(lines) * fitted_leading > (y2 - y1 - 12) and fitted.size > 13:
        fitted = font('gothic', fitted.size - 1, True)
        fitted_leading = int(fitted.size * 1.23)
        lines = wrap(d, text, fitted, x2 - x1 - 16)
    fnt = fitted
    leading = fitted_leading
    total = len(lines) * leading
    yy = y1 + ((y2 - y1) - total) / 2
    for line in lines:
        center(d, int(yy), line, fnt, fill=fill, x1=x1 + 8, x2=x2 - 8)
        yy += leading


def row(d, y, label, body, height, label_fill=ORANGE, body_fill=(255, 255, 253), top_width=2) -> int:
    x = 58
    label_w = 183
    full_w = W - 116
    d.rectangle([x, y, x + full_w, y + height], fill=body_fill, outline=LINE, width=1)
    d.rectangle([x, y, x + label_w, y + height], fill=label_fill, outline=LINE, width=1)
    if top_width > 1:
        d.line([x, y, x + full_w, y], fill=LINE, width=top_width)
    cell_text_center(d, [x + 8, y, x + label_w - 8, y + height], label, F['label'])
    yy = y + 15
    for part in body:
        if isinstance(part, tuple):
            text, style = part
            fnt = F['body_bold'] if style == 'bold' else F['body']
            fill = BLUE if style == 'blue' else INK
        else:
            text, fnt, fill = part, F['body'], INK
        yy = draw_wrapped(d, (x + label_w + 16, yy), text, fnt, width=full_w - label_w - 34, fill=fill, leading=int(fnt.size * 1.34))
        yy += 3
    return y + height


def bullet_box(d, x, y, w, h, lines) -> None:
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=(247, 232, 181), outline=(212, 196, 138), width=1)
    yy = y + 18
    for line in lines:
        d.text((x + 24, yy), '•', font=F['footer'], fill=BLUE)
        yy = draw_wrapped(d, (x + 46, yy), line, F['footer'], width=w - 72, fill=INK, leading=24)
        yy += 3


def page1() -> Image.Image:
    im, d = new_page()
    draw_header(d)
    y = 235
    y = row(d, y, '상품명 및 특징', [
        ('상품명 : 「 생활든든 신용대출 」', 'bold'),
        '특   징 : 직장인 및 안정소득자를 대상으로 거래실적, 신용도, 상환능력에 따라 한도와 금리를 차등 적용하는 무담보 개인신용대출.',
    ], 116, label_fill=CYAN, top_width=2)
    y += 6
    y = row(d, y, '1. 적용이율의\n결정방법', [
        '기준금리(금융채 6개월 또는 12개월), 가산금리, 우대금리를 합산하여 결정하며, 고객의 신용점수, 소득, 부채현황, 당행 거래실적에 따라 달라질 수 있습니다.',
    ], 92)
    y = row(d, y, '2. 이자 및 원금\n관련', [
        '① 이자는 고객이 선택한 납입일에 매월 후취합니다.',
        '② 만기일시상환은 대출기간 중 이자만 납부하고 만기에 원금을 상환합니다.',
        '③ 원리금균등분할상환은 매월 원금과 이자를 함께 납부합니다.',
    ], 138)
    y = row(d, y, '3. 수수료 등\n부대비용', [
        '* 인지세 : 약정금액이 5천만원을 초과하는 경우 관련 법령에 따라 고객과 은행이 각 50%씩 부담합니다.',
        '* 중도상환수수료 : 대출실행일로부터 3년 이내 상환 시 다음 산식으로 부과될 수 있습니다.',
        '  중도상환금액 X 수수료율 X 잔존일수 / 대출기간',
        '* 담보권 설정이 없는 신용대출은 별도 근저당 설정비용이 없습니다.',
    ], 234)
    y = row(d, y, '4. 계약기간\n관련', [
        '대출기간과 상환방법은 고객의 신용등급, 소득 안정성, 심사결과에 따라 구분됩니다.',
        '* 일시상환 : 1년 이내, 심사 후 연장 가능    * 분할상환 : 12개월 이상 60개월 이내',
    ], 116)
    y = row(d, y, '5. 최저거래금액\n또는 한도', [
        '최저 취급금액은 1백만원이며, 대출한도는 신용평가 결과와 기존 차입금 현황을 종합하여 산정합니다. 단, 마이너스통장 방식은 최고 2억원 이내에서 운용됩니다.',
    ], 98)
    y = row(d, y, '6. 담보 또는 보증\n필요여부', ['무담보, 무보증을 원칙으로 하나 심사결과에 따라 보증기관 보증 또는 별도 조건이 요청될 수 있습니다.'], 80)
    y = row(d, y, '7. 대출거래\n제한사항 및\n신청자격요건', [
        '연체, 금융질서문란, 회생·파산 절차 진행, 소득확인 곤란 또는 과다채무가 확인되는 경우 대출이 제한될 수 있습니다.',
        '재직기간, 연소득, 신용정보, 금융기관 대출현황, 카드론 및 현금서비스 이용액 등을 종합하여 심사합니다.',
    ], 142)
    y = row(d, y, '8. 차주에게\n발생할 수 있는\n불이익 및 조건', [
        '금리 상승, 신용도 하락, 연체 발생 시 이자부담이 증가하거나 한도 감액, 기한의 이익 상실, 신용정보 등록 등이 발생할 수 있습니다.',
    ], 104)
    y = row(d, y, '9. 부가혜택이\n주어지는 조건', [
        '급여이체, 자동이체, 온유카드 결제계좌 등록, 비대면 알림 동의 등 거래실적 충족 시 우대금리가 적용될 수 있습니다.',
    ], 88)
    bullet_box(d, 42, 1521, W - 84, 118, [
        '이 상품은 온유은행 개인여신부(02-6200-3180)에서 개발한 상품입니다.',
        '본 설명서는 주요 내용을 요약한 것으로, 계약 전 약관과 대출거래약정서를 반드시 확인하시기 바랍니다.',
        '분쟁 발생 시 금융감독원 또는 금융분쟁조정기구의 도움을 요청할 수 있습니다.',
    ])
    return apply_scan_finish(im, -0.05)


def section_band(d, y, title, subtitle=None, color=GREEN_DARK) -> int:
    d.rectangle([58, y, W - 58, y + 60], fill=color)
    d.text((84, y + 14), title, font=F['title2'], fill='white')
    if subtitle:
        d.text((W - 58 - tw(d, subtitle, F['small']) - 24, y + 21), subtitle, font=F['small'], fill=(230, 248, 246))
    return y + 82


def card(d, x, y, w, h, title, body, color=GREEN_DARK) -> int:
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([x + 7, y + 8, x + w + 7, y + h + 8], radius=18, fill=(0, 0, 0, 26))
    blurred = shadow.filter(ImageFilter.GaussianBlur(9))
    alpha_composite_logical(d, blurred)
    d.rounded_rectangle([x, y, x + w, y + h], radius=18, fill=(255, 255, 252), outline=(218, 224, 224), width=2)
    d.rounded_rectangle([x, y, x + w, y + 54], radius=18, fill=color)
    d.rectangle([x, y + 31, x + w, y + 54], fill=color)
    d.text((x + 22, y + 14), title, font=F['body_bold'], fill='white')
    yy = y + 76
    for line in body:
        d.text((x + 22, yy), '■' if line.startswith('핵심') else '-', font=F['small'], fill=color)
        yy = draw_wrapped(d, (x + 51, yy - 2), line.replace('핵심 ', ''), F['small'], width=w - 72, fill=INK, leading=25)
        yy += 6
    return y + h


def mini_table(d, x, y) -> int:
    widths = [190, 230, 210, 305]
    headers = ['구분', '적용 예시', '수수료율', '비고']
    rows = [
        ['1년 이내 상환', '실행 후 180일', '0.7%', '잔존기간 비례 적용'],
        ['2년차 상환', '실행 후 520일', '0.5%', '일부상환 가능'],
        ['3년 경과', '실행 후 1,096일', '면제', '별도 약정 제외'],
    ]
    h = 54
    cx = x
    d.rectangle([x, y, x + sum(widths), y + h], fill=(56, 69, 84))
    for head, w in zip(headers, widths):
        d.text((cx + 12, y + 15), head, font=F['small'], fill='white')
        cx += w
    y += h
    for i, row_values in enumerate(rows):
        cx = x
        rh = 56
        fill = (255, 255, 252) if i % 2 == 0 else (241, 247, 246)
        for value, w in zip(row_values, widths):
            d.rectangle([cx, y, cx + w, y + rh], fill=fill, outline=(195, 204, 204))
            d.text((cx + 12, y + 15), value, font=F['small'], fill=INK)
            cx += w
        y += rh
    return y


def flow(d, x, y) -> int:
    steps = [('상담', '필요금액\n상환계획'), ('심사', '소득·부채\n신용정보'), ('약정', '설명서 확인\n전자서명'), ('실행', '계좌입금\n사후관리')]
    gap = 25
    w = 225
    h = 95
    for i, (title, body) in enumerate(steps):
        xx = x + i * (w + gap)
        d.rounded_rectangle([xx, y, xx + w, y + h], radius=15, fill=(236, 246, 245), outline=GREEN, width=2)
        center(d, y + 12, title, F['body_bold'], fill=GREEN_DARK, x1=xx, x2=xx + w)
        draw_wrapped(d, (xx + 20, y + 49), body, F['tiny'], width=w - 40, fill=INK, leading=19, align='center')
        if i < len(steps) - 1:
            ax = xx + w + 7
            ay = y + h // 2
            d.line([ax, ay, ax + gap - 14, ay], fill=GREEN_DARK, width=3)
            d.polygon([(ax + gap - 14, ay - 8), (ax + gap - 14, ay + 8), (ax + gap - 2, ay)], fill=GREEN_DARK)
    return y + h


def stamp(d, cx, cy, text='확인', size=70) -> None:
    paste_asset_center(d, 'stamp', 3, cx, cy, size * 1.15, opacity=0.82, rotate=-2)
    center(d, cy - 15, text, F['stamp_big'], fill=RED, x1=cx - size // 2, x2=cx + size // 2)


def page2() -> Image.Image:
    im, d = new_page()
    d.rectangle([0, 0, W, 142], fill=(241, 244, 242))
    logo(d, 58, 28, 0.78)
    d.text((728, 45), '생활든든 신용대출 상품설명서', font=F['body_bold'], fill=INK)
    d.line([58, 127, W - 58, 127], fill=GREEN_DARK, width=4)
    y = section_band(d, 170, '세부 유의사항 및 소비자 권리 안내', '계약 전 필수 확인')
    card(d, 72, y, 510, 268, '01 금리 변동 및 연체', [
        '핵심 기준금리 변경, 신용도 변동, 우대조건 미충족 시 적용금리가 상승할 수 있습니다.',
        '연체 시 약정금리에 연체가산금리가 더해지며, 장기 연체는 신용정보 등록과 한도 회수의 원인이 됩니다.',
        '상환능력 대비 과도한 대출은 개인신용평점 하락으로 이어질 수 있습니다.',
    ], GREEN_DARK)
    card(d, 610, y, 510, 268, '02 계약 전 유의사항', [
        '핵심 대출 실행 전 상품설명서, 약관, 대출거래약정서, 금리산정내역서를 함께 확인해야 합니다.',
        '자동이체일, 만기일, 한도거래 방식 여부, 수수료 면제 조건을 별도로 확인하십시오.',
        '대출 가능 여부와 한도는 최종 심사 후 확정되며 상담 단계의 안내와 다를 수 있습니다.',
    ], (75, 96, 121))
    y += 308
    d.text((74, y), '중도상환수수료 산정 예시', font=F['body_bold'], fill=INK)
    d.text((74, y + 38), '아래 표는 이해를 돕기 위한 예시이며 실제 부담액은 약정조건, 상환일, 잔여기간에 따라 달라집니다.', font=F['small'], fill=MUTED)
    y = mini_table(d, 74, y + 75) + 44
    d.text((74, y), '신청 및 계약 흐름', font=F['body_bold'], fill=INK)
    y = flow(d, 92, y + 54) + 52
    card(d, 72, y, 1048, 260, '03 소비자 권리 안내', [
        '금리인하요구권 : 취업, 승진, 소득 증가, 신용도 개선 등 여건이 개선된 경우 금리 인하를 요구할 수 있습니다.',
        '청약철회권 : 법령에서 정한 기간 내 원리금과 부대비용을 반환하면 대출계약 철회를 신청할 수 있습니다.',
        '자료열람요구권 : 심사 결과에 이의가 있는 경우 관련 법령이 허용하는 범위에서 평가 근거 자료 열람을 요청할 수 있습니다.',
        '위법계약해지권 : 금융소비자보호법상 판매규제 위반이 확인되는 경우 해지를 요구할 수 있습니다.',
    ], BLUE)
    y += 300
    d.rounded_rectangle([72, y, 1120, y + 194], radius=14, fill=(255, 252, 238), outline=(217, 197, 128), width=2)
    d.text((96, y + 22), '고객 확인란', font=F['body_bold'], fill=GOLD_DARK)
    d.text((96, y + 63), '본인은 상품의 주요 내용, 비용, 위험 및 권리사항에 대한 설명을 듣고 이해하였습니다.', font=F['small'], fill=INK)
    label_y = y + 116
    line_y = y + 133
    d.text((202, label_y), '고객명', font=F['tiny'], fill=MUTED)
    d.line([270, line_y, 555, line_y], fill=LINE, width=1)
    d.text((632, label_y), '설명의무 이행자', font=F['tiny'], fill=MUTED)
    d.line([780, line_y, 1015, line_y], fill=LINE, width=1)
    stamp(d, 1060, y + 98, '확인', 64)
    center(d, H - 72, '- 2 -', F['tiny'], fill=MUTED)
    return apply_scan_finish(im, 0.04)


def apply_scan_finish(im: Image.Image, angle: float = 0.0) -> Image.Image:
    rng = random.Random(20260702)
    overlay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for _ in range(180):
        x = rng.randrange(18, W - 18)
        y = rng.randrange(18, H - 18)
        c = rng.randrange(185, 235)
        a = rng.randrange(12, 30)
        od.point((x, y), fill=(c, c, c, a))
    im = Image.alpha_composite(im.convert('RGBA'), overlay).convert('RGB')
    if abs(angle) > 0:
        im = im.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(255, 255, 252))
    return im


def save_pages() -> list[Path]:
    pages = [page1(), page2()]
    paths: list[Path] = []
    for i, im in enumerate(pages, 1):
        im = finish_supersampled_page(im, (W, H), RENDER_SCALE)
        path = PAGES / f'page_{i:03d}.png'
        im.save(path)
        paths.append(path)
    return paths


def images_to_pdf(page_paths: list[Path], out_pdf: Path) -> None:
    images = [Image.open(p).convert('RGB') for p in page_paths]
    images[0].save(out_pdf, save_all=True, append_images=images[1:], resolution=200)


def render_pdf(pdf: Path) -> list[Path]:
    out_dir = QA / 'pdf_rendered_pages'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    rendered: list[Path] = []
    for i, page in enumerate(doc, 1):
        zoom = 1200 / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        path = out_dir / f'rendered_{i:03d}.png'
        pix.save(str(path))
        rendered.append(path)
    return rendered


def make_contact_sheet(paths: list[Path]) -> Path:
    thumbs = []
    for p in paths:
        im = Image.open(p).convert('RGB')
        im.thumbnail((520, 735))
        thumbs.append((p, im.copy()))
    sheet = Image.new('RGB', (1120, 880), (242, 242, 239))
    d = ImageDraw.Draw(sheet)
    d.text((36, 26), 'APP-12 약관·상품설명서 cleanroom QA contact sheet', font=F['body_bold'], fill=INK)
    for i, (path, thumb) in enumerate(thumbs):
        x = 35 + i * 540
        y = 88
        d.text((x, y - 28), path.stem, font=F['small'], fill=MUTED)
        sheet.paste(thumb, (x, y))
        d.rectangle([x, y, x + thumb.width, y + thumb.height], outline=(160, 160, 160), width=1)
    out = QA / 'contact_sheet.jpg'
    sheet.save(out, quality=92)
    return out


def write_notes() -> None:
    text = '''# APP-12 약관·상품설명서 클린룸 작성 메모

## Source visual facts used
- A4 단면 상품설명서 샘플의 상단 브랜드/심의번호/상품명 카드/상품설명서 제목 구조.
- 좌측 번호 라벨과 우측 장문 설명이 결합된 격자형 상품설명 테이블.
- 하단 주의 문구 박스와 금융소비자 안내 문구의 시각적 밀도.

## Cleanroom boundaries
- 원본 은행명, 로고, 상품명, 심의번호, 연락처, URL, 문장, 금리/수수료 수치 및 페이지 이미지를 복사하지 않았다.
- 신규 가상 은행명(온유은행), 신규 상품명(생활든든 신용대출), 신규 문구/수치/표/확인란으로 구성했다.
- 로고 심볼은 built-in image generation으로 만든 프로젝트 로컬 asset을 사용하고, 한글/영문 워드마크는 글자 정확성을 위해 렌더러에서 직접 조판했다.
- PDF 본문에는 합성, 라이선스, 검수, 테스트 같은 내부 메타 문구를 넣지 않았다.

## Page plan
1. 상품명 및 특징, 적용이율, 이자/원금, 수수료, 계약기간, 한도, 담보, 제한사항, 불이익, 부가혜택 요약표
2. 금리/연체, 계약 전 유의사항, 수수료 예시, 신청 흐름, 소비자 권리, 고객 확인란
'''
    (QA / 'source_vs_cleanroom_notes.md').write_text(text, encoding='utf-8')


def write_manifest(pdf: Path, pages: list[Path], rendered: list[Path], contact: Path) -> None:
    manifest = {
        'schema_version': 1,
        'doc_id': 'APP-12',
        'title': '약관·상품설명서 클린룸 대표본',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'method': 'Pillow ImageDraw direct raster composition, then PDF packaging + external-font supersampling',
        'render_scale': RENDER_SCALE,
        'source_reference': str(SRC_DIR),
        'cleanroom_policy': 'source visual structure only; no copied bank name, logo, product name, review number, prose, contact details, or page images',
        'deliverables': {
            'pdf': str(pdf.relative_to(OUT)),
            'pages': [str(p.relative_to(OUT)) for p in pages],
            'rendered_pages': [str(p.relative_to(OUT)) for p in rendered],
            'contact_sheet': str(contact.relative_to(OUT)),
            'notes': str((QA / 'source_vs_cleanroom_notes.md').relative_to(OUT)),
        },
        'page_plan': ['summary explanation table', 'consumer rights and fee examples'],
        'logo_assets': {
            'generated_symbol': str(LOGO_SYMBOL),
            'source': 'built-in image generation tool; chroma-key background removed locally; deterministic wordmark text composed by renderer for Korean text accuracy',
        },
        'status': 'cleanroom_trial_ready',
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


def write_progress(pdf: Path, contact: Path) -> None:
    PROGRESS.write_text(f'''# 2026-07-02 APP-12 약관·상품설명서 클린룸 테스트

## 목표
- `약관·상품설명서__APP-12` 1종을 클린룸 방식으로 대표본 제작.
- 원본은 상단 제목부, 좌측 라벨/우측 본문 테이블, 하단 안내 박스 같은 시각 구조 파악에만 사용.

## 산출물
- PDF: `{pdf}`
- 페이지 PNG: `{PAGES}`
- QA contact sheet: `{contact}`
- PDF 재렌더: `{QA / 'pdf_rendered_pages'}`
- notes: `{QA / 'source_vs_cleanroom_notes.md'}`
- manifest: `{OUT / 'manifest.json'}`

## 구현 원칙
- HTML 렌더러를 사용하지 않고 Pillow 직접 드로잉 방식으로 작성.
- 가상 은행/가상 상품/신규 문구로 구성하며 원본 고유 식별정보와 문장을 사용하지 않음.
- 상단 로고 심볼은 생성형 이미지 asset을 투명 PNG로 후처리한 뒤 삽입하고, 워드마크는 렌더러에서 조판함.
- PDF 본문에는 내부 작업 조건이나 생성 메타데이터를 노출하지 않음.

## 자체 판단
- 샘플의 금융상품설명서다운 정보 밀도와 표 구조를 유지하면서, 2페이지 구성으로 소비자 권리/수수료 예시/확인란을 보강했다.
- 최종 확인은 contact sheet와 PDF 재렌더링 페이지를 기준으로 수행한다.
''', encoding='utf-8')


def promote(pdf: Path) -> None:
    dst = WB / 'samples' / 'cleanroom'
    if dst.exists():
        shutil.rmtree(dst)
    (dst / 'pages').mkdir(parents=True, exist_ok=True)
    (dst / 'qa' / 'pdf_rendered_pages').mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf, dst / 'cleanroom_product_terms.pdf')
    shutil.copy2(OUT / 'manifest.json', dst / 'manifest.json')
    for p in sorted(PAGES.glob('page_*.png')):
        shutil.copy2(p, dst / 'pages' / p.name)
    shutil.copy2(QA / 'contact_sheet.jpg', dst / 'qa' / 'contact_sheet.jpg')
    shutil.copy2(QA / 'source_vs_cleanroom_notes.md', dst / 'qa' / 'source_vs_cleanroom_notes.md')
    for p in sorted((QA / 'pdf_rendered_pages').glob('rendered_*.png')):
        shutil.copy2(p, dst / 'qa' / 'pdf_rendered_pages' / p.name)

    man_path = WB / 'manifest.json'
    if man_path.exists():
        man = json.loads(man_path.read_text(encoding='utf-8'))
    else:
        man = {'schema_version': 1, 'doc_id': 'APP-12', 'title': '약관·상품설명서'}
    files = []
    for p in [dst / 'cleanroom_product_terms.pdf', dst / 'manifest.json'] + sorted((dst / 'pages').glob('page_*.png')) + [dst / 'qa' / 'contact_sheet.jpg'] + sorted((dst / 'qa' / 'pdf_rendered_pages').glob('rendered_*.png')) + [dst / 'qa' / 'source_vs_cleanroom_notes.md']:
        files.append({'path': str(p), 'kind': 'cleanroom_trial', 'source': str(OUT)})
    man['status'] = 'cleanroom_sample_ready'
    man['cleanroom_samples'] = files
    man['updated_at'] = datetime.now().astimezone().isoformat()
    man.setdefault('artifacts', {})['cleanroom'] = {
        'pdf': str(dst / 'cleanroom_product_terms.pdf'),
        'contact_sheet': str(dst / 'qa' / 'contact_sheet.jpg'),
        'pages_dir': str(dst / 'pages'),
        'rendered_pages_dir': str(dst / 'qa' / 'pdf_rendered_pages'),
        'notes': str(dst / 'qa' / 'source_vs_cleanroom_notes.md'),
        'trial_manifest': str(dst / 'manifest.json'),
        'quality_judgement': 'pending_user_review_cleanroom_reference',
        'render_scale': RENDER_SCALE,
    }
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> None:
    clean()
    pages = save_pages()
    pdf = OUT / 'cleanroom_product_terms.pdf'
    images_to_pdf(pages, pdf)
    rendered = render_pdf(pdf)
    contact = make_contact_sheet(rendered)
    write_notes()
    write_manifest(pdf, pages, rendered, contact)
    write_progress(pdf, contact)
    promote(pdf)
    print(pdf)
    print(contact)
    print(f'pages={len(pages)} rendered={len(rendered)}')


if __name__ == '__main__':
    main()
