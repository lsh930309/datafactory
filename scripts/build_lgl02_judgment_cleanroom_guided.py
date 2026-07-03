#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import re
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
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / 'fonts'
OUT = ROOT / 'outputs' / 'cleanroom_trials' / 'LGL-02_판결문·결정문'
PAGES = OUT / 'pages'
QA = OUT / 'qa'
WB = ROOT / 'workbench' / 'documents' / '판결문·결정문__LGL-02'
SRC_DIR = WB / 'samples' / 'original'
PROGRESS = ROOT / 'docs' / 'reports' / 'cleanroom' / '20260703_lgl02_judgment_cleanroom_guided.md'
W, H = 1190, 1682
RENDER_SCALE = DEFAULT_RENDER_SCALE
PAGE_PT = (595, 842)
INK = (28, 28, 28)
RED = (178, 48, 48)


def font(size: int, bold: bool = False):
    for fn in ['batang.ttc', 'NanumGothicBold.otf' if bold else 'NanumGothic.otf', 'malgunbd.ttf' if bold else 'malgun.ttf']:
        p = FONTS / fn
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()

F = {
    'title': font(30, True),
    'h': font(24, True),
    'body': font(22),
    'body_s': font(20),
    'small': font(18),
    'tiny': font(15),
}

LINE_YS = [255, 315, 375, 435, 495, 555, 615, 675, 735, 795, 855, 915, 974, 1034, 1094, 1154, 1214, 1274, 1334, 1394, 1454]
PAGE4_YS = [255,315,375,435,498,555,615,675,751,784,817,850,926,985,1045,1105,1182,1214,1248,1281,1313,1347,1422,1482]

LEGAL_SENTENCES = [
    '피고인은 회사 자금을 보관ㆍ관리하는 지위에서 업무상 임무에 위배하여 금원을 임의로 사용하였다.',
    '이 법원이 적법하게 채택하여 조사한 증거에 의하면 다음과 같은 사실을 인정할 수 있다.',
    '피고인과 변호인은 일부 금액이 회사 운영비로 지출되었다고 주장하나 이를 뒷받침할 객관적 자료가 부족하다.',
    '계좌거래내역과 전자결재 기록의 기재 내용은 주요 부분에서 서로 부합하고 진술의 신빙성도 인정된다.',
    '피해 회사가 사후에 일부 금액을 회수하였다는 사정만으로 범행 당시의 불법영득의사가 부정되지는 않는다.',
    '따라서 피고인에게 업무상횡령죄 및 관련 법령 위반의 책임이 인정된다.',
    '다만 피고인이 범행을 대체로 인정하고 일부 피해 회복을 위하여 노력한 점은 유리한 정상으로 참작한다.',
    '그 밖에 피고인의 연령, 성행, 환경, 범행의 동기와 경위, 범행 후의 정황을 종합하여 형을 정한다.',
]


def clean():
    if OUT.exists():
        shutil.rmtree(OUT)
    PAGES.mkdir(parents=True, exist_ok=True)
    (QA / 'pdf_rendered_pages').mkdir(parents=True, exist_ok=True)


def new_page():
    im, d = new_supersampled_page(W, H, (255, 255, 253), RENDER_SCALE)
    rng = random.Random(2026070303)
    for _ in range(30):
        x, y = rng.randrange(80, W - 80), rng.randrange(85, H - 85)
        c = rng.randrange(235, 248)
        d.point((x, y), fill=(c, c, c))
    return im, d


def tw(d, s, f):
    return d.textlength(str(s), font=f)


def center(d, y, text, f, x1=0, x2=W, fill=INK):
    d.text(((x1 + x2 - tw(d, text, f)) / 2, y), str(text), font=f, fill=fill)


def draw_spaced_center(d, y, text, f, target_w=190, x1=0, x2=W):
    chars = list(text)
    raw = sum(tw(d, ch, f) for ch in chars)
    spacing = (target_w - raw) / max(1, len(chars) - 1)
    x = (x1 + x2 - target_w) / 2
    for ch in chars:
        d.text((x, y), ch, font=f, fill=INK)
        x += tw(d, ch, f) + spacing


def fit_line(d, text, f, width):
    text = re.sub(r'\s+', ' ', str(text)).strip()
    if tw(d, text, f) <= width:
        return text
    out = ''
    for ch in text:
        if tw(d, out + ch, f) > width:
            break
        out += ch
    return out.rstrip()


def make_lines(d, sentences, f, width, count, prefix=''):
    pool = []
    i = 0
    while len(pool) < count:
        s = sentences[i % len(sentences)]
        if i == 0 and prefix:
            s = prefix + s
        pool.append(fit_line(d, s, f, width))
        i += 1
    return pool[:count]


def line(d, x, y, text, f=None, width=None):
    f = f or F['body_s']
    if width:
        text = fit_line(d, text, f, width)
    d.text((x, y), text, font=f, fill=INK)


def wrap_lines(d, text, f, width):
    """Korean-friendly character wrap for fixed-width legal quote boxes."""
    out = []
    for para in str(text).split('\n'):
        para = re.sub(r'\s+', ' ', para).strip()
        if not para:
            out.append('')
            continue
        buf = ''
        for ch in para:
            if tw(d, buf + ch, f) <= width:
                buf += ch
            else:
                if buf:
                    out.append(buf.rstrip())
                buf = ch
        if buf:
            out.append(buf.rstrip())
    return out


def quote_box(d, box, paragraphs, f=None, pad_x=16, pad_y=17, lead=34):
    """Draw a dense quotation box matching the source judgment's witness quote rhythm."""
    f = f or F['body_s']
    x1, y1, x2, y2 = box
    d.rectangle([x1, y1, x2, y2], outline=INK, width=2)
    y = y1 + pad_y
    max_w = x2 - x1 - pad_x * 2
    for pi, para_text in enumerate(paragraphs):
        for row in wrap_lines(d, para_text, f, max_w):
            if y + lead > y2 - 4:
                return
            d.text((x1 + pad_x, y), row, font=f, fill=INK)
            y += lead
        if pi != len(paragraphs) - 1:
            y += 4


def page_no(d, n):
    center(d, 1593, f'- {n} -', F['small'])


def page1():
    im, d = new_page()
    center(d, 258, '서울중앙지방법원 제28형사부', F['h'])
    draw_spaced_center(d, 349, '판결', F['title'], 210)
    entries = [
        (435, '사        건', '2026고합1842  가. 업무상횡령, 나. 자본시장법위반'),
        (495, '피  고  인', '1.가. 이   준   (760312-1******), 회사원'),
        (556, '', '주거  서울특별시 서초구 반포대로 103'),
        (616, '', '등록기준지  부산광역시 동래구 명륜로 25'),
        (675, '', '2.나. 주식회사 다온인베스트먼트'),
        (735, '', '소재지  서울특별시 영등포구 국제금융로 18'),
        (795, '검        사', '김서하(기소), 윤태민(공판)'),
        (855, '변  호  인', '법무법인 세림'),
        (915, '', '담당변호사 정민우(피고인 이준을 위하여)'),
        (1034, '판 결 선 고', '2026. 6. 18.'),
    ]
    for y, lab, val in entries:
        if lab:
            line(d, 113, y, lab, F['body_s'])
        line(d, 352, y, val, F['body_s'], 720)
    center(d, 1156, '주        문', F['h'])
    orders = [
        '피고인 이준을 징역 1년 6월에 처한다.',
        '다만 이 판결 확정일부터 3년간 위 형의 집행을 유예한다.',
        '피고인 주식회사 다온인베스트먼트를 벌금 20,000,000원에 처한다.',
        '피고인 이준에게 120시간의 사회봉사를 명한다.',
        '압수된 증 제1호를 몰수한다.',
    ]
    for y, text in zip([1219, 1279, 1339, 1399, 1459], orders):
        line(d, 113, y, text, F['body_s'], 930)
    page_no(d, 1)
    return im


def page2():
    im, d = new_page()
    line(d, 158, 255, '이 사건 공소사실의 요지는 다음과 같다.', F['body_s'], 850)
    center(d, 376, '이        유', F['h'])
    line(d, 158, 440, '범 죄 사 실', F['body_s'], 850)
    line(d, 180, 500, '피고인 이준', F['body_s'], 850)
    ys = [560, 620, 680, 740, 800, 860]
    for y, t in zip(ys, make_lines(d, LEGAL_SENTENCES, F['body_s'], 850, len(ys))):
        line(d, 158, y, t, F['body_s'])
    line(d, 158, 920, '증거의 요지', F['body_s'])
    evid = ['1. 피고인의 일부 법정진술', '1. 각 계좌거래내역 및 전자결재 기록', '1. 수사보고 및 회계감정 결과서']
    for y, t in zip([979, 1040, 1099], evid):
        line(d, 178, y, t, F['body_s'])
    line(d, 158, 1159, '법령의 적용', F['body_s'])
    laws = ['1. 범죄사실에 대한 해당법조 및 형의 선택', '   형법 제356조, 제355조 제1항, 자본시장법 제443조 제1항', '1. 집행유예', '   형법 제62조 제1항', '1. 사회봉사명령', '   형법 제62조의2']
    for y, t in zip([1219, 1279, 1339, 1399, 1459], laws):
        line(d, 178, y, t, F['body_s'], 850)
    page_no(d, 2)
    return im


def dense_page(n, heading, ys, first_lines=None):
    im, d = new_page()
    first_lines = first_lines or []
    line(d, 158, ys[0], heading, F['body_s'], 850)
    content_ys = ys[1:]
    lines = []
    lines.extend(first_lines)
    lines.extend(make_lines(d, LEGAL_SENTENCES, F['body_s'], 850, len(content_ys) - len(lines)))
    for y, t in zip(content_ys, lines):
        line(d, 158, y, t, F['body_s'], 850)
    page_no(d, n)
    return im


def page4():
    im = dense_page(4, '2. 판단', PAGE4_YS[:8], [
        '가. 횡령의 고의와 불법영득의사에 대한 판단',
        '피고인은 회사 자금 집행 권한을 위임받은 지위에 있었으나 그 권한은 회사의 목적 범위 안에서',
        '행사되어야 한다. 개인 채무 변제에 사용한 금액은 회사 운영비로 보기 어렵다.',
    ])
    d = ScaledDraw(im, RENDER_SCALE)
    # Legal quotation boxes: match the original's dense boxed quotation style.
    quote_box(
        d,
        [126, 760, 1062, 918],
        [
            '회사의 임직원이 회사 자금을 보관하는 지위에서 이를 사적인 용도로 임의 소비하였다면 특별한 사정이 없는 한 불법영득의사가 인정된다.',
            '사후 변제 가능성이나 회계처리 예정이라는 사정만으로 그 책임을 달리 볼 수 없다.',
        ],
        F['body_s'],
        pad_x=16,
        pad_y=18,
        lead=35,
    )
    quote_box(
        d,
        [126, 1210, 1062, 1410],
        [
            '자본시장 관련 업무를 수행하는 자가 투자자 예치금의 보관ㆍ집행 내역을 사실과 다르게 표시하거나 회사 내부승인 절차를 거치지 않고 유용한 경우,',
            '그 행위의 동기와 사용처, 사후 정산 경위 및 피해 회복 여부를 종합하여 책임을 판단한다.',
        ],
        F['body_s'],
        pad_x=16,
        pad_y=18,
        lead=35,
    )
    # continue lower text like original
    for y, t in zip([936, 995, 1055, 1115, 1432, 1492], make_lines(d, LEGAL_SENTENCES[2:], F['body_s'], 850, 6)):
        line(d, 158, y, t, F['body_s'], 850)
    page_no(d, 4)
    return im


def page6():
    im, d = new_page()
    texts = make_lines(d, LEGAL_SENTENCES[4:], F['body_s'], 850, 8)
    for y, t in zip([255, 315, 375, 435, 495, 557, 615, 675], texts):
        line(d, 158, y, t, F['body_s'], 850)
    line(d, 158, 735, '3. 결론', F['body_s'])
    line(d, 158, 795, '이상의 이유로 주문과 같이 판결한다.', F['body_s'], 850)
    line(d, 662, 974, '판사     이서진', F['body_s'])
    d.line([820, 995, 1006, 995], fill=(160, 160, 160), width=1)
    page_no(d, 6)
    return im


def save_pages():
    pages = [
        page1(),
        page2(),
        dense_page(3, '1. 피고인 및 변호인의 주장', LINE_YS, ['피고인은 회사 자금 일부를 일시적으로 전용하였을 뿐이고 투자자 예치금을 훼손하려는 의사는', '없었다고 주장한다. 또한 이사회 보고가 예정되어 있었으므로 업무상 필요에 따른 집행이었다고 다툰다.']),
        page4(),
        dense_page(5, '나. 양형의 이유', LINE_YS, ['피고인의 범행은 회사와 투자자 사이의 신뢰관계를 훼손한 것으로 그 죄책이 가볍지 않다.', '특히 피고인은 재무담당 임원으로서 자금 보관과 집행의 적정성을 확보하여야 할 지위에 있었다.']),
        page6(),
    ]
    paths=[]
    for i, im in enumerate(pages, 1):
        im = finish_supersampled_page(im, (W, H), RENDER_SCALE)
        p = PAGES / f'page_{i:03d}.png'
        im.save(p)
        paths.append(p)
    return paths


def images_to_pdf(paths, pdf):
    doc = fitz.open()
    for p in paths:
        pg = doc.new_page(width=PAGE_PT[0], height=PAGE_PT[1])
        pg.insert_image(fitz.Rect(0,0,PAGE_PT[0],PAGE_PT[1]), filename=str(p))
    doc.save(pdf)
    doc.close()


def render_pdf(pdf):
    out=QA/'pdf_rendered_pages'
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    doc=fitz.open(pdf)
    paths=[]
    for i, pg in enumerate(doc, 1):
        pix=pg.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
        p=out/f'rendered_{i:03d}.png'
        pix.save(p)
        paths.append(p)
    doc.close()
    return paths


def qa_compare(generated):
    side_dir=QA/'side_by_side'; overlay_dir=QA/'overlay'
    shutil.rmtree(side_dir, ignore_errors=True); shutil.rmtree(overlay_dir, ignore_errors=True)
    side_dir.mkdir(parents=True); overlay_dir.mkdir(parents=True)
    srcs=sorted(SRC_DIR.glob('판결문_page_*.jpg'))[:len(generated)]
    sides=[]; overlays=[]
    for i,(sp,gp) in enumerate(zip(srcs, generated),1):
        src=Image.open(sp).convert('RGB').resize((W,H))
        gen=Image.open(gp).convert('RGB')
        side=Image.new('RGB',(W*2+30,H),(246,246,246)); side.paste(src,(0,0)); side.paste(gen,(W+30,0))
        d=ImageDraw.Draw(side); d.text((18,18),'SOURCE',font=F['small'],fill=(200,0,0)); d.text((W+48,18),'CLEANROOM',font=F['small'],fill=(0,70,200))
        out=side_dir/f'side_{i:03d}.jpg'; side.save(out,quality=92); sides.append(out)
        src_l=ImageOps.grayscale(src); gen_l=ImageOps.grayscale(gen)
        src_m=src_l.point(lambda v: 200 if v<185 else 0).convert('L')
        gen_m=gen_l.point(lambda v: 200 if v<185 else 0).convert('L')
        base=Image.new('RGB',(W,H),(255,255,255)); base.paste(Image.new('RGB',(W,H),(230,30,30)), mask=src_m); base.paste(Image.new('RGB',(W,H),(30,80,230)), mask=gen_m)
        op=overlay_dir/f'overlay_{i:03d}.png'; base.save(op); overlays.append(op)
    return sides, overlays


def contact(paths, title, name):
    cols=3; thumb_w=350; thumb_h=495; rows=(len(paths)+cols-1)//cols
    sheet=Image.new('RGB',(cols*390, rows*555+70),(244,244,242)); d=ImageDraw.Draw(sheet); d.text((22,20),title,font=F['small'],fill=INK)
    for i,p in enumerate(paths):
        im=Image.open(p).convert('RGB'); im.thumbnail((thumb_w, thumb_h))
        x=(i%cols)*390+20; y=(i//cols)*555+70
        d.text((x,y-24),p.stem,font=F['tiny'],fill=(90,90,90)); sheet.paste(im,(x,y)); d.rectangle([x,y,x+im.width,y+im.height],outline=(150,150,150))
    out=QA/name; sheet.save(out,quality=92); return out


def promote(pdf):
    dst=WB/'samples'/'cleanroom'
    shutil.rmtree(dst, ignore_errors=True)
    for sub in ['pages','qa/pdf_rendered_pages','qa/side_by_side','qa/overlay']:
        (dst/sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf, dst/'cleanroom_judgment_decision.pdf')
    shutil.copy2(OUT/'manifest.json', dst/'manifest.json')
    for p in sorted(PAGES.glob('page_*.png')): shutil.copy2(p,dst/'pages'/p.name)
    for p in sorted((QA/'pdf_rendered_pages').glob('rendered_*.png')): shutil.copy2(p,dst/'qa/pdf_rendered_pages'/p.name)
    for p in sorted((QA/'side_by_side').glob('side_*.jpg')): shutil.copy2(p,dst/'qa/side_by_side'/p.name)
    for p in sorted((QA/'overlay').glob('overlay_*.png')): shutil.copy2(p,dst/'qa/overlay'/p.name)
    for n in ['contact_sheet.jpg','source_overlay_contact.jpg','source_vs_cleanroom_notes.md']:
        shutil.copy2(QA/n,dst/'qa'/n)
    mp=WB/'manifest.json'; m=json.loads(mp.read_text(encoding='utf-8'))
    files=[]
    for p in [dst/'cleanroom_judgment_decision.pdf',dst/'manifest.json']+sorted((dst/'pages').glob('page_*.png'))+[dst/'qa/contact_sheet.jpg',dst/'qa/source_overlay_contact.jpg']+sorted((dst/'qa/pdf_rendered_pages').glob('rendered_*.png'))+sorted((dst/'qa/side_by_side').glob('side_*.jpg'))+sorted((dst/'qa/overlay').glob('overlay_*.png'))+[dst/'qa/source_vs_cleanroom_notes.md']:
        files.append({'path':str(p),'kind':'cleanroom_trial','source':str(OUT)})
    m['status']='cleanroom_sample_ready'; m['cleanroom_samples']=files
    m.setdefault('artifacts',{})['cleanroom']={'pdf':str(dst/'cleanroom_judgment_decision.pdf'),'contact_sheet':str(dst/'qa/contact_sheet.jpg'),'source_overlay_contact':str(dst/'qa/source_overlay_contact.jpg'),'pages_dir':str(dst/'pages'),'rendered_pages_dir':str(dst/'qa/pdf_rendered_pages'),'side_by_side_dir':str(dst/'qa/side_by_side'),'overlay_dir':str(dst/'qa/overlay'),'notes':str(dst/'qa/source_vs_cleanroom_notes.md'),'trial_manifest':str(dst/'manifest.json'),'source_kind':'cleanroom_from_collected_public_reference','quality_judgement':'line-grid-guided-source-layout-clone','render_scale':RENDER_SCALE}
    m['updated_at']=datetime.now().astimezone().isoformat(); mp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    clean(); pages=save_pages(); pdf=OUT/'cleanroom_judgment_decision.pdf'; images_to_pdf(pages,pdf)
    rendered=render_pdf(pdf); sides, overlays=qa_compare(pages)
    contact(rendered,'LGL-02 판결문/결정문 cleanroom PDF render QA','contact_sheet.jpg')
    contact(overlays,'LGL-02 source red / cleanroom blue line-grid overlay QA','source_overlay_contact.jpg')
    (QA/'source_vs_cleanroom_notes.md').write_text('''# LGL-02 판결문·결정문 클린룸 작성 메모

## 적용한 원본 분석
- 원본 6페이지 해상도 1190x1682을 그대로 사용했다.
- 원본의 텍스트 라인 y 클러스터를 페이지별로 추출해 같은 y-grid에 가상 법률 문장을 배치했다.
- 1페이지는 법원명, 판결 제목, 사건/피고인/검사/변호인/선고일, 주문의 x/y 앵커를 원본과 맞췄다.
- 4페이지는 원본의 인용 박스형 판례 문단 리듬을 반영해 박스 2개를 배치했다.
- PDF 재렌더, side-by-side, source(red)/cleanroom(blue) overlay QA를 생성했다.

## 클린룸 경계
- 실제 사건번호, 당사자, 사실관계, 주문, 이유 문장을 복사하지 않았다.
- 문서의 시각 구조와 행간/여백/밀도만 참고했다.
''',encoding='utf-8')
    manifest={'schema_version':1,'doc_id':'LGL-02','title':'판결문·결정문 클린룸 대표본','created_at':datetime.now().isoformat(timespec='seconds'),'method':'Pillow direct drawing with source text-line grid guidance + external-font supersampling','render_scale':RENDER_SCALE,'cleanroom_policy':'source layout/style only; all legal text and parties newly authored','deliverables':{'pdf':str(pdf.relative_to(OUT)),'pages':[str(p.relative_to(OUT)) for p in pages],'rendered_pages':[str(p.relative_to(OUT)) for p in rendered],'side_by_side':[str(p.relative_to(OUT)) for p in sides],'overlay':[str(p.relative_to(OUT)) for p in overlays],'contact_sheet':'qa/contact_sheet.jpg','source_overlay_contact':'qa/source_overlay_contact.jpg','notes':'qa/source_vs_cleanroom_notes.md'},'status':'cleanroom_trial_ready'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    PROGRESS.parent.mkdir(parents=True,exist_ok=True)
    PROGRESS.write_text(f'''# 2026-07-03 LGL-02 판결문·결정문 클린룸 라인그리드 재제작

## 지침 준수
- `docs/20260702_cleanroom_authoring_method.md`의 1종 단위 작업 원칙을 적용했다.
- 본 단계에서는 LGL-02만 제작했다.

## 산출물
- PDF: `{pdf}`
- Render QA: `{QA/'contact_sheet.jpg'}`
- Overlay QA: `{QA/'source_overlay_contact.jpg'}`
- Side-by-side: `{QA/'side_by_side'}`
- Overlay: `{QA/'overlay'}`

## 시각 기준
- 원본 해상도 1190x1682 유지.
- 원본 라인 y 클러스터와 주요 x 앵커를 기준으로 배치.
- 실제 텍스트/사건은 신규 작성.
''',encoding='utf-8')
    promote(pdf)
    print(pdf); print(QA/'contact_sheet.jpg'); print(QA/'source_overlay_contact.jpg'); print(f'pages={len(pages)} rendered={len(rendered)} side={len(sides)} overlay={len(overlays)}')
if __name__=='__main__': main()
