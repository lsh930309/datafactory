#!/usr/bin/env python3
from __future__ import annotations
import json, shutil
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
from PIL import Image, ImageDraw, ImageFont, ImageOps
ROOT=Path(__file__).resolve().parents[1]
FONTS=ROOT/'fonts'; OUT=ROOT/'outputs/cleanroom_trials/RPT-06_타당성·시장조사 보고서'; PAGES=OUT/'pages'; QA=OUT/'qa'; WB=ROOT/'workbench/documents/타당성·시장조사_보고서__RPT-06'; SRC_DIR=WB/'samples/original'; PROGRESS=ROOT/'docs/reports/cleanroom/20260703_rpt06_feasibility_cleanroom_guided.md'
W,H=750,1018; EXPORT_SCALE=2; EXPORT_SIZE=(W*EXPORT_SCALE,H*EXPORT_SCALE); PAGE_PT=(595,842); INK=(18,18,18); BLUE=(24,76,150); GOLD=(152,127,48)
# The collected public reference for RPT-06 is only 750x1018, but the cleanroom
# artifact is a first-class deliverable.  Keep the source-matched logical layout
# grid while exporting 2x page PNGs; render internally at 4x so external-font
# supersampling is retained after the 2x export downsample.
RENDER_SCALE = DEFAULT_RENDER_SCALE * EXPORT_SCALE
def font(size,bold=False):
    for fn in ['batang.ttc','NanumGothicBold.otf' if bold else 'NanumGothic.otf','malgunbd.ttf' if bold else 'malgun.ttf']:
        p=FONTS/fn
        if p.exists(): return ImageFont.truetype(str(p),size=size)
    return ImageFont.load_default()
F={'title':font(31,True),'h':font(18,True),'b':font(15),'s':font(13),'xs':font(11),'toc0':font(16),'toc1':font(14),'toc2':font(13),'toc':font(14),'tiny':font(9)}
def clean():
    if OUT.exists(): shutil.rmtree(OUT)
    PAGES.mkdir(parents=True); (QA/'pdf_rendered_pages').mkdir(parents=True)
def page(): return new_supersampled_page(W,H,(255,255,253),RENDER_SCALE)
def draw(im): return ScaledDraw(im, RENDER_SCALE)
def tw(d,s,f): return d.textlength(str(s),font=f)
def center(d,y,t,f,x1=0,x2=W,fill=INK): d.text(((x1+x2-tw(d,t,f))/2,y),str(t),font=f,fill=fill)
def right(d,x2,y,t,f,fill=INK): d.text((x2-tw(d,t,f),y),str(t),font=f,fill=fill)
def line(d,x,y,t,f=F['b'],fill=INK): d.text((x,y),str(t),font=f,fill=fill)
def wrap(d,text,f,w):
    out=[]
    for para in str(text).split('\n'):
        if not para.strip(): out.append(''); continue
        buf=''
        for ch in para:
            if tw(d,buf+ch,f)<=w: buf+=ch
            else:
                if buf: out.append(buf)
                buf=ch
        if buf: out.append(buf)
    return out
def para(d,x,y,text,f=F['b'],width=560,lead=24,indent=0):
    for pi,p in enumerate(str(text).split('\n')):
        if not p.strip(): y+=int(lead*.7); continue
        for li,l in enumerate(wrap(d,p,f,width-(indent if pi==0 else 0))):
            d.text((x+(indent if pi==0 and li==0 else 0),y),l,font=f,fill=INK); y+=lead
    return y
def pageno(d,n,roman=False): center(d,942,f'- {n} -',F['xs'])
def logo(d,x,y):
    paste_asset_center(d, 'logo', 5, x+28, y+28, 58, opacity=0.95)
    line(d,x+76,y+13,'한빛미래정책연구원',F['h'])

def cover():
    im,_=page(); d=draw(im); d.rectangle([100,126,193,167],outline=INK,width=1); center(d,138,'최종보고서',F['s'],x1=100,x2=193)
    center(d,278,'지역 물류 자동화 허브 구축을 위한',F['title']); center(d,327,'시장성 및 사업타당성 연구',F['title']); center(d,585,'2026. 7.',F['b']); logo(d,115,690); return im
def blank(): im,_=page(); return im
def submission():
    im,_=page(); d=draw(im); center(d,160,'제    출    문',F['h']); line(d,245,230,'한빛미래정책연구원 귀중',F['b'])
    para(d,180,290,'본 보고서를 「지역 물류 자동화 허브 구축을 위한 시장성 및 사업타당성 연구」 연구용역의 최종보고서로 제출합니다.',F['b'],420,28,20)
    center(d,455,'2026. 7.',F['s']);
    y=545
    for t in ['한빛미래정책연구원  산업전략센터', '연구책임자  책임연구원  서민재', '공동연구원  선임연구원  강하윤', '공동연구원  연구위원    오지훈', '자문위원    물류시스템공학과  박도겸']:
        center(d,y,t,F['s']); y+=28
    return im
def dot_leader(d,x1,y,x2,fill=INK):
    """Draw regular dot leaders without relying on variable-length text strings."""
    x=max(x1, 170)
    while x<x2:
        d.text((x,y),'.',font=F['tiny'],fill=fill)
        x+=6
def toc_page(num, items, roman):
    im,_=page(); d=draw(im)
    if num==1:
        center(d,154,'<목 차>',F['toc0'])
        y=222
    else:
        y=132
    prev_level=None
    for label,pn,level in items:
        if level==0 and prev_level is not None:
            y+=22
        x={0:94,1:110,2:126,3:143}.get(level,110+level*18)
        f={0:F['toc0'],1:F['toc1'],2:F['toc2'],3:F['toc2']}.get(level,F['toc2'])
        line(d,x,y,label,f)
        dot_start=x+tw(d,label,f)+14
        dot_y=y+5 if level==0 else y+4
        dot_leader(d,dot_start,dot_y,612)
        right(d,650,y,str(pn),f)
        y+={0:31,1:30,2:28,3:26}.get(level,27)
        prev_level=level
        if y>880: break
    pageno(d,roman,True); return im
def body_page(num, heading, paras, table=False):
    im,_=page(); d=draw(im); y=120; center(d,y,heading,F['h']); y+=70
    for p in paras[:3]: y=para(d,105,y,p,F['b'],540,26,18)+14
    if table:
        x=125; y+=20; widths=[120,165,120,120]; rows=[['구분','기준값','보수','낙관'],['처리능력','일 18,000박스','14,000박스','22,000박스'],['가동률','72%','58%','84%'],['손익분기','31개월','42개월','24개월']]
        for r,row in enumerate(rows):
            xx=x; h=34
            for c,val in enumerate(row):
                d.rectangle([xx,y,xx+widths[c],y+h],fill=(235,235,235) if r==0 else None,outline=INK,width=1); center(d,y+9,val,F['tiny'] if r else F['xs'],x1=xx,x2=xx+widths[c]); xx+=widths[c]
            y+=h
    pageno(d,num); return im
def pages():
    toc1=[
        ('I. 연구개요',1,0),('1. 연구추진 배경 및 목적',1,1),('2. 연구수행 절차',3,1),
        ('II. 지역 물류 자동화 허브 구축 타당성 검토',4,0),('1. 허브 구축의 기본 개념',4,1),
        ('가. 공동 물류거점의 기능',4,2),('나. 자동화 설비 도입의 필요성',5,2),
        ('다. 운영 데이터 연계 구조',6,2),('1) 주문·출고 데이터 통합',6,3),('2) 반품 처리와 재고 보정',7,3),
        ('2. 후보 권역별 수요 및 입지 검토',8,1),('가. 수요 기업 분포',8,2),('나. 고속도로·산업단지 접근성',9,2),
        ('다. 인력 수급 및 야간운영 여건',10,2),('라. 주요 성공사례와 적용 한계',12,2),
        ('3. 사업 추진방식 검토',14,1),('가. 민간 단독 추진 방식',14,2),('나. 공공·민간 협력 방식',15,2),
        ('다. 특수목적법인 설립 방식',16,2),('4. 시설 구성과 단계별 확장계획',18,1),('가. 1단계 핵심시설',18,2),('나. 2단계 확장시설',19,2),
    ]
    toc2=[
        ('5. 운영모델 및 서비스 체계',21,1),('가. 기본 운영 방향',21,2),('나. 표준 서비스 단가',22,2),
        ('다. 참여기업 정산 기준',23,2),('라. 품질관리 및 장애대응 체계',24,2),
        ('III. 시장환경 및 수요분석',25,0),('1. 국내 물류 자동화 시장 현황',25,1),('가. 시장 규모와 성장률',25,2),
        ('나. 산업별 도입 수요',27,2),('다. 설비 공급망과 유지보수 여건',29,2),
        ('2. 수요기업 인터뷰 결과',31,1),('가. 제조업체 요구사항',31,2),('나. 유통기업 요구사항',33,2),('다. 공통 애로사항',35,2),
        ('IV. 경제성 분석',37,0),('1. 투자비 산정',37,1),('가. 토지 및 건축비',37,2),('나. 자동화 설비비',39,2),
        ('다. 정보시스템 구축비',40,2),('2. 수익 및 비용 추정',41,1),('가. 처리물량 전망',41,2),('나. 운영비 및 인건비',43,2),
        ('3. 현금흐름 및 민감도 분석',45,1),('가. 기준 시나리오',45,2),('나. 보수·낙관 시나리오',47,2),
    ]
    toc3=[
        ('V. 법·제도 및 리스크 검토',49,0),('1. 인허가 및 입지규제 검토',49,1),('2. 사업추진 위험요인',52,1),
        ('VI. 종합 결론',56,0),('1. 추진 타당성 종합',56,1),('2. 단계별 실행계획',58,1),
        ('표 목차',61,0),('〈표 1-1〉 연구수행 단계',3,1),('〈표 2-1〉 후보 권역별 접근성 비교',11,1),
        ('〈표 3-1〉 수요기업 인터뷰 요약',32,1),('〈표 4-1〉 투자비 산정 내역',38,1),('〈표 4-3〉 경제성 분석 결과',46,1),
        ('그림 목차',65,0),('〈그림 2-1〉 공동 물류허브 운영 흐름',6,1),('〈그림 3-1〉 수요 산업별 구성',28,1),('〈그림 4-1〉 민감도 분석 결과',48,1)
    ]
    return [cover(),blank(),submission(),blank(),toc_page(1,toc1,'i'),toc_page(2,toc2,'ii'),toc_page(3,toc3,'iii'),body_page(1,'I. 연구개요',['본 연구는 수도권 남부권역의 중견 제조업체와 유통기업을 대상으로 자동화 물류 허브 구축 가능성을 검토하기 위하여 수행되었다.','조사 범위는 입지, 수요, 기술 적용성, 투자비 및 운영수익성을 포함하며 공개 통계와 기업 인터뷰, 유사시설 벤치마킹을 결합하였다.','연구의 중점은 단순 창고 확장이 아니라 피킹, 분류, 온도관리, 반품처리, 데이터 연동을 통합하는 허브 모델의 실현 가능성을 확인하는 데 있다.'],True)]
def save_pages():
    paths=[]
    for i,im in enumerate(pages(),1): im=finish_supersampled_page(im,EXPORT_SIZE,RENDER_SCALE); p=PAGES/f'page_{i:03d}.png'; im.save(p); paths.append(p)
    return paths
def images_to_pdf(paths,pdf):
    doc=fitz.open()
    for p in paths:
        pg=doc.new_page(width=PAGE_PT[0],height=PAGE_PT[1]); pg.insert_image(fitz.Rect(0,0,PAGE_PT[0],PAGE_PT[1]),filename=str(p))
    doc.save(pdf); doc.close()
def render(pdf):
    out=QA/'pdf_rendered_pages'; shutil.rmtree(out,ignore_errors=True); out.mkdir(parents=True); doc=fitz.open(pdf); res=[]
    for i,pg in enumerate(doc,1): pix=pg.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False); p=out/f'rendered_{i:03d}.png'; pix.save(p); res.append(p)
    doc.close(); return res
def qa(gens):
    side=QA/'side_by_side'; overlay=QA/'overlay'; shutil.rmtree(side,ignore_errors=True); shutil.rmtree(overlay,ignore_errors=True); side.mkdir(); overlay.mkdir(); sides=[]; overlays=[]
    srcs=sorted(SRC_DIR.glob('*page_*.jpg'))[:len(gens)]
    for i,(sp,gp) in enumerate(zip(srcs,gens),1):
        src=Image.open(sp).convert('RGB').resize(EXPORT_SIZE); gen=Image.open(gp).convert('RGB')
        canvas=Image.new('RGB',(EXPORT_SIZE[0]*2+48,EXPORT_SIZE[1]),(246,246,246)); canvas.paste(src,(0,0)); canvas.paste(gen,(EXPORT_SIZE[0]+48,0)); dd=ImageDraw.Draw(canvas); dd.text((24,24),'SOURCE',font=font(22),fill=(180,0,0)); dd.text((EXPORT_SIZE[0]+72,24),'CLEANROOM',font=font(22),fill=(0,70,190)); op=side/f'side_{i:03d}.jpg'; canvas.save(op,quality=92); sides.append(op)
        sm=ImageOps.grayscale(src).point(lambda v:190 if v<190 else 0).convert('L'); gm=ImageOps.grayscale(gen).point(lambda v:190 if v<190 else 0).convert('L'); base=Image.new('RGB',EXPORT_SIZE,'white'); base.paste(Image.new('RGB',EXPORT_SIZE,(230,30,30)),mask=sm); base.paste(Image.new('RGB',EXPORT_SIZE,(30,80,230)),mask=gm); oo=overlay/f'overlay_{i:03d}.png'; base.save(oo); overlays.append(oo)
    return sides,overlays
def contact(paths,title,name):
    sheet=Image.new('RGB',(4*280,2*410+70),(244,244,242)); d=ImageDraw.Draw(sheet); d.text((20,20),title,font=F['s'],fill=INK)
    for i,p in enumerate(paths):
        im=Image.open(p).convert('RGB'); im.thumbnail((250,350)); x=(i%4)*280+15; y=(i//4)*410+65; d.text((x,y-22),p.stem,font=F['tiny'],fill=(80,80,80)); sheet.paste(im,(x,y)); d.rectangle([x,y,x+im.width,y+im.height],outline=(150,150,150))
    out=QA/name; sheet.save(out,quality=92); return out
def promote(pdf):
    dst=WB/'samples/cleanroom'; shutil.rmtree(dst,ignore_errors=True)
    for sub in ['pages','qa/pdf_rendered_pages','qa/side_by_side','qa/overlay']: (dst/sub).mkdir(parents=True,exist_ok=True)
    shutil.copy2(pdf,dst/'cleanroom_feasibility_market_report.pdf'); shutil.copy2(OUT/'manifest.json',dst/'manifest.json')
    for p in sorted(PAGES.glob('page_*.png')): shutil.copy2(p,dst/'pages'/p.name)
    for p in sorted((QA/'pdf_rendered_pages').glob('rendered_*.png')): shutil.copy2(p,dst/'qa/pdf_rendered_pages'/p.name)
    for p in sorted((QA/'side_by_side').glob('side_*.jpg')): shutil.copy2(p,dst/'qa/side_by_side'/p.name)
    for p in sorted((QA/'overlay').glob('overlay_*.png')): shutil.copy2(p,dst/'qa/overlay'/p.name)
    for n in ['contact_sheet.jpg','source_overlay_contact.jpg','source_vs_cleanroom_notes.md']: shutil.copy2(QA/n,dst/'qa'/n)
    mp=WB/'manifest.json'; m=json.loads(mp.read_text(encoding='utf-8')); files=[]
    for p in [dst/'cleanroom_feasibility_market_report.pdf',dst/'manifest.json']+sorted((dst/'pages').glob('page_*.png'))+[dst/'qa/contact_sheet.jpg',dst/'qa/source_overlay_contact.jpg']+sorted((dst/'qa/pdf_rendered_pages').glob('rendered_*.png'))+sorted((dst/'qa/side_by_side').glob('side_*.jpg'))+sorted((dst/'qa/overlay').glob('overlay_*.png'))+[dst/'qa/source_vs_cleanroom_notes.md']: files.append({'path':str(p),'kind':'cleanroom_trial','source':str(OUT)})
    m['status']='cleanroom_sample_ready'; m['cleanroom_samples']=files; m.setdefault('artifacts',{})['cleanroom']={'pdf':str(dst/'cleanroom_feasibility_market_report.pdf'),'contact_sheet':str(dst/'qa/contact_sheet.jpg'),'source_overlay_contact':str(dst/'qa/source_overlay_contact.jpg'),'pages_dir':str(dst/'pages'),'rendered_pages_dir':str(dst/'qa/pdf_rendered_pages'),'side_by_side_dir':str(dst/'qa/side_by_side'),'overlay_dir':str(dst/'qa/overlay'),'notes':str(dst/'qa/source_vs_cleanroom_notes.md'),'trial_manifest':str(dst/'manifest.json'),'source_kind':'cleanroom_from_collected_public_reference','quality_judgement':'source-frontmatter-style-guided','render_scale':RENDER_SCALE}; m['updated_at']=datetime.now().astimezone().isoformat(); mp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    clean(); ps=save_pages(); pdf=OUT/'cleanroom_feasibility_market_report.pdf'; images_to_pdf(ps,pdf); rendered=render(pdf); sides,overlays=qa(ps); contact(rendered,'RPT-06 cleanroom PDF render QA','contact_sheet.jpg'); contact(overlays,'RPT-06 source red / cleanroom blue overlay QA','source_overlay_contact.jpg')
    (QA/'source_vs_cleanroom_notes.md').write_text('# RPT-06 타당성·시장조사 보고서 클린룸 작성 메모\n\n- 원본 앞 8페이지의 표지/공백/제출문/공백/목차 구조를 그대로 페이지 유형으로 분해했다.\n- 기관명, 제목, 목차 항목, 본문은 신규 작성했다.\n- side-by-side 및 overlay QA를 생성했다.\n',encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps({'schema_version':1,'doc_id':'RPT-06','title':'타당성·시장조사 보고서 클린룸 대표본','created_at':datetime.now().isoformat(timespec='seconds'),'method':'Pillow direct drawing with source frontmatter style guidance + external-font supersampling + 2x cleanroom export','render_scale':RENDER_SCALE,'export_scale':EXPORT_SCALE,'export_size':list(EXPORT_SIZE),'status':'cleanroom_trial_ready','deliverables':{'pdf':str(pdf.relative_to(OUT)),'pages':[str(p.relative_to(OUT)) for p in ps],'rendered_pages':[str(p.relative_to(OUT)) for p in rendered],'side_by_side':[str(p.relative_to(OUT)) for p in sides],'overlay':[str(p.relative_to(OUT)) for p in overlays],'contact_sheet':'qa/contact_sheet.jpg','source_overlay_contact':'qa/source_overlay_contact.jpg','notes':'qa/source_vs_cleanroom_notes.md'}},ensure_ascii=False,indent=2),encoding='utf-8')
    PROGRESS.parent.mkdir(parents=True,exist_ok=True); PROGRESS.write_text(f'# 2026-07-03 RPT-06 클린룸 전면부 스타일 가이드 제작\n\n- PDF: `{pdf}`\n- Render QA: `{QA/"contact_sheet.jpg"}`\n- Overlay QA: `{QA/"source_overlay_contact.jpg"}`\n- 본 단계에서는 RPT-06 1종만 제작했다.\n',encoding='utf-8')
    promote(pdf); print(pdf); print(QA/'contact_sheet.jpg'); print(QA/'source_overlay_contact.jpg'); print(f'pages={len(ps)} rendered={len(rendered)} side={len(sides)} overlay={len(overlays)}')
if __name__=='__main__': main()
