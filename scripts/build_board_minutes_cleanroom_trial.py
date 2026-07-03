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
OUT = ROOT / 'outputs' / 'cleanroom_trials' / 'ADM-01_회의록(이사회·주총)'
PAGES = OUT / 'pages'
QA = OUT / 'qa'
FONTS = ROOT / 'fonts'
SRC_DIR = ROOT / 'seed_samples' / '회의록(이사회·주총)'
WB = ROOT / 'workbench' / 'documents' / '회의록(이사회·주총)__ADM-01'
PROGRESS = ROOT / 'docs/reports/cleanroom/20260702_board_minutes_cleanroom_trial.md'

W, H = 1654, 2339
RENDER_SCALE = DEFAULT_RENDER_SCALE
INK = (22, 22, 22)
LIGHT = (248, 248, 246)
LINE = (35, 35, 35)
RED = (188, 42, 54)
GRAY = (110, 110, 110)


def font(name: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    files = {
        'serif': 'batang.ttc',
        'gothic': 'gulim.ttc',
        'sans': 'malgunbd.ttf' if bold else 'malgun.ttf',
        'mono': 'NGULIM.TTF',
    }
    path = FONTS / files.get(name, files['serif'])
    if not path.exists():
        path = FONTS / 'malgun.ttf'
    return ImageFont.truetype(str(path), size=size)

F = {
    'cover_top': font('serif', 25),
    'cert_no': font('serif', 34),
    'cert_title': font('serif', 54),
    'cert_body': font('serif', 39),
    'doc_title': font('serif', 47),
    'h1': font('serif', 35),
    'h2': font('serif', 30),
    'body': font('serif', 31),
    'body_small': font('serif', 27),
    'table': font('serif', 25),
    'tiny': font('serif', 19),
    'stamp': font('serif', 26),
    'stamp_big': font('serif', 33),
    'sign': font('sans', 44, True),
}


def new_page(scanned: bool = True):
    im, d = new_supersampled_page(W, H, (255, 255, 253), RENDER_SCALE)
    if scanned:
        rng = random.Random(20260702)
        for _ in range(90):
            x, y = rng.randrange(80, W-80), rng.randrange(70, H-70)
            col = rng.randrange(215, 245)
            r = rng.choice([1, 1, 2])
            d.ellipse([x-r, y-r, x+r, y+r], fill=(col, col, col))
        # faint punch/scan marks at top
        for x in [315, 1395]:
            d.ellipse([x-5, 135, x+5, 145], fill=(214, 214, 212))
    return im, d


def tw(d, s, fnt):
    return d.textlength(str(s), font=fnt)


def center(d, y, text, fnt, fill=INK, x1=0, x2=W):
    d.text(((x1+x2-tw(d, text, fnt))/2, y), text, font=fnt, fill=fill)


def wrap(d, text, fnt, width):
    lines=[]
    for para in str(text).split('\n'):
        if not para.strip():
            lines.append('')
            continue
        buf=''
        for ch in para:
            if tw(d, buf+ch, fnt) <= width:
                buf += ch
            else:
                if buf: lines.append(buf)
                buf = ch
        if buf: lines.append(buf)
    return lines


def paragraph(d, x, y, text, fnt=None, width=1180, leading=1.82, first_indent=0, fill=INK, justify=False):
    fnt = fnt or F['body']
    for pi, para in enumerate(str(text).split('\n')):
        if not para.strip():
            y += int(fnt.size * leading * 0.7)
            continue
        lines = wrap(d, para, fnt, width - (first_indent if pi == 0 else 0))
        for li, line in enumerate(lines):
            xx = x + (first_indent if li == 0 and pi == 0 else 0)
            d.text((xx, y), line, font=fnt, fill=fill)
            y += int(fnt.size * leading)
    return y


def page_no(d, n):
    if n > 1:
        center(d, H - 108, f'- {n} -', F['tiny'], fill=GRAY)


def seal(d, cx, cy, label='인', size=94, alpha=210):
    paste_asset_center(d, 'stamp', 7, cx, cy, size * 1.12, opacity=0.82, rotate=1.5)
    center(d, cy-17, label, F['stamp_big'], fill=RED, x1=cx-size//2, x2=cx+size//2)


def round_stamp(d, cx, cy, text='간인', size=72):
    paste_asset_center(d, 'stamp', 3, cx, cy, size * 1.12, opacity=0.82, rotate=-2.0)
    center(d, cy-15, text, F['stamp'], fill=RED, x1=cx-size//2, x2=cx+size//2)


def hand_signature(d, x, y, scale=1.0):
    paste_cleanroom_asset(d, 'signature', 3, (x - 10*scale, y - 34*scale, x + 340*scale, y + 95*scale), opacity=0.90, rotate=-1.0)


def ruled_border(d, x=130, y=180, w=1390, h=1920, rows=None, lw=3):
    d.rectangle([x, y, x+w, y+h], outline=LINE, width=lw)
    if rows:
        yy = y
        for rh in rows[:-1]:
            yy += rh
            d.line([x, yy, x+w, yy], fill=LINE, width=2)


def table(d, x, y, headers, rows, widths, row_h=55, header=False):
    if headers:
        cx=x
        for h,w in zip(headers,widths):
            d.rectangle([cx,y,cx+w,y+row_h], outline=LINE, width=2)
            center(d, y+15, str(h), F['table'], x1=cx, x2=cx+w)
            cx += w
        y += row_h
    for row in rows:
        cx=x
        max_lines=1
        all_lines=[]
        for val,w in zip(row,widths):
            lines=wrap(d,str(val),F['table'],w-22)
            all_lines.append(lines)
            max_lines=max(max_lines,len(lines))
        h=max(row_h, 33*max_lines+20)
        for lines,w in zip(all_lines,widths):
            d.rectangle([cx,y,cx+w,y+h], outline=LINE, width=1)
            yy=y+12
            for line in lines:
                d.text((cx+11,yy),line,font=F['table'],fill=INK)
                yy += 33
            cx+=w
        y+=h
    return y


def cover_page():
    im,d=new_page()
    d.text((185, 110), '공증인 서윤정 사무소', font=F['cover_top'], fill=INK)
    d.text((1135, 110), 'TEL 02-473-2600', font=F['tiny'], fill=INK)
    d.text((1135, 138), 'FAX 02-473-2601', font=F['tiny'], fill=INK)
    d.line([180, 172, 1470, 172], fill=LINE, width=2)
    ruled_border(d, 190, 245, 1270, 1695, rows=None, lw=3)
    d.text((250, 305), '등부 2026년 제184호', font=F['cert_no'], fill=INK)
    center(d, 830, '인     증     서', F['cert_title'])
    d.rectangle([675, 980, 980, 1060], outline=LINE, width=2)
    center(d, 1001, '등     본', F['cert_body'], x1=675, x2=980)
    d.text((1085, 1975), 'B5 257mm x 182mm 70g/m²', font=F['tiny'], fill=GRAY)
    round_stamp(d, 1180, 880, '접수', 85)
    return im


def minutes_intro_page():
    im,d=new_page()
    center(d, 340, '라온모빌리티 주식회사', F['doc_title'])
    center(d, 405, '임시주주총회 의사록', F['doc_title'])
    y=565
    y=paragraph(d, 225, y, '라온모빌리티 주식회사(이하 "회사")의 임시주주총회를 다음과 같이 개최하다.', F['body'], 1200, 1.6)
    rows=[('1. 일    시', '2026년 3월 18일(수요일) 오전 10시'), ('2. 장    소', '서울특별시 강남구 테헤란로 218, 12층 회의실'), ('3. 출석상황', '주주총수 7명     발행주식총수 820,000주\n출석주주수 3명     출석주주의 주식수 612,400주')]
    for k,v in rows:
        d.text((250,y),k,font=F['body'],fill=INK)
        y=paragraph(d, 520, y, ': ' + v, F['body'], 790, 1.55)
        y += 10
    round_stamp(d, 860, 925, '간인', 86)
    y=paragraph(d, 225, 1050, '의장 대표이사 한도윤은 정관 규정에 따라 의장석에 등단하여 출석 주주수와 주식수를 보고한 후, 위와 같이 법정수에 달하는 주주가 출석하였으므로 본 총회가 적법하게 성립되었음을 알리고 개회를 선언하였다.', F['body'], 1200, 1.82, first_indent=45)
    y=paragraph(d, 225, y+55, '이어 다음 의안을 부의하고 그 심의와 승인을 구하다.', F['body'], 1200, 1.82)
    d.text((260, 1580), '제 1 호 의안. 대표이사 및 사내이사 선임의 건', font=F['h1'], fill=INK)
    d.line([260, 1622, 1030, 1622], fill=LINE, width=2)
    paragraph(d, 260, 1700, '의장은 회사의 신규 사업 확대와 경영관리 체계 정비를 위하여 사내이사 1인을 추가 선임할 필요가 있음을 설명하고, 후보자의 주요 경력과 이해관계 여부를 주주에게 보고하였다.', F['body'], 1080, 1.82, first_indent=40)
    page_no(d,2)
    return im


def agenda_page_1():
    im,d=new_page()
    d.text((225, 215), '제 1 호 의안. 대표이사 및 사내이사 선임의 건', font=F['h1'], fill=INK)
    d.line([225, 260, 1130, 260], fill=LINE, width=2)
    body=(
        '의장은 후보자 박서준이 회사의 제조 데이터 플랫폼 사업, 해외 고객관리 및 내부통제 업무를 총괄한 경험이 있어 회사의 장기 성장전략을 수행하기에 적합하다고 설명하였다. 이에 주주는 후보자의 약력, 겸직 현황, 특수관계 여부 및 결격사유가 없음을 확인하였다.\n\n'
        '출석 주주는 신중히 토의한 결과 다음 사람을 회사의 사내이사로 선임하고, 피선임자는 즉석에서 그 취임을 승낙하였다. 임기는 정관에서 정하는 바에 따른다.'
    )
    y=paragraph(d,225,330,body,F['body'],1200,1.83,first_indent=45)
    table(d, 275, y+45, ['성명','생년월일','주소','비고'], [['박서준','1984년 6월 12일','서울특별시 송파구 올림픽로 104','신규 선임']], [210,280,520,220], row_h=66)
    y += 225
    d.text((225, y+80), '제 2 호 의안. 본점 이전의 건', font=F['h1'], fill=INK)
    d.line([225, y+122, 820, y+122], fill=LINE, width=2)
    paragraph(d,225,y+175,'의장은 회사의 연구개발 인력 증원과 고객지원 조직 확대에 따라 본점을 이전할 필요가 있음을 설명하였다. 출석 주주는 이전 예정지의 임대차 조건, 교통 접근성 및 등기 변경 절차를 검토한 후 아래와 같이 본점 이전을 승인하였다.',F['body'],1200,1.83,first_indent=45)
    table(d, 275, 1585, None, [['변경 전','서울특별시 강남구 테헤란로 218, 12층'],['변경 후','서울특별시 성동구 아차산로 17길 48, 9층'],['이전일','2026년 4월 1일']], [250,900], row_h=62)
    round_stamp(d, 1180, 1680, '간인', 76)
    page_no(d,3)
    return im


def agenda_page_2():
    im,d=new_page()
    d.text((225, 210), '제 3 호 의안. 신주발행 및 투자계약 승인에 관한 건', font=F['h1'], fill=INK)
    d.line([225, 252, 1270, 252], fill=LINE, width=2)
    y=paragraph(d,225,325,'의장은 운영자금 확보와 생산설비 고도화를 위하여 보통주식 신주를 제3자 배정 방식으로 발행하고, 이에 부수하는 투자계약을 체결할 필요가 있음을 설명하였다. 출석 주주는 발행가액 산정 근거, 납입일, 배정대상자, 자금의 사용목적 및 기존 주주의 권리 보호 방안을 검토하였다.',F['body'],1200,1.8,first_indent=45)
    rows=[('1. 발행할 주식의 종류와 수','기명식 보통주식 120,000주'),('2. 1주의 발행가액','금 5,000원'),('3. 납입기일','2026년 4월 15일'),('4. 배정방법','제3자 배정'),('5. 자금사용 목적','연구개발비, 장비구입비 및 운전자금'),('6. 기타 사항','세부 계약조건은 대표이사에게 위임')]
    y=table(d, 260, y+40, None, rows, [360,860], row_h=58)
    y=paragraph(d,225,y+50,'위 의안에 대하여 출석 주주는 충분한 설명을 들은 후 질의하였고, 의장은 주요 질의에 답변하였다. 그 결과 출석 주주 전원의 찬성으로 원안대로 승인 가결되었다.',F['body'],1200,1.83,first_indent=45)
    d.text((225, y+70), '제 4 호 의안. 정관 일부 변경의 건', font=F['h1'], fill=INK)
    d.line([225, y+112, 890, y+112], fill=LINE, width=2)
    paragraph(d,225,y+165,'의장은 사업목적 추가, 전자문서 보관 및 이사회 소집 절차 정비를 위하여 정관 일부를 변경할 필요가 있음을 설명하고, 변경안의 주요 내용을 별지 대비표와 같이 제시하였다.',F['body'],1200,1.83,first_indent=45)
    page_no(d,4)
    return im


def agenda_page_3():
    im,d=new_page()
    d.text((225, 205), '제 4 호 의안. 정관 일부 변경의 건', font=F['h1'], fill=INK)
    d.line([225, 247, 890, 247], fill=LINE, width=2)
    y=paragraph(d,225,315,'정관 변경의 주요 사항은 다음과 같다. 본 변경은 회사의 사업 확장과 내부 의사결정 절차의 명확화를 위한 것이며, 관계 법령에 위반되는 사항이 없음을 확인하였다.',F['body'],1200,1.8,first_indent=45)
    clauses=[
        ('제2조(목적)', '인공지능 기반 문서처리 소프트웨어 개발, 데이터 검증 서비스, 기업 업무자동화 솔루션 공급 및 이에 부대하는 사업을 목적에 추가한다.'),
        ('제10조(주식의 전자등록)', '회사가 발행하는 주식 및 신주인수권증서에 표시되어야 할 권리는 전자등록기관의 전자등록계좌부에 전자등록한다.'),
        ('제27조(소집통지)', '주주총회 소집통지는 서면 또는 전자문서로 할 수 있으며, 전자문서 발송 기록을 회사가 보관한다.'),
        ('제35조(이사회)', '이사회는 대표이사가 소집하되, 긴급을 요하는 경우 소집기간을 단축할 수 있다.'),
        ('제42조(의사록)', '주주총회 및 이사회의 의사록은 전자문서 또는 서면으로 보관할 수 있다.')]
    for title, body in clauses:
        d.text((250,y),title,font=F['h2'],fill=INK)
        y=paragraph(d,300,y+48,body,F['body_small'],1100,1.72,first_indent=30)
        y+=22
    d.text((225, y+35), '제 5 호 의안. 임원 보수한도 승인의 건', font=F['h1'], fill=INK)
    d.line([225, y+78, 970, y+78], fill=LINE, width=2)
    paragraph(d,225,y+128,'의장은 2026 사업연도의 이사 보수한도를 금 600,000,000원, 감사 보수한도를 금 80,000,000원으로 정할 것을 제안하였다. 출석 주주는 회사의 사업 규모와 전년도 집행 내역을 고려하여 원안대로 승인하였다.',F['body'],1200,1.8,first_indent=45)
    round_stamp(d, 1220, 1985, '간인', 72)
    page_no(d,5)
    return im


def articles_table_page():
    im,d=new_page()
    d.text((225, 200), '[별지] 정관 변경 대비표', font=F['h1'], fill=INK)
    d.line([225, 245, 735, 245], fill=LINE, width=2)
    rows=[
        ('제2조\n목적', '회사는 다음의 사업을 영위함을 목적으로 한다.\n1. 소프트웨어 개발 및 공급업\n2. 데이터 처리 및 분석 서비스업', '회사는 다음의 사업을 영위함을 목적으로 한다.\n1. 소프트웨어 개발 및 공급업\n2. 데이터 처리 및 분석 서비스업\n3. 인공지능 기반 문서처리 서비스업\n4. 기업 업무자동화 솔루션 공급업'),
        ('제27조\n소집통지', '총회 소집은 회일 2주 전에 각 주주에게 서면으로 통지한다.', '총회 소집은 회일 2주 전에 각 주주에게 서면 또는 전자문서로 통지한다.'),
        ('제35조\n이사회', '이사회는 대표이사가 소집한다.', '이사회는 대표이사가 소집한다. 다만 긴급한 필요가 있는 경우 소집기간을 단축할 수 있다.'),
        ('제42조\n의사록', '총회 및 이사회 의사록은 본점에 비치한다.', '총회 및 이사회 의사록은 서면 또는 전자문서로 보관하며, 열람 요청 시 관계 법령에 따른다.')]
    table(d, 155, 320, ['조항','변경 전','변경 후'], rows, [190,600,600], row_h=62)
    y=1735
    paragraph(d,225,y,'위 대비표의 변경 사항은 주주총회 결의와 동시에 효력이 발생한다. 다만 관계 법령상 등기 또는 신고가 필요한 사항은 해당 절차를 완료한 때 대외적으로 효력이 발생한다.',F['body'],1200,1.8,first_indent=45)
    page_no(d,6)
    return im


def signature_page():
    im,d=new_page()
    d.text((225, 210), '결의 및 폐회', font=F['h1'], fill=INK)
    d.line([225, 253, 520, 253], fill=LINE, width=2)
    y=paragraph(d,225,330,'위 각 의안에 대하여 출석 주주 전원의 찬성으로 원안대로 승인 가결되었다. 의장은 더 이상 토의할 사항이 없음을 확인하고 오전 11시 35분 폐회를 선언하였다. 본 의사록은 의사의 경과요령과 그 결과를 명확히 하기 위하여 작성하고, 의장 및 출석 이사가 기명날인한다.',F['body'],1200,1.83,first_indent=45)
    center(d, y+100, '2026년 3월 18일', F['body'])
    y += 250
    rows=[('의장 대표이사','한도윤','(인)'),('사내이사','박서준','(인)'),('사내이사','이서연','(인)'),('감사','정민호','(인)')]
    for role,name,mark in rows:
        d.text((360,y),role,font=F['body'],fill=INK)
        d.text((720,y),name,font=F['body'],fill=INK)
        d.text((1040,y),mark,font=F['body'],fill=INK)
        seal(d,1110,y+22,'인',70)
        y += 105
    d.text((225, 1630), '라온모빌리티 주식회사', font=F['h1'], fill=INK)
    seal(d,710,1652,'법인',96)
    d.text((225, 1810), '첨부서류', font=F['h2'], fill=INK)
    table(d, 260, 1870, None, [['1. 주주명부','2. 진술서 및 확인서'],['3. 법인등기부등본','4. 정관 변경 대비표'],['5. 위임장 및 인감증명서','6. 참석자 신분확인 자료']], [560,560], row_h=68)
    page_no(d,7)
    return im


def notary_page():
    im,d=new_page()
    d.text((155, 135), '[별지 제37호 서식]', font=F['body_small'], fill=INK)
    rows=[88,110,92,92,92,150,145,145,145,145,145,145,145,145,145]
    ruled_border(d, 130, 190, 1395, 1845, rows=rows, lw=3)
    d.text((180, 220), '등부 2026년 제184호', font=F['cert_no'], fill=INK)
    center(d, 335, '인        증', F['cert_title'], x1=130, x2=1525)
    # Keep body text inside the official ruled rows.  The lines are intentionally
    # split at form-row boundaries to avoid overlap with the horizontal rules.
    notary_lines = [
        (500, '위 라온모빌리티 주식회사의 2026년 3월 18일자 임시주주총회 의사록에 대하여 촉탁인'),
        (590, '대표이사 한도윤은 본 공증인의 면전에서 위 의사록의 내용이 진실에 부합한다고 진술하고,'),
        (690, '기명날인이 본인의 것임을 확인하였다.'),
        (748, '본 공증인은 위 진술과 아래 기재 자료에 의하여 그 결의의 절차와 내용이 진실에 부합함을 확인하였다.'),
    ]
    for yy, line in notary_lines:
        d.text((175, yy), line, font=F['body_small'], fill=INK)
    center(d, 1040, '2026년 3월 19일 이 사무소에서 위 인증한다.', F['cert_body'], x1=130, x2=1525)
    d.text((250, 1290), '공증사무소명칭', font=F['cert_body'], fill=INK)
    d.text((620, 1290), '공증인 서윤정 사무소', font=F['cert_body'], fill=INK)
    d.text((250, 1428), '소        속', font=F['cert_body'], fill=INK)
    d.text((620, 1428), '서울중앙지방검찰청', font=F['cert_body'], fill=INK)
    d.text((250, 1565), '소 재 지 표 시', font=F['cert_body'], fill=INK)
    d.text((620, 1565), '서울특별시 서초구 서초대로 301', font=F['cert_body'], fill=INK)
    d.text((250, 1705), '공   증   인', font=F['cert_body'], fill=INK)
    d.text((760, 1705), '서   윤   정', font=F['cert_body'], fill=INK)
    hand_signature(d, 825, 1672, 1.0)
    seal(d, 1195, 1722, '인', 94)
    round_stamp(d, 820, 1800, '확인', 78)
    center(d, 1900, '아        래', F['cert_body'], x1=130, x2=1525)
    d.text((220, 1992), '1. 진술서 및 확인서 ____________     2. 주주명부 ____________', font=F['body'], fill=INK)
    d.text((220, 2072), '3. 법인등기부등본 ____________     4. 정관 ____________', font=F['body'], fill=INK)
    d.text((1120, 2190), '210mm x 297mm 70g/m²', font=F['tiny'], fill=GRAY)
    return im


def apply_scan_finish(im: Image.Image, angle=0.0):
    # Very light blur and contrast preservation for scanned legal document feel.
    if angle:
        im = im.rotate(angle, expand=False, fillcolor=(255,255,253), resample=Image.Resampling.BICUBIC)
    return im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=4))


def make_contact_sheet(page_paths):
    QA.mkdir(parents=True, exist_ok=True)
    cols, rows = 4, 2
    cell_w, cell_h = 420, 595
    sheet = Image.new('RGB', (cols*cell_w, rows*cell_h+70), 'white')
    d = ImageDraw.Draw(sheet)
    d.text((20,18), 'Cleanroom Board/Shareholders Meeting Minutes - 8 page overview', font=F['body_small'], fill=INK)
    for i,p in enumerate(page_paths):
        im=Image.open(p).convert('RGB')
        im.thumbnail((cell_w-30, cell_h-65))
        x=(i%cols)*cell_w+15
        y=(i//cols)*cell_h+70
        d.text((x,y-28), p.stem, font=F['tiny'], fill=INK)
        sheet.paste(im,(x,y))
    out=QA/'contact_sheet.jpg'
    sheet.save(out, quality=92)
    return out


def render_pdf_to_png(pdf_path: Path):
    out_dir=QA/'pdf_rendered_pages'
    if out_dir.exists(): shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc=fitz.open(pdf_path)
    paths=[]
    for i,page in enumerate(doc,1):
        zoom=1200/page.rect.width
        pix=page.get_pixmap(matrix=fitz.Matrix(zoom,zoom), alpha=False)
        p=out_dir/f'rendered_{i:03d}.png'
        pix.save(str(p))
        paths.append(p)
    return paths


def write_notes():
    text='''# Source vs Cleanroom Notes - ADM-01 Board/Shareholders Meeting Minutes

## Source visual facts used
- Notarial cover/certification flow, sparse legal-document pages, Batang-style Korean legal prose, long agenda clauses, attachment lists, red seals/gan-in marks, ruled notarial certificate forms.
- Source has scanned-paper artifacts and official form-like borders; the cleanroom sample recreates that genre without copying actual names, wording, stamps, or signatures.

## Cleanroom boundaries
- New fictional company: 라온모빌리티 주식회사.
- New fictional notary office and fictional officers/shareholders.
- All prose, agenda items, table values, seals, signatures, and certification numbers are newly authored.
- No internal generation/license/test metadata is placed inside the PDF body.

## Page plan
1. notarial certificate cover
2. meeting minutes opening and first agenda
3. agenda detail and head-office relocation
4. share issuance and investment approval
5. articles amendment and compensation limit
6. articles amendment comparison table
7. resolution/signature/attachment list
8. notarial certification form
'''
    (QA/'source_vs_cleanroom_notes.md').write_text(text, encoding='utf-8')


def write_manifest(pdf_path, page_paths, contact, rendered):
    data={
        'schema_version':1,
        'doc_id':'ADM-01',
        'title':'회의록(이사회·주총) 클린룸 대표본',
        'created_at':datetime.now().isoformat(),
        'source_reference':str(SRC_DIR),
        'cleanroom_policy':'source visual structure only; no copied company names, prose, stamps, signatures, or page images',
        'method':'Pillow ImageDraw direct raster composition, then PDF packaging + external-font supersampling + generated cleanroom visual assets',
        'render_scale':RENDER_SCALE,
        'deliverables':{
            'pdf':str(pdf_path.relative_to(OUT)),
            'pages':[str(p.relative_to(OUT)) for p in page_paths],
            'contact_sheet':str(contact.relative_to(OUT)),
            'rendered_pages':[str(p.relative_to(OUT)) for p in rendered],
        },
        'page_plan':['notarial cover','meeting opening','agenda 1-2','agenda 3-4','articles clauses','comparison table','signatures','notarial certification'],
    }
    (OUT/'manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def write_progress(pdf_path, contact):
    text=f'''# 2026-07-02 회의록 클린룸 테스트

## 목표
- `회의록(이사회·주총)` 1종을 클린룸 방식으로 8페이지 대표본 제작.
- 원본은 시각 구조 분석에만 사용하고, 원본 회사명/문장/도장/서명/페이지 이미지는 복제하지 않음.

## 산출물
- PDF: `{pdf_path}`
- 페이지 PNG: `{PAGES}`
- QA contact sheet: `{contact}`
- notes: `{QA / 'source_vs_cleanroom_notes.md'}`

## 구현 원칙
- 공통 보고서 렌더러를 사용하지 않고 회의록/공증 문서 전용 렌더러로 작성.
- 문서 본문에는 배포등급/배포범위/합성/라이선스/검수 같은 내부 메타를 넣지 않음.
- 공증 표지, 임시주주총회 의사록, 장문 의안, 정관 변경 대비표, 기명날인, 공증 인증서 양식을 페이지 유형별로 분리.

## 자체 판단
- 회의록 원본의 핵심 특징인 흑백 법무문서, 장문 조항, 붉은 간인/직인, 공증 양식 흐름을 반영했다.
- 최종 확인은 contact sheet와 PDF 재렌더링 페이지를 기준으로 수행한다.
'''
    PROGRESS.write_text(text, encoding='utf-8')


def sync_to_workbench():
    dst=WB/'samples'/'cleanroom'
    if dst.exists(): shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT/'cleanroom_board_minutes.pdf', dst/'cleanroom_board_minutes.pdf')
    shutil.copy2(OUT/'manifest.json', dst/'manifest.json')
    shutil.copytree(OUT/'pages', dst/'pages')
    shutil.copytree(OUT/'qa', dst/'qa')
    man_path=WB/'manifest.json'
    if man_path.exists():
        man=json.loads(man_path.read_text(encoding='utf-8'))
    else:
        man={'schema_version':1,'doc_id':'ADM-01','title':'회의록(이사회·주총)'}
    files=[]
    for p in sorted(dst.rglob('*')):
        if p.is_file():
            files.append({'path':str(p), 'source':str(OUT / p.relative_to(dst)) if (OUT / p.relative_to(dst)).exists() else str(OUT), 'kind':'cleanroom_trial'})
    man['cleanroom_samples']=files
    man['status']='cleanroom_sample_ready'
    man['updated_at']=datetime.now().astimezone().isoformat()
    man.setdefault('artifacts', {})['cleanroom']={
        'pdf':str(dst/'cleanroom_board_minutes.pdf'),
        'contact_sheet':str(dst/'qa/contact_sheet.jpg'),
        'pages_dir':str(dst/'pages'),
        'rendered_pages_dir':str(dst/'qa/pdf_rendered_pages'),
        'notes':str(dst/'qa/source_vs_cleanroom_notes.md'),
        'trial_manifest':str(dst/'manifest.json'),
        'quality_judgement':'accepted_for_workbench_cleanroom_reference',
        'render_scale':RENDER_SCALE
    }
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    if OUT.exists(): shutil.rmtree(OUT)
    PAGES.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    pages=[cover_page(), minutes_intro_page(), agenda_page_1(), agenda_page_2(), agenda_page_3(), articles_table_page(), signature_page(), notary_page()]
    # slight per-page scan rotation to break perfect synthetic feeling; keep text readable.
    angles=[0.0, -0.18, 0.12, -0.10, 0.08, -0.06, 0.10, -0.12]
    pages=[apply_scan_finish(im, a) for im,a in zip(pages, angles)]
    page_paths=[]
    for i,im in enumerate(pages,1):
        im = finish_supersampled_page(im, (W, H), RENDER_SCALE)
        pages[i-1] = im
        p=PAGES/f'page_{i:03d}.png'
        im.save(p)
        page_paths.append(p)
    pdf_path=OUT/'cleanroom_board_minutes.pdf'
    pages[0].save(pdf_path, save_all=True, append_images=pages[1:], resolution=200)
    contact=make_contact_sheet(page_paths)
    rendered=render_pdf_to_png(pdf_path)
    write_notes()
    write_manifest(pdf_path, page_paths, contact, rendered)
    write_progress(pdf_path, contact)
    sync_to_workbench()
    print(pdf_path)
    print(contact)
    print(f'pages={len(page_paths)} rendered={len(rendered)}')

if __name__ == '__main__':
    main()
