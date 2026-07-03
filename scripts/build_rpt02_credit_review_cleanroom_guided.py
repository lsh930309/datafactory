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
from PIL import Image, ImageDraw, ImageFont, ImageOps
ROOT=Path(__file__).resolve().parents[1]
FONTS=ROOT/'fonts'; OUT=ROOT/'outputs/cleanroom_trials/RPT-02_여신 심사의견서 [산출물]'; PAGES=OUT/'pages'; QA=OUT/'qa'; WB=ROOT/'workbench/documents/여신_심사의견서_[산출물]__RPT-02'; SRC_DIR=WB/'samples/original'; PROGRESS=ROOT/'docs/reports/cleanroom/20260703_rpt02_credit_review_cleanroom_guided.md'
W,H=1191,1684; PAGE_PT=(595,842); INK=(18,18,18); GRAY=(238,238,238)
RENDER_SCALE = DEFAULT_RENDER_SCALE
def font(size,bold=False):
    for fn in ['batang.ttc','NanumGothicBold.otf' if bold else 'NanumGothic.otf','malgunbd.ttf' if bold else 'malgun.ttf']:
        p=FONTS/fn
        if p.exists(): return ImageFont.truetype(str(p),size=size)
    return ImageFont.load_default()
F={'title':font(38,True),'h':font(25),'b':font(22),'s':font(19),'xs':font(16),'tiny':font(13)}
def clean():
    if OUT.exists(): shutil.rmtree(OUT)
    PAGES.mkdir(parents=True); (QA/'pdf_rendered_pages').mkdir(parents=True)
def page(): return new_supersampled_page(W,H,(255,255,253),RENDER_SCALE)
def new():
    return new_supersampled_page(W,H,(255,255,253),RENDER_SCALE)
def tw(d,s,f): return d.textlength(str(s),font=f)
def center(d,y,t,f,x1=0,x2=W,fill=INK): d.text(((x1+x2-tw(d,t,f))/2,y),str(t),font=f,fill=fill)
def line(d,x,y,t,f=F['s'],fill=INK): d.text((x,y),str(t),font=f,fill=fill)
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
def para(d,x,y,text,f=F['s'],width=700,lead=34):
    for l in wrap(d,text,f,width):
        if not l: y+=int(lead*.7); continue
        d.text((x,y),l,font=f,fill=INK); y+=lead
    return y
def cell(d,box,text,f=F['s'],fill=None,align='center'):
    x1,y1,x2,y2=box; d.rectangle(box,fill=fill,outline=INK,width=2)
    lines=wrap(d,text,f,x2-x1-10); yy=y1+(y2-y1-len(lines)*int(f.size*1.25))/2
    for l in lines:
        xx=x1+8 if align=='left' else (x1+x2-tw(d,l,f))/2
        d.text((xx,yy),l,font=f,fill=INK); yy+=int(f.size*1.25)
def approval(d):
    x,y=682,290; widths=[40,82,82,82,82]; h1,h2=38,86
    d.rectangle([x,y,x+sum(widths),y+h1+h2],outline=INK,width=3); cell(d,[x,y,x+widths[0],y+h1+h2],'결\n재',F['xs'])
    cx=x+widths[0]
    for lab,nm in zip(['담당','부서장','임원','사장'],['김도윤','이상훈','박경태','최명철']):
        cell(d,[cx,y,cx+82,y+h1],lab,F['xs']); cell(d,[cx,y+h1,cx+82,y+h1+h2],nm,F['xs']); cx+=82
def page1():
    im,d=new(); center(d,205,'여신심사 결과표',F['title']); d.line([435,255,756,255],fill=INK,width=3); approval(d)
    x,y=144,452; w=898
    # main outer table closely matches source
    cell(d,[x,y,x+232,y+44],'안    건',F['s'],GRAY); cell(d,[x+232,y,x+w,y+44],'주식회사 한빛푸드 운전자금 대출 여신 승인의 건',F['s'],None,'left'); y+=44
    left_w=76; lab_w=156; val_w=318; mid_lab=154; right_w=w-left_w-lab_w-val_w-mid_lab
    d.rectangle([x,y,x+w,y+600],outline=INK,width=3); d.rectangle([x,y,x+left_w,y+600],fill=GRAY,outline=INK,width=2); center(d,y+248,'심사',F['s'],x1=x,x2=x+left_w); center(d,y+286,'내용',F['s'],x1=x,x2=x+left_w)
    rows=[('신청구분','신규','',''),('재 무 자','주식회사 한빛푸드\n(대표: 이서준)','업종·업태','농·소매업/식품유통'),('보 증 인','정하영 (주민번호: 680312-2******)','',''),('신청금액','금 오억원정\n(₩500,000,000)','기 여신금액','금 이억원정\n(₩200,000,000)'),('대출과목','운전자금대출','대출이율','연 4.5% (변동금리)'),('총여신금액','금 칠억원정 (₩700,000,000)','',''),('대출기한','2026.07.02 ~ 2028.07.01 (2년)','',''),('담보물건','서울특별시 강남구 역삼동 123-45 대지 및 건물','',''),('감정가액','금 십이억원정 (₩1,200,000,000)','',''),('선 순 위','금 삼억원정 (₩300,000,000)','',''),('당사설정금액','금 육억원정 (₩600,000,000)','',''),('신청지점','강남지점','청 약 자','박민준')]
    yy=y
    heights=[43,100,43,73,43,43,43,43,43,43,43,43]
    for (lab,val,lab2,val2),h in zip(rows,heights):
        cell(d,[x+left_w,yy,x+left_w+lab_w,yy+h],lab,F['s'],GRAY); 
        if lab2:
            cell(d,[x+left_w+lab_w,yy,x+left_w+lab_w+val_w,yy+h],val,F['s'],None,'left'); cell(d,[x+left_w+lab_w+val_w,yy,x+left_w+lab_w+val_w+mid_lab,yy+h],lab2,F['s'],GRAY); cell(d,[x+left_w+lab_w+val_w+mid_lab,yy,x+w,yy+h],val2,F['s'],None,'left')
        else:
            cell(d,[x+left_w+lab_w,yy,x+w,yy+h],val,F['s'],None,'left')
        yy+=h
    y2=y+600; d.rectangle([x,y2,x+w,y2+385],outline=INK,width=3); d.rectangle([x,y2,x+left_w,y2+385],fill=GRAY,outline=INK,width=2); center(d,y2+150,'심사',F['s'],x1=x,x2=x+left_w); center(d,y2+188,'결과',F['s'],x1=x,x2=x+left_w)
    para(d,x+105,y2+68,'본건 주식회사 한빛푸드에서 여신 승인 신청한 건으로 융자협의서 및 부속서류에 대하여 아래 심사 위원이 심의한바, 아래 취급 조건부로 가결한다.',F['s'],720,36)
    center(d,y2+200,'- 취급조건 -',F['s']); yy=y2+245
    for t in ['1. 대출금리: 기준금리(COFIX 3개월물) + 가산금리 1.5%p','2. 원금 균등 분할상환 (매월 말일 자동이체)','3. 담보 근저당권 설정 완료 후 실행','4. 보증인 연대보증 징구']:
        line(d,x+105,yy,t,F['s']); yy+=35
    return im
def page2():
    im,d=new(); x,y=144,195; widths=[105,165,105,78,248,145,70]; headers=['구분','직위','성명','가·부','심사의견','서명 또는\n날인','비고']; rows=[headers,['위원장','상무이사','정대현','가','담보 충분, 상환능력 양호','정대현 (인)',''],['심사위원','여신심사부장','오승현','가','재무구조 안정, LTV 적정','오승현 (인)',''],['심사위원','리스크관리팀장','한미란','가','신용등급 BBB+, 조건 충족','한미란 (인)',''],['심사위원','준법감시인','윤태석','가','법규 위반 사항 없음','윤태석 (인)','']]
    yy=y
    for r,row in enumerate(rows):
        h=75 if r==0 else 43; xx=x
        for c,val in enumerate(row): cell(d,[xx,yy,xx+widths[c],yy+h],val,F['s'] if r else F['xs'],GRAY if r==0 else None); xx+=widths[c]
        yy+=h
    return im
def save_pages():
    paths=[]
    for i,im in enumerate([page1(),page2()],1): im=finish_supersampled_page(im,(W,H),RENDER_SCALE); p=PAGES/f'page_{i:03d}.png'; im.save(p); paths.append(p)
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
    srcs=[SRC_DIR/'여신심사결과서_filled_page_001.jpg',SRC_DIR/'여신심사결과서_filled_page_002.jpg']; side=QA/'side_by_side'; overlay=QA/'overlay'; shutil.rmtree(side,ignore_errors=True); shutil.rmtree(overlay,ignore_errors=True); side.mkdir(); overlay.mkdir(); sides=[]; overlays=[]
    for i,(sp,gp) in enumerate(zip(srcs,gens),1):
        src=Image.open(sp).convert('RGB').resize((W,H)); gen=Image.open(gp).convert('RGB'); canvas=Image.new('RGB',(W*2+30,H),(246,246,246)); canvas.paste(src,(0,0)); canvas.paste(gen,(W+30,0)); dd=ImageDraw.Draw(canvas); dd.text((18,18),'SOURCE',font=F['xs'],fill=(180,0,0)); dd.text((W+48,18),'CLEANROOM',font=F['xs'],fill=(0,70,190)); op=side/f'side_{i:03d}.jpg'; canvas.save(op,quality=92); sides.append(op)
        sm=ImageOps.grayscale(src).point(lambda v:190 if v<190 else 0).convert('L'); gm=ImageOps.grayscale(gen).point(lambda v:190 if v<190 else 0).convert('L'); base=Image.new('RGB',(W,H),'white'); base.paste(Image.new('RGB',(W,H),(230,30,30)),mask=sm); base.paste(Image.new('RGB',(W,H),(30,80,230)),mask=gm); oo=overlay/f'overlay_{i:03d}.png'; base.save(oo); overlays.append(oo)
    return sides,overlays
def contact(paths,title,name):
    sheet=Image.new('RGB',(820,650),(244,244,242)); d=ImageDraw.Draw(sheet); d.text((20,20),title,font=F['s'],fill=INK)
    for i,p in enumerate(paths): im=Image.open(p).convert('RGB'); im.thumbnail((365,516)); x=20+i*400; y=65; d.text((x,y-23),p.stem,font=F['xs'],fill=(80,80,80)); sheet.paste(im,(x,y)); d.rectangle([x,y,x+im.width,y+im.height],outline=(150,150,150))
    out=QA/name; sheet.save(out,quality=92); return out
def promote(pdf):
    dst=WB/'samples/cleanroom'; shutil.rmtree(dst,ignore_errors=True)
    for sub in ['pages','qa/pdf_rendered_pages','qa/side_by_side','qa/overlay']: (dst/sub).mkdir(parents=True,exist_ok=True)
    shutil.copy2(pdf,dst/'cleanroom_credit_review_opinion.pdf'); shutil.copy2(OUT/'manifest.json',dst/'manifest.json')
    for p in sorted(PAGES.glob('page_*.png')): shutil.copy2(p,dst/'pages'/p.name)
    for p in sorted((QA/'pdf_rendered_pages').glob('rendered_*.png')): shutil.copy2(p,dst/'qa/pdf_rendered_pages'/p.name)
    for p in sorted((QA/'side_by_side').glob('side_*.jpg')): shutil.copy2(p,dst/'qa/side_by_side'/p.name)
    for p in sorted((QA/'overlay').glob('overlay_*.png')): shutil.copy2(p,dst/'qa/overlay'/p.name)
    for n in ['contact_sheet.jpg','source_overlay_contact.jpg','source_vs_cleanroom_notes.md']: shutil.copy2(QA/n,dst/'qa'/n)
    mp=WB/'manifest.json'; m=json.loads(mp.read_text(encoding='utf-8')); files=[]
    for p in [dst/'cleanroom_credit_review_opinion.pdf',dst/'manifest.json']+sorted((dst/'pages').glob('page_*.png'))+[dst/'qa/contact_sheet.jpg',dst/'qa/source_overlay_contact.jpg']+sorted((dst/'qa/pdf_rendered_pages').glob('rendered_*.png'))+sorted((dst/'qa/side_by_side').glob('side_*.jpg'))+sorted((dst/'qa/overlay').glob('overlay_*.png'))+[dst/'qa/source_vs_cleanroom_notes.md']: files.append({'path':str(p),'kind':'cleanroom_trial','source':str(OUT)})
    m['status']='cleanroom_sample_ready'; m['cleanroom_samples']=files; m.setdefault('artifacts',{})['cleanroom']={'pdf':str(dst/'cleanroom_credit_review_opinion.pdf'),'contact_sheet':str(dst/'qa/contact_sheet.jpg'),'source_overlay_contact':str(dst/'qa/source_overlay_contact.jpg'),'pages_dir':str(dst/'pages'),'rendered_pages_dir':str(dst/'qa/pdf_rendered_pages'),'side_by_side_dir':str(dst/'qa/side_by_side'),'overlay_dir':str(dst/'qa/overlay'),'notes':str(dst/'qa/source_vs_cleanroom_notes.md'),'trial_manifest':str(dst/'manifest.json'),'source_kind':'cleanroom_from_synthetic_reference','quality_judgement':'source-table-layout-guided','render_scale':RENDER_SCALE}; m['updated_at']=datetime.now().astimezone().isoformat(); mp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    clean(); ps=save_pages(); pdf=OUT/'cleanroom_credit_review_opinion.pdf'; images_to_pdf(ps,pdf); rendered=render(pdf); sides,overlays=qa(ps); contact(rendered,'RPT-02 cleanroom PDF render QA','contact_sheet.jpg'); contact(overlays,'RPT-02 source red / cleanroom blue overlay QA','source_overlay_contact.jpg')
    (QA/'source_vs_cleanroom_notes.md').write_text('# RPT-02 여신 심사의견서 클린룸 작성 메모\n\n- 대표 원본 `여신심사결과서_filled` 2페이지의 결재란, 본문 표, 심사위원표 좌표를 기준으로 제작했다.\n- 차주, 보증인, 금액, 지점, 심사의견, 위원명은 신규 가상 데이터다.\n- side-by-side 및 overlay QA를 생성했다.\n',encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps({'schema_version':1,'doc_id':'RPT-02','title':'여신 심사의견서 클린룸 대표본','created_at':datetime.now().isoformat(timespec='seconds'),'method':'Pillow direct drawing with source table layout guidance + external-font supersampling','render_scale':RENDER_SCALE,'status':'cleanroom_trial_ready','deliverables':{'pdf':str(pdf.relative_to(OUT)),'pages':[str(p.relative_to(OUT)) for p in ps],'rendered_pages':[str(p.relative_to(OUT)) for p in rendered],'side_by_side':[str(p.relative_to(OUT)) for p in sides],'overlay':[str(p.relative_to(OUT)) for p in overlays],'contact_sheet':'qa/contact_sheet.jpg','source_overlay_contact':'qa/source_overlay_contact.jpg','notes':'qa/source_vs_cleanroom_notes.md'}},ensure_ascii=False,indent=2),encoding='utf-8')
    PROGRESS.parent.mkdir(parents=True,exist_ok=True); PROGRESS.write_text(f'# 2026-07-03 RPT-02 여신 심사의견서 클린룸 표 구조 가이드 제작\n\n- PDF: `{pdf}`\n- Render QA: `{QA/"contact_sheet.jpg"}`\n- Overlay QA: `{QA/"source_overlay_contact.jpg"}`\n- 본 단계에서는 RPT-02 1종만 제작했다.\n',encoding='utf-8')
    promote(pdf); print(pdf); print(QA/'contact_sheet.jpg'); print(QA/'source_overlay_contact.jpg'); print(f'pages={len(ps)} rendered={len(rendered)} side={len(sides)} overlay={len(overlays)}')
if __name__=='__main__': main()
