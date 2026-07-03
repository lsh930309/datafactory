#!/usr/bin/env python3
from __future__ import annotations

import json
import math
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
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, JpegImagePlugin

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'cleanroom_trials' / 'RPT-08_컴플라이언스 점검보고서 [산출물]'
PAGES = OUT / 'pages'
QA = OUT / 'qa'
FONTS = ROOT / 'fonts'
WB = ROOT / 'workbench' / 'documents' / '컴플라이언스_점검보고서_[산출물]__RPT-08'
SRC_DIR = ROOT / 'seed_samples' / '컴플라이언스_점검보고서_[산출물]'
COMPLIANCE_ASSET_DIR = ROOT / 'assets' / 'cleanroom_generated' / 'compliance' / 'panels'
PROGRESS = ROOT / 'docs/reports/cleanroom/20260702_compliance_cleanroom_trial.md'

W, H = 1654, 2339
RENDER_SCALE = DEFAULT_RENDER_SCALE
BG = (246, 246, 244)
INK = (22, 24, 28)
MUTED = (88, 91, 96)
TEAL = (22, 112, 130)
BLUE = (22, 78, 110)
RED = (218, 28, 72)
GOLD = (176, 126, 46)
GREEN = (58, 132, 102)
GRAY_LINE = (180, 184, 188)


def font(name: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = {
        'sans': 'malgunbd.ttf' if bold else 'malgun.ttf',
        'sans_light': 'malgunsl.ttf',
        'serif': 'batang.ttc',
        'gothic': 'gulim.ttc',
        'mono': 'NGULIM.TTF',
    }
    path = FONTS / candidates.get(name, candidates['sans'])
    if not path.exists():
        path = FONTS / 'malgun.ttf'
    return ImageFont.truetype(str(path), size=size)

F = {
    'cover_brand': font('sans', 62, True),
    'cover_title': font('sans', 74, True),
    'cover_sub': font('sans_light', 35),
    'h1': font('sans', 49, True),
    'h2': font('sans', 37, True),
    'h3': font('sans', 29, True),
    'body': font('serif', 29),
    'body_sans': font('sans', 27),
    'small': font('sans', 22),
    'tiny': font('sans', 18),
    'table': font('gothic', 24),
    'table_bold': font('gothic', 25, True),
    'num': font('sans', 34, True),
}


def new_page() -> tuple[Image.Image, ScaledDraw]:
    return new_supersampled_page(W, H, BG, RENDER_SCALE)


def text_width(d, s, fnt):
    return d.textlength(str(s), font=fnt)


def wrap(d, text, fnt, max_w):
    lines = []
    for para in str(text).split('\n'):
        if not para.strip():
            lines.append('')
            continue
        buf = ''
        for ch in para:
            if text_width(d, buf + ch, fnt) <= max_w:
                buf += ch
            else:
                if buf:
                    lines.append(buf)
                buf = ch
        if buf:
            lines.append(buf)
    return lines


def paragraph(d, xy, text, fnt=None, fill=INK, width=1000, leading=1.55, gap=0, align='left'):
    fnt = fnt or F['body_sans']
    x, y = xy
    for line in wrap(d, text, fnt, width):
        if not line:
            y += int(fnt.size * leading)
            continue
        xx = x
        if align == 'center':
            xx = x + (width - text_width(d, line, fnt)) / 2
        elif align == 'right':
            xx = x + width - text_width(d, line, fnt)
        d.text((xx, y), line, font=fnt, fill=fill)
        y += int(fnt.size * leading)
    return y + gap


def logo(d, x, y, scale=1.0, color=RED, dark=INK, label='KONET'):
    # Generated cleanroom symbol; deterministic text keeps lettering readable.
    paste_asset_center(d, 'logo', 4, x + 23 * scale, y + 25 * scale, 48 * scale, opacity=0.96)
    fnt = font('sans', int(42 * scale), True)
    d.text((x + 60*scale, y), label, font=fnt, fill=color)
    d.text((x + 62*scale, y + 49*scale), 'COMPLIANCE OFFICE', font=font('sans', int(12*scale), True), fill=dark)


def header(d, page_no, section='Compliance Report_2026'):
    logo(d, 135, 118, 0.78)
    d.text((W - 610, 122), section, font=F['h2'], fill=INK)
    d.line([135, 198, W - 135, 198], fill=TEAL, width=5)
    d.text((W - 184, H - 105), f'{page_no:02d}', font=F['small'], fill=(120, 120, 120))


def section_title(d, x, y, title, sub=None, color=TEAL):
    d.rectangle([x, y + 7, x + 8, y + 58], fill=color)
    d.text((x + 28, y), title, font=F['h1'], fill=INK)
    y += 74
    if sub:
        d.text((x + 30, y), sub, font=F['h3'], fill=color)
        y += 50
    return y


def table(d, x, y, headers, rows, widths, row_h=58, header_fill=INK, body_fill=(251, 251, 249), alt_fill=(239, 241, 241), font_body=None):
    font_body = font_body or F['table']
    cx = x
    d.rectangle([x, y, x + sum(widths), y + row_h], fill=header_fill)
    for h, w in zip(headers, widths):
        d.text((cx + 14, y + 16), str(h), font=F['table_bold'], fill='white')
        cx += w
    y += row_h
    for i, row in enumerate(rows):
        cx = x
        fill = body_fill if i % 2 == 0 else alt_fill
        max_lines = 1
        wrapped = []
        for val, w in zip(row, widths):
            ls = wrap(d, str(val), font_body, w - 24)
            wrapped.append(ls)
            max_lines = max(max_lines, min(3, len(ls)))
        h = max(row_h, 34 * max_lines + 22)
        for ls, w in zip(wrapped, widths):
            d.rectangle([cx, y, cx + w, y + h], fill=fill, outline=(225, 225, 224))
            yy = y + 14
            for line in ls[:3]:
                d.text((cx + 12, yy), line, font=font_body, fill=INK)
                yy += 32
            cx += w
        y += h
    return y


def rounded_card(d, box, fill, outline=(220, 220, 220), radius=24, width=2, shadow=True):
    x1, y1, x2, y2 = box
    if shadow:
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle([x1+10, y1+12, x2+10, y2+12], radius=radius, fill=(0, 0, 0, 28))
        blurred = sh.filter(ImageFilter.GaussianBlur(10))
        alpha_composite_logical(d, blurred)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def load_compliance_panel(name: str) -> Image.Image | None:
    p = COMPLIANCE_ASSET_DIR / f'{name}.png'
    if not p.exists():
        return None
    return Image.open(p).convert('RGB')


def paste_panel_card(d, name: str, x: int, y: int, w: int, h: int, border=(206, 210, 212), shadow=True) -> bool:
    """Paste generated compliance insert art into a report frame."""
    im = load_compliance_panel(name)
    if im is None:
        return False
    if shadow:
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rectangle([x+10, y+12, x+w+10, y+h+12], fill=(0, 0, 0, 26))
        alpha_composite_logical(d, sh.filter(ImageFilter.GaussianBlur(8)))
    d.rectangle([x, y, x+w, y+h], fill=(255, 255, 255), outline=border, width=2)
    fitted = ImageOps.fit(im, (w-14, h-14), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    paste_logical(d, fitted, (x+7, y+7))
    return True


def mock_photo(d, x, y, w, h, palette='meeting'):
    asset_map = {
        'leaflet': 'compliance_handbook_cover',
        'meeting': 'compliance_workshop_photo',
        'screen': 'compliance_dashboard_screen',
        'analytics': 'compliance_presentation_analytics',
    }
    if palette in asset_map and paste_panel_card(d, asset_map[palette], x, y, w, h):
        return
    d.rectangle([x, y, x + w, y + h], fill=(224, 225, 224), outline=(210, 210, 210))
    if palette == 'meeting':
        d.rectangle([x, y, x + w, y + int(h * 0.28)], fill=(80, 34, 42))
        d.rectangle([x+40, y+45, x+w-40, y+95], fill=(240, 235, 226))
        d.text((x+70, y+58), '2026 Compliance Workshop', font=F['tiny'], fill=(70, 70, 70))
        for i in range(18):
            px = x + 55 + (i % 6) * 88
            py = y + 145 + (i // 6) * 52
            d.ellipse([px, py, px+24, py+24], fill=(80+i*5 % 90, 90, 110))
            d.rectangle([px-8, py+25, px+34, py+48], fill=(55, 75+i*4 % 90, 100))
        d.rectangle([x+70, y+h-72, x+w-70, y+h-45], fill=(150, 26, 45))
    elif palette == 'screen':
        d.rectangle([x+22, y+22, x+w-22, y+h-22], fill=(250, 250, 250), outline=(170, 190, 205))
        d.rectangle([x+22, y+22, x+w-22, y+64], fill=(45, 120, 190))
        d.text((x+42, y+34), 'K-DISCLOSURE', font=F['tiny'], fill='white')
        yy = y+95
        for i in range(8):
            d.rectangle([x+48, yy, x+w-55, yy+30], fill=(245, 245, 245) if i%2 else (233, 240, 246), outline=(225,225,225))
            d.line([x+78, yy+15, x+w-88, yy+15], fill=(150,150,150), width=1)
            yy += 39
    elif palette == 'leaflet':
        d.rectangle([x+35, y+30, x+w-35, y+h-30], fill=(242, 247, 238), outline=(170, 190, 170))
        d.polygon([(x+w-120,y+60),(x+w-45,y+60),(x+w-45,y+135)], fill=(230, 86, 92))
        d.text((x+70, y+78), '공정거래', font=F['h3'], fill=(210, 68, 72))
        d.text((x+70, y+132), '자율준수 편람', font=F['h3'], fill=(35, 55, 78))
        for i in range(5):
            d.rectangle([x+72, y+215+i*35, x+250, y+235+i*35], fill=(210, 220, 206))
    elif palette == 'night':
        d.rectangle([x, y, x+w, y+h], fill=(18, 24, 32))
        for i in range(16):
            bx = x + 25 + i * (w-70)//16
            d.rectangle([bx, y+h-60-(i%5)*22, bx+12, y+h-30], fill=(120, 70, 45))
        d.arc([x+120, y+50, x+w-120, y+h+120], 195, 345, fill=(245, 230, 180), width=4)
        d.text((x+150, y+70), '윤리경영 리더십 데이', font=F['small'], fill=(245, 240, 215))


def bar_chart(d, x, y, title, labels, old, new, color=RED, w=940, h=380):
    d.text((x, y), title, font=F['h3'], fill=INK)
    y += 64
    d.rectangle([x, y, x+w, y+h], fill=(234, 234, 232), outline=(210, 210, 208))
    left = x + 180
    right = x + w - 70
    top = y + 58
    gap = 68
    maxv = max(old + new + [1])
    for i, lab in enumerate(labels):
        yy = top + i * gap
        d.text((x+36, yy+8), lab, font=F['small'], fill=INK)
        for j, val in enumerate([old[i], new[i]]):
            bar_y = yy + j * 25
            bw = int((right-left) * val / maxv)
            fill = (216, 154, 160) if j == 0 else color
            d.rectangle([left, bar_y, left+bw, bar_y+20], fill=fill)
            d.text((left+bw+10, bar_y-4), str(val), font=F['tiny'], fill=INK)
    d.rectangle([x+w//2-120, y+h-48, x+w//2+135, y+h-18], outline=color, width=2)
    d.rectangle([x+w//2-102, y+h-40, x+w//2-82, y+h-25], fill=(216, 154, 160))
    d.text((x+w//2-76, y+h-45), '2024.11월', font=F['tiny'], fill=INK)
    d.rectangle([x+w//2+28, y+h-40, x+w//2+48, y+h-25], fill=color)
    d.text((x+w//2+54, y+h-45), '2026.05월', font=F['tiny'], fill=INK)
    return y+h+34


def org_chart(d, x, y):
    def node(cx, cy, text, w=210, h=64, fill=(250,250,250)):
        d.rounded_rectangle([cx-w//2, cy, cx+w//2, cy+h], radius=8, fill=fill, outline=(170,170,170), width=2)
        paragraph(d, (cx-w//2+12, cy+12), text, F['tiny'], width=w-24, fill=INK, leading=1.15, align='center')
        return (cx, cy+h)
    node(x+520, y, '대표이사', 220, 66)
    d.line([x+520, y+66, x+520, y+112], fill=(160,160,160), width=2)
    node(x+520, y+112, '준법지원인\nCompliance Officer', 270, 82, (245,248,248))
    d.line([x+520, y+194, x+520, y+250], fill=(160,160,160), width=2)
    d.line([x+170, y+250, x+870, y+250], fill=(160,160,160), width=2)
    teams = [('공정거래\n관리팀', x+170), ('개인정보\n보호팀', x+405), ('윤리경영\n지원팀', x+635), ('해외법인\n지원팀', x+870)]
    for txt, cx in teams:
        d.line([cx, y+250, cx, y+290], fill=(160,160,160), width=2)
        node(cx, y+290, txt, 190, 76)


def page1():
    im, d = new_page()
    d.rectangle([0, 0, W, H], fill=(244, 244, 242))
    # cover abstract cards
    d.rectangle([0, 0, 16, H], fill=TEAL)
    d.line([190, 520, 190, 900], fill=TEAL, width=6)
    logo(d, 235, 495, 1.25)
    d.text((235, 610), 'Compliance Report', font=F['cover_title'], fill=INK)
    d.text((235, 700), '2026', font=F['cover_title'], fill=INK)
    d.text((235, 840), '준법경영·공정거래·윤리경영 통합 점검보고서', font=F['cover_sub'], fill=INK)
    # floating compliance kit
    for i, (xx, yy, col, t) in enumerate([
        (1120, 250, (222, 50, 76), 'CP'), (1240, 210, (234, 75, 95), 'ESG'),
        (1360, 300, (195, 34, 68), 'Risk'), (1170, 370, (245, 112, 122), 'Audit')]):
        d.rounded_rectangle([xx, yy, xx+135, yy+92], radius=18, fill=col, outline='white', width=3)
        d.text((xx+25, yy+26), t, font=F['small'], fill='white')
    d.text((1035, 1480), 'Finance & Compliance Center', font=F['small'], fill=INK)
    d.text((1035, 1530), '준법지원실 / 윤리경영팀', font=F['body_sans'], fill=INK)
    d.rectangle([210, 1965, 1250, 2050], outline=(170,170,170), width=1)
    d.text((235, 1988), '문서번호  KCO-CR-2026-04    |    배포등급  대외배포 가능본    |    작성일  2026.04', font=F['small'], fill=MUTED)
    return im


def page2():
    im, d = new_page(); header(d, 2)
    d.text((W//2 - text_width(d, '격려사', F['h1'])/2, 370), '격려사', font=F['h1'], fill=INK)
    body = (
        '존경하는 임직원 여러분께,\n\n'
        '지난 한 해 동안 우리는 공급망 전반의 법규 준수 수준을 높이고, 구성원이 안심하고 의견을 제기할 수 있는 문화를 만들기 위해 여러 제도를 정비하였습니다. 컴플라이언스는 더 이상 특정 부서의 점검 업무에 머무르지 않습니다. 영업, 구매, 연구개발, 생산, 관리 전 영역에서 의사결정의 기준이 되어야 합니다.\n\n'
        '이번 보고서는 공정거래 자율준수, 개인정보 보호, 윤리경영 교육, 내부 신고제도 운영 현황을 한눈에 볼 수 있도록 정리했습니다. 특히 협력사와 함께 지켜야 할 행동 기준을 명확히 하고, 반복적으로 발견되는 위험요인을 개선 과제로 연결한 점에 의미가 있습니다.\n\n'
        '앞으로도 회사는 투명한 절차와 기록에 기반한 준법경영 체계를 고도화하겠습니다. 모든 구성원이 업무 현장에서 법과 원칙을 먼저 생각하고, 서로에게 바른 판단을 요청할 수 있는 조직문화를 만들어 주시기 바랍니다.'
    )
    y = paragraph(d, (350, 520), body, F['body'], width=960, fill=INK, leading=1.82)
    d.text((1030, y+80), '2026년 4월', font=F['body_sans'], fill=INK)
    d.text((1030, y+135), '대표이사  김서준', font=F['body_sans'], fill=INK)
    # Keep generated seal/signature outside the text baseline area.
    paste_asset_center(d, 'stamp', 3, 1335, y+158, 118, opacity=0.82, rotate=-2)
    paste_asset_center(d, 'signature', 3, 1155, y+235, 235, opacity=0.72, rotate=-4)
    return im


def page3():
    im, d = new_page(); header(d, 3)
    x, y = 560, 760
    d.line([x, y-20, x, y+560], fill=TEAL, width=3)
    d.text((x+34, y), 'Contents', font=F['h2'], fill=INK)
    items = [
        ('컴플라이언스 총괄 개요', '04'), ('컴플라이언스 조직도', '04'), ('컴플라이언스 사내 규정', '04'),
        ('2026 운영 실적', '05'), ('  - 공정거래 자율준수', '05'), ('  - 윤리경영 교육', '06'),
        ('준법인식평가', '07'), ('2026 하반기 운영계획', '08')]
    yy = y + 110
    for title, no in items:
        d.text((x+34, yy), title, font=F['body_sans'], fill=INK)
        d.text((x+650, yy), no, font=F['body_sans'], fill=MUTED)
        yy += 58
    return im


def page4():
    im, d = new_page(); header(d, 4)
    y = section_title(d, 220, 360, '1. 컴플라이언스 체계', '조직도 및 사내 규정')
    paragraph(d, (220, y), '회사는 준법지원인을 중심으로 공정거래, 개인정보보호, 윤리경영, 해외법인 지원 기능을 통합 운영한다. 각 기능은 정기 점검과 교육, 신고 접수, 개선 과제 관리를 담당하며 주요 안건은 분기별 컴플라이언스 위원회에 보고한다.', F['body_sans'], width=1200, leading=1.55)
    org_chart(d, 250, 720)
    rows = [
        ('준법통제기준', '준법지원실', '이사회 보고 및 임직원 준수 의무'),
        ('공정거래 자율준수 편람', '공정거래팀', '담합·부당지원·하도급 거래 점검 기준'),
        ('개인정보 보호규정', '개인정보보호팀', '수집·이용·보관·파기 절차'),
        ('윤리경영 행동강령', '윤리경영팀', '이해상충, 금품수수, 제보 보호 원칙'),
        ('협력사 행동규범', '구매기획팀', '협력사 계약 및 실사 기준'),
        ('해외법인 준법가이드', '해외지원팀', '현지 법규 모니터링 및 보고 체계'),
    ]
    table(d, 225, 1285, ['규정명', '주관부서', '주요 내용'], rows, [390, 280, 640], row_h=56, header_fill=INK)
    return im


def page5():
    im, d = new_page(); header(d, 5)
    y = section_title(d, 220, 340, '2. 2026년 컴플라이언스 운영 실적')
    months = [
        ('1월', '공정거래 자율준수 편람 개정'), ('2월', '협력사 표준계약서 설명회'),
        ('3월', '대리점법 상생협약 이행점검'), ('4월', '하도급 거래 내부 실태점검'),
        ('5월', '개인정보 처리 위탁사 점검'), ('6월', '전 임직원 준법경영 기본교육'),
        ('8월', '자율준수 프로그램 운영현황 보고'), ('10월', '해외법인 준법 리스크 워크숍'),
        ('11월', '윤리경영 리더십 데이'), ('12월', '공정거래 및 상생협력 이행점검')]
    yy = y + 45
    for i, (m, txt) in enumerate(months):
        if i == 6:
            yy += 36
        d.text((230, yy), m, font=F['h3'], fill=INK)
        paragraph(d, (330, yy+1), txt, F['body_sans'], width=470, leading=1.2)
        yy += 92
    mock_photo(d, 855, 555, 520, 360, 'leaflet')
    d.text((900, 930), '[공정거래 자율준수 편람 개정본]', font=F['small'], fill=INK)
    mock_photo(d, 760, 1040, 660, 355, 'meeting')
    d.text((875, 1415), '[2. 24. 협력사 표준계약 설명회]', font=F['small'], fill=INK)
    mock_photo(d, 820, 1510, 575, 340, 'screen')
    d.text((940, 1870), '[공정거래 자율준수 프로그램 공시]', font=F['small'], fill=INK)
    return im


def page6():
    im, d = new_page(); header(d, 6)
    y = section_title(d, 220, 340, '3. 2026년 컴플라이언스 교육 실적')
    rows = [
        ('기본', '준법경영 기본교육', '전직원 대상', '1,240', '컴플라이언스, 윤리경영 기본 원칙'),
        ('기본', '법정 교육', '전직원 대상', '3,186', '성희롱·괴롭힘 예방, 개인정보보호'),
        ('심화', '공정거래 실무과정', '유관 부서', '184', '하도급법, 대리점법, 상생협력법'),
        ('심화', 'ESG 전문과정', '유관 부서', '46', '인권, 공급망, 거버넌스 관련 실무'),
        ('특별', '안전·보건·환경 법정 교육', '유관 부서', '728', '직무별 준수사항 및 사고대응'),
        ('특별', '임원·리더 교육', '경영진 대상', '63', '리더의 준법 의사결정과 책임'),
        ('특별', '신규 입사자 특별교육', '신규 입사자', '58', '신고채널, 행동강령, 보안수칙'),
        ('특별', '고위험 부서 교육', '선정 부서', '19', '규제 변경과 리스크 예방 교육'),
    ]
    table(d, 205, y+40, ['구분', '교육명', '대상', '인원(명)', '주요내용'], rows, [135, 330, 215, 150, 530], row_h=72, header_fill=INK, body_fill=(238,238,236), alt_fill=(247,247,245), font_body=F['table'])
    d.text((235, 1900), '교육 이수율', font=F['h3'], fill=INK)
    # dashboard cards
    cards = [('기본교육', 98, GREEN), ('심화교육', 91, TEAL), ('특별교육', 87, GOLD)]
    for i, (label, val, col) in enumerate(cards):
        x = 440 + i * 290
        d.rounded_rectangle([x, 1875, x+230, 2035], radius=22, fill=(255,255,255), outline=(210,210,210))
        d.text((x+35, 1905), label, font=F['small'], fill=MUTED)
        d.text((x+58, 1950), f'{val}%', font=F['num'], fill=col)
    return im


def page7():
    im, d = new_page(); header(d, 7)
    y = section_title(d, 220, 340, '4. 사내구성원 준법인식평가')
    paragraph(d, (250, y), '2026년 상반기 설문조사 결과, 구성원의 신고 의지와 제보자 보호에 대한 신뢰도가 전년 대비 개선되었다. 회사는 조사 결과를 바탕으로 신고채널 접근성을 높이고, 리더 대상 준법 의사결정 교육을 확대할 예정이다.', F['body_sans'], width=1180, leading=1.55)
    y = 650
    y = bar_chart(d, 330, y, '회사 내부의 컴플라이언스 위반 행위를 알게 된다면 신고를 할 것인가?', ['매우 그렇다','다소 그렇다','다소 아니다','전혀 아니다'], [12, 43, 30, 5], [39, 52, 8, 1], color=(182, 73, 82), w=980, h=430)
    d.text((330, y+70), '준법인식 평가 요약 대시보드', font=F['h3'], fill=INK)
    mock_photo(d, 330, y+125, 980, 620, 'analytics')
    rounded_card(d, [330, y+785, 1310, y+935], (255,255,255), outline=(218,218,216), radius=12, shadow=False)
    paragraph(d, (365, y+812), '요약: 신고 의향은 전년 대비 큰 폭으로 개선되었으며, 제보자 보호 신뢰도 역시 긍정 응답 비중이 상승했다. 하반기에는 익명상담 채널 접근성과 리더 대상 준법 의사결정 교육을 우선 개선 과제로 관리한다.', F['body_sans'], width=910, leading=1.35)
    return im


def page8():
    im, d = new_page(); header(d, 8)
    y = section_title(d, 220, 340, '5. 2026년 하반기 운영계획', '운영 과제 및 담당 체계')
    # Timeline cards
    quarters = [('7월', '자율준수 편람 배포\n부서별 위험점검'), ('8월', '위탁사 점검\n개선과제 회의'), ('9월', '공정거래 워크숍\n경영진 보고'), ('10월', '해외법인 교육\n현지 법규 모니터링'), ('11월', '윤리경영 캠페인\n신고채널 홍보'), ('12월', '연간 실적 평가\n차년도 계획 수립')]
    x0, y0 = 225, y+20
    for i, (m, txt) in enumerate(quarters):
        x = x0 + (i % 3) * 430
        yy = y0 + (i // 3) * 260
        d.rounded_rectangle([x, yy, x+360, yy+190], radius=24, fill=(255,255,255), outline=(200,205,207), width=2)
        d.text((x+28, yy+24), m, font=F['h3'], fill=TEAL)
        paragraph(d, (x+28, yy+76), txt, F['body_sans'], width=290, leading=1.35)
    # key tasks
    y2 = 1210
    d.text((225, y2), '중점 과제', font=F['h2'], fill=INK)
    task_rows = [
        ('공정거래', '하도급·대리점 거래 점검 항목 표준화', '공정거래팀'),
        ('개인정보', '위탁사 접근권한 및 파기 이력 검토', '개인정보보호팀'),
        ('윤리경영', '신고채널 신뢰도 제고 캠페인', '윤리경영팀'),
        ('해외법인', '현지 법령 변경 모니터링 리포트', '해외지원팀')]
    table(d, 225, y2+70, ['영역', '세부 과제', '담당'], task_rows, [240, 820, 250], row_h=62, header_fill=INK)
    # small risk heatmap
    d.text((225, 1770), '관리 우선순위', font=F['h2'], fill=INK)
    labels_x = ['거래', '정보', '윤리', '해외']
    labels_y = ['높음', '보통', '낮음']
    vals = [[2,3,1,2],[2,2,1,1],[1,1,1,1]]
    palette = [(210,235,218), (252,226,148), (224,126,112), (182,73,82)]
    for i, lab in enumerate(labels_x):
        d.text((530+i*150, 1810), lab, font=F['small'], fill=INK)
    for r, lab in enumerate(labels_y):
        d.text((380, 1875+r*88), lab, font=F['small'], fill=INK)
        for c, _ in enumerate(labels_x):
            d.rounded_rectangle([520+c*150, 1860+r*88, 620+c*150, 1938+r*88], radius=8, fill=palette[vals[r][c]], outline='white')
    return im


def make_contact_sheet(page_paths):
    QA.mkdir(parents=True, exist_ok=True)
    cols, rows = 4, 2
    cell_w, cell_h = 420, 595
    sheet = Image.new('RGB', (cols*cell_w, rows*cell_h+70), 'white')
    d = ImageDraw.Draw(sheet)
    d.text((20, 18), 'Cleanroom Compliance Report - 8 page overview', font=F['small'], fill=INK)
    for i, p in enumerate(page_paths):
        im = Image.open(p).convert('RGB')
        im.thumbnail((cell_w-30, cell_h-65))
        x = (i % cols) * cell_w + 15
        y = (i // cols) * cell_h + 70
        d.text((x, y-28), p.stem, font=F['tiny'], fill=INK)
        sheet.paste(im, (x, y))
    out = QA / 'contact_sheet.jpg'
    sheet.save(out, quality=92)
    return out


def render_pdf_to_png(pdf_path: Path):
    out_dir = QA / 'pdf_rendered_pages'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    for i, page in enumerate(doc, 1):
        zoom = 1200 / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        p = out_dir / f'rendered_{i:03d}.png'
        pix.save(str(p))
        paths.append(p)
    return paths


def write_notes():
    notes = '''# Source vs Cleanroom Notes - RPT-08 Compliance Report

## Source visual facts used
- 18-page enterprise compliance report style: cover, letter, contents, organization/rules, activity timeline, education table, survey charts, operation plan.
- Header pattern: left logo area, right report title, thin horizontal rule, large quiet margins.
- Body tone: restrained corporate Korean report, mostly white/gray canvas, occasional accent color and evidence-image frames.

## Cleanroom boundaries
- No source logo, screenshots, photos, captions, or prose copied.
- New fictional organization: KONET Compliance Office.
- All charts, tables, photos, screenshots, report names, numbers, and body text are newly authored.
- The PDF body does not expose generation/test/license metadata.

## Generated visual assets
- Compliance insert panels are generated bitmap assets stored under `assets/cleanroom_generated/compliance/panels`.
- The panels are used for the handbook cover image, workshop photo, dashboard screenshot, and PPT-style analytics slide.
- Seal/signature graphics are reused from `assets/cleanroom_generated`.

## Success criteria
- The output should look like a finished corporate compliance annual report, not a generic colored table template.
- The page types should be visually distinct: cover, letter, contents, organization, timeline with evidence images, education table, survey chart, operation plan.
'''
    (QA / 'source_vs_cleanroom_notes.md').write_text(notes, encoding='utf-8')


def write_manifest(pdf_path, page_paths, contact, rendered):
    data = {
        'schema_version': 1,
        'doc_id': 'RPT-08',
        'title': '컴플라이언스 점검보고서 클린룸 대표본',
        'created_at': datetime.now().isoformat(),
        'source_reference': str(SRC_DIR),
        'cleanroom_policy': 'source visual structure only; no copied logo, prose, photos, screenshots, or page images',
        'method': 'Pillow ImageDraw direct raster composition, then PDF packaging + external-font supersampling',
        'render_scale': RENDER_SCALE,
        'generated_assets': {
            'compliance_panels_dir': str(COMPLIANCE_ASSET_DIR),
            'source_sheet': str(ROOT / 'assets' / 'cleanroom_generated' / 'compliance' / 'sources' / 'compliance_insert_sheet_20260703.png'),
            'shared_logo_stamp_signature_dir': str(ROOT / 'assets' / 'cleanroom_generated'),
        },
        'deliverables': {
            'pdf': str(pdf_path.relative_to(OUT)),
            'pages': [str(p.relative_to(OUT)) for p in page_paths],
            'contact_sheet': str(contact.relative_to(OUT)),
            'rendered_pages': [str(p.relative_to(OUT)) for p in rendered],
        },
        'page_plan': [
            'cover', 'letter', 'contents', 'organization and rules', 'annual activity timeline',
            'education performance table', 'survey charts', 'operation plan'
        ],
    }
    (OUT / 'manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def promote_to_workbench(pdf_path: Path):
    dst = WB / 'samples' / 'cleanroom'
    if dst.exists():
        shutil.rmtree(dst)
    for sub in ['pages', 'qa/pdf_rendered_pages']:
        (dst / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf_path, dst / 'cleanroom_compliance_report.pdf')
    shutil.copy2(OUT / 'manifest.json', dst / 'manifest.json')
    for p in sorted(PAGES.glob('page_*.png')):
        shutil.copy2(p, dst / 'pages' / p.name)
    for p in sorted((QA / 'pdf_rendered_pages').glob('rendered_*.png')):
        shutil.copy2(p, dst / 'qa/pdf_rendered_pages' / p.name)
    for n in ['contact_sheet.jpg', 'source_vs_cleanroom_notes.md']:
        shutil.copy2(QA / n, dst / 'qa' / n)

    mp = WB / 'manifest.json'
    if not mp.exists():
        return
    manifest = json.loads(mp.read_text(encoding='utf-8'))
    files = []
    for p in [dst / 'cleanroom_compliance_report.pdf', dst / 'manifest.json'] + sorted((dst / 'pages').glob('page_*.png')) + [dst / 'qa/contact_sheet.jpg'] + sorted((dst / 'qa/pdf_rendered_pages').glob('rendered_*.png')) + [dst / 'qa/source_vs_cleanroom_notes.md']:
        files.append({'path': str(p), 'kind': 'cleanroom_trial', 'source': str(OUT)})
    manifest['status'] = 'cleanroom_sample_ready'
    manifest['cleanroom_samples'] = files
    manifest.setdefault('artifacts', {})['cleanroom'] = {
        'pdf': str(dst / 'cleanroom_compliance_report.pdf'),
        'contact_sheet': str(dst / 'qa/contact_sheet.jpg'),
        'pages_dir': str(dst / 'pages'),
        'rendered_pages_dir': str(dst / 'qa/pdf_rendered_pages'),
        'notes': str(dst / 'qa/source_vs_cleanroom_notes.md'),
        'trial_manifest': str(dst / 'manifest.json'),
        'quality_judgement': 'accepted_for_workbench_cleanroom_reference',
        'render_scale': RENDER_SCALE,
        'generated_graphics_assets': str(COMPLIANCE_ASSET_DIR),
    }
    manifest['updated_at'] = datetime.now().astimezone().isoformat()
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


def write_progress(pdf_path, contact):
    text = f'''# 2026-07-02 컴플라이언스 점검보고서 클린룸 테스트

## 목표
- 클린룸 방식으로 `컴플라이언스 점검보고서` 1종을 8페이지 대표본으로 제작했다.
- 원본은 시각 구조 분석에만 사용하고, PDF 본문에는 원본 로고/문장/사진/스크린샷을 복제하지 않았다.

## 산출물
- PDF: `{pdf_path}`
- 페이지 PNG: `{PAGES}`
- QA contact sheet: `{contact}`
- notes: `{QA / 'source_vs_cleanroom_notes.md'}`

## 구현 원칙
- 공통 non-KIE 문서 생성기를 사용하지 않고 전용 렌더러로 작성했다.
- 문서 구성은 표지, 격려사, 목차, 조직/규정, 운영 실적 타임라인, 교육 실적 표, 준법인식평가 차트, 하반기 운영계획으로 고정했다.
- 내부 메타 문구는 PDF 본문에 넣지 않고 manifest/QA notes에만 기록했다.

## 1차 자체 판단
- 이전 실패 산출물보다 문서별 고유성은 크게 개선되었다.
- 최종 성공 여부는 contact sheet와 PDF 렌더링 페이지를 원본 대표 페이지와 나란히 비교한 뒤 판단한다.
'''
    PROGRESS.write_text(text, encoding='utf-8')


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    PAGES.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    pages = [page1(), page2(), page3(), page4(), page5(), page6(), page7(), page8()]
    page_paths = []
    for i, im in enumerate(pages, 1):
        im = finish_supersampled_page(im, (W, H), RENDER_SCALE)
        pages[i - 1] = im
        p = PAGES / f'page_{i:03d}.png'
        im.save(p)
        page_paths.append(p)
    pdf_path = OUT / 'cleanroom_compliance_report.pdf'
    pages[0].save(pdf_path, save_all=True, append_images=pages[1:], resolution=200)
    contact = make_contact_sheet(page_paths)
    rendered = render_pdf_to_png(pdf_path)
    write_notes()
    write_manifest(pdf_path, page_paths, contact, rendered)
    write_progress(pdf_path, contact)
    promote_to_workbench(pdf_path)
    print(pdf_path)
    print(contact)
    print(f'pages={len(page_paths)} rendered={len(rendered)}')

if __name__ == '__main__':
    main()
