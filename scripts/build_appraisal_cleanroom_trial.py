#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import random
import shutil
import sys
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
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from datafactory.rendering.punched import PunchedStyle, draw_punched_text

OUT = ROOT / 'outputs' / 'cleanroom_trials' / 'COL-02_감정평가서'
PAGES = OUT / 'pages'
QA = OUT / 'qa'
WB = ROOT / 'workbench' / 'documents' / '감정평가서__COL-02'
PROGRESS = ROOT / 'docs/reports/cleanroom/20260702_appraisal_cleanroom_trial.md'
FONTS = ROOT / 'fonts'
MAP_POOL = ROOT / 'assets' / 'map_pool' / 'appraisal'
PRIMARY_MAP_ASSET = MAP_POOL / 'kr_wonju_ganhyeon_osm_z15.png'
PHOTO_POOL = ROOT / 'assets' / 'photo_pool' / 'appraisal' / 'generated'
PHOTO_ASSETS = [
    PHOTO_POOL / 'synthetic_appraisal_site_road_01.jpg',
    PHOTO_POOL / 'synthetic_appraisal_surroundings_01.jpg',
]
PUNCH_MARKS_ENABLED = False

W, H = 1191, 1684
RENDER_SCALE = DEFAULT_RENDER_SCALE
PAGE_PT = (595, 842)
INK = (45, 55, 55)
LINE = (50, 60, 60)
BLUE = (49, 88, 135)
BLUE_GRAY = (105, 126, 148)
RED = (196, 54, 54)
LIGHT = (248, 248, 244)
GRID = (164, 172, 172)
GRAY = (110, 112, 112)


def font(name: str, size: int, bold: bool = False):
    files = {
        'serif': ['batang.ttc', 'malgun.ttf'],
        'sans': ['malgunbd.ttf' if bold else 'malgun.ttf', 'gulim.ttc'],
        'gothic': ['gulim.ttc', 'malgun.ttf'],
        'mono': ['NGULIM.TTF', 'malgun.ttf'],
    }
    for f in files.get(name, files['serif']):
        p = FONTS / f
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()

F = {
    'title': font('gothic', 76, True),
    'title_mid': font('gothic', 40, True),
    'h1': font('gothic', 34, True),
    'h2': font('gothic', 24, True),
    'body': font('serif', 25),
    'body_bold': font('gothic', 25, True),
    'small': font('serif', 20),
    'tiny': font('serif', 16),
    'table': font('serif', 18),
    'table_bold': font('gothic', 18, True),
    'stamp': font('serif', 24),
    'stamp_big': font('serif', 32),
    'logo': font('sans', 24, True),
    'sign': font('sans', 34, True),
}

DATA = {
    'case_no': 'A042607-3-025',
    'title_property': '강원특별자치도 원주시 지정면 간현리 128-4 외 소재 부동산',
    'client': '하나유동화전문 유한회사',
    'submit_to': '하나유동화전문 유한회사',
    'owner': '서원자산신탁 주식회사',
    'company': '청솔감정평가법인 주식회사',
    'branch': '강원지사',
    'appraiser': '박  지  훈',
    'reviewer': '감정평가사 이  민  서',
    'purpose': '담보',
    'basis': '시장가치',
    'condition': '현황 기준',
    'base_date': '2026.06.18',
    'survey_period': '2026.06.15 ~ 2026.06.18',
    'write_date': '2026.06.19',
    'value': '₩ 3,842,615,000.-',
    'value_ko': '삼십팔억사천이백육십일만오천원정',
    'address': '강원특별자치도 원주시 지정면 간현리 128-4 외',
    'tel': '033-742-1180',
    'fax': '033-742-1181',
}

LAND_ROWS = [
    ['1', '원주시 지정면\n간현리 128-4', '13,420', '전', '자연녹지', '계획관리', '세로(가)', '부정형\n완경사', '71,000'],
    ['2', '원주시 지정면\n간현리 128-7', '2,860', '임', '자연림', '계획관리', '세로(불)', '부정형\n완경사', '39,000'],
    ['3', '원주시 지정면\n간현리 129-1', '510', '대', '주거기타', '계획관리', '세로(가)', '사다리\n평지', '118,000'],
]

VALUE_ROWS = [
    ['토지', '13,420㎡', '전', '개별요인 보정 후\n표준지공시지가 기준', '71,000', '952,820,000'],
    ['토지', '2,860㎡', '임야', '임야·자연림 상태\n접근성 열세 반영', '39,000', '111,540,000'],
    ['토지', '510㎡', '대', '인근 주거·근생\n전환 가능성 반영', '118,000', '60,180,000'],
    ['제시외건물', '412.6㎡', '창고 외', '관찰감가 및\n잔존내용연수 반영', '—', '86,475,000'],
    ['기타 권리', '일괄', '부대시설', '포장·배수·옹벽 등\n현황 보정', '—', '31,600,000'],
]
COMPARABLES = [
    ['A', '원주시 지정면 보통리 211', '전', '2026.03', '68,500', '세로(가), 완경사'],
    ['B', '원주시 지정면 간현리 97-2', '임야', '2025.12', '41,200', '세로(불), 자연림'],
    ['C', '원주시 지정면 월송리 55-1', '대', '2026.01', '121,000', '주거지 인접'],
]


def clean():
    if OUT.exists():
        shutil.rmtree(OUT)
    PAGES.mkdir(parents=True, exist_ok=True)
    (QA/'pdf_rendered_pages').mkdir(parents=True, exist_ok=True)


def new_page(scanned=True):
    im, d = new_supersampled_page(W, H, (255, 255, 250), RENDER_SCALE)
    if scanned:
        rng = random.Random(20260702)
        for _ in range(110):
            x, y = rng.randrange(45, W-45), rng.randrange(45, H-45)
            c = rng.randrange(217, 244)
            r = rng.choice([1, 1, 2])
            d.ellipse([x-r, y-r, x+r, y+r], fill=(c, c, c))
    return im, d


def tw(d, s, fnt):
    return d.textlength(str(s), font=fnt)


def center(d, y, text, fnt, fill=INK, x1=0, x2=W):
    lines = str(text).split('\n')
    if len(lines) == 1:
        d.text(((x1+x2-tw(d,text,fnt))/2, y), text, font=fnt, fill=fill)
        return
    yy = y
    for line in lines:
        d.text(((x1+x2-tw(d,line,fnt))/2, yy), line, font=fnt, fill=fill)
        yy += int(fnt.size * 1.25)


def cell_center_wrapped(d, box, text, fnt, fill=INK, max_lines=3, leading=None):
    x1, y1, x2, y2 = box
    leading = leading or int(fnt.size * 1.22)
    lines = wrap(d, str(text), fnt, max(10, x2 - x1 - 14))[:max_lines]
    if not lines:
        return
    yy = y1 + ((y2 - y1) - len(lines) * leading) / 2
    for line in lines:
        d.text(((x1 + x2 - tw(d, line, fnt)) / 2, yy), line, font=fnt, fill=fill)
        yy += leading


def wrap(d, text, fnt, width):
    out=[]
    for para in str(text).split('\n'):
        if not para.strip():
            out.append('')
            continue
        buf=''
        for ch in para:
            if tw(d, buf+ch, fnt) <= width:
                buf += ch
            else:
                if buf:
                    out.append(buf)
                buf=ch
        if buf:
            out.append(buf)
    return out


def paragraph(d, x, y, text, fnt=None, width=900, leading=1.65, first_indent=0):
    fnt = fnt or F['body']
    for pi, para in enumerate(str(text).split('\n')):
        if not para.strip():
            y += int(fnt.size*leading*0.7); continue
        lines=wrap(d, para, fnt, width - (first_indent if pi == 0 else 0))
        for li,line in enumerate(lines):
            xx=x+(first_indent if li==0 and pi==0 else 0)
            d.text((xx,y), line, font=fnt, fill=INK)
            y += int(fnt.size*leading)
    return y


def top_no(d):
    d.text((78, 64), DATA['case_no'], font=F['small'], fill=GRAY)


def footer(d, n=None):
    d.line([80, 1548, 1110, 1548], fill=BLUE_GRAY, width=4)
    if n is not None:
        center(d, 1575, str(n), F['tiny'], fill=GRAY)
    d.text((885, 1570), 'Cheongsol Appraisal Co.,Ltd.', font=F['tiny'], fill=INK)
    d.text((900, 1594), DATA['company'], font=F['tiny'], fill=BLUE)
    d.text((970, 1618), DATA['branch'], font=F['tiny'], fill=INK)


def section_header(d, title, page_title='감정평가액의 산출근거 및 결정 의견'):
    top_no(d)
    center(d, 155, page_title, F['h1'], fill=INK)
    d.line([72, 272, 1118, 272], fill=BLUE, width=5)
    d.text((95, 315), title, font=F['h1'], fill=INK)


def blue_logo(d, x, y, size=88):
    paste_asset_center(d, 'logo', 2, x + size/2, y + size/2, size, opacity=0.95)
    d.text((x+size+18, y+6), DATA['company'][:8], font=F['logo'], fill=INK)
    d.text((x+size+18, y+42), DATA['branch'], font=F['h2'], fill=INK)


def round_stamp(d, cx, cy, label='발송', size=100, color=RED):
    idx = 4 if color[2] > color[0] else 1
    paste_asset_center(d, 'stamp', idx, cx, cy, size * 1.12, opacity=0.84, rotate=-3)
    lines = str(label).split('\n')
    start = cy - (len(lines) * F['stamp'].size) / 2
    for i, line in enumerate(lines):
        center(d, int(start + i * (F['stamp'].size + 2)), line, F['stamp'], fill=color, x1=cx-size//2, x2=cx+size//2)


def square_stamp(d, cx, cy, label='청솔', size=92):
    paste_asset_center(d, 'stamp', 5, cx, cy, size * 1.08, opacity=0.84, rotate=1.5)
    center(d, cy-18, label, F['stamp_big'], fill=RED, x1=cx-size//2, x2=cx+size//2)


def punched_case_mark(d, x, y, text=None, scale=4.7):
    if not PUNCH_MARKS_ENABLED:
        return None
    serial = (text or DATA['case_no']).replace('-', '')
    return draw_punched_text(
        d,
        (x, y),
        serial,
        PunchedStyle(scale=scale, hole_radius=max(1.9, scale * 0.46), spacing=max(5.2, scale * 1.25), jitter=0.42, alpha=150, shadow_alpha=72, seed=20260702),
    )


def signature(d, x, y, scale=1.0):
    paste_cleanroom_asset(d, 'signature', 5, (x - 5*scale, y - 32*scale, x + 330*scale, y + 88*scale), opacity=0.92, rotate=-1.0)


def table_grid(d, x, y, col_w, row_h, rows, headers=None, font_body=None, font_header=None, fills=None, align=None):
    font_body = font_body or F['table']
    font_header = font_header or F['table_bold']
    if headers:
        yy=y
        cx=x
        for h,w in zip(headers,col_w):
            d.rectangle([cx, yy, cx+w, yy+row_h], outline=LINE, width=1, fill=(242,245,246))
            header_lines = wrap(d, h, font_header, w-8)[:3]
            line_h = max(18, int(font_header.size * 1.18))
            start_y = yy + (row_h - len(header_lines) * line_h) / 2
            for j,line in enumerate(header_lines):
                center(d, start_y+j*line_h, line, font_header, x1=cx, x2=cx+w)
            cx += w
        y += row_h
    for ri,row in enumerate(rows):
        cx=x
        fill = fills[ri % len(fills)] if fills else (255,255,250)
        max_lines=1
        cell_lines=[]
        for val,w in zip(row,col_w):
            lines=wrap(d, str(val), font_body, w-12)
            cell_lines.append(lines)
            max_lines=max(max_lines,len(lines))
        h=max(row_h, max_lines*22+16)
        for ci,(lines,w) in enumerate(zip(cell_lines,col_w)):
            d.rectangle([cx, y, cx+w, y+h], outline=GRID, width=1, fill=fill)
            yy=y+(h-len(lines)*22)/2
            for line in lines:
                if align and align[ci]=='right':
                    d.text((cx+w-tw(d,line,font_body)-8, yy), line, font=font_body, fill=INK)
                else:
                    center(d, yy, line, font_body, x1=cx+4, x2=cx+w-4)
                yy += 22
            cx += w
        y += h
    return y


def paste_generated_photo(d, box, variant=0):
    available = [p for p in PHOTO_ASSETS if p.exists()]
    if not available:
        return False
    src = available[(variant - 1) % len(available)]
    x1, y1, x2, y2 = box
    ww, hh = max(10, x2 - x1), max(10, y2 - y1)
    im = Image.open(src).convert('RGB')
    scale = max(ww / im.width, hh / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - ww) // 2)
    top = max(0, (nh - hh) // 2)
    im = im.crop((left, top, left + ww, top + hh))
    # Slightly flatten contrast/saturation so the photo sits naturally in the scanned report page.
    im = im.filter(ImageFilter.UnsharpMask(radius=0.6, percent=65, threshold=4))
    d.rectangle(box, fill=(245,245,240), outline=LINE, width=1)
    paste_logical(d, im, (x1, y1))
    d.rectangle(box, outline=(148,148,140), width=2)
    return True


def draw_landscape(d, box, variant=0):
    if paste_generated_photo(d, box, variant):
        return
    x1,y1,x2,y2=box
    ww, hh = max(10, x2-x1), max(10, y2-y1)
    rng=random.Random(100+variant)
    im=Image.new('RGB',(ww,hh),(210,220,218))
    dd=ImageDraw.Draw(im)
    # sky / ground gradient with slight overcast tint
    horizon=int(hh*0.47)
    for y in range(hh):
        if y < horizon:
            t=y/max(1,horizon)
            col=(192+int(t*30), 211+int(t*24), 220+int(t*18))
        else:
            t=(y-horizon)/max(1,hh-horizon)
            col=(139-int(t*26), 158-int(t*42), 119-int(t*38))
        dd.line([0,y,ww,y], fill=col)
    # distant hills
    for layer,base_col in enumerate([(103,132,105),(82,113,86),(68,96,72)]):
        pts=[(0,horizon+layer*18)]
        for i in range(10):
            xx=i*ww//9
            yy=horizon-int(hh*(0.05+rng.random()*0.10))+layer*25
            pts.append((xx,yy))
        pts += [(ww,hh),(0,hh)]
        dd.polygon(pts, fill=base_col)
    # road / dirt path
    mid=ww//2+(variant-2)*28
    dd.polygon([(mid-80,hh),(mid+95,hh),(mid+34,horizon+15),(mid-18,horizon+10)], fill=(178,158,122))
    dd.polygon([(mid-18,horizon+10),(mid+34,horizon+15),(mid+8,horizon+70),(mid-40,horizon+55)], fill=(151,135,106))
    for off in [-170,-100,-35,35,95,155]:
        dd.line([(mid+off,hh),(mid+off//3,horizon+35)], fill=(123,108,88), width=2)
    # buildings / retaining wall fragments
    for bx in [int(ww*.60), int(ww*.70), int(ww*.77)]:
        by=horizon+rng.randrange(35,95)
        dd.rectangle([bx,by,bx+rng.randrange(38,80),by+rng.randrange(22,45)], fill=(128,126,112))
        dd.rectangle([bx+4,by+4,bx+28,by+20], fill=(167,163,145))
    # vegetation masses
    for _ in range(140):
        tx=rng.randrange(0,ww)
        ty=rng.randrange(horizon-20,hh)
        r=rng.randrange(3,15)
        green=rng.choice([(45,81,48),(53,93,55),(75,111,65),(95,112,73),(86,91,60)])
        dd.ellipse([tx-r,ty-r,tx+r,ty+r], fill=green)
    # tree trunks and crowns
    for _ in range(34):
        tx=rng.randrange(15,ww-15)
        base=rng.randrange(horizon+25,hh-10)
        th=rng.randrange(34,115)
        dd.line([tx,base,tx+rng.randrange(-8,9),base-th], fill=(70,62,48), width=rng.randrange(2,5))
        cr=rng.randrange(14,32)
        dd.ellipse([tx-cr,base-th-cr,tx+cr,base-th+cr], fill=rng.choice([(45,84,50),(58,99,58),(78,105,62)]))
    # image grain and scan/photo softness
    px=im.load()
    for _ in range(ww*hh//12):
        x=rng.randrange(ww); y=rng.randrange(hh)
        r,g,b=px[x,y]
        delta=rng.randrange(-16,17)
        px[x,y]=(max(0,min(255,r+delta)), max(0,min(255,g+delta)), max(0,min(255,b+delta)))
    im=im.filter(ImageFilter.GaussianBlur(radius=0.55)).filter(ImageFilter.UnsharpMask(radius=1.0, percent=80, threshold=5))
    d.rectangle(box, fill=(245,245,240), outline=LINE, width=1)
    paste_logical(d, im, (x1, y1))
    d.rectangle(box, outline=(148,148,140), width=2)


def draw_map(d, box):
    x1,y1,x2,y2=box
    if PRIMARY_MAP_ASSET.exists():
        map_im = Image.open(PRIMARY_MAP_ASSET).convert('RGB').resize((x2-x1, y2-y1), Image.Resampling.LANCZOS)
        paste_logical(d, map_im, (x1, y1))
        d.rectangle(box, outline=LINE, width=2)
        return
    d.rectangle(box, fill=(240,238,198), outline=LINE, width=2)
    rng=random.Random(404)
    # river
    river=[(x2-230,y1),(x2-190,y1+150),(x2-220,y1+330),(x2-180,y1+520),(x2-230,y2)]
    d.line(river, fill=(112,169,205), width=150, joint='curve')
    # contour/parcel lines
    for _ in range(35):
        pts=[]
        sx=rng.randrange(x1+30,x2-70); sy=rng.randrange(y1+30,y2-30)
        for k in range(5):
            pts.append((sx+k*rng.randrange(35,70), sy+rng.randrange(-45,45)))
        d.line(pts, fill=(204,184,130), width=2)
    # roads
    d.line([(x1+120,y2-130),(x1+350,y2-280),(x1+600,y2-360),(x2-100,y2-520)], fill=(245,245,235), width=34)
    d.line([(x1+120,y2-130),(x1+350,y2-280),(x1+600,y2-360),(x2-100,y2-520)], fill=(185,165,130), width=3)
    # target parcels
    poly=[(x1+310,y1+520),(x1+460,y1+430),(x1+610,y1+470),(x1+730,y1+600),(x1+680,y1+760),(x1+420,y1+730)]
    d.polygon(poly, outline=RED, fill=(255,235,210))
    d.line(poly+[poly[0]], fill=RED, width=5)
    d.text((x1+500,y1+570),'기호 1\n간현리 128-4',font=F['small'],fill=RED)
    for label,pt in [('기호 2',(x1+535,y1+360)),('기호 3',(x1+690,y1+330))]:
        d.text((pt[0]-30,pt[1]-55),label,font=F['small'],fill=RED)
        d.line([pt[0],pt[1]-18,pt[0]+25,pt[1]+115], fill=RED, width=3)
    # compass
    cx,cy=x1+85,y1+78
    d.polygon([(cx,cy-42),(cx+12,cy),(cx,cy+42),(cx-12,cy)], fill=(44,70,120))
    d.polygon([(cx-42,cy),(cx,cy-12),(cx+42,cy),(cx,cy+12)], fill=(70,130,88))
    d.text((cx-7,cy-65),'N',font=F['tiny'],fill=RED)
    d.text((cx+50,cy-9),'E',font=F['tiny'],fill=(180,110,30))
    d.text((cx-60,cy-9),'W',font=F['tiny'],fill=(44,70,120))
    d.text((cx-6,cy+48),'S',font=F['tiny'],fill=(70,130,88))


def cover_page():
    im,d=new_page()
    top_no(d)
    punched_case_mark(d, 665, 62, scale=3.8)
    d.rectangle([260, 275, 935, 292], fill=BLUE_GRAY)
    center(d, 335, '감 정 평 가 서', F['title'], fill=INK)
    d.rectangle([260, 455, 935, 472], fill=BLUE_GRAY)
    # summary table
    x,y,w,h=260,540,675,210
    d.rectangle([x,y,x+w,y+h], outline=LINE, width=2)
    rows=[('건        명', DATA['title_property']),('감정의뢰인', DATA['client']),('평가서번호', DATA['case_no'])]
    yy=y
    for lab,val in rows:
        d.rectangle([x,yy,x+150,yy+70], outline=LINE, width=1)
        d.rectangle([x+150,yy,x+w,yy+70], outline=LINE, width=1)
        center(d, yy+21, lab, F['small'], x1=x, x2=x+150)
        cell_center_wrapped(d, (x+150, yy, x+w, yy+70), val, F['small'], max_lines=2)
        yy += 70
    draw_landscape(d, (260, 768, 935, 1110), 1)
    round_stamp(d, 1005, 1048, '발송\nNo.16', 132, color=(66,83,171))
    d.rectangle([180, 1120, 1020, 1265], outline=BLUE, width=4)
    paragraph(d, 195, 1135, '이 감정평가서는 감정평가 의뢰목적 외의 목적에 사용하거나 타인이 사용할 수 없으며, 복사·개작·전재할 수 없습니다. 이로 인한 결과에 대하여 감정평가업자는 책임을 지지 않습니다.', F['small'], 800, 1.55)
    blue_logo(d, 210, 1328, 88)
    square_stamp(d, 905, 1370, '청솔', 118)
    punched_case_mark(d, 100, 1428, scale=4.3)
    d.text((190, 1510), f"CHEONGSOL APPRAISAL CO., LTD  (T:{DATA['tel']}  F:{DATA['fax']})", font=F['small'], fill=INK)
    return im


def eval_sheet_page():
    im,d=new_page()
    top_no(d)
    punched_case_mark(d, 665, 62, scale=3.8)
    center(d, 125, '( 토지 ) 감정평가표', F['title_mid'], fill=INK)
    d.line([350, 182, 840, 182], fill=LINE, width=2)
    # certification box
    d.rectangle([95, 230, 1095, 500], outline=LINE, width=2)
    paragraph(d, 200, 270, '이 감정평가서는 감정평가에 관한 법규를 준수하고 감정평가이론에 따라 성실하고 공정하게 작성하였기에 서명날인합니다.', F['small'], 800, 1.7)
    d.text((360, 380), '감 정 평 가 사', font=F['small'], fill=INK)
    d.text((360, 430), DATA['appraiser'], font=F['small'], fill=INK)
    signature(d, 650, 360, .8)
    round_stamp(d, 960, 360, '감정', 95)
    d.text((330, 520), f"{DATA['company']} {DATA['branch']}     지사장  {DATA['appraiser']}", font=F['small'], fill=INK)
    # main info table
    y=585
    info_total_h = sum([72,62,62,72,72,72])
    d.rectangle([95,y,1095,y+info_total_h], outline=LINE, width=2)
    info=[
        ['감정평가액', DATA['value_ko'] + f"({DATA['value']})"],
        ['의뢰인', DATA['client'], '감정평가\n목적', DATA['purpose']],
        ['제출처', DATA['submit_to'], '기준가치', DATA['basis']],
        ['소유자\n(대상업체명)', DATA['owner'], '감정평가\n조건', DATA['condition']],
        ['목록표시\n근거', '토지대장, 등기사항전부증명서 등', '기준시점', DATA['base_date']],
        ['기타\n참고사항', '현장조사 및 공부대조에 의함', '작성일', DATA['write_date']],
    ]
    row_h=[72,62,62,72,72,72]
    yy=y
    for i,row in enumerate(info):
        h=row_h[i]
        if i==0:
            d.rectangle([95,yy,245,yy+h], outline=GRID)
            d.rectangle([245,yy,1095,yy+h], outline=GRID)
            center(d, yy+20, row[0], F['table_bold'], x1=95, x2=245)
            d.text((270,yy+20), row[1], font=F['table_bold'], fill=INK)
        else:
            xs=[95,245,610,760,1095]
            for a,b in zip(xs,xs[1:]): d.rectangle([a,yy,b,yy+h], outline=GRID)
            cell_center_wrapped(d, (95, yy, 245, yy+h), row[0], F['table'], max_lines=3)
            cell_center_wrapped(d, (245, yy, 610, yy+h), row[1], F['table'], max_lines=2)
            cell_center_wrapped(d, (610, yy, 760, yy+h), row[2], F['table'], max_lines=3)
            cell_center_wrapped(d, (760, yy, 1095, yy+h), row[3], F['table'], max_lines=2)
        yy += h
    # valuation table
    y=1030
    d.text((105, y+30), '감\n정\n평\n가\n내\n용', font=F['table_bold'], fill=INK)
    headers=['종류','면적 또는 수량','종류','면적 또는 수량','단가','금액']
    rows=[['토지','16,790㎡','토지','16,790㎡','—','3,724,540,000'],['제시외\n건물','412.6㎡','제시외\n건물','412.6㎡','—','86,475,000'],['기타','일괄','부대시설','일괄','—','31,600,000']]
    table_grid(d, 150, y, [105,150,105,150,150,285], 52, rows, headers=headers, fills=[(255,255,250),(250,250,247)], align=['center','right','center','right','right','right'])
    d.rectangle([150, 1300, 1095, 1370], outline=LINE)
    d.text((185,1322), '합        계', font=F['table_bold'], fill=INK)
    d.text((895,1322), DATA['value'], font=F['table_bold'], fill=INK)
    d.rectangle([95,1390,1095,1535], outline=LINE, width=2)
    paragraph(d, 170, 1420, '본인은 이 감정평가서에 제시된 자료를 기준으로 성실하고 공정하게 심사한 결과 이 감정평가 내용이 타당하다고 인정하므로 이에 서명날인합니다.', F['small'], 820, 1.55)
    d.text((265,1500),'심 사 자    감 정 평 가 사', font=F['small'], fill=INK)
    signature(d, 650, 1455, .85)
    round_stamp(d, 955, 1478, '심사', 90)
    footer(d)
    return im


def rationale_page1():
    im,d=new_page()
    section_header(d, 'I. 감정평가의 개요')
    y=395
    items=[
        ('1. 감정평가의 목적', '본건은 담보 제공을 목적으로 의뢰된 부동산에 대한 시장가치를 산정하기 위한 감정평가입니다.'),
        ('2. 감정평가의 기준', '본 평가는 「감정평가 및 감정평가사에 관한 법률」, 「감정평가에 관한 규칙」 및 일반적으로 인정되는 감정평가이론에 따라 수행하였습니다.'),
        ('3. 기준가치', '대상물건이 통상적인 시장에서 충분한 기간 거래를 위하여 공개된 후 그 대상물건의 내용에 정통한 당사자 사이에 자발적으로 거래될 가능성이 가장 높다고 인정되는 시장가치를 기준으로 하였습니다.'),
        ('4. 기준시점 및 조사기간', f"기준시점은 {DATA['base_date']}이며, 현장조사는 {DATA['survey_period']} 기간 중 공부확인, 현황확인 및 인근 거래사례 조사를 병행하여 수행하였습니다."),
    ]
    for h,body in items:
        d.text((95,y),h,font=F['h2'],fill=INK); y+=42
        y=paragraph(d,120,y,body,F['small'],940,1.65,first_indent=22); y+=26
    footer(d,1)
    return im


def rationale_page2():
    im,d=new_page()
    section_header(d, 'II. 감정평가의 기준 및 방법')
    y=395
    d.text((95,y),'1. 토지의 평가방법',font=F['h2'],fill=INK); y+=44
    body='토지는 대상토지와 가치형성요인이 같거나 유사한 비교표준지를 선정하고, 공시지가 기준법을 주된 방법으로 적용하되 거래사례비교법에 의한 시산가액과 비교·검토하여 합리성을 확인하였습니다.'
    y=paragraph(d,120,y,body,F['small'],940,1.65,first_indent=22); y+=28
    d.text((95,y),'2. 건물 및 부대시설의 평가방법',font=F['h2'],fill=INK); y+=44
    y=paragraph(d,120,y,'제시외 건물 및 부대시설은 구조, 용도, 관리상태, 관찰감가 및 잔존내용연수를 종합적으로 고려한 원가방식에 의하여 평가하였습니다.',F['small'],940,1.65,first_indent=22); y+=32
    d.text((95,y),'3. 가격형성요인의 검토',font=F['h2'],fill=INK); y+=44
    rows=[['구분','검토내용'],['지역요인','간선도로 및 IC 접근성, 주변 농경지·전원주택 혼재, 개발압력 보통'],['개별요인','부정형 완경사지, 일부 진입도로 폭 협소, 대지 일부와 부대시설 존재'],['기타요인','공부와 현황의 차이, 제시외건물 존재, 인근 거래사례의 개별성 보정']]
    table_grid(d, 120, y, [160,780], 48, rows[1:], headers=rows[0], fills=[(255,255,250),(250,250,247)])
    footer(d,2)
    return im


def rationale_page3():
    im,d=new_page()
    section_header(d, 'III. 대상물건의 개요')
    y=392
    d.text((95,y),'1. 감정평가 대상물건',font=F['h2'],fill=INK); y+=70
    table_grid(d, 150, y, [65,205,90,80,105,110,110,105,110], 55, LAND_ROWS, headers=['일련\n번호','소재지','면적\n(㎡)','지목','이용\n상황','용도\n지역','도로\n교통','형상\n지세','2026년\n공시지가'], fills=[(255,255,250),(251,251,248)])
    draw_landscape(d, (165, 900, 1045, 1325), 2)
    d.line([165, 1345, 1045, 1345], fill=LINE, width=2)
    footer(d,3)
    return im


def value_detail_page():
    im,d=new_page()
    section_header(d, 'IV. 감정평가액의 산출')
    y=390
    d.text((95,y),'1. 평가내역',font=F['h2'],fill=INK); y+=55
    table_grid(d, 105, y, [105,120,115,280,135,210], 52, VALUE_ROWS, headers=['구분','수량','세목','산출근거','단가','금액'], fills=[(255,255,250),(250,250,247)], align=['center','right','center','center','right','right'])
    y=920
    d.rectangle([105,y,1085,y+82], outline=LINE, width=2, fill=(247,249,249))
    d.text((135,y+27),'감정평가액 합계',font=F['table_bold'],fill=INK)
    d.text((760,y+27),DATA['value'],font=F['table_bold'],fill=INK)
    y+=130
    d.text((95,y),'2. 거래사례 검토',font=F['h2'],fill=INK); y+=55
    table_grid(d, 125, y, [75,275,90,105,130,250], 48, COMPARABLES, headers=['기호','소재지','지목','거래시점','거래단가\n(원/㎡)','비고'], fills=[(255,255,250),(250,250,247)])
    y=1330
    paragraph(d, 105, y, '상기 거래사례 및 공시지가 변동률, 지역요인·개별요인 보정치를 종합 검토한 결과, 대상물건의 최종 감정평가액을 위와 같이 결정하였습니다.', F['small'], 930, 1.65, first_indent=24)
    footer(d,4)
    return im


def decision_page():
    im,d=new_page()
    section_header(d, 'V. 결정 의견')
    y=395
    paras=[
        '대상물건은 원주시 지정면 간현리 일대의 계획관리지역 내 토지 및 제시외 건물로서, 인근에 소규모 농경지와 전원주택, 창고시설이 혼재하고 있습니다. 접근성은 보통이나 일부 필지의 형상 및 도로조건은 다소 열세입니다.',
        '공시지가 기준법에 따른 시산가액을 중심으로 하되, 인근 유사 부동산의 거래사례, 대상물건의 개별요인, 기준시점 현재의 시장상황 및 제시외 건물의 사용가능성을 종합적으로 비교·검토하였습니다.',
        f"따라서 대상물건의 감정평가액은 {DATA['value']}으로 결정함이 타당하다고 판단됩니다.",
    ]
    for p in paras:
        y=paragraph(d, 120, y, p, F['body'], 930, 1.72, first_indent=30); y+=36
    center(d, 1080, DATA['write_date'], F['body'])
    d.text((350, 1190), DATA['company'], font=F['h2'], fill=INK)
    square_stamp(d, 780, 1208, '청솔', 95)
    d.text((350, 1280), DATA['reviewer'], font=F['body'], fill=INK)
    signature(d, 670, 1248, .85)
    round_stamp(d, 940, 1295, '인', 70)
    footer(d,5)
    return im


def map_page():
    im,d=new_page()
    top_no(d)
    punched_case_mark(d, 675, 62, scale=3.7)
    center(d, 155, '위 치 도', F['title_mid'], fill=INK)
    d.text((1000, 210), 'Page : 1', font=F['small'], fill=INK)
    d.line([60, 260, 1130, 260], fill=LINE, width=2)
    d.line([60, 268, 1130, 268], fill=LINE, width=1)
    d.rectangle([95, 300, 1095, 1530], outline=LINE, width=2)
    d.rectangle([200, 330, 1080, 405], outline=LINE, width=1)
    d.rectangle([200, 330, 330, 405], outline=LINE, width=1)
    center(d, 354, '소 재 지', F['h2'], x1=200, x2=330)
    d.text((360, 352), DATA['address'], font=F['small'], fill=INK)
    draw_map(d, (150, 465, 1085, 1445))
    footer(d)
    return im


def photo_page():
    im,d=new_page()
    top_no(d)
    center(d, 155, '사 진 용 지', F['title_mid'], fill=INK)
    d.text((1000, 210), 'Page : 2', font=F['small'], fill=INK)
    d.line([60, 260, 1130, 260], fill=LINE, width=2)
    d.line([60, 268, 1130, 268], fill=LINE, width=1)
    d.rectangle([95, 300, 1095, 1530], outline=LINE, width=2)
    draw_landscape(d, (245, 405, 945, 760), 3)
    center(d, 840, '대상물건 전경', F['small'])
    draw_landscape(d, (245, 960, 945, 1315), 4)
    center(d, 1395, '주위환경', F['small'])
    footer(d)
    return im


def save_pages():
    pages=[cover_page(), eval_sheet_page(), rationale_page1(), rationale_page2(), rationale_page3(), value_detail_page(), decision_page(), map_page(), photo_page()]
    paths=[]
    for i,im in enumerate(pages,1):
        im=im.filter(ImageFilter.UnsharpMask(radius=1.0, percent=112, threshold=4))
        im=finish_supersampled_page(im, (W, H), RENDER_SCALE)
        p=PAGES/f'page_{i:03d}.png'
        im.save(p)
        paths.append(p)
    return paths


def images_to_pdf(paths, pdf_path):
    doc=fitz.open()
    for p in paths:
        page=doc.new_page(width=PAGE_PT[0], height=PAGE_PT[1])
        page.insert_image(fitz.Rect(0,0,PAGE_PT[0],PAGE_PT[1]), filename=str(p))
    doc.save(pdf_path)
    doc.close()


def render_pdf(pdf_path):
    out=QA/'pdf_rendered_pages'
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    doc=fitz.open(pdf_path)
    paths=[]
    for i,page in enumerate(doc,1):
        pix=page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
        p=out/f'rendered_{i:03d}.png'
        pix.save(p)
        paths.append(p)
    doc.close()
    return paths


def make_contact_sheet(paths):
    cols=3
    rows=(len(paths)+cols-1)//cols
    cell_w,cell_h=360,510
    sheet=Image.new('RGB',(cols*cell_w, rows*cell_h+65),'white')
    d=ImageDraw.Draw(sheet)
    d.text((18,18),'Cleanroom Appraisal Report - Pillow direct drawing overview', font=F['small'], fill=INK)
    for i,p in enumerate(paths):
        im=Image.open(p).convert('RGB')
        im.thumbnail((cell_w-35,cell_h-65))
        x=(i%cols)*cell_w+15
        y=(i//cols)*cell_h+65
        d.text((x,y-25), p.stem, font=F['tiny'], fill=INK)
        sheet.paste(im,(x,y))
    out=QA/'contact_sheet.jpg'
    sheet.save(out,quality=92)
    return out


def write_notes():
    text='''# COL-02 감정평가서 클린룸 작성 메모

- 원본 샘플은 표지, 감정평가표, 산출근거 및 결정의견, 대상물건 개요, 위치도, 사진용지의 페이지 유형 파악에만 사용했다.
- 원본 업체명, 평가번호, 사진, 지도, 도장, 서명, 문구를 복사하지 않았다.
- 사진은 built-in image generation으로 만든 합성 사진 asset pool을 사용했다.
- 위치도는 로컬 지도 asset pool의 OSM 기반 이미지와 가상 필지 overlay를 사용했다.
- 지도 asset에는 OSM attribution을 표시했고, 대량 생성 전에는 자체 타일/허가된 공급자로 전환한다.
- 펀칭 각인 모듈은 보존하되 `PUNCH_MARKS_ENABLED = False`로 렌더링 대상에서 제외했다.
- 문서 본문에는 배포등급/배포범위/합성/라이선스/검수 같은 내부 메타를 넣지 않았다.
'''
    (QA/'source_vs_cleanroom_notes.md').write_text(text, encoding='utf-8')


def write_manifest(pdf, pages, rendered, contact):
    manifest={
        'doc_id':'COL-02',
        'title':'감정평가서 클린룸 대표본',
        'created_at':datetime.now().isoformat(timespec='seconds'),
        'method':'Pillow ImageDraw direct raster composition, then PDF packaging + external-font supersampling',
        'render_scale':RENDER_SCALE,
        'pdf':str(pdf),
        'pages':[str(p) for p in pages],
        'rendered_pages':[str(p) for p in rendered],
        'contact_sheet':str(contact),
        'notes':str(QA/'source_vs_cleanroom_notes.md'),
        'policy':'cleanroom fictional appraisal company/client/property; generated synthetic photos; no copied source photos/prose/stamps/signatures/page images; map asset uses OpenStreetMap attribution/ODbL metadata',
        'photo_assets':{
            'pool':str(PHOTO_POOL),
            'index':str(PHOTO_POOL/'index.json'),
            'files':[str(p) for p in PHOTO_ASSETS if p.exists()],
            'source':'built-in image generation tool; project-local copies under assets/photo_pool/appraisal/generated',
        },
        'map_assets':{
            'primary':str(PRIMARY_MAP_ASSET),
            'index':str(MAP_POOL/'index.json'),
            'license_note':'OpenStreetMap data is ODbL; visible attribution is embedded in the map asset. Avoid bulk tile prefetching for production.',
        },
        'punched_mark_module':'datafactory.rendering.punched',
        'punched_marks_enabled':PUNCH_MARKS_ENABLED,
        'status':'cleanroom_trial_ready',
    }
    (OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    PROGRESS.write_text(f'''# 2026-07-02 감정평가서 클린룸 테스트

## 목표
- `감정평가서__COL-02` 1종을 Pillow 직접 드로잉 방식으로 대표본 제작.
- 웹 레이아웃 엔진 접목 없이, 표/도장/지도/사진형 시각 요소까지 코드에서 직접 생성.

## 산출물
- PDF: `{pdf}`
- 페이지 PNG: `{PAGES}`
- QA contact sheet: `{contact}`
- PDF 재렌더: `{QA / 'pdf_rendered_pages'}`
- notes: `{QA / 'source_vs_cleanroom_notes.md'}`
- manifest: `{OUT / 'manifest.json'}`

## 자체 판단
- 원본 감정평가서의 핵심 유형인 표지, 감정평가표, 산출근거 및 결정의견, 평가내역 표, 위치도, 사진용지 흐름을 반영했다.
- 원본 사진/지도는 사용하지 않았다. 사진은 생성형 이미지 asset pool로 대체했고, 위치도는 attribution 포함 OSM 기반 로컬 지도 asset으로 대체했다.
- 펀칭 각인 모듈은 보존하되 이번 산출물에서는 렌더링하지 않는다.
- 최종 확인은 contact sheet와 PDF 재렌더링 페이지를 기준으로 수행한다.
''', encoding='utf-8')


def promote(pdf):
    dst=WB/'samples'/'cleanroom'
    if dst.exists(): shutil.rmtree(dst)
    (dst/'pages').mkdir(parents=True, exist_ok=True)
    (dst/'qa').mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf, dst/'cleanroom_appraisal_report.pdf')
    shutil.copy2(OUT/'manifest.json', dst/'manifest.json')
    for p in sorted(PAGES.glob('page_*.png')):
        shutil.copy2(p, dst/'pages'/p.name)
    shutil.copy2(QA/'contact_sheet.jpg', dst/'qa'/'contact_sheet.jpg')
    shutil.copy2(QA/'source_vs_cleanroom_notes.md', dst/'qa'/'source_vs_cleanroom_notes.md')
    (dst/'qa'/'pdf_rendered_pages').mkdir(parents=True, exist_ok=True)
    for p in sorted((QA/'pdf_rendered_pages').glob('rendered_*.png')):
        shutil.copy2(p, dst/'qa'/'pdf_rendered_pages'/p.name)
    man_path=WB/'manifest.json'
    if man_path.exists():
        man=json.loads(man_path.read_text(encoding='utf-8'))
    else:
        man={'doc_id':'COL-02','title':'감정평가서'}
    files=[]
    for p in [dst/'cleanroom_appraisal_report.pdf', dst/'manifest.json'] + sorted((dst/'pages').glob('page_*.png')) + [dst/'qa'/'contact_sheet.jpg'] + sorted((dst/'qa'/'pdf_rendered_pages').glob('rendered_*.png')) + [dst/'qa'/'source_vs_cleanroom_notes.md']:
        files.append({'path':str(p), 'kind':'cleanroom_trial', 'source':str(OUT)})
    man['status']='cleanroom_sample_ready'
    man['cleanroom_samples']=files
    man.setdefault('artifacts',{})['cleanroom']={
        'pdf':str(dst/'cleanroom_appraisal_report.pdf'),
        'contact_sheet':str(dst/'qa'/'contact_sheet.jpg'),
        'pages_dir':str(dst/'pages'),
        'rendered_pages_dir':str(dst/'qa'/'pdf_rendered_pages'),
        'notes':str(dst/'qa'/'source_vs_cleanroom_notes.md'),
        'trial_manifest':str(dst/'manifest.json'),
        'quality_judgement':'pending_user_review_cleanroom_reference',
        'render_scale':RENDER_SCALE,
    }
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    clean()
    pages=save_pages()
    pdf=OUT/'cleanroom_appraisal_report.pdf'
    images_to_pdf(pages,pdf)
    rendered=render_pdf(pdf)
    contact=make_contact_sheet(rendered)
    write_notes()
    write_manifest(pdf,pages,rendered,contact)
    promote(pdf)
    print(pdf)
    print(contact)
    print(f'pages={len(pages)} rendered={len(rendered)}')


if __name__ == '__main__':
    main()
