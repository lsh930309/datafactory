from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from datafactory.authoring import render_authoring_preview
from datafactory.fonts import default_font_path
from datafactory.registry import FIRST_PRIORITY_DOC_IDS
from datafactory.authoring_backup import backup_authoring_json_before_write

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "workbench" / "documents"
NOW = datetime.now(timezone.utc).isoformat()

DATE_KR = "choice:2024년 06월 21일|2025년 08월 07일|2026년 06월 29일|2023년 05월 08일|2024년 03월 08일"
DATE_DOT = "choice:2025.08.01|2025.08.06|2023.01.01|2023.07.07|2022.01.01|2022.12.31|2024.08.15."
DATE_ISO = "choice:2025-08-01|2025-08-06|2023-01-01|2023-07-07|2020-07-30|2025-07-14"
DATETIME = "choice:2026-06-29 11:37|2026-06-29 13:03|2025-09-19 09:30|2024-03-08 15:20"
COMPANIES = "choice:한국딥러닝 주식회사|미래테크 주식회사|대한산업 주식회사|한빛솔루션 주식회사|주식회사 지엘어소시에이츠|메가스터디교육(주)|주식회사엔식품|주식회사엠케이컨텐츠"
TAX_OFFICES = "choice:동대문세무서장|삼성세무서장|서초세무서장|김포세무서장|국세청장"
LOCAL_GOV = "choice:서울특별시 시장|경기도 용인시장|서울특별시 서초구청장|김포세무서장"
ADDRESS = "address.ko"
MONEY = "money.krw"
RRN = "person.rrn"
PHONE = "person.phone_kr"
NAME = "person.name_ko"
BIZNO = "pattern:###-##-#####"
CORPNO = "pattern:######-#######"
DOCNO16 = "pattern:####-####-####-####"
DOCNO_LONG = "pattern:############################************"
PAGE = "choice:1 / 1|( 1 / 1 )|( 1 / 4 )|(2쪽 중 제1쪽)|1/3|1/8"

Spec = tuple[str, str, str, str]
ManualSpec = tuple[str, str, str, str, list[int], str]

def s(field_id: str, label: str, rule: str, align: str = "left") -> Spec:
    return field_id, label, rule, align


def ms(field_id: str, label: str, rule: str, align: str, bbox: list[int], source_text: str = "") -> ManualSpec:
    return field_id, label, rule, align, bbox, source_text


FIN01_COMPANY_NAMES = [
    "한빛정밀 주식회사", "대한소재 주식회사", "미래모빌리티 주식회사", "세종바이오 주식회사", "주식회사 지엘어소시에이츠",
    "주식회사 엔식품", "주식회사 엠케이컨텐츠", "아라전자 주식회사", "태성기계 주식회사", "누리패키징 주식회사",
    "동원테크놀로지 주식회사", "서린화학 주식회사", "대영물류 주식회사", "케이엠디지털 주식회사", "비전메디칼 주식회사",
    "해솔에너지 주식회사", "우리푸드 주식회사", "금강건설 주식회사", "중앙산업 주식회사", "유니온오토 주식회사",
    "블루웨이브 주식회사", "청명금속 주식회사", "에이치앤에스테크 주식회사", "제일플랜트 주식회사", "도담소프트 주식회사",
    "라온시스템 주식회사", "에코그린 주식회사", "스마트팩토리솔루션 주식회사", "대림정공 주식회사", "경인유통 주식회사",
    "아이앤씨로지스 주식회사", "케이알푸드 주식회사", "성우전자부품 주식회사", "동서바이오팜 주식회사", "비케이첨단소재 주식회사",
    "에스엠이노베이션 주식회사", "한국전장 주식회사", "더원건축 주식회사", "프라임디스플레이 주식회사", "메트로솔루션 주식회사",
    "한울정보통신 주식회사", "리치팜 주식회사", "새론패션 주식회사", "제이앤케이상사 주식회사", "오션테크 주식회사",
    "그린팩토리 주식회사", "나래정밀화학 주식회사", "인사이트랩 주식회사", "코리아컴포넌트 주식회사", "엘앤비서비스 주식회사",
    "에이스금형 주식회사", "파인로보틱스 주식회사", "넥스트에너지 주식회사", "에버메디 주식회사", "신화산전 주식회사",
    "마루물산 주식회사", "티에스반도체 주식회사", "제니스바이오 주식회사", "한강디자인 주식회사", "오름제조 주식회사",
]
FIN01_REPRESENTATIVES = [
    "김민준", "이서준", "박도윤", "최예준", "정시우", "강하준", "조주원", "윤지호", "장지후", "임준우",
    "한서연", "오서윤", "서지우", "신서현", "권민서", "김하은", "이하윤", "박윤서", "최지유", "정지민",
]
FIN01_BUSINESS_TYPES = ["제조업", "건설업", "정보통신업", "도매 및 소매업", "전문, 과학 및 기술서비스업", "운수 및 창고업", "음식료품 제조업", "전기장비 제조업"]
FIN01_BUSINESS_ITEMS = [
    "산업용 기계 및 장비 제조", "전자부품 제조 및 도소매", "시스템 소프트웨어 개발 및 공급업", "금속구조물 및 창호공사",
    "식품 가공 및 유통", "전시물 제작 및 환경연출 설치", "물류대행 및 보관서비스", "의료기기 연구개발",
    "자동차 부품 제조", "건축공사업 및 실내건축", "화학소재 제조", "정보통신 공사업", "산업플랜트 설계 및 제작",
    "농산물 가공 및 판매", "반도체 장비 부품 제조",
]
FIN01_ADDRESSES = [
    "서울특별시 강남구 테헤란로 152", "서울특별시 중구 세종대로 110", "서울특별시 마포구 월드컵북로 396",
    "경기도 성남시 분당구 판교역로 235", "경기도 화성시 동탄산단6길 15", "경기도 안산시 단원구 산단로 325",
    "인천광역시 연수구 송도과학로 32", "부산광역시 해운대구 센텀중앙로 79", "대구광역시 달서구 성서공단로 11",
    "대전광역시 유성구 테크노중앙로 50", "광주광역시 북구 첨단과기로 123", "울산광역시 남구 산업로 100",
]
FIN01_TAX_OFFICE_NAMES = [
    "종로", "중부", "남대문", "용산", "성북", "서대문", "마포", "영등포", "강서", "양천",
    "구로", "동작", "금천", "관악", "강남", "삼성", "반포", "서초", "역삼", "성동",
    "동대문", "중랑", "도봉", "노원", "송파", "잠실", "강동", "분당", "성남", "수원",
    "동수원", "화성", "평택", "안산", "동안양", "안양", "부천", "인천", "북인천", "서인천",
    "남인천", "김포", "고양", "파주", "의정부", "남양주", "춘천", "원주", "대전", "서대전",
    "북대전", "청주", "천안", "전주", "광주", "북광주", "대구", "서대구", "부산진", "동울산",
]
ID03_SHAREHOLDER_NAMES = [
    "김민준", "이서준", "박도윤", "최예준", "정시우", "강하준", "조주원", "윤지호", "장지후", "임준우",
    "한서연", "오서윤", "서지우", "신서현", "권민서", "김하은", "이하윤", "박윤서", "최지유", "정지민",
    "강도현", "조현우", "윤서진", "장유준", "임건우", "한지안", "오하린", "서아윤", "신채원", "권예린",
    "김도겸", "이시온", "박지훈", "최유찬", "정태민", "강서우", "조민재", "윤하람", "장수현", "임유나",
    "한재윤", "오다은", "서은우", "신우진", "권나윤", "김가온", "이현서", "박준서", "최서아", "정라온",
    "강유진", "조은서", "윤지율", "장채윤", "임시현", "한도하", "오예준", "서건", "신태오", "권하늘",
]
ID03_ISSUE_DATES = [
    "2023년 5월 8일", "2023년 12월 29일", "2024년 3월 8일", "2024년 6월 21일", "2024년 9월 30일",
    "2025년 1월 15일", "2025년 4월 11일", "2025년 8월 7일", "2025년 12월 18일", "2026년 2월 5일",
]
ID03_SHARE_COUNTS = [
    5_000, 10_000, 20_000, 30_000, 50_000, 75_000, 100_000, 120_000, 150_000, 200_000,
    250_000, 300_000, 450_000, 501_000, 532_597, 600_000, 750_000, 1_000_000,
]
ID03_PAR_VALUES = [100, 500, 1_000, 5_000]
ID01_ACTIVITY_BUNDLES = [
    {
        "types": ["제조업", "제조업", "도소매", "서비스업", "정보통신업", "도소매", "전문,과학 및 기술서비스업"],
        "items": ["전자부품 제조업", "산업용 장비 제조", "전자상거래 소매업", "시스템 유지보수", "응용 소프트웨어 개발", "전기전자 부품 도소매", "기술 연구개발업"],
    },
    {
        "types": ["농업", "농업", "농업", "제조업", "제조업", "도소매", "전문,과학 및 기술서비스업"],
        "items": ["채소작물 재배업", "채소류 수경재배", "작물재배 지원 서비스업", "농산물 식품 제조", "식품 가공 및 포장", "농산물 유통 판매", "농림수산학 연구개발업"],
    },
    {
        "types": ["건설업", "건설업", "제조업", "도소매", "서비스업", "전문,과학 및 기술서비스업", "정보통신업"],
        "items": ["금속구조물 창호공사", "실내건축 공사업", "건축자재 제조", "건축자재 도소매", "시설물 유지관리", "건축 설계 및 감리", "건설정보 시스템 개발"],
    },
    {
        "types": ["도소매", "도소매", "제조업", "서비스업", "정보통신업", "운수 및 창고업", "전문,과학 및 기술서비스업"],
        "items": ["생활용품 도매업", "온라인 상품 중개업", "포장재 제조업", "물류대행 서비스", "판매관리 소프트웨어 개발", "상품 보관 및 운송", "시장조사 및 컨설팅"],
    },
    {
        "types": ["전문,과학 및 기술서비스업", "정보통신업", "서비스업", "도소매", "제조업", "전문,과학 및 기술서비스업", "교육서비스업"],
        "items": ["연구개발 컨설팅", "데이터 처리 및 호스팅", "디자인 서비스", "연구장비 도소매", "시제품 제조", "기술 시험 분석", "직무교육 서비스"],
    },
    {
        "types": ["정보통신업", "정보통신업", "서비스업", "도소매", "전문,과학 및 기술서비스업", "제조업", "교육서비스업"],
        "items": ["소프트웨어 개발 및 공급", "정보시스템 통합 구축", "클라우드 운영 서비스", "컴퓨터 주변기기 도소매", "정보보호 컨설팅", "통신장비 제조", "소프트웨어 교육"],
    },
]
ID01_ISSUE_REASONS = ["공공기관 제출용", "금융기관 제출용", "거래처 제출용", "입찰 참가용", "계약 체결용", "보조금 신청용", "해외거래 제출용"]
CRD02_RATING_GRADES = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC",
]
CRD02_PURPOSES = [
    "공공기관 제출용", "조달청 입찰 제출용", "지방자치단체 제출용", "금융기관 제출용", "협력업체 등록용",
    "상거래 신용도 확인용", "계약 심사용", "납품업체 평가용", "대리점 개설 심사용", "용역 입찰 제출용",
    "민간기업 제출용", "보증기관 제출용", "투자심사 참고용", "거래처 등록용", "공사 입찰 제출용",
]
CRD02_COMPANY_NAMES = [
    "서울평가정보", "한빛정밀", "대한소재", "미래모빌리티", "세종바이오", "지엘어소시에이츠",
    "엔식품", "엠케이컨텐츠", "아라전자", "태성기계", "누리패키징", "동원테크",
    "서린화학", "대영물류", "케이엠디지털", "비전메디칼", "해솔에너지", "우리푸드",
    "금강건설", "중앙산업", "유니온오토", "블루웨이브", "청명금속", "에이치앤에스",
    "제일플랜트", "도담소프트", "라온시스템", "에코그린", "스마트팩토리", "대림정공",
    "경인유통", "아이앤씨로지스", "케이알푸드", "성우전자", "동서바이오팜", "비케이소재",
    "에스엠이노베이션", "한국전장", "더원건축", "프라임디스플레이", "메트로솔루션", "한울정보통신",
    "리치팜", "새론패션", "제이앤케이", "오션테크", "그린팩토리", "나래정밀",
    "인사이트랩", "코리아컴포넌트", "엘앤비서비스", "에이스금형", "파인로보틱스", "넥스트에너지",
    "에버메디", "신화산전", "마루물산", "티에스반도체", "제니스바이오", "오름제조",
]
CRD02_RATING_DESCRIPTIONS = {
    "AAA": "상거래 신용능력이 최고 수준이며 환경 변화에 대한 안정성이 매우 높음",
    "AA+": "상거래 신용능력이 매우 우수하며 채무이행 안정성이 높음",
    "AA": "상거래 신용능력이 우수하며 단기적인 환경 변화에도 안정적임",
    "AA-": "상거래 신용능력이 우수하나 상위 등급 대비 일부 변동 가능성이 있음",
    "A+": "상거래 신용능력이 양호하고 채무이행 능력이 안정적임",
    "A": "상거래 신용능력이 양호하나 경기 변화에 따른 영향이 일부 있음",
    "A-": "상거래 신용능력은 양호하나 장래 안정성은 상위 등급보다 낮음",
    "BBB+": "상거래 신용능력은 보통 이상이며 환경 변화에 따른 관리가 필요함",
    "BBB": "상거래 신용능력은 보통 수준이며 채무이행 능력은 인정됨",
    "BBB-": "상거래 신용능력은 보통이나 경기 변화에 대한 민감도가 있음",
    "BB+": "상거래 신용능력이 다소 제한적이나 단기 지급능력은 보유함",
    "BB": "상거래 신용능력이 제한적이고 환경 변화에 취약할 수 있음",
    "BB-": "상거래 신용능력이 낮은 편이며 거래 조건 확인이 필요함",
    "B+": "상거래 신용능력이 미흡하고 채무이행 안정성이 낮음",
    "B": "상거래 신용능력이 미흡하여 거래 위험 관리가 필요함",
    "B-": "상거래 신용능력이 취약하고 재무 변동 위험이 큼",
    "CCC+": "채무불이행 위험이 높고 상거래 신용도가 매우 취약함",
    "CCC": "채무불이행 위험이 매우 높아 거래 안정성이 낮음",
    "CCC-": "채무불이행 가능성이 현저하여 거래상 주의가 필요함",
    "CC": "채무불이행 가능성이 매우 크며 정상적 상거래 신용이 제한됨",
}
ID11_WRITER_POSITIONS = ["대표이사", "이사", "재무이사", "자금팀장", "경영지원팀장", "준법감시인", "관리부장", "총무팀장", "회계책임자", "대리인"]
ID11_OWNERSHIP_SETS = [
    (40, 30, 20, 10), (55, 25, 10, 10), (35, 30, 25, 10), (60, 20, 10, 10), (45, 35, 10, 10),
    (70, 10, 10, 10), (50, 30, 15, 5), (34, 33, 23, 10), (48, 27, 15, 10), (80, 10, 5, 5),
]
ID11_ENGLISH_GIVEN_NAMES = [
    "Minjun", "Seojun", "Doyun", "Yejun", "Siwoo", "Hajun", "Juwon", "Jiho", "Jihu", "Junwoo",
    "Seoyeon", "Seoyun", "Jiwoo", "Seohyeon", "Minseo", "Haeun", "Hayun", "Yunseo", "Jiyu", "Jimin",
    "Dohyun", "Hyunwoo", "Seojin", "Yujun", "Geonwoo", "Jian", "Harin", "Ayun", "Chaewon", "Yerin",
]
ID11_ENGLISH_SURNAMES = ["Kim", "Lee", "Park", "Choi", "Jung", "Kang", "Cho", "Yoon", "Jang", "Lim", "Han", "Oh", "Seo", "Shin", "Kwon"]




SEC01_FUND_THEMES = [
    ("코리아배당성장", "주식", "2등급(높은위험)"),
    ("단기채권플러스", "채권", "5등급(낮은위험)"),
    ("글로벌테크성장", "주식", "2등급(높은위험)"),
    ("미국S&P500", "주식", "2등급(높은위험)"),
    ("국공채10년", "채권", "4등급(보통위험)"),
    ("머니마켓", "단기금융", "6등급(매우낮은위험)"),
    ("차이나전기차", "주식", "1등급(매우높은위험)"),
    ("인컴멀티에셋", "혼합", "3등급(다소높은위험)"),
    ("반도체TOP10", "주식", "2등급(높은위험)"),
    ("리츠부동산인프라", "부동산", "3등급(다소높은위험)"),
    ("ESG우량채권", "채권", "5등급(낮은위험)"),
    ("고배당커버드콜", "주식", "2등급(높은위험)"),
]
SEC01_ASSET_MANAGERS = [
    ("삼성자산운용주식회사", "www.samsungfund.com"),
    ("미래에셋자산운용주식회사", "www.miraeassetfund.com"),
    ("한국투자신탁운용주식회사", "www.kim.co.kr"),
    ("KB자산운용주식회사", "www.kbam.co.kr"),
    ("신한자산운용주식회사", "www.shinhanfund.com"),
    ("NH-Amundi자산운용주식회사", "www.nh-amundi.com"),
    ("한화자산운용주식회사", "www.hanwhafund.com"),
    ("키움투자자산운용주식회사", "www.kiwoomam.com"),
    ("교보악사자산운용주식회사", "www.kyoboaxa-im.co.kr"),
    ("우리자산운용주식회사", "www.wooriam.kr"),
]
SEC01_BRANDS = ["KODEX", "TIGER", "ACE", "KBSTAR", "SOL", "HANARO", "ARIRANG", "KOSEF", "PLUS", "WOORI"]
SEC01_OFFERING_AMOUNTS = ["1조좌", "2조좌", "3조좌", "5조좌", "10조좌", "20조좌", "5,000억좌", "8,000억좌", "1억좌", "3억좌"]
SEC01_SECURITY_TYPES = ["투자신탁 수익증권", "집합투자증권", "상장지수집합투자기구 수익증권", "증권상장지수투자신탁 수익증권"]
SEC01_OFFERING_PERIODS = [
    "이 집합투자기구는 별도의 모집(매출)기간이 정해져 있지 않으며, 계속하여 모집할 수 있습니다.",
    "이 투자신탁은 별도의 모집기간 없이 설정일부터 계속하여 모집할 수 있습니다.",
    "모집기간은 효력발생일 이후 별도로 정하지 않으며 판매회사를 통하여 계속 모집합니다.",
    "이 집합투자증권은 판매회사의 영업일에 한하여 계속하여 모집할 수 있습니다.",
]


def sec01_fund_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index in range(60):
        theme, asset_type, risk_grade = SEC01_FUND_THEMES[index % len(SEC01_FUND_THEMES)]
        manager, domain = SEC01_ASSET_MANAGERS[index % len(SEC01_ASSET_MANAGERS)]
        brand = SEC01_BRANDS[index % len(SEC01_BRANDS)]
        year = 2024 + (index % 3)
        month = 1 + (index * 2) % 12
        day = 1 + (index * 5) % 27
        prep = date(year, month, day)
        effective = prep + timedelta(days=7 + (index % 14))
        fund_name = f"{brand} {theme} 증권상장지수투자신탁[{asset_type}]"
        profiles.append(
            {
                "investment_risk_grade_label": "투자 위험 등급",
                "investment_risk_grade": risk_grade,
                "fund_name": fund_name,
                "asset_manager_name": manager,
                "disclosure_reference_text": f"집합투자업자(http://{domain}) 및 금융투자협회(www.kofia.or.kr) 홈페이지 참조",
                "prospectus_preparation_date": f"{prep.year}. {prep.month}.{prep.day}",
                "securities_registration_effective_date": f"{effective.year}. {effective.month}.{effective.day}",
                "offered_security_type": SEC01_SECURITY_TYPES[index % len(SEC01_SECURITY_TYPES)],
                "offering_total_amount": f"[모집(매출) 총액:{SEC01_OFFERING_AMOUNTS[index % len(SEC01_OFFERING_AMOUNTS)]}]",
                "offering_period_description": SEC01_OFFERING_PERIODS[index % len(SEC01_OFFERING_PERIODS)],
            }
        )
    return profiles

TRD07_BUYER_COMPANIES = [
    "아남정밀", "동원정밀", "세명기공", "대성금형", "한빛테크", "유림산업", "삼영정공", "태광이엔지", "대진산업", "우진하이텍",
    "경남정밀", "성우테크", "명진금속", "한솔기계", "진성정공", "세진오토", "대흥테크", "코리아몰드", "부광산업", "신우정밀",
    "영진산업", "남도기계", "케이엠테크", "서진엠텍", "창원정공", "다온테크", "하나기전", "대림테크", "유성정밀", "청우산업",
]
TRD07_VENDOR_COMPANIES = [
    "(주)고려이노테크", "(주)한성엠텍", "(주)대광정밀", "(주)진영테크", "(주)성진하이텍", "(주)우림엔지니어링",
    "(주)태산금형", "(주)동양이노텍", "(주)세원정공", "(주)영남테크", "(주)비전몰드", "(주)해성기계",
    "(주)케이피아이", "(주)명성툴링", "(주)창신메카텍",
]
TRD07_CONTACT_NAMES = ["정창식", "김도현", "박민수", "이준호", "최성훈", "장현우", "오지훈", "한상민", "윤태석", "서동욱", "임재현", "강민재", "조승현", "권영수", "신재훈"]
TRD07_VENDOR_STAFF = ["정규현", "김민재", "박서준", "이도윤", "최지훈", "장우진", "한지호", "오현석", "서준영", "강태민", "윤성호", "임건우", "조현우", "권도현", "신유찬"]
TRD07_VENDOR_EMAIL_IDS = ["gyuhyun", "minjae", "seojun", "doyun", "jihoon", "woojin", "jiho", "hyunseok", "junyoung", "taemin", "sungho", "geonwoo", "hyunwoo", "dohyun", "yuchan"]
TRD07_ADDRESSES = [
    "경남 창원시 마산합포구 문화동 3길 14", "경남 창원시 마산합포구 진북면 산단1길 5", "경남 창원시 성산구 완암로 50",
    "경남 김해시 주촌면 골든루트로 80", "부산 강서구 녹산산단 335로 20", "울산 북구 매곡산업로 35",
    "경북 구미시 1공단로 212", "대구 달성군 구지면 국가산단대로 33길 12", "충남 천안시 서북구 직산읍 2공단5로 97",
    "충북 청주시 흥덕구 오송읍 오송생명로 123", "경기 화성시 동탄산단6길 15", "경기 안산시 단원구 산단로 325",
]
TRD07_PRODUCT_CATALOG = [
    "Side Retainer Core 직경 및 길이 검사용 Jig 폭 76.3mm*길이100mm",
    "Side Retainer Core 직경 및 길이 검사용 Jig 폭 77.7mm*길이100mm",
    "Side Retainer Core 직경 및 길이 검사용 Jig 폭 76.3mm*길이120mm",
    "Side Retainer Core 직경 및 길이 검사용 Jig 폭 77.7mm*길이120mm",
    "Guide Pin 검사구 Ø12*L80 열처리품", "Bracket LH 용접검사용 Fixture", "Bracket RH 용접검사용 Fixture",
    "Al Plate 가공품 120*80*15T", "SUS304 Spacer Ring Ø45*Ø30*8T", "Bearing Housing 정밀가공품",
    "Motor Shaft Runout 측정 Jig", "Press Die Insert Block A형", "Press Die Insert Block B형", "Sensor Bracket 검사용 Gauge",
    "Connector Cover 사출금형 코어", "Cooling Plate 알루미늄 가공품", "Cylinder Mount Block", "Linear Guide Base Plate",
    "Robot Gripper Finger L형", "Robot Gripper Finger R형", "Vacuum Pad Holder Ø30", "Pallet Stopper Block",
    "Positioning Pin SKD11 Ø10", "Locating Bush SCM440", "Inspection Master Block", "Welding Jig Clamp Set",
    "CNC 가공용 Base Plate 250*180", "Transfer Rail Support", "Cam Slide Wear Plate", "Mold Core Pin Ø6*L55",
    "Mold Ejector Plate 가공품", "Die Cushion Spacer", "Heat Sink Bracket", "자동화라인 센서 브라켓",
    "컨베이어 Stopper Assy", "포장기 Knife Holder", "압입 Jig Guide Block", "치수 검사 Master Gauge",
    "Air Cylinder Bracket", "LM Guide Rail Support", "소형 Gear Housing", "샤프트 고정용 Collar",
    "배터리 셀 트레이 가이드", "PCB 검사 Jig Plate", "Frame Angle Bracket", "Laser Marking Fixture",
    "Vision Camera Mount", "Servo Motor Adapter Plate", "Turn Table Locator", "Hinge Bracket 가공품",
    "금형 냉각수 Manifold", "Loader Arm Bush", "Pin Press Fixture", "조립검사용 Master Jig",
    "도장라인 Hanger Hook", "Clamp Block SCM440", "Shaft Holder Ø25", "Tube Cutting Guide",
    "Casting 검사 Gauge", "Al6061 Cover Plate", "정밀 Spacer Set", "Index Plate 가공품",
]
TRD07_DELIVERY_TERMS = ["ASAP", "7일 이내", "10일 이내", "2주 이내", "12/20", "12/27", "1/10", "1/17", "협의", "납기준수"]
TRD07_REMARKS = ["Core 직경 및 길이 검사용", "도면 기준 제작", "열처리 후 납품", "검사성적서 첨부", "재질증명서 첨부", "긴급 발주", "분할 납품 가능", "표면처리 포함"]


def _trd07_phone(index: int, *, ext: bool = False) -> str:
    base = f"055-{240 + index % 40:03d}-{3000 + (index * 137) % 7000:04d}"
    return f"{base}({300 + index % 80})" if ext else base


def trd07_purchase_order_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index in range(60):
        order_date = date(2024 + index % 3, 1 + (index * 2) % 12, 1 + (index * 3) % 27)
        buyer = TRD07_BUYER_COMPANIES[index % len(TRD07_BUYER_COMPANIES)]
        vendor = TRD07_VENDOR_COMPANIES[index % len(TRD07_VENDOR_COMPANIES)]
        buyer_contact = TRD07_CONTACT_NAMES[index % len(TRD07_CONTACT_NAMES)]
        vendor_staff = TRD07_VENDOR_STAFF[index % len(TRD07_VENDOR_STAFF)]
        buyer_addr = TRD07_ADDRESSES[index % len(TRD07_ADDRESSES)]
        vendor_addr = TRD07_ADDRESSES[(index + 1) % len(TRD07_ADDRESSES)]
        row: dict[str, str] = {
            "purchase_order_number": f"P{order_date:%y%m%d}-{10 + index % 90}",
            "receiver_company_name": buyer,
            "sender_company_name": vendor,
            "receiver_contact_title": f"{buyer_contact} 사장님",
            "sender_department_contact": f"구매팀 {vendor_staff} 대리",
            "receiver_tel": f"010-{3000 + (index * 73) % 7000:04d}-{1000 + (index * 91) % 9000:04d}",
            "sender_tel": _trd07_phone(index, ext=True),
            "receiver_fax": _trd07_phone(index + 11),
            "sender_fax": _trd07_phone(index + 23),
            "sender_email": f"{TRD07_VENDOR_EMAIL_IDS[index % len(TRD07_VENDOR_EMAIL_IDS)]}@kinno.co.kr",
            "receiver_address": buyer_addr,
            "sender_address": vendor_addr,
            "prepared_date": f"{order_date.month}/{order_date.day}",
            "reviewed_date": f"{order_date.month}/{order_date.day}",
            "approved_date": f"{order_date.month}/{order_date.day}",
            "shipping_address": f"발송지 : {vendor_addr}",
            "delivery_site_name": f"{vendor.replace('(주)', '').replace('주식회사', '').strip()} 진북공장",
            "form_code": f"KIT-QP-S09-{1 + index % 9:02d}_Rev.{index % 4}",
            "issuer_company_footer": vendor,
        }
        total = 0
        for slot in range(1, 5):
            product = TRD07_PRODUCT_CATALOG[(index * 3 + slot - 1) % len(TRD07_PRODUCT_CATALOG)]
            qty = 1 + ((index + slot) % 4)
            unit_price = [30_000, 45_000, 60_000, 75_000, 90_000, 120_000, 150_000][(index + slot) % 7]
            amount = qty * unit_price
            total += amount
            row[f"line_{slot}_number"] = str(slot)
            row[f"line_{slot}_item_description"] = product
            row[f"line_{slot}_unit"] = "EA"
            row[f"line_{slot}_quantity"] = str(qty)
            row[f"line_{slot}_unit_price"] = f"{unit_price:,}"
            row[f"line_{slot}_amount"] = f"{amount:,}"
            row[f"line_{slot}_due_date"] = TRD07_DELIVERY_TERMS[(index + slot) % len(TRD07_DELIVERY_TERMS)]
            row[f"line_{slot}_remark"] = TRD07_REMARKS[(index + slot) % len(TRD07_REMARKS)]
        row["supply_total_amount"] = f"{total:,}"
        profiles.append(row)
    return profiles


ADM04_CLIENT_COMPANIES = [
    "슬기계측기", "한빛테크", "대성정밀", "우진계전", "성우산전", "태광이엔지", "미래오토", "대한계측", "세진테크", "동원시스템",
    "신우전기", "영남산업", "코리아몰드", "진성하이텍", "부광정밀", "다온엔지니어링", "경남기전", "서진테크", "한솔기계", "대진산업",
]
ADM04_SUPPLIERS = [
    ("슬기계측기", "105-07-16785", "김남재", "서울 종로구 장사동 27번지 1층", "도소매/계측기,자동화부품", "02-2263-5826", "02-2272-5827", "www.sulgicom.co.kr", "knjds@naver.com"),
    ("한국계측교정", "214-12-45890", "박도현", "서울 구로구 디지털로 31길 20", "서비스/계측기 교정대행", "02-868-2451", "02-868-2452", "www.kmic.co.kr", "sales@kmic.co.kr"),
    ("정밀테크", "312-06-90731", "이민수", "경기 안산시 단원구 산단로 325", "제조/시험장비", "031-493-8801", "031-493-8802", "www.jmtech.kr", "quote@jmtech.kr"),
    ("한성계전", "128-81-34720", "최성훈", "경기 화성시 동탄산단6길 15", "도소매/전기제어부품", "031-377-4105", "031-377-4106", "www.hansunginst.co.kr", "order@hansunginst.co.kr"),
    ("동양측정기", "503-19-26844", "정우진", "대구 달서구 성서공단로 11", "도소매/측정공구", "053-583-2901", "053-583-2902", "www.dytool.co.kr", "dytool@naver.com"),
]
ADM04_EQUIPMENT_CATALOG = [
    ("전압계(V METER)-0.5급", "DW-6090", 450_000, 210_000),
    ("전류계(A METER)-0.5급", "DW-6090", 0, 0),
    ("전력계(W METER)-0.5급", "DW-6090", 0, 0),
    ("절연저항계", "500V 1000M", 70_000, 90_000),
    ("내전압시험기", "AC 5KV/HS", 290_000, 80_000),
    ("자동전압조정기", "AVR 3KVA", 340_000, 70_000),
    ("열전식온도계", "YF-160A", 78_000, 55_000),
    ("버어니어켈리퍼스", "150mm 0.05mm", 45_000, 30_000),
    ("마이크로메타 25mm", "0-25mm(0.01)", 45_000, 30_000),
    ("토크게이지(법정검사용)", "2800kg/cm", 620_000, 80_000),
    ("토크드라이버", "LTDK(일본)", 250_000, 47_000),
    ("테스트 핀/핑거", "SS-100", 160_000, 0),
    ("디지털 멀티미터", "DMM-6500", 280_000, 65_000),
    ("클램프메타", "CM-3289", 95_000, 45_000),
    ("접지저항계", "ER-4105", 180_000, 60_000),
    ("조도계", "LX-1108", 85_000, 35_000),
    ("소음계", "SL-4023", 190_000, 55_000),
    ("회전계", "DT-2234C", 75_000, 32_000),
    ("압력계", "PG-100", 120_000, 40_000),
    ("온습도계", "TH-200", 68_000, 30_000),
    ("누설전류계", "LCM-300", 210_000, 70_000),
    ("전원공급장치", "PS-305D", 160_000, 50_000),
    ("오실로스코프", "DS1054Z", 430_000, 120_000),
    ("함수발생기", "FG-100", 230_000, 80_000),
    ("LCR 미터", "LCR-620", 310_000, 90_000),
    ("절연내력시험기", "TOS-5101", 520_000, 110_000),
    ("디지털 온도계", "TK-100", 55_000, 25_000),
    ("표준저항기", "SR-10K", 140_000, 45_000),
    ("표준전압발생기", "SV-1000", 610_000, 150_000),
    ("데이터로거", "DL-2000", 260_000, 70_000),
    ("하이트게이지", "HG-300", 180_000, 55_000),
    ("두께측정기", "TG-25", 110_000, 38_000),
    ("푸시풀게이지", "PP-50", 240_000, 75_000),
    ("전자저울", "BAL-2200", 150_000, 45_000),
    ("표준분동", "F1-1kg", 90_000, 35_000),
    ("전력분석기", "PQA-310", 690_000, 160_000),
    ("전기안전시험기", "EST-300", 580_000, 130_000),
    ("온도기록계", "TR-72", 125_000, 40_000),
    ("캘리브레이터", "CAL-950", 740_000, 180_000),
    ("표면온도계", "IR-380", 80_000, 28_000),
    ("핀 게이지 세트", "PGS-100", 160_000, 0),
    ("링 게이지", "RG-25", 130_000, 0),
    ("플러그 게이지", "PG-20", 120_000, 0),
    ("다이얼게이지", "DG-2046", 95_000, 35_000),
    ("토크렌치", "TW-200", 210_000, 65_000),
    ("경도계", "HT-6510", 390_000, 95_000),
    ("진동계", "VM-6360", 230_000, 75_000),
    ("유량계", "FM-150", 270_000, 85_000),
    ("가스검지기", "GD-100", 190_000, 60_000),
    ("pH 미터", "PH-700", 85_000, 30_000),
    ("염도계", "SAL-200", 70_000, 25_000),
    ("스톱워치", "SW-100", 30_000, 18_000),
    ("분광조도계", "SP-500", 520_000, 130_000),
    ("열화상카메라", "IR-CAM", 880_000, 190_000),
    ("디지털 각도계", "AG-360", 75_000, 28_000),
    ("압축시험 지그", "CT-JIG", 210_000, 0),
    ("로드셀", "LC-500", 260_000, 70_000),
    ("인장시험 그립", "TG-GRIP", 310_000, 0),
    ("표준자", "SR-1000", 65_000, 25_000),
    ("전류프로브", "CP-100", 180_000, 55_000),
]
ADM04_PAYMENT_TERMS = ["현금결재", "계좌이체", "납품 후 현금", "검수 후 현금", "월말 현금", "선입금", "세금계산서 발행 후 입금"]
ADM04_VALIDITY_TERMS = ["견적일로부터 2주", "견적일로부터 15일", "견적일로부터 30일", "발행일로부터 14일", "발행일로부터 1개월"]
ADM04_DELIVERY_TERMS = ["발주 후 9일이내(검교정기간포함)", "발주 후 7일이내", "발주 후 10일이내", "발주일로부터 2주 이내", "협의 후 납품"]
ADM04_CALIBRATION_TERMS = ["발주일로부터 8일 이내", "발주일로부터 7일 이내", "검교정 접수 후 5일 이내", "검교정 접수 후 10일 이내", "협의"]


def _adm04_money(value: int) -> str:
    return f"W{value:,}"


def _adm04_korean_million(value: int) -> str:
    # 견적서 본문처럼 만원 단위 한글 금액을 간단히 표기한다.
    units = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
    tens = ["", "십", "이십", "삼십", "사십", "오십", "육십", "칠십", "팔십", "구십"]
    hundreds = ["", "일백", "이백", "삼백", "사백", "오백", "육백", "칠백", "팔백", "구백"]
    man = max(1, value // 10_000)
    h = man // 100
    t = (man % 100) // 10
    o = man % 10
    return f"{hundreds[h]}{tens[t]}{units[o]}만원".replace("일십", "십")


def adm04_estimate_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index in range(60):
        supplier_name, biz_no, rep, address, biz_type_item, tel, fax, website, email = ADM04_SUPPLIERS[index % len(ADM04_SUPPLIERS)]
        client = ADM04_CLIENT_COMPANIES[index % len(ADM04_CLIENT_COMPANIES)]
        contact = FIN01_REPRESENTATIVES[index % len(FIN01_REPRESENTATIVES)]
        phone = f"010-{3000 + (index * 71) % 7000:04d}-{1000 + (index * 97) % 9000:04d}"
        estimate_date = date(2024 + index % 3, 1 + (index * 2) % 12, 1 + (index * 5) % 27)
        row: dict[str, str] = {
            "top_contact_line": f"{client} 법정장비 담당자:{contact} 팀장({phone})",
            "supplier_company_stamp_name": supplier_name,
            "recipient_title": "법정장비 담당자 님",
            "supplier_business_registration_number": biz_no,
            "estimate_date_text": f"{estimate_date.year}년 {estimate_date.month}월 {estimate_date.day}일",
            "supplier_company_name": supplier_name,
            "payment_terms": ADM04_PAYMENT_TERMS[index % len(ADM04_PAYMENT_TERMS)],
            "supplier_representative_name": rep,
            "delivery_period": ADM04_DELIVERY_TERMS[index % len(ADM04_DELIVERY_TERMS)],
            "supplier_address": address,
            "supplier_business_type_item": biz_type_item,
            "supplier_tel": tel,
            "supplier_fax": fax,
            "estimate_subject": "전기제조 형식승인 법정장비 보유품목",
            "bank_account_kb": f"국민:{408801 + index:06d}-01-{167169 + index * 17:06d}",
            "bank_account_holder": f"예금주:{rep}({supplier_name})",
            "bank_account_shinhan": f"신한:110-{219 + index % 700:03d}-{132688 + index * 23:06d}",
            "bank_account_woori": f"우리:077-{290768 + index * 19:06d}-13-{101 + index % 800:03d}",
            "bank_account_enterprise_nonghyup": f"기업:023-{81255 + index * 29:06d}-04-{17 + index % 900:03d} 농협:1271-01-{873 + index * 31:06d}",
            "company_description": f"저희 {supplier_name} 회사는 각종 검교정 대행 및 법정장비(시험장비) 등록 업체입니다.",
            "homepage_url": website,
            "email_address": email,
            "quote_validity_period": ADM04_VALIDITY_TERMS[index % len(ADM04_VALIDITY_TERMS)],
            "calibration_period": ADM04_CALIBRATION_TERMS[index % len(ADM04_CALIBRATION_TERMS)],
        }
        subtotal = 0
        for slot in range(1, 13):
            item_name, model, supply_price, calibration_fee = ADM04_EQUIPMENT_CATALOG[(index + slot - 1) % len(ADM04_EQUIPMENT_CATALOG)]
            quantity = 1
            amount = quantity * (supply_price + calibration_fee)
            if slot in {2, 3} and index % 3 == 0:
                supply_price = 0
                calibration_fee = 0
                amount = 0
            subtotal += amount
            row[f"line_{slot}_number"] = str(slot)
            row[f"line_{slot}_item_name"] = item_name
            row[f"line_{slot}_model"] = model
            row[f"line_{slot}_unit"] = "SET"
            row[f"line_{slot}_quantity"] = str(quantity)
            row[f"line_{slot}_unit_price"] = _adm04_money(supply_price) if supply_price else ""
            row[f"line_{slot}_calibration_fee"] = _adm04_money(calibration_fee) if calibration_fee else ""
            row[f"line_{slot}_amount"] = _adm04_money(amount) if amount else ""
            row[f"line_{slot}_note"] = "*한장비로 전압,전류,전력 공통사용" if slot == 2 else ("*검교정 전압,전류,전력 3개 모두" if slot == 3 else "")
        vat = int(round(subtotal * 0.1))
        grand_total = subtotal + vat
        row["subtotal_amount"] = _adm04_money(subtotal)
        row["vat_amount"] = _adm04_money(vat)
        row["grand_total_amount"] = _adm04_money(grand_total)
        row["estimate_total_text"] = f"{_adm04_korean_million(subtotal)}({_adm04_money(subtotal)}--)부가세별도"
        profiles.append(row)
    return profiles


QC02_SUPPLIERS = ["한빛테크", "대성정밀", "우진하이텍", "성우산전", "태광이엔지", "미래오토", "대한계측", "세진테크", "동원시스템", "신우전기", "영남산업", "코리아몰드", "진성하이텍", "부광정밀", "다온엔지니어링", "경남기전", "서진테크", "한솔기계", "대진산업", "우림엔지니어링"]
QC02_RECEIVING_LOCATIONS = ["창원 1공장 입고장", "진북공장 자재창고", "본사 품질검사실", "A동 수입검사실", "B동 자재창고", "외주품 검수장", "생산기술팀 검사구역", "물류센터 2층 검수장", "성산공장 입고대기장", "마산공장 품질보증실"]
QC02_INSPECTION_METHODS = ["육안검사 및 수량대조", "샘플링 치수검사", "전수 수량검사 및 외관검사", "검사성적서 대조 및 외관 확인", "AQL 샘플링 검사", "입고명세서와 실물 대조", "포장상태 확인 및 수량검수", "도면 기준 치수검사"]
QC02_INSPECTOR_OPINIONS = [
    "입고 수량 및 외관 상태 양호하여 입고 승인함.",
    "일부 경미한 포장 손상이 있으나 품질 이상 없어 입고 처리함.",
    "불량 수량은 격리 후 교환 요청하고 잔여 수량은 입고 승인함.",
    "검사성적서와 실물 수량이 일치하며 품질 기준을 충족함.",
    "규격 확인 결과 사용 가능하므로 창고 입고 처리함.",
]
QC02_PRODUCT_CATALOG = [
    ("Side Retainer Core", "폭 76.3mm*길이100mm"), ("Side Retainer Core", "폭 77.7mm*길이100mm"),
    ("Guide Pin", "SKD11 Ø10*L80"), ("Bracket LH", "SPCC 2.0T"), ("Bracket RH", "SPCC 2.0T"),
    ("Al Plate", "120*80*15T"), ("Spacer Ring", "SUS304 Ø45"), ("Bearing Housing", "AL6061"),
    ("Motor Shaft", "SCM440 Ø18"), ("Die Insert Block", "SKD61 A형"), ("Sensor Bracket", "SUS304"),
    ("Cooling Plate", "AL6061"), ("Cylinder Mount Block", "S45C"), ("Robot Gripper Finger", "L형"),
    ("Robot Gripper Finger", "R형"), ("Vacuum Pad Holder", "Ø30"), ("Pallet Stopper Block", "S45C"),
    ("Positioning Pin", "Ø10 h7"), ("Locating Bush", "SCM440"), ("Inspection Master Block", "STD-01"),
    ("Welding Jig Clamp", "SET"), ("Base Plate", "250*180"), ("Transfer Rail Support", "M8 TAP"),
    ("Cam Slide Wear Plate", "SKD11"), ("Mold Core Pin", "Ø6*L55"), ("Mold Ejector Plate", "가공품"),
    ("Die Cushion Spacer", "t12"), ("Heat Sink Bracket", "AL5052"), ("Sensor Bracket", "자동화라인용"),
    ("Conveyor Stopper", "Assy"), ("Knife Holder", "포장기용"), ("Guide Block", "압입 Jig"),
    ("Master Gauge", "치수검사용"), ("Air Cylinder Bracket", "ACB-20"), ("LM Guide Rail Support", "L=300"),
    ("Gear Housing", "소형"), ("Shaft Collar", "Ø25"), ("Cell Tray Guide", "배터리용"),
    ("PCB 검사 Jig Plate", "FR-4"), ("Frame Angle Bracket", "AL"), ("Laser Marking Fixture", "LMF-02"),
    ("Vision Camera Mount", "VCM-01"), ("Servo Motor Adapter", "Plate"), ("Turn Table Locator", "TTL-100"),
    ("Hinge Bracket", "가공품"), ("Cooling Manifold", "금형용"), ("Loader Arm Bush", "LAB-20"),
    ("Pin Press Fixture", "PPF-01"), ("Assembly Master Jig", "AMJ-03"), ("Hanger Hook", "도장라인"),
    ("Clamp Block", "SCM440"), ("Shaft Holder", "Ø25"), ("Tube Cutting Guide", "TCG-01"),
    ("Casting Gauge", "CG-08"), ("Cover Plate", "AL6061"), ("Spacer Set", "정밀"),
    ("Index Plate", "IP-12"), ("Control Box Bracket", "CB-02"), ("Packing Guide", "PG-15"),
]


TRD01_SELLERS = [
    ("MK GLOBAL CO., LTD.", "HWASEONG-SI, GYEONGGI-DO,", "REPUBLIC OF KOREA", "MK"),
    ("HANBIT PRECISION CO., LTD.", "ANSAN-SI, GYEONGGI-DO,", "REPUBLIC OF KOREA", "HB"),
    ("MIRAE MOBILITY CO., LTD.", "DONGTAN-SANDAN, HWASEONG-SI,", "REPUBLIC OF KOREA", "MM"),
    ("DAEHAN MATERIALS INC.", "NAM-GU, ULSAN,", "REPUBLIC OF KOREA", "DM"),
    ("TAESUNG MACHINERY CO., LTD.", "CHANGWON-SI, GYEONGSANGNAM-DO,", "REPUBLIC OF KOREA", "TS"),
    ("SEORIN CHEMICAL CO., LTD.", "DAEDEOK-GU, DAEJEON,", "REPUBLIC OF KOREA", "SC"),
    ("KOREA COMPONENTS CO., LTD.", "YEONGDEUNGPO-GU, SEOUL,", "REPUBLIC OF KOREA", "KC"),
    ("ORUM MANUFACTURING CO., LTD.", "BUK-GU, DAEGU,", "REPUBLIC OF KOREA", "OM"),
]
TRD01_BUYERS = [
    ("GOSINARA CO., LTD.", "14524 YUAN LAOSHAN QU,", "QINGDAO SHI, SHANDONG SHENG,", "CHINA", "QINGDAO, CHINA", "QINGDAO"),
    ("NIPPON PRECISION CO., LTD.", "2-11-5 NIHONBASHI, CHUO-KU,", "TOKYO,", "JAPAN", "TOKYO, JAPAN", "TOKYO"),
    ("ACME AEROSPACE INC.", "1280 WILSHIRE BLVD,", "LOS ANGELES, CA,", "U.S.A", "LOS ANGELES, U.S.A", "LOS ANGELES"),
    ("SINGAPORE ROBOTICS PTE LTD", "18 TAMPINES INDUSTRIAL CRESCENT,", "SINGAPORE,", "SINGAPORE", "SINGAPORE", "SINGAPORE"),
    ("BERLIN OPTICS GMBH", "KURFUERSTENDAMM 21,", "BERLIN,", "GERMANY", "HAMBURG, GERMANY", "HAMBURG"),
    ("DUBAI SYSTEMS FZE", "JEBEL ALI FREE ZONE,", "DUBAI,", "U.A.E", "JEBEL ALI, U.A.E", "JEBEL ALI"),
    ("TAIPEI SEMICONDUCTOR LTD", "NO. 88, MINSHENG E. RD.,", "TAIPEI,", "TAIWAN", "TAIPEI, TAIWAN", "TAIPEI"),
    ("SYDNEY MEDTECH PTY LTD", "25 GEORGE STREET,", "SYDNEY NSW,", "AUSTRALIA", "SYDNEY, AUSTRALIA", "SYDNEY"),
]
TRD01_COMMODITIES = [
    ("GIRL'S SHIRTS", "(Cotton 40%, Nylon 30%, Rayon 30%)", "PC", 1.00, 10000),
    ("INDUSTRIAL SENSOR", "(Stainless Steel 60%, PCB 40%)", "EA", 18.50, 480),
    ("PRECISION BRACKET", "(Aluminum 70%, Steel 30%)", "EA", 7.25, 1200),
    ("BATTERY MODULE", "(Lithium cell 80%, Case 20%)", "SET", 245.00, 60),
    ("OPTICAL LENS ASSY", "(Glass 65%, Aluminum 35%)", "EA", 32.40, 350),
    ("CNC SPINDLE UNIT", "(SCM440 Steel Assembly)", "SET", 510.00, 24),
    ("PACKAGING FILM", "(PET 90%, Adhesive 10%)", "ROLL", 42.00, 300),
    ("WIRING HARNESS", "(Copper 55%, PVC 45%)", "PC", 3.80, 2500),
]
TRD01_INCOTERMS = ["F.O.B INCHEON", "F.O.B BUSAN", "C.I.F SHANGHAI", "C.F.R HAMBURG", "F.C.A INCHEON", "D.A.P SINGAPORE"]
TRD01_PAYMENT_TERMS = ["L/C AT SIGHT", "T/T IN ADVANCE", "T/T 30 DAYS", "D/P AT SIGHT", "T/T 50% ADVANCE", "O/A 60 DAYS"]
TRD01_VESSELS = ["QCY123", "HMM SEOUL", "KAL908", "EVER AIM", "ONE TRITON", "MAERSK HANOI", "KE271", "SITC BUSAN"]
TRD01_SIGNERS = ["S. D. PARK", "M. J. KIM", "J. W. LEE", "H. S. CHOI", "D. Y. PARK", "S. Y. HAN", "J. H. YOON", "T. M. JUNG"]


def _trd01_date_text(value: date) -> str:
    return value.strftime("%b %d. %Y").upper()


def _trd01_money(value: float) -> str:
    if abs(value - round(value)) < 0.005:
        return f"US${int(round(value)):,}"
    return f"US${value:,.2f}"


def trd01_commercial_invoice_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index in range(60):
        invoice_date = date(2023 + index % 4, 1 + (index * 5) % 12, 1 + (index * 7) % 27)
        lc_date = invoice_date + timedelta(days=1 + (index % 3))
        departure_date = lc_date + timedelta(days=1 + (index % 5))
        seller_name, seller_addr, seller_country, seller_code = TRD01_SELLERS[index % len(TRD01_SELLERS)]
        buyer_name, buyer_addr1, buyer_addr2, buyer_country, destination_port, shipping_dest = TRD01_BUYERS[index % len(TRD01_BUYERS)]
        goods, material, unit, unit_price, base_qty = TRD01_COMMODITIES[index % len(TRD01_COMMODITIES)]
        quantity = base_qty + (index % 7) * max(1, base_qty // 20)
        amount = quantity * unit_price
        invoice_no = f"{seller_code}{invoice_date:%Y%m%d}"
        lc_no = f"{seller_code}{invoice_date:%y}{100000 + index * 137:06d}"
        carton_count = max(1, min(999, int(quantity / 400) + 1))
        lot_no = f"LOT {invoice_date:%y%m}{index % 9 + 1:02d}"
        profiles.append(
            {
                "invoice_number_date": f"{invoice_no}, {_trd01_date_text(invoice_date)}",
                "shipper_name": seller_name,
                "shipper_address": seller_addr,
                "shipper_country": seller_country,
                "lc_number_date": f"{lc_no}, {_trd01_date_text(lc_date)}",
                "buyer_reference": "SAME AS CONSIGNEE" if index % 4 else buyer_name,
                "consignee_name": buyer_name,
                "consignee_address_line1": buyer_addr1,
                "consignee_address_line2": buyer_addr2,
                "consignee_country": buyer_country,
                "country_of_origin": "REPUBLIC OF KOREA",
                "departure_date": _trd01_date_text(departure_date),
                "vessel_flight": TRD01_VESSELS[index % len(TRD01_VESSELS)],
                "loading_port": "INCHEON, KOREA" if index % 3 else "BUSAN, KOREA",
                "terms_of_delivery": TRD01_INCOTERMS[index % len(TRD01_INCOTERMS)],
                "payment_terms": TRD01_PAYMENT_TERMS[index % len(TRD01_PAYMENT_TERMS)],
                "destination_port": destination_port,
                "goods_description": goods,
                "quantity": f"{quantity:,} {unit}",
                "unit_price": f"US${unit_price:,.2f}/{unit}",
                "amount": _trd01_money(amount),
                "shipping_mark_code": f"{seller_code}-{200 + index}",
                "material_composition": material,
                "shipping_mark_destination": shipping_dest,
                "lot_number": lot_no,
                "carton_range": f"C/NO.1-{carton_count}",
                "origin_mark": "MADE IN KOREA",
                "signed_by": TRD01_SIGNERS[index % len(TRD01_SIGNERS)],
            }
        )
    return profiles


TRD02_PORT_ROUTES = [
    ("BUSAN,", "SOUTH KOREA", "NEW YORK,", "U.S.A", "HMM SEOUL V.120E"),
    ("INCHEON,", "SOUTH KOREA", "LOS ANGELES,", "U.S.A", "HYUNDAI VOYAGER V.77W"),
    ("BUSAN,", "SOUTH KOREA", "TOKYO,", "JAPAN", "SITC BUSAN V.44N"),
    ("INCHEON,", "SOUTH KOREA", "SINGAPORE,", "SINGAPORE", "ONE TRITON V.31S"),
    ("BUSAN,", "SOUTH KOREA", "HAMBURG,", "GERMANY", "MAERSK HANOI V.18W"),
    ("INCHEON,", "SOUTH KOREA", "JEBEL ALI,", "U.A.E", "EVER AIM V.52E"),
    ("BUSAN,", "SOUTH KOREA", "TAIPEI,", "TAIWAN", "WAN HAI 327 V.09N"),
    ("INCHEON,", "SOUTH KOREA", "SYDNEY,", "AUSTRALIA", "COSCO KOREA V.63S"),
]
TRD02_GOODS = [
    ("MOTORCYCLE GLOVES", "MG", "PRS", 0.42, 0.50, 0.212, "1,200 X 420 X 420 MM", 200),
    ("PLASTIC OFFICE SUPPLIES", "POS", "PCS", 0.18, 0.23, 0.096, "600 X 400 X 400 MM", 500),
    ("POWER TRANSFORMERS", "PT", "UNITS", 12.50, 14.00, 0.850, "1,000 X 800 X 1,060 MM", 10),
    ("INDUSTRIAL SENSORS", "IS", "PCS", 0.08, 0.10, 0.045, "450 X 300 X 330 MM", 100),
    ("PRECISION BRACKETS", "PB", "PCS", 0.32, 0.38, 0.075, "500 X 360 X 420 MM", 80),
    ("BATTERY MODULES", "BM", "SETS", 9.50, 10.80, 0.520, "900 X 600 X 960 MM", 8),
    ("OPTICAL LENS ASSEMBLIES", "OLA", "PCS", 0.14, 0.18, 0.062, "520 X 360 X 330 MM", 120),
    ("CNC SPINDLE UNITS", "CSU", "SETS", 18.00, 20.50, 0.770, "1,050 X 820 X 900 MM", 6),
    ("PACKAGING FILM ROLLS", "PFR", "ROLLS", 6.20, 7.40, 0.380, "850 X 620 X 720 MM", 12),
    ("WIRING HARNESSES", "WH", "PCS", 0.22, 0.27, 0.110, "650 X 450 X 380 MM", 160),
    ("ALUMINUM HEAT SINKS", "AHS", "PCS", 0.75, 0.86, 0.140, "700 X 480 X 420 MM", 60),
    ("CONTROL BOX PANELS", "CBP", "PCS", 2.40, 2.80, 0.260, "780 X 560 X 600 MM", 25),
    ("GUIDE PINS", "GP", "PCS", 0.10, 0.13, 0.038, "400 X 300 X 320 MM", 200),
    ("ROBOT GRIPPER FINGERS", "RGF", "PCS", 0.48, 0.56, 0.092, "550 X 380 X 440 MM", 70),
    ("BEARING HOUSINGS", "BH", "PCS", 1.80, 2.10, 0.180, "650 X 500 X 550 MM", 35),
    ("MOTOR SHAFTS", "MS", "PCS", 1.25, 1.45, 0.125, "750 X 360 X 460 MM", 40),
    ("COOLING PLATES", "CP", "PCS", 2.05, 2.35, 0.210, "700 X 520 X 580 MM", 30),
    ("SENSOR BRACKETS", "SB", "PCS", 0.28, 0.34, 0.064, "480 X 340 X 390 MM", 110),
    ("PCB INSPECTION JIGS", "PIJ", "SETS", 4.20, 4.80, 0.330, "820 X 620 X 650 MM", 15),
    ("LASER MARKING FIXTURES", "LMF", "SETS", 5.50, 6.30, 0.410, "900 X 650 X 700 MM", 10),
    ("SERVO MOTOR ADAPTERS", "SMA", "PCS", 0.95, 1.12, 0.100, "560 X 420 X 420 MM", 55),
    ("CELL TRAY GUIDES", "CTG", "PCS", 0.38, 0.45, 0.082, "540 X 390 X 390 MM", 90),
    ("MEDICAL SENSOR MODULES", "MSM", "PCS", 0.16, 0.20, 0.052, "460 X 330 X 340 MM", 130),
    ("OLED DISPLAY MODULES", "ODM", "PCS", 0.18, 0.22, 0.058, "500 X 360 X 320 MM", 120),
    ("VACUUM PAD HOLDERS", "VPH", "PCS", 0.25, 0.31, 0.070, "500 X 360 X 390 MM", 100),
    ("TRANSFER RAIL SUPPORTS", "TRS", "PCS", 1.70, 1.95, 0.160, "720 X 480 X 470 MM", 45),
    ("DIE INSERT BLOCKS", "DIB", "PCS", 3.80, 4.35, 0.290, "800 X 600 X 600 MM", 20),
    ("ASSEMBLY MASTER JIGS", "AMJ", "SETS", 8.00, 9.20, 0.600, "980 X 760 X 800 MM", 8),
    ("CONVEYOR STOPPERS", "CST", "PCS", 1.10, 1.32, 0.120, "600 X 420 X 480 MM", 50),
    ("GEAR HOUSINGS", "GH", "PCS", 2.85, 3.25, 0.240, "760 X 540 X 580 MM", 24),
    ("HINGE BRACKETS", "HB", "PCS", 0.42, 0.49, 0.080, "520 X 360 X 420 MM", 90),
    ("COOLING MANIFOLDS", "CM", "SETS", 4.60, 5.20, 0.360, "820 X 620 X 700 MM", 12),
    ("CLAMP BLOCKS", "CB", "PCS", 1.55, 1.78, 0.150, "650 X 450 X 520 MM", 50),
    ("SHAFT HOLDERS", "SH", "PCS", 0.90, 1.05, 0.105, "580 X 420 X 420 MM", 65),
    ("TUBE CUTTING GUIDES", "TCG", "SETS", 2.70, 3.10, 0.225, "750 X 540 X 560 MM", 22),
    ("CASTING GAUGES", "CG", "SETS", 3.20, 3.75, 0.270, "800 X 560 X 600 MM", 18),
    ("COVER PLATES", "CVP", "PCS", 0.82, 0.94, 0.112, "620 X 420 X 430 MM", 80),
    ("SPACER SETS", "SPS", "SETS", 0.36, 0.42, 0.078, "500 X 350 X 400 MM", 100),
    ("INDEX PLATES", "IP", "PCS", 1.95, 2.25, 0.190, "700 X 500 X 540 MM", 35),
    ("PACKING GUIDES", "PG", "PCS", 0.44, 0.52, 0.086, "540 X 380 X 420 MM", 85),
    ("ELECTRONIC RELAYS", "ER", "PCS", 0.06, 0.08, 0.032, "380 X 280 X 300 MM", 250),
    ("TERMINAL BLOCKS", "TB", "PCS", 0.05, 0.07, 0.030, "360 X 260 X 300 MM", 300),
    ("HYDRAULIC FITTINGS", "HF", "PCS", 0.30, 0.37, 0.072, "500 X 360 X 400 MM", 120),
    ("AIR CYLINDER BRACKETS", "ACB", "PCS", 0.62, 0.72, 0.098, "560 X 400 X 440 MM", 80),
    ("VISION CAMERA MOUNTS", "VCM", "PCS", 0.40, 0.48, 0.086, "540 X 380 X 420 MM", 90),
    ("MACHINE SAFETY COVERS", "MSC", "PCS", 1.30, 1.55, 0.180, "720 X 500 X 500 MM", 40),
    ("STAINLESS SPACERS", "SSP", "PCS", 0.18, 0.23, 0.050, "450 X 320 X 350 MM", 150),
    ("FACTORY CABLE TRAYS", "FCT", "PCS", 2.10, 2.45, 0.220, "800 X 540 X 520 MM", 28),
    ("AUTOMOTIVE SWITCH HOUSINGS", "ASH", "PCS", 0.20, 0.25, 0.060, "480 X 340 X 360 MM", 140),
    ("RUBBER SEALING GASKETS", "RSG", "PCS", 0.04, 0.06, 0.028, "340 X 260 X 280 MM", 400),
    ("SMART METER CASES", "SMC", "PCS", 0.26, 0.32, 0.068, "500 X 360 X 380 MM", 110),
    ("THERMAL PRINTER PARTS", "TPP", "PCS", 0.12, 0.15, 0.044, "420 X 300 X 330 MM", 180),
    ("PRECISION SPRINGS", "PS", "PCS", 0.03, 0.05, 0.025, "320 X 240 X 260 MM", 500),
    ("FOOD PACKAGING TRAYS", "FPT", "PCS", 0.08, 0.11, 0.040, "460 X 340 X 300 MM", 300),
    ("LABORATORY SAMPLE HOLDERS", "LSH", "PCS", 0.22, 0.28, 0.066, "500 X 360 X 370 MM", 130),
    ("INDUSTRIAL LED MODULES", "ILM", "PCS", 0.16, 0.20, 0.052, "440 X 320 X 340 MM", 160),
    ("MACHINE TOOL COVERS", "MTC", "PCS", 1.60, 1.88, 0.170, "720 X 500 X 480 MM", 38),
    ("AUTOMATED FEEDER BOWLS", "AFB", "SETS", 7.50, 8.60, 0.540, "950 X 720 X 780 MM", 8),
    ("MOLD EJECTOR PLATES", "MEP", "PCS", 2.70, 3.15, 0.245, "760 X 560 X 560 MM", 22),
    ("INSPECTION MASTER BLOCKS", "IMB", "SETS", 3.40, 3.95, 0.280, "800 X 580 X 600 MM", 18),
]
TRD02_PAYMENT_TERMS = ["FREIGHT COLLECT BY OCEAN", "FREIGHT PREPAID BY OCEAN", "FREIGHT COLLECT BY AIR", "FOB BUSAN, SOUTH KOREA", "CIF NEW YORK, U.S.A", "CFR HAMBURG, GERMANY"]
TRD02_SIGNERS = [("K. D. HONG", "MANAGING DIRECTOR"), ("M. J. KIM", "EXPORT MANAGER"), ("S. D. PARK", "SALES DIRECTOR"), ("J. W. LEE", "LOGISTICS MANAGER"), ("H. S. CHOI", "GENERAL MANAGER"), ("D. Y. PARK", "TRADE MANAGER")]


def _trd02_moneyless_date(value: date) -> str:
    return value.strftime("%b %d, %Y").upper()


def _trd02_weight(value: float) -> str:
    return f"{value:,.3f}"


def trd02_packing_list_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index in range(60):
        exporter = TRD06_EXPORTERS[index % len(TRD06_EXPORTERS)]
        buyer = TRD06_IMPORTERS[index % len(TRD06_IMPORTERS)]
        route = TRD02_PORT_ROUTES[index % len(TRD02_PORT_ROUTES)]
        goods1 = TRD02_GOODS[index % len(TRD02_GOODS)]
        goods2 = TRD02_GOODS[(index + 1) % len(TRD02_GOODS)]
        invoice_date = date(2023 + index % 4, 1 + (index * 5) % 12, 1 + (index * 7) % 27)
        sail_date = invoice_date + timedelta(days=5 + index % 9)
        exporter_code = ''.join(part[0] for part in exporter[0].replace(',', '').split()[:2])[:3].upper()
        packing_no = f"{exporter_code}PL {invoice_date:%Y}-{index + 1:03d}"
        bl_no = f"{exporter_code}{sail_date:%m%d}{10000 + index * 137}"
        container = f"{exporter_code}P{1000000 + index * 791:07d}"
        seal = f"EFB{200000 + index * 313:06d}"
        carton1 = 1 + (index % 4)
        carton2 = carton1 + 1 + (index % 3)
        def item_values(goods, slot, cartons):
            desc, code, unit, net_each, gross_each, vol_each, dims, per_carton = goods
            qty = per_carton * cartons
            net = net_each * qty
            gross = gross_each * qty
            volume = vol_each * cartons
            return desc, code, unit, qty, net, gross, volume, dims, per_carton
        i1 = item_values(goods1, 1, carton1)
        i2 = item_values(goods2, 2, carton2)
        total_cartons = carton1 + carton2
        total_net = i1[4] + i2[4]
        total_gross = i1[5] + i2[5]
        total_volume = i1[6] + i2[6]
        term = TRD02_PAYMENT_TERMS[index % len(TRD02_PAYMENT_TERMS)]
        signer, position = TRD02_SIGNERS[index % len(TRD02_SIGNERS)]
        row = {
            "shipper_exporter_name": exporter[0],
            "packing_list_number_date": f"{packing_no}  {_trd02_moneyless_date(invoice_date)}",
            "shipper_address_line1": exporter[4].split(', REPUBLIC')[0][:34] + ",",
            "shipper_address_line2": "SEOUL, SOUTH KOREA" if "SEOUL" in exporter[4] else "SOUTH KOREA",
            "shipper_tel": exporter[2],
            "shipper_fax": exporter[3],
            "buyer_importer_name": buyer[0],
            "buyer_address_line1": buyer[4].split(',')[0] + ",",
            "notify_party": "SAME AS CONSIGNEE",
            "buyer_address_line2": ','.join(buyer[4].split(',')[1:3]).strip() or buyer[4],
            "buyer_tel": buyer[2],
            "consignee_name": "SAME AS ABOVE",
            "payment_delivery_1": f"1) {term}",
            "payment_delivery_2": f"2) H.S. CODE NO. : {goods1[1][:4]}-{goods1[1][-2:]}-0000",
            "payment_delivery_3": f"3) NO. OF BILL OF LADING : {bl_no}",
            "port_loading_city": route[0],
            "port_loading_country": route[1],
            "final_destination_city": route[2],
            "final_destination_country": route[3],
            "carrier_vessel": route[4],
            "sailing_date": _trd02_moneyless_date(sail_date),
            "shipping_mark_buyer": buyer[0].replace(" CORPORATION", " CORP.").replace(" INC.", " INC.")[:18],
            "shipping_mark_destination": route[2].replace(',', ''),
            "shipping_mark_carton_range": f"C/NO.1~{total_cartons}",
            "shipping_mark_item_no": "ITEM NO.",
            "description_goods_header": goods1[0],
            "box_1_title": f"BOX NO. 1 - {goods1[0]}",
            "box_1_net_weight": _trd02_weight(i1[4]),
            "box_1_gross_weight": _trd02_weight(i1[5]),
            "box_1_volume": f"{i1[6]:.3f}",
            "box_1_dimensions": f"( {i1[7]} )",
            "box_1_item_code": f"(1) {i1[1]}-{index % 900 + 1:03d}",
            "box_1_quantity": f"X {i1[3]:,} {i1[2]}",
            "box_1_carton_breakdown": f"({i1[8]:,} {i1[2]} X {carton1} CARTONS)",
            "box_2_title": f"BOX NO. 2 - {goods2[0]}",
            "box_2_net_weight": _trd02_weight(i2[4]),
            "box_2_gross_weight": _trd02_weight(i2[5]),
            "box_2_volume": f"{i2[6]:.3f}",
            "box_2_dimensions": f"( {i2[7]} )",
            "box_2_item_code": f"(1) {i2[1]}-{index % 900 + 2:03d}",
            "box_2_quantity": f"X {i2[3]:,} {i2[2]}",
            "box_2_carton_breakdown": f"({i2[8]:,} {i2[2]} X {carton2} CARTONS)",
            "total_trade_terms": f"TOTAL : {term.split(' BY ')[0] if ' BY ' in term else term}",
            "total_net_weight": _trd02_weight(total_net),
            "total_gross_weight": _trd02_weight(total_gross),
            "total_volume": f"{total_volume:.3f}",
            "net_weight_unit": "KGS",
            "gross_weight_unit": "KGS",
            "volume_unit": "CBM",
            "package_summary": f"{total_cartons} ({total_cartons}) BOXES OF {goods1[0]}",
            "say_package_only": f"*SAY: {total_cartons} ({total_cartons}) BOXES ONLY.",
            "container_seal_no": f"* CONTAINER & SEAL NO. : {container}/{seal}",
            "origin_country_statement": "* ORIGIN OF COUNTRY : REPUBLIC OF KOREA (R.O.K)",
            "footer_company_name": exporter[0],
            "footer_tel": exporter[2],
            "footer_fax": exporter[3],
            "signed_by_name": f"{signer} / {position}",
        }
        profiles.append(row)
    return profiles


TRD06_EXPORTERS = [
    ("HANBIT PRECISION CO., LTD.", "export@hanbitprecision.co.kr", "+82-31-410-2100", "+82-31-410-2101", "128 SANDAN-RO, ANSAN-SI, GYEONGGI-DO, REPUBLIC OF KOREA"),
    ("MIRAE MOBILITY CO., LTD.", "trade@miraemobility.co.kr", "+82-31-8003-1120", "+82-31-8003-1121", "45 DONGTAN-SANDAN 6-GIL, HWASEONG-SI, REPUBLIC OF KOREA"),
    ("DAEHAN MATERIALS INC.", "sales@daehanmaterials.co.kr", "+82-52-275-7300", "+82-52-275-7301", "102 INDUSTRIAL-RO, NAM-GU, ULSAN, REPUBLIC OF KOREA"),
    ("TAESUNG MACHINERY CO., LTD.", "export@tsmachinery.co.kr", "+82-55-260-4400", "+82-55-260-4401", "77 WANAM-RO, CHANGWON-SI, REPUBLIC OF KOREA"),
    ("SEORIN CHEMICAL CO., LTD.", "overseas@seorinchem.co.kr", "+82-42-935-8800", "+82-42-935-8801", "33 TECHNO 2-RO, YUSEONG-GU, DAEJEON, REPUBLIC OF KOREA"),
    ("KOREA COMPONENTS CO., LTD.", "global@kcomponents.co.kr", "+82-2-6670-3300", "+82-2-6670-3301", "19 DIGITAL-RO, GURO-GU, SEOUL, REPUBLIC OF KOREA"),
    ("ORUM MANUFACTURING CO., LTD.", "export@orumfg.co.kr", "+82-53-580-9100", "+82-53-580-9101", "88 SEONGSEO-GONGDAN-RO, DAEGU, REPUBLIC OF KOREA"),
    ("SMART FACTORY SOLUTIONS INC.", "sales@sfs-korea.co.kr", "+82-70-4210-6300", "+82-70-4210-6301", "235 PANGYO-RO, SEONGNAM-SI, REPUBLIC OF KOREA"),
    ("BLUEWAVE ELECTRONICS CO., LTD.", "export@bluewave-elec.co.kr", "+82-32-850-7100", "+82-32-850-7101", "32 SONGDOGWAHAK-RO, INCHEON, REPUBLIC OF KOREA"),
    ("NURI PACKAGING CO., LTD.", "trade@nuripack.co.kr", "+82-41-560-2200", "+82-41-560-2201", "64 JIKSAN-RO, CHEONAN-SI, REPUBLIC OF KOREA"),
    ("A-ONE MOLDING CO., LTD.", "coo@aonemold.co.kr", "+82-31-493-4200", "+82-31-493-4201", "325 SANDAN-RO, DANWON-GU, ANSAN-SI, REPUBLIC OF KOREA"),
    ("PRIME DISPLAY CO., LTD.", "export@primedisplay.co.kr", "+82-43-240-7700", "+82-43-240-7701", "50 OSAN-GIL, CHEONGJU-SI, REPUBLIC OF KOREA"),
]
TRD06_IMPORTERS = [
    ("NIPPON PRECISION CO., LTD.", "imports@nipponprecision.co.jp", "+81-3-6200-1100", "+81-3-6200-1101", "2-11-5 NIHONBASHI, CHUO-KU, TOKYO, JAPAN"),
    ("ACME AEROSPACE INC.", "customs@acmeaero.com", "+1-213-987-6543", "+1-213-987-6544", "1280 WILSHIRE BLVD, LOS ANGELES, CA, U.S.A"),
    ("SINGAPORE ROBOTICS PTE LTD", "imports@sgrobotics.com", "+65-6777-2100", "+65-6777-2101", "18 TAMPINES INDUSTRIAL CRESCENT, SINGAPORE"),
    ("BERLIN OPTICS GMBH", "import@berlinoptics.de", "+49-30-2201-5600", "+49-30-2201-5601", "KURFUERSTENDAMM 21, BERLIN, GERMANY"),
    ("DUBAI SYSTEMS FZE", "trade@dubaisystems.ae", "+971-4-884-3200", "+971-4-884-3201", "JEBEL ALI FREE ZONE, DUBAI, U.A.E"),
    ("TAIPEI SEMICONDUCTOR LTD", "customs@tpsc.com.tw", "+886-2-2711-3000", "+886-2-2711-3001", "NO. 88, MINSHENG E. RD., TAIPEI, TAIWAN"),
    ("SYDNEY MEDTECH PTY LTD", "imports@sydmedtech.com.au", "+61-2-9011-4500", "+61-2-9011-4501", "25 GEORGE STREET, SYDNEY NSW, AUSTRALIA"),
    ("GREAT LAKES DISTRIBUTION LLC", "entry@gldist.com", "+1-312-555-2800", "+1-312-555-2801", "200 W MADISON ST, CHICAGO, IL, U.S.A"),
    ("PACIFIC OFFICE SUPPLY INC.", "imports@pac-office.com", "+1-206-555-0190", "+1-206-555-0191", "601 UNION STREET, SEATTLE, WA, U.S.A"),
    ("MEXICO INDUSTRIAL SOURCING SA", "comercio@misourcing.mx", "+52-55-4100-8700", "+52-55-4100-8701", "AV. REFORMA 250, MEXICO CITY, MEXICO"),
    ("TORONTO AUTOMATION LTD", "import@torontoauto.ca", "+1-416-555-4300", "+1-416-555-4301", "88 KING STREET WEST, TORONTO, CANADA"),
    ("LA WHOLESALE MART INC.", "imports@lawholesale.com", "+1-323-555-7100", "+1-323-555-7101", "789 TRADE AVE, LOS ANGELES, CA, U.S.A"),
]
TRD06_GOODS = [
    ("Plastic Office Supplies", "3926.90", "pcs", "CTC"), ("Power Transformers", "8504.40", "units", "CTC"),
    ("Leather Wallets", "4202.22", "pcs", "RVC"), ("Industrial Sensors", "9031.80", "pcs", "CTC"),
    ("Precision Brackets", "7326.90", "pcs", "CTC"), ("Battery Modules", "8507.60", "sets", "RVC"),
    ("Optical Lens Assemblies", "9002.11", "pcs", "CTC"), ("CNC Spindle Units", "8466.93", "sets", "RVC"),
    ("Packaging Film Rolls", "3920.62", "rolls", "CTC"), ("Wiring Harnesses", "8544.42", "pcs", "CTC"),
    ("Aluminum Heat Sinks", "7616.99", "pcs", "CTC"), ("Control Box Panels", "8538.10", "pcs", "RVC"),
    ("Guide Pins", "7318.29", "pcs", "CTC"), ("Robot Gripper Fingers", "8479.90", "pcs", "RVC"),
    ("Bearing Housings", "8483.30", "pcs", "CTC"), ("Motor Shafts", "8483.10", "pcs", "CTC"),
    ("Cooling Plates", "8419.90", "pcs", "RVC"), ("Sensor Brackets", "8302.49", "pcs", "CTC"),
    ("PCB Inspection Jigs", "9031.49", "sets", "PE"), ("Laser Marking Fixtures", "8466.20", "sets", "RVC"),
    ("Servo Motor Adapters", "8503.00", "pcs", "CTC"), ("Cell Tray Guides", "3926.90", "pcs", "CTC"),
    ("Medical Sensor Modules", "9018.19", "pcs", "RVC"), ("OLED Display Modules", "8524.92", "pcs", "CTC"),
    ("Vacuum Pad Holders", "8414.90", "pcs", "CTC"), ("Transfer Rail Supports", "7308.90", "pcs", "CTC"),
    ("Die Insert Blocks", "8207.30", "pcs", "RVC"), ("Assembly Master Jigs", "9031.80", "sets", "PE"),
    ("Conveyor Stoppers", "8428.90", "pcs", "RVC"), ("Gear Housings", "8483.90", "pcs", "CTC"),
    ("Hinge Brackets", "8302.10", "pcs", "CTC"), ("Cooling Manifolds", "8481.80", "sets", "RVC"),
    ("Clamp Blocks", "7326.90", "pcs", "CTC"), ("Shaft Holders", "8483.90", "pcs", "CTC"),
    ("Tube Cutting Guides", "8466.94", "sets", "RVC"), ("Casting Gauges", "9031.80", "sets", "PE"),
    ("Cover Plates", "7616.99", "pcs", "CTC"), ("Spacer Sets", "7318.19", "sets", "CTC"),
    ("Index Plates", "7326.90", "pcs", "CTC"), ("Packing Guides", "3926.90", "pcs", "CTC"),
    ("Electronic Relays", "8536.49", "pcs", "CTC"), ("Terminal Blocks", "8536.90", "pcs", "CTC"),
    ("Hydraulic Fittings", "7307.99", "pcs", "CTC"), ("Air Cylinder Brackets", "8412.90", "pcs", "RVC"),
    ("Vision Camera Mounts", "8529.90", "pcs", "CTC"), ("Machine Safety Covers", "3926.90", "pcs", "CTC"),
    ("Stainless Spacers", "7318.22", "pcs", "CTC"), ("Factory Cable Trays", "7308.90", "pcs", "CTC"),
    ("Automotive Switch Housings", "8538.90", "pcs", "RVC"), ("Rubber Sealing Gaskets", "4016.93", "pcs", "CTC"),
    ("Smart Meter Cases", "9028.90", "pcs", "RVC"), ("Thermal Printer Parts", "8443.99", "pcs", "CTC"),
    ("Precision Springs", "7320.20", "pcs", "CTC"), ("Food Packaging Trays", "3923.90", "pcs", "CTC"),
    ("Laboratory Sample Holders", "3926.90", "pcs", "CTC"), ("Industrial LED Modules", "8541.41", "pcs", "RVC"),
    ("Machine Tool Covers", "8466.93", "pcs", "RVC"), ("Automated Feeder Bowls", "8428.39", "sets", "PE"),
    ("Mold Ejector Plates", "8207.30", "pcs", "RVC"), ("Inspection Master Blocks", "9031.80", "sets", "PE"),
]
TRD06_AUTHORIZED_NAMES = ["M. J. KIM", "S. D. PARK", "J. W. LEE", "H. S. CHOI", "D. Y. PARK", "S. Y. HAN", "T. M. JUNG", "Y. J. KANG", "J. H. YOON", "E. S. OH"]


def _trd06_date(value: date) -> str:
    return f"{value.year}/{value.month:02d}/{value.day:02d}"


def trd06_certificate_origin_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index in range(60):
        exporter = TRD06_EXPORTERS[index % len(TRD06_EXPORTERS)]
        producer = TRD06_EXPORTERS[(index + 3) % len(TRD06_EXPORTERS)]
        importer = TRD06_IMPORTERS[index % len(TRD06_IMPORTERS)]
        cert_date = date(2023 + index % 4, 1 + (index * 5) % 12, 1 + (index * 7) % 27)
        blanket_from = cert_date
        blanket_to = blanket_from + timedelta(days=330 + (index % 30))
        row: dict[str, str] = {
            "exporter_name": exporter[0],
            "exporter_email": exporter[1],
            "exporter_telephone": exporter[2],
            "exporter_fax": exporter[3],
            "exporter_address": exporter[4],
            "blanket_period_from": _trd06_date(blanket_from),
            "blanket_period_to": _trd06_date(blanket_to),
            "producer_name": producer[0].replace("CO., LTD.", "MANUFACTURING CO., LTD."),
            "producer_email": producer[1].replace("export@", "producer@").replace("sales@", "producer@"),
            "producer_telephone": producer[2],
            "producer_fax": producer[3],
            "producer_address": producer[4],
            "importer_name": importer[0],
            "importer_email": importer[1],
            "importer_telephone": importer[2],
            "importer_fax": importer[3],
            "importer_address": importer[4],
            "certification_date": _trd06_date(cert_date),
            "authorized_name": TRD06_AUTHORIZED_NAMES[index % len(TRD06_AUTHORIZED_NAMES)],
        }
        for slot in range(1, 4):
            goods, hs, unit, criterion = TRD06_GOODS[(index * 3 + slot - 1) % len(TRD06_GOODS)]
            quantity = (index % 9 + 1) * (slot + 1) * 100
            serial = f"{index + 1:02d}{slot:02d}"
            row.update({
                f"item_{slot}_serial_no": serial,
                f"item_{slot}_description": goods,
                f"item_{slot}_quantity_unit": f"{quantity:,} {unit}",
                f"item_{slot}_hs_no": hs,
                f"item_{slot}_preference_criterion": criterion,
                f"item_{slot}_country_of_origin": "Republic of Korea",
            })
        profiles.append(row)
    return profiles


TRD05_FOREIGN_BUYERS = [
    ("TUBITAK UZAY", "TRTUB ITA0003C", "TR", "TURKEY", "ICN", "인천공항", "항공사"),
    ("ACME AEROSPACE INC.", "USACM LAX0012A", "US", "UNITED STATES", "ICN", "인천공항", "KOREAN AIR"),
    ("NIPPON PRECISION CO., LTD.", "JPNIP TYO0041B", "JP", "JAPAN", "PUS", "부산항", "HYUNDAI MERCHANT"),
    ("BERLIN OPTICS GMBH", "DEBER HAM0027C", "DE", "GERMANY", "ICN", "인천공항", "LUFTHANSA"),
    ("SINGAPORE ROBOTICS PTE LTD", "SGROB SIN0098A", "SG", "SINGAPORE", "ICN", "인천공항", "SINGAPORE AIR"),
    ("TAIPEI SEMICONDUCTOR LTD", "TWTSC TPE0175D", "TW", "TAIWAN", "PUS", "부산항", "EVERGREEN"),
    ("DUBAI SYSTEMS FZE", "AEDUB DXB0214E", "AE", "U.A.E", "ICN", "인천공항", "EMIRATES"),
    ("SYDNEY MEDTECH PTY LTD", "AUSYD SYD0158F", "AU", "AUSTRALIA", "ICN", "인천공항", "QANTAS"),
]
TRD05_COMMODITIES = [
    ("PART OF SATELLITERS", "SPACEBORNE OPTICAL IMAGING SYSTEM", "FLIGHT MODEL", "8803.90-2000", "S1-GIS-1120"),
    ("SEMICONDUCTOR TESTER", "AUTOMATED TEST EQUIPMENT MODULE", "ATE-9000", "9030.82-0000", "E-ATE-2401"),
    ("ROBOT CONTROLLER", "INDUSTRIAL ROBOT CONTROL UNIT", "RCU-500", "8537.10-9090", "E-RBT-1305"),
    ("PRECISION LENS ASSY", "OPTICAL INSPECTION LENS MODULE", "OLM-250", "9002.11-9000", "E-OPT-0811"),
    ("BATTERY PACK", "LITHIUM ION BATTERY PACK", "BP-48V", "8507.60-9000", "E-BAT-5502"),
    ("MEDICAL SENSOR", "BIO SIGNAL SENSOR MODULE", "BSM-20", "9018.19-9000", "E-MED-3207"),
    ("CNC SPINDLE UNIT", "HIGH SPEED SPINDLE ASSEMBLY", "HS-24000", "8466.93-0000", "E-CNC-7781"),
    ("DISPLAY MODULE", "OLED DISPLAY DRIVER MODULE", "ODM-13", "8524.92-0000", "E-DSP-6104"),
]
TRD05_EXPORTER_TRADE_CODES = ["쎄트렉아-1-99-1-01-5", "한빛정-2-15-3-04-1", "미래모-3-27-2-09-8", "대한소-1-44-7-11-2", "태성기-5-02-1-08-6"]
TRD05_CUSTOMS_BROKERS = [("다산관세사무소", "김두경", "대전세관장"), ("한빛관세법인", "박서준", "인천세관장"), ("대한관세사무소", "이도윤", "서울세관장"), ("중앙관세법인", "정민재", "부산세관장"), ("유니온관세법인", "최지호", "대구세관장")]
TRD05_EXPORTER_REPRESENTATIVES = ["박성동", "김민준", "이서준", "정시우", "오서윤", "서지우", "임준우", "최유찬"]
TRD05_TRANSPORT_TYPES = ["40 ETC", "10 SEA", "20 AIR", "30 RAIL", "50 POST"]
TRD05_PAYMENT_METHODS = ["TT 단순송금방식", "LC 신용장", "DP 지급인도", "DA 인수인도", "OA 사후송금"]
TRD05_TRADE_TERMS = ["DDU", "FOB", "CIF", "DAP", "EXW"]


QC01_LABS = ["한국건설품질연구소", "대한건설시험연구원", "한국건설재료시험원", "중앙품질시험연구원", "미래건설품질원"]
QC01_SAMPLE_PRODUCTS = [
    "울트라 커플러(현장체결식철근커플러)(한국)", "스마트 커플러(기계식철근이음)(한국)", "하이텐션 철근커플러(한국)",
    "원터치 철근커플러(한국)", "나사식 철근커플러(한국)", "슬리브형 철근커플러(한국)", "그립형 철근커플러(한국)",
    "고강도 철근커플러(한국)", "현장체결식 이음커플러(한국)", "토목용 철근커플러(한국)", "건축용 철근커플러(한국)",
    "내진용 철근커플러(한국)", "D19-D25 겸용 철근커플러(한국)", "D29-D32 대구경 커플러(한국)", "프리미엄 기계식이음 커플러(한국)",
]
QC01_CONSTRUCTION_COMPANIES = [
    "준성산업", "한빛건설", "대영산업", "성우이앤씨", "태광건설", "미래토건", "우진건설", "동원개발", "서린건설", "금강산업",
    "삼호엔지니어링", "경남토건", "세진건설", "대림산업개발", "도담건설", "한솔이엔지", "진성산업", "코리아스틸", "부광건설", "다온건설",
    "영남산업개발", "신우토건", "제일건설", "오름건설", "에이스건설", "중앙산업", "라온건설", "누리종합건설", "해솔건설", "신화산업",
]
QC01_PROJECT_NAMES = [
    "김해 물류센터 신축공사", "평택 반도체 공장 증축공사", "부산항 배후단지 창고 신축공사", "대구 지식산업센터 신축공사",
    "인천 검단 공동주택 신축공사", "화성 기계부품공장 증축공사", "창원 스마트공장 신축공사", "울산 산업단지 공장동 증축공사",
    "광주 복합물류센터 신축공사", "천안 제조시설 증축공사", "구미 전자부품공장 신축공사", "아산 배터리소재 공장 신축공사",
    "김포 데이터센터 신축공사", "원주 의료기기 공장 신축공사", "세종 업무시설 신축공사", "여수 플랜트 부대시설 공사",
]
QC01_PURPOSES = ["공급원승인용", "현장 반입 승인용", "품질관리 확인용", "감리단 제출용", "시공 품질확인용", "자재승인 제출용", "준공자료 제출용", "공사 품질검토용"]
QC01_NATIONAL_FACILITY_STATUS = ["해당사항없음", "해당없음", "비대상", "시설명 미해당", "국가중요시설 아님"]
QC01_INSPECTION_METHODS = ["의뢰인제시방법", "KS 기준 준용", "현장 제출시료 치수측정", "버니어캘리퍼스 측정", "시험기관 표준절차", "품질관리계획서 기준"]
QC01_ENGINEER_NAMES = ["곽재현", "김현준", "박준우", "서지우", "임준우", "한서연", "오서윤", "신채원", "정시우", "장지후", "최유찬", "강도현"]
QC01_CERT_NUMBERS = ["062021411561", "062019318742", "062022104833", "062020557196", "062023214509", "062018903175", "062024118620", "062021774031"]
QC01_OFFICE_ADDRESSES = [
    "대구광역시 달성군 화원읍 비슬로530길 39", "경기도 화성시 동탄산단6길 15", "경상남도 창원시 성산구 완암로 50",
    "부산광역시 강서구 녹산산단261로 74", "충청남도 천안시 서북구 직산읍 직산로 136", "인천광역시 연수구 송도과학로 32",
]

def _trd05_money(value: int) -> str:
    return f"{value:,}"


def _trd05_usd(value: int) -> str:
    return f"${value:,}"


def _trd05_krw(value: int) -> str:
    return f"W{value:,}"


def _trd05_date_slash(value: date) -> str:
    return f"{value.year}/{value.month:02d}/{value.day:02d}"


def trd05_export_declaration_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index in range(60):
        declaration_date = date(2023 + index % 4, 1 + (index * 3) % 12, 1 + (index * 7) % 27)
        due_date = declaration_date + timedelta(days=30)
        buyer, buyer_code, dest_code, dest_country, loading_code, loading_port, carrier = TRD05_FOREIGN_BUYERS[index % len(TRD05_FOREIGN_BUYERS)]
        goods_name, trade_goods_name, model_spec, hs_code, export_approval_stub = TRD05_COMMODITIES[index % len(TRD05_COMMODITIES)]
        exporter = FIN01_COMPANY_NAMES[(index + 10) % len(FIN01_COMPANY_NAMES)].replace(" 주식회사", "").replace("주식회사 ", "(주)")
        representative = TRD05_EXPORTER_REPRESENTATIVES[index % len(TRD05_EXPORTER_REPRESENTATIVES)]
        broker_office, broker_name, customs_chief = TRD05_CUSTOMS_BROKERS[index % len(TRD05_CUSTOMS_BROKERS)]
        exchange = 1120.35 + (index % 30) * 7.42
        quantity = 1 + (index % 5)
        unit_price = 125_000 + (index % 17) * 85_000
        amount_usd = quantity * unit_price
        net_weight = 80 + (index % 40) * 7
        gross_weight = net_weight + 30 + (index % 8) * 5
        package_count = 1 + (index % 4)
        freight = int(amount_usd * 0.009) + 1200 + index * 17
        insurance = max(75, int(freight * 0.1))
        fob_usd = max(1, amount_usd - freight - insurance)
        fob_krw = int(round(fob_usd * exchange))
        transport = TRD05_TRANSPORT_TYPES[index % len(TRD05_TRANSPORT_TYPES)]
        payment_method = TRD05_PAYMENT_METHODS[index % len(TRD05_PAYMENT_METHODS)]
        incoterm = TRD05_TRADE_TERMS[index % len(TRD05_TRADE_TERMS)]
        issue_no = f"11298-{declaration_date:%y}-{200000 + index * 37:07d}"
        declaration_no = f"150-{declaration_date:%y}-{declaration_date.month:02d}-{5000000 + index * 137:08d}"
        business_no = f"{100 + index % 800:03d}-{10 + index % 80:02d}-{20000 + index * 139:05d}"
        address = FIN01_ADDRESSES[index % len(FIN01_ADDRESSES)]
        exporter_trade_code = TRD05_EXPORTER_TRADE_CODES[index % len(TRD05_EXPORTER_TRADE_CODES)]
        row = {
            "settlement_exchange_rate": f"{exchange:,.3f}",
            "usd_exchange_rate": f"{exchange:,.3f}",
            "issue_number": issue_no,
            "customs_broker_office": broker_office,
            "customs_broker_name": broker_name,
            "declaration_number": declaration_no,
            "declaration_date": str(declaration_date),
            "declaration_type_name": "일반P/L신고",
            "exporter_name_top": exporter,
            "exporter_trade_code_top": exporter_trade_code,
            "exporter_category": "A",
            "transaction_type": "11 일반형태",
            "export_type": "A 일반수출",
            "payment_method": payment_method,
            "destination_code": dest_code,
            "destination_country": dest_country,
            "loading_port": loading_port,
            "carrier_name": carrier,
            "exporter_name": exporter,
            "exporter_trade_code": exporter_trade_code,
            "exporter_address": address,
            "exporter_representative_name": representative,
            "exporter_location_code": f"{300 + index % 80}",
            "exporter_business_registration_number": business_no,
            "inspection_due_date": _trd05_date_slash(declaration_date),
            "transport_type": transport,
            "goods_location_code": f"{300 + (index * 2) % 90}",
            "goods_location_address": address.replace("서울특별시 ", "서울 ")[:28],
            "manufacturer_name": exporter,
            "manufacturer_trade_code": exporter_trade_code,
            "manufacture_place_code": f"{300 + (index * 3) % 90}",
            "industrial_zone_code": f"{900 + index % 90}",
            "buyer_name": buyer,
            "buyer_code": buyer_code,
            "refund_applicant_type": "2",
            "refund_applicant_description": "간이환급 NO",
            "item_count_text": "001/001",
            "goods_name": goods_name,
            "trade_goods_name": trade_goods_name,
            "model_specification": model_spec,
            "item_quantity": f"{quantity}(SET)",
            "unit_price_usd": _trd05_money(unit_price),
            "amount_usd": _trd05_money(amount_usd),
            "hs_code": hs_code,
            "net_weight": f"{net_weight}(KG)",
            "empty_quantity_marker": "()",
            "reported_price_fob": f"{_trd05_usd(fob_usd)}\n{_trd05_krw(fob_krw)}",
            "export_goods_number": export_approval_stub,
            "package_count_type": f"{package_count}(CT)",
            "export_requirement_approval_number": f"E-{7000000000000000 + index * 10091:016d}",
            "export_requirement_document_name": "(전략물자수출허가서)",
            "total_gross_weight": f"{gross_weight}(KG)",
            "total_package_count": f"{package_count}(CT)",
            "total_reported_price_fob": f"{_trd05_usd(fob_usd)}\n{_trd05_krw(fob_krw)}",
            "freight_krw": _trd05_money(freight),
            "insurance_krw": _trd05_money(insurance),
            "payment_amount_text": f"{incoterm}-USD-{amount_usd:,}.00",
            "container_flag": "N",
            "customs_chief_name": customs_chief,
            "customs_officer_name": broker_name,
            "period_start_date": "",
            "period_end_date": "",
            "loading_due_date": _trd05_date_slash(due_date),
            "acceptance_date": _trd05_date_slash(declaration_date),
        }
        profiles.append(row)
    return profiles


def _qc01_dot_date(value: date) -> str:
    return f"{value.year}. {value.month:02d}. {value.day:02d}."


def _qc01_korean_date(value: date) -> str:
    return f"{value.year}년 {value.month:02d}월 {value.day:02d}일"


def qc01_quality_test_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    base_dims = {
        "D19": (22.3, 41.4, 63.4),
        "D22": (25.5, 47.7, 68.6),
        "D25": (28.7, 51.1, 74.9),
        "D29": (32.6, 58.2, 83.6),
        "D32": (36.4, 64.3, 94.1),
    }
    for index in range(60):
        receipt_date = date(2023 + index % 4, 1 + (index * 5) % 12, 1 + (index * 7) % 27)
        sampling_date = receipt_date - timedelta(days=1 + index % 5)
        issue_date = receipt_date + timedelta(days=5 + index % 9)
        company = QC01_CONSTRUCTION_COMPANIES[index % len(QC01_CONSTRUCTION_COMPANIES)]
        requester = ID03_SHAREHOLDER_NAMES[(index + 8) % len(ID03_SHAREHOLDER_NAMES)]
        responsible = QC01_ENGINEER_NAMES[index % len(QC01_ENGINEER_NAMES)]
        examiner = QC01_ENGINEER_NAMES[(index + 3) % len(QC01_ENGINEER_NAMES)]
        shift = ((index % 7) - 3) * 0.1
        row: dict[str, str] = {
            "sample_name_country": QC01_SAMPLE_PRODUCTS[index % len(QC01_SAMPLE_PRODUCTS)],
            "receipt_number": f"{receipt_date:%y%m%d}-{12 + index:03d}",
            "sampling_location": company,
            "receipt_date_text": _qc01_dot_date(receipt_date),
            "intended_use": QC01_PURPOSES[index % len(QC01_PURPOSES)],
            "sampling_date_text": _qc01_dot_date(sampling_date),
            "project_name": QC01_PROJECT_NAMES[index % len(QC01_PROJECT_NAMES)],
            "sampler_name": f"{company} 품질관리자 {requester}",
            "ordering_client": company,
            "observer_name": "-" if index % 4 else f"감리단 {ID03_SHAREHOLDER_NAMES[(index + 11) % len(ID03_SHAREHOLDER_NAMES)]}",
            "contractor_name": company,
            "manufacturer_name": QC01_CONSTRUCTION_COMPANIES[(index + 9) % len(QC01_CONSTRUCTION_COMPANIES)],
            "requester_name": f"{company} {requester}",
            "inventory_quantity": "-" if index % 3 else f"{20 + index % 25} EA",
            "national_critical_facility_status": QC01_NATIONAL_FACILITY_STATUS[index % len(QC01_NATIONAL_FACILITY_STATUS)],
            "section_1_number": "1",
            "section_1_test_item_name": "치수",
            "section_1_inner_label": "내경(D2)",
            "section_1_outer_label": "외경(D1)",
            "section_1_length_label": "길이(L1)",
            "section_1_test_method": QC01_INSPECTION_METHODS[index % len(QC01_INSPECTION_METHODS)],
            "section_1_responsible_qualification": "건설재료시험기사",
            "section_1_responsible_cert_number": QC01_CERT_NUMBERS[index % len(QC01_CERT_NUMBERS)],
            "section_1_responsible_engineer_name": responsible,
            "section_1_responsible_engineer_signature": responsible,
            "section_1_examiner_name": examiner,
            "section_1_examiner_signature": examiner,
            "section_2_number": "2",
            "section_2_test_item_name": "치수",
            "section_2_inner_label": "내경(D2)",
            "section_2_outer_label": "외경(D1)",
            "section_2_length_label": "길이(L1)",
            "section_2_test_method": QC01_INSPECTION_METHODS[(index + 2) % len(QC01_INSPECTION_METHODS)],
            "section_2_responsible_qualification": "건설재료시험기사",
            "section_2_responsible_cert_number": QC01_CERT_NUMBERS[(index + 1) % len(QC01_CERT_NUMBERS)],
            "section_2_responsible_engineer_name": responsible,
            "section_2_responsible_engineer_signature": responsible,
            "section_2_examiner_name": examiner,
            "section_2_examiner_signature": examiner,
            "issue_date_text": _qc01_korean_date(issue_date),
            "representative_title_name": f"대표 {FIN01_REPRESENTATIVES[(index + 6) % len(FIN01_REPRESENTATIVES)]}",
            "office_phone": f"053-58{index % 10}-{1000 + (index * 37) % 9000:04d}",
            "office_fax": f"053-58{(index + 2) % 10}-{1000 + (index * 41) % 9000:04d}",
            "office_address": QC01_OFFICE_ADDRESSES[index % len(QC01_OFFICE_ADDRESSES)],
            "page_indicator": "총2페이지중 1페이지",
        }
        for section, sizes in [("section_1", ["D19", "D22", "D25"]), ("section_2", ["D29", "D32"] )]:
            for size in sizes:
                inner, outer, length = base_dims[size]
                row[f"{section}_{size.lower()}_inner_diameter"] = f"{inner + shift:.1f} mm"
                row[f"{section}_{size.lower()}_outer_diameter"] = f"{outer + shift * 1.5:.1f} mm"
                row[f"{section}_{size.lower()}_length"] = f"{length + shift * 2:.1f} mm"
        profiles.append(row)
    return profiles


def qc02_inspection_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index in range(60):
        supplier = QC02_SUPPLIERS[index % len(QC02_SUPPLIERS)]
        order_date = date(2024 + index % 3, 1 + (index * 2) % 12, 1 + (index * 5) % 27)
        receiving_date = order_date + timedelta(days=3 + index % 9)
        inspector = ID03_SHAREHOLDER_NAMES[index % len(ID03_SHAREHOLDER_NAMES)]
        row: dict[str, str] = {
            "approval_owner_name": FIN01_REPRESENTATIVES[(index + 1) % len(FIN01_REPRESENTATIVES)],
            "approval_reviewer_name": FIN01_REPRESENTATIVES[(index + 2) % len(FIN01_REPRESENTATIVES)],
            "approval_manager_name": FIN01_REPRESENTATIVES[(index + 3) % len(FIN01_REPRESENTATIVES)],
            "supplier_company_name": supplier,
            "purchase_order_number": f"PO-{order_date:%Y%m%d}-{100 + index:03d}",
            "purchase_order_date": f"{order_date.year}년 {order_date.month:02d}월 {order_date.day:02d}일",
            "purchase_order_year": str(order_date.year),
            "purchase_order_month": str(order_date.month),
            "purchase_order_day": str(order_date.day),
            "receiving_date": f"{receiving_date.year}년 {receiving_date.month:02d}월 {receiving_date.day:02d}일",
            "receiving_year": str(receiving_date.year),
            "receiving_month": str(receiving_date.month),
            "receiving_day": str(receiving_date.day),
            "inspection_manager_name": inspector,
            "receiving_location": QC02_RECEIVING_LOCATIONS[index % len(QC02_RECEIVING_LOCATIONS)],
            "inspection_method": QC02_INSPECTION_METHODS[index % len(QC02_INSPECTION_METHODS)],
            "inspector_opinion": QC02_INSPECTOR_OPINIONS[index % len(QC02_INSPECTOR_OPINIONS)],
            "department_head_confirmation": FIN01_REPRESENTATIVES[(index + 4) % len(FIN01_REPRESENTATIVES)],
        }
        for slot in range(1, 9):
            item, spec = QC02_PRODUCT_CATALOG[(index * 2 + slot - 1) % len(QC02_PRODUCT_CATALOG)]
            ordered_qty = 10 + ((index + slot) % 9) * 5
            defect_qty = 0 if (index + slot) % 5 else 1 + (index % 3)
            accepted_qty = ordered_qty - defect_qty
            quality_result = "합격" if defect_qty == 0 else "부분합격"
            other_result = "입고" if defect_qty == 0 else "불량격리"
            remark = "정상입고" if defect_qty == 0 else f"불량 {defect_qty}EA 교환요청"
            row[f"line_{slot}_number"] = str(slot)
            row[f"line_{slot}_item_name"] = item
            row[f"line_{slot}_specification"] = spec
            row[f"line_{slot}_received_quantity"] = str(ordered_qty)
            row[f"line_{slot}_quality_result"] = quality_result
            row[f"line_{slot}_other_result"] = other_result
            row[f"line_{slot}_remark"] = remark
            row[f"line_{slot}_accepted_quantity"] = str(accepted_qty)
            row[f"line_{slot}_defect_quantity"] = str(defect_qty)
        profiles.append(row)
    return profiles


def fin01_company_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index, name in enumerate(FIN01_COMPANY_NAMES, start=1):
        profiles.append(
            {
                "name": name,
                "biz_no": f"{100 + index:03d}-{10 + index % 89:02d}-{20000 + index * 137:05d}",
                "representative": FIN01_REPRESENTATIVES[(index - 1) % len(FIN01_REPRESENTATIVES)],
                "corp_no_masked": f"{110000 + index:06d}-*******",
                "business_type": FIN01_BUSINESS_TYPES[(index - 1) % len(FIN01_BUSINESS_TYPES)],
                "business_item": FIN01_BUSINESS_ITEMS[(index - 1) % len(FIN01_BUSINESS_ITEMS)],
                "address": FIN01_ADDRESSES[(index - 1) % len(FIN01_ADDRESSES)],
            }
        )
    return profiles


def fin01_tax_office_profiles() -> list[dict[str, str]]:
    return [
        {
            "chief": f"{name}세무서장",
            "phone": f"02-{3000 + index:04d}-{7000 + (index * 37) % 1000:04d}",
            "counter": "민원봉사실" if index % 3 == 0 else ("세무민원실" if index % 3 == 1 else "통합민원실"),
        }
        for index, name in enumerate(FIN01_TAX_OFFICE_NAMES, start=1)
    ]


def fin01_accounting_periods() -> list[dict[str, str]]:
    return [
        {"start": f"{year}.01.01", "end": f"{year}.12.31", "filing_type": "정기 신고", "filing_date": f"{year + 1}. 03. 31", "issue_date": f"{year + 1}년 4월 {day}일"}
        for year, day in [(2021, 5), (2022, 5), (2023, 8), (2024, 11), (2025, 7)]
    ] + [
        {"start": "2023.07.01", "end": "2024.06.30", "filing_type": "수정 신고", "filing_date": "2024. 09. 30", "issue_date": "2024년 10월 8일"},
        {"start": "2024.04.01", "end": "2025.03.31", "filing_type": "정기 신고", "filing_date": "2025. 06. 30", "issue_date": "2025년 7월 14일"},
    ]


def id03_registry_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    addresses = FIN01_ADDRESSES + [
        "경기도 하남시 대성로 69번길 48", "경기도 용인시 수지구 광교중앙로 338", "충청남도 천안시 서북구 직산읍 2공단5로 97",
        "충청북도 청주시 흥덕구 오송읍 오송생명로 123", "전라북도 전주시 덕진구 기린대로 451", "전라남도 여수시 산단중앙로 77",
        "경상북도 구미시 1공단로 212", "경상남도 창원시 성산구 완암로 50", "강원특별자치도 원주시 혁신로 19",
        "제주특별자치도 제주시 첨단로 242",
    ]
    for index in range(60):
        share_count = ID03_SHARE_COUNTS[index % len(ID03_SHARE_COUNTS)]
        par_value = ID03_PAR_VALUES[index % len(ID03_PAR_VALUES)]
        date_text = ID03_ISSUE_DATES[index % len(ID03_ISSUE_DATES)]
        company_name = FIN01_COMPANY_NAMES[index]
        shareholder_name = ID03_SHAREHOLDER_NAMES[index]
        profiles.append(
            {
                "list_date": date_text,
                "list_date_suffix": "현재",
                "shareholder_name": shareholder_name,
                "shareholder_share_count": f"{share_count:,}",
                "total_issued_shares": f"{share_count:,}주",
                "par_value": f"{par_value:,}원",
                "issue_date": date_text,
                "company_name": company_name,
                "company_address": addresses[index % len(addresses)],
                "representative_name": shareholder_name,
                "ownership_ratio": "100.00%",
                "capital_amount": f"{share_count * par_value:,}원",
            }
        )
    return profiles


def _spaced_tax_office_chief(name: str) -> str:
    return " ".join(f"{name}세무서장")


def id01_registration_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    addresses = FIN01_ADDRESSES + [
        "경기도 김포시 고촌읍 상미로9번길 51-5", "경기도 하남시 대성로 69번길 48", "충청남도 천안시 서북구 직산읍 2공단5로 97",
        "충청북도 청주시 흥덕구 오송읍 오송생명로 123", "전라북도 전주시 덕진구 기린대로 451", "경상북도 구미시 1공단로 212",
        "경상남도 창원시 성산구 완암로 50", "제주특별자치도 제주시 첨단로 242",
    ]
    for index, company_name in enumerate(FIN01_COMPANY_NAMES, start=1):
        activity = ID01_ACTIVITY_BUNDLES[(index - 1) % len(ID01_ACTIVITY_BUNDLES)]
        address = addresses[(index - 1) % len(addresses)]
        split_pos = min(len(address), max(8, len(address) // 2))
        line1 = address[:split_pos].rstrip()
        line2 = address[split_pos:].lstrip() or address
        opening_year = 2014 + (index % 12)
        opening_month = 1 + (index * 3) % 12
        opening_day = 1 + (index * 7) % 27
        issue_year = max(opening_year + 1, 2023 + (index % 4))
        issue_month = 1 + (index * 2) % 12
        issue_day = 1 + (index * 5) % 27
        tax_name = FIN01_TAX_OFFICE_NAMES[(index - 1) % len(FIN01_TAX_OFFICE_NAMES)]
        row = {
            "business_registration_number": f"등록번호:{200 + index:03d}-{10 + index % 89:02d}-{30000 + index * 149:05d}",
            "corporate_name": f"법인명(단 체명):{company_name}",
            "representative_name": f"대 표 자 :{FIN01_REPRESENTATIVES[(index - 1) % len(FIN01_REPRESENTATIVES)]}",
            "opening_date": f"개 업 연 월 일 :{opening_year} 년 {opening_month:02d}월{opening_day:02d}일",
            "corporate_registration_number": f"법인등록 번호 :{110000 + index:06d}-{1000000 + index * 173:07d}",
            "workplace_address": f"사 업 장 소 재 지 :{address}",
            "head_office_address_line1": f"본 점 소 재 지 :{line1}",
            "head_office_address_line2": line2,
            "issue_reason": f"발 급 사 유 :{ID01_ISSUE_REASONS[(index - 1) % len(ID01_ISSUE_REASONS)]}",
            "issue_date": f"{issue_year} 년 {issue_month:02d} 월 {issue_day:02d} 일",
            "tax_office_chief": _spaced_tax_office_chief(tax_name),
        }
        for slot in range(1, 8):
            row[f"business_type_{slot}"] = activity["types"][slot - 1]
        for slot in range(1, 7):
            row[f"business_item_{slot}"] = activity["items"][slot - 1]
        profiles.append(row)
    return profiles


def _date_kr(value: date, *, compact_year: bool = False) -> str:
    if compact_year:
        return f"{value.year}년{value.month:02d}월 {value.day:02d}일"
    return f"{value.year}년 {value.month:02d}월 {value.day:02d}일"


def crd02_credit_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    addresses = FIN01_ADDRESSES + [
        "서울특별시 영등포구 국회대로70길 23, 10층", "서울특별시 강서구 마곡중앙로 161-8, B동 902호",
        "경기도 용인시 기흥구 흥덕중앙로 120, 1501호", "경기도 김포시 고촌읍 상미로9번길 51-5",
        "인천광역시 남동구 남동대로 215번길 30", "부산광역시 강서구 녹산산단335로 20",
        "대구광역시 달성군 구지면 국가산단대로 33길 12", "광주광역시 광산구 평동산단로 184",
        "충청북도 청주시 흥덕구 오송읍 오송생명로 123", "충청남도 천안시 서북구 직산읍 2공단5로 97",
        "전라북도 전주시 덕진구 팔복로 59", "경상남도 창원시 성산구 완암로 50",
    ]
    for index, company_name in enumerate(CRD02_COMPANY_NAMES, start=1):
        fiscal_year = 2023 + (index % 3)
        fiscal_end = date(fiscal_year, 12, 31)
        eval_date = date(fiscal_year + 1, 3 + (index % 4), 1 + (index * 4) % 27)
        valid_until = eval_date.replace(year=eval_date.year + 1) - timedelta(days=1)
        rating = CRD02_RATING_GRADES[index % len(CRD02_RATING_GRADES)]
        profiles.append(
            {
                "certificate_serial_number": f"PPR-{eval_date.year}-{eval_date.month}-{21000 + index * 137}-U",
                "issue_number": f"SCRI-{eval_date:%Y%m%d}-{index % 997:03d}",
                "recipient_company_name": company_name,
                "evaluated_company_name": company_name,
                "representative_name": FIN01_REPRESENTATIVES[(index - 1) % len(FIN01_REPRESENTATIVES)],
                "corporate_registration_number": f"{110000 + index:06d}-{1000000 + index * 173:07d}",
                "business_registration_number": f"{100 + index:03d}-{10 + index % 89:02d}-{20000 + index * 137:05d}",
                "headquarters_address": addresses[(index - 1) % len(addresses)],
                "fiscal_year_end": _date_kr(fiscal_end, compact_year=True),
                "rating_evaluation_date": _date_kr(eval_date),
                "rating_valid_until": _date_kr(valid_until),
                "credit_rating": rating,
                "rating_description_grade": rating,
                "rating_description": CRD02_RATING_DESCRIPTIONS[rating],
                "submission_purpose": CRD02_PURPOSES[(index - 1) % len(CRD02_PURPOSES)],
            }
        )
    return profiles


def id11_beneficial_owner_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for index, company_name in enumerate(FIN01_COMPANY_NAMES, start=1):
        ownership = ID11_OWNERSHIP_SETS[(index - 1) % len(ID11_OWNERSHIP_SETS)]
        writer_name = FIN01_REPRESENTATIVES[(index - 1) % len(FIN01_REPRESENTATIVES)]
        row: dict[str, str] = {
            "writer_organization_name_top": company_name,
            "writer_position_top": ID11_WRITER_POSITIONS[(index - 1) % len(ID11_WRITER_POSITIONS)],
            "writer_name_top": writer_name,
            "owner_path_25_percent_checkbox": "✓",
            "writer_organization_name_bottom": company_name,
            "writer_position_bottom": ID11_WRITER_POSITIONS[(index - 1) % len(ID11_WRITER_POSITIONS)],
            "writer_name_bottom": writer_name,
        }
        for slot in range(1, 5):
            name_index = (index + slot * 7 - 1) % len(ID03_SHAREHOLDER_NAMES)
            name_ko = ID03_SHAREHOLDER_NAMES[name_index]
            english = f"{ID11_ENGLISH_GIVEN_NAMES[name_index % len(ID11_ENGLISH_GIVEN_NAMES)]} {ID11_ENGLISH_SURNAMES[name_index % len(ID11_ENGLISH_SURNAMES)]}".upper()
            birth_year = 1968 + ((index + slot * 3) % 30)
            birth_month = 1 + ((index + slot * 5) % 12)
            birth_day = 1 + ((index + slot * 7) % 27)
            row[f"beneficial_owner_{slot}_name_ko"] = name_ko
            row[f"beneficial_owner_{slot}_name_en"] = english
            row[f"beneficial_owner_{slot}_birth_date"] = f"{birth_year}.{birth_month:02d}.{birth_day:02d}"
            row[f"beneficial_owner_{slot}_ownership_percent"] = str(ownership[slot - 1])
            row[f"beneficial_owner_{slot}_nationality"] = "대한민국"
        profiles.append(row)
    return profiles

SPECS: dict[str, list[Spec]] = {
    "ID-06": [
        s("resident_name", "성명", NAME),
        s("resident_registration_number", "주민등록번호", RRN, "center"),
        s("resident_address_line1", "주소 1행", ADDRESS),
        s("resident_address_line2", "주소 2행", "pattern:###"),
        s("resident_address_line3", "주소 3행", "choice:아파트 101동 505호|101동 1203호|르헤브빌딩 502호"),
        s("id_issue_date", "발급일", DATE_DOT, "center"),
        s("id_issuer", "발급기관", LOCAL_GOV, "center"),
    ],
    "FIN-03": [
        s("page_number", "페이지", PAGE, "center"),
        s("document_confirmation_number", "문서확인번호", DOCNO16, "center"),
        s("processing_period", "처리기간", "choice:즉시(단 해외이주용 10일)|즉시|3시간 이내"),
        s("taxpayer_name", "납세자 성명", NAME),
        s("taxpayer_rrn", "주민등록번호", RRN, "center"),
        s("taxpayer_address", "주소", ADDRESS),
        s("valid_until", "증명 유효일", DATE_KR, "center"),
        s("issue_date", "발급일", DATE_KR, "center"),
        s("tax_office_chief", "세무서장", TAX_OFFICES, "center"),
        s("tax_office_phone", "세무서 연락처", PHONE, "center"),
    ],
    "FIN-06": [
        s("page_number", "페이지", "choice:(1 / 1)|(1 / 2)|(1 / 11)", "center"),
        s("document_confirmation_number", "문서확인번호", DOCNO16, "center"),
        s("income_year", "귀속연도", "choice:(2023년 귀속)|(2024년 귀속)|(2025년 귀속)", "center"),
        s("taxpayer_name", "성명", NAME),
        s("taxpayer_rrn", "주민등록번호", RRN, "center"),
        s("taxpayer_address", "주소", ADDRESS),
        s("business_registration_number", "사업자등록번호", BIZNO, "center"),
        s("revenue_amount_1", "수입금액 1", MONEY, "right"),
        s("income_amount_1", "소득금액 1", MONEY, "right"),
        s("tax_amount_1", "총결정세액 1", "choice:0|1|2|3", "right"),
        s("income_type_1", "소득구분 1", "choice:(연말정산)|(종합소득세)|(사업소득)"),
        s("revenue_amount_2", "수입금액 2", MONEY, "right"),
        s("income_amount_2", "소득금액 2", MONEY, "right"),
        s("tax_amount_2", "총결정세액 2", "choice:0|1|2|3", "right"),
    ],
    "ID-13": [
        s("certificate_number", "증명서 번호", "pattern:제KA0GI##-###호", "center"),
        s("department", "소속", f"template:소 속:{{{{{COMPANIES}}}}}"),
        s("job_title", "직책", "choice:직책: 기획이사|직책: 국장|직책: 팀장|직책: 책임연구원"),
        s("employee_name", "성명", "template:성 명:{{person.name_ko}}"),
        s("employment_period", "근무기간", "choice:근무기간 : 2020년 03월 01일부터 2025년 3월 31일 현재까지 (5년 1개월)|근무기간 : 2021년 01월 01일부터 2024년 12월 31일 현재까지 (4년 0개월)"),
        s("submission_to", "제출처", "choice:제 출 처 : 학교 제출|제 출 처 : 금융기관 제출|제 출 처 : 공공기관 제출"),
        s("purpose", "용도", "choice:용   도: 구비 서류|용   도: 대출 심사|용   도: 신원 확인"),
        s("issue_date", "발급일", DATE_KR, "center"),
        s("organization_name", "기관명", "choice:(사)한 국 게 임 산 업 협회|한국소프트웨어산업협회|한국제조산업협회", "center"),
        s("chairperson_name", "대표자명", "template:회 장 {{person.name_ko}}", "center"),
        s("confirmation_department", "확인부서", "template:확인부서: 직책 국장,성명:{{person.name_ko}}"),
        s("confirmation_phone", "확인부서 연락처", "template:(확인부서 연락처: {{person.phone_kr}})"),
    ],
    "ID-01": [
        s("business_registration_number", "등록번호", "pool:id01_business_registration_numbers", "center"),
        s("corporate_name", "법인명", "pool:id01_corporate_names"),
        s("representative_name", "대표자", "pool:id01_representative_names"),
        s("opening_date", "개업연월일", "pool:id01_opening_dates"),
        s("corporate_registration_number", "법인등록번호", "pool:id01_corporate_registration_numbers", "center"),
        s("workplace_address", "사업장 소재지", "pool:id01_workplace_addresses"),
        s("head_office_address_line1", "본점 소재지 1행", "pool:id01_head_office_address_line1"),
        s("head_office_address_line2", "본점 소재지 2행", "pool:id01_head_office_address_line2"),
        s("business_type_1", "업태 1", "pool:id01_business_type_1"),
        s("business_item_1", "종목 1", "pool:id01_business_item_1"),
        s("business_type_2", "업태 2", "pool:id01_business_type_2"),
        s("business_item_2", "종목 2", "pool:id01_business_item_2"),
        s("business_type_3", "업태 3", "pool:id01_business_type_3"),
        s("business_item_3", "종목 3", "pool:id01_business_item_3"),
        s("business_type_4", "업태 4", "pool:id01_business_type_4"),
        s("business_type_5", "업태 5", "pool:id01_business_type_5"),
        s("business_item_4", "종목 4", "pool:id01_business_item_4"),
        s("business_type_6", "업태 6", "pool:id01_business_type_6"),
        s("business_item_5", "종목 5", "pool:id01_business_item_5"),
        s("business_type_7", "업태 7", "pool:id01_business_type_7"),
        s("business_item_6", "종목 6", "pool:id01_business_item_6"),
        s("issue_reason", "발급사유", "pool:id01_issue_reasons"),
        s("issue_date", "발급일", "pool:id01_issue_dates", "center"),
        s("tax_office_chief", "세무서장", "pool:id01_tax_office_chiefs", "center"),
    ],
    "FIN-01": [
        s("page_number", "페이지", "choice:( 1 / 4 )|( 2 / 4 )", "center"),
        s("document_confirmation_number", "문서확인번호", DOCNO16, "center"),
        s("applicant_type_individual_checkbox", "개인 체크박스", "literal:☐", "center"),
        s("applicant_type_corporate_checkbox", "법인 체크박스", "literal:☑", "center"),
        s("company_name", "상호", "pool:fin01_company_names"),
        s("business_registration_number", "사업자등록번호", BIZNO, "center"),
        s("representative_name", "대표자", NAME),
        s("corporate_registration_number_masked", "법인등록번호", "pattern:######-*******", "center"),
        s("business_type", "업태", "pool:fin01_business_types"),
        s("business_item", "종목", "pool:fin01_business_items"),
        s("company_address", "사업장 주소", ADDRESS),
        s("fiscal_period_start", "과세기간 시작일", "pool:fin01_period_starts", "center"),
        s("fiscal_period_end", "과세기간 종료일", "pool:fin01_period_ends", "center"),
        s("filing_type", "신고구분", "choice:정기 신고|수정 신고|기한후 신고", "center"),
        s("filing_date", "신고일", "choice:2023. 03. 31|2024. 03. 31|2025. 03. 31", "center"),
        s("certificate_issue_date", "증명 발급일", "choice:2024년 4월 5일|2025년 4월 11일|2026년 4월 7일", "center"),
        s("receipt_number", "접수번호", "pattern:############", "center"),
        s("service_counter", "민원창구", "pool:fin01_service_counters", "center"),
        s("tax_office_chief", "세무서장", "pool:fin01_tax_office_chiefs", "center"),
        s("tax_office_phone", "문의전화", "pool:fin01_tax_office_phones", "center"),
    ],
    "CRD-02": [
        s("certificate_serial_number", "일련번호", "pool:crd02_certificate_serial_numbers"),
        s("issue_number", "교부번호", "pool:crd02_issue_numbers"),
        s("recipient_company_name", "수신 기업체명", "pool:crd02_recipient_company_names"),
        s("evaluated_company_name", "기업체", "pool:crd02_evaluated_company_names"),
        s("representative_name", "대표자", "pool:crd02_representative_names"),
        s("corporate_registration_number", "법인등록번호", "pool:crd02_corporate_registration_numbers"),
        s("credit_rating", "기업신용평가등급", "pool:crd02_credit_ratings", "center"),
        s("business_registration_number", "사업자등록번호", "pool:crd02_business_registration_numbers"),
        s("headquarters_address", "주소", "pool:crd02_headquarters_addresses"),
        s("fiscal_year_end", "재무결산기준일", "pool:crd02_fiscal_year_ends"),
        s("rating_evaluation_date", "등급평가일", "pool:crd02_rating_evaluation_dates"),
        s("rating_valid_until", "등급유효기한", "pool:crd02_rating_valid_untils"),
        s("rating_description_grade", "등급 설명 내 등급", "same_as:credit_rating", "center"),
        s("submission_purpose", "제출처 및 용도", "pool:crd02_submission_purposes"),
    ],
    "TRD-07": [
        s("purchase_order_number", "발주번호", "pool:trd07_purchase_order_numbers", "center"),
        s("receiver_company_name", "수신 회사명", "pool:trd07_receiver_company_names"),
        s("sender_company_name", "발신 회사명", "pool:trd07_sender_company_names"),
        s("receiver_contact_title", "수신 담당/직함", "pool:trd07_receiver_contact_titles"),
        s("sender_department_contact", "발신 부서/담당", "pool:trd07_sender_department_contacts"),
        s("receiver_tel", "수신 전화", "pool:trd07_receiver_tels", "center"),
        s("sender_tel", "발신 전화", "pool:trd07_sender_tels", "center"),
        s("receiver_fax", "수신 FAX", "pool:trd07_receiver_faxes", "center"),
        s("sender_fax", "발신 FAX", "pool:trd07_sender_faxes", "center"),
        s("sender_email", "발신 이메일", "pool:trd07_sender_emails"),
        s("receiver_address", "수신 주소", "pool:trd07_receiver_addresses"),
        s("sender_address", "발신 주소", "pool:trd07_sender_addresses"),
        s("prepared_date", "작성일", "pool:trd07_prepared_dates", "center"),
        s("reviewed_date", "검토일", "pool:trd07_reviewed_dates", "center"),
        s("approved_date", "승인일", "pool:trd07_approved_dates", "center"),
        s("line_1_number", "품목 1 번호", "pool:trd07_line_1_numbers", "center"),
        s("line_1_item_description", "품목 1 품명/규격", "pool:trd07_line_1_item_descriptions"),
        s("line_1_quantity", "품목 1 수량", "pool:trd07_line_1_quantities", "center"),
        s("line_1_unit_price", "품목 1 단가", "pool:trd07_line_1_unit_prices", "right"),
        s("line_1_amount", "품목 1 금액", "pool:trd07_line_1_amounts", "right"),
        s("line_1_due_date", "품목 1 납기", "pool:trd07_line_1_due_dates", "center"),
        s("line_2_number", "품목 2 번호", "pool:trd07_line_2_numbers", "center"),
        s("line_2_item_description", "품목 2 품명/규격", "pool:trd07_line_2_item_descriptions"),
        s("line_2_quantity", "품목 2 수량", "pool:trd07_line_2_quantities", "center"),
        s("line_2_unit_price", "품목 2 단가", "pool:trd07_line_2_unit_prices", "right"),
        s("line_2_amount", "품목 2 금액", "pool:trd07_line_2_amounts", "right"),
        s("line_2_due_date", "품목 2 납기", "pool:trd07_line_2_due_dates", "center"),
        s("line_2_remark", "품목 2 비고", "pool:trd07_line_2_remarks"),
        s("line_3_number", "품목 3 번호", "pool:trd07_line_3_numbers", "center"),
        s("line_3_item_description", "품목 3 품명/규격", "pool:trd07_line_3_item_descriptions"),
        s("line_3_quantity", "품목 3 수량", "pool:trd07_line_3_quantities", "center"),
        s("line_3_unit_price", "품목 3 단가", "pool:trd07_line_3_unit_prices", "right"),
        s("line_3_amount", "품목 3 금액", "pool:trd07_line_3_amounts", "right"),
        s("line_3_due_date", "품목 3 납기", "pool:trd07_line_3_due_dates", "center"),
        s("line_4_number", "품목 4 번호", "pool:trd07_line_4_numbers", "center"),
        s("line_4_item_description", "품목 4 품명/규격", "pool:trd07_line_4_item_descriptions"),
        s("line_4_quantity", "품목 4 수량", "pool:trd07_line_4_quantities", "center"),
        s("line_4_unit_price", "품목 4 단가", "pool:trd07_line_4_unit_prices", "right"),
        s("line_4_amount", "품목 4 금액", "pool:trd07_line_4_amounts", "right"),
        s("line_4_due_date", "품목 4 납기", "pool:trd07_line_4_due_dates", "center"),
        s("shipping_address", "발송지", "pool:trd07_shipping_addresses"),
        s("delivery_site_name", "납품처", "pool:trd07_delivery_site_names"),
        s("supply_total_amount", "공급가 합계", "pool:trd07_supply_total_amounts", "right"),
        s("form_code", "양식 코드", "pool:trd07_form_codes"),
        s("issuer_company_footer", "하단 발주회사", "pool:trd07_issuer_company_footers", "center"),
    ],
    "SEC-01": [
        s("investment_risk_grade_label", "투자위험등급 표제", "pool:sec01_investment_risk_grade_labels", "center"),
        s("investment_risk_grade", "투자위험등급", "pool:sec01_investment_risk_grades", "center"),
        s("fund_name", "집합투자기구 명칭", "pool:sec01_fund_names"),
        s("asset_manager_name", "집합투자업자 명칭", "pool:sec01_asset_manager_names"),
        s("disclosure_reference_text", "판매회사·공시 참조 안내", "pool:sec01_disclosure_reference_texts"),
        s("prospectus_preparation_date", "작성기준일", "pool:sec01_prospectus_preparation_dates", "center"),
        s("offering_total_amount", "모집(매출) 총액", "pool:sec01_offering_total_amounts", "center"),
        s("offering_period_description", "모집(매출) 기간", "pool:sec01_offering_period_descriptions"),
        s("securities_registration_effective_date", "증권신고서 효력발생일", "pool:sec01_effective_dates", "center"),
        s("offered_security_type", "모집(매출) 증권의 종류", "pool:sec01_offered_security_types"),
    ],
    "FIN-05": [
        s("employer_name", "징수의무자 상호", COMPANIES),
        s("employer_representative_name", "대표자", NAME),
        s("employer_business_registration_number", "사업자등록번호", BIZNO, "center"),
        s("employer_address", "사업장 소재지", ADDRESS),
        s("employee_name", "소득자 성명", NAME),
        s("employee_rrn", "주민등록번호", RRN, "center"),
        s("workplace_business_registration_number", "근무처 사업자번호", BIZNO, "center"),
        s("employment_period", "근무기간", "choice:2023.01.01 ~2023.07.07|2024.01.01 ~2024.12.31|2025.03.01 ~2025.12.31", "center"),
        s("gross_salary_current", "총급여 현재", MONEY, "right"),
        s("gross_salary_total", "총급여 합계", MONEY, "right"),
        s("taxable_income_current", "과세소득 현재", MONEY, "right"),
        s("taxable_income_total", "과세소득 합계", MONEY, "right"),
        s("income_tax_paid", "기납부 소득세", MONEY, "right"),
        s("local_income_tax_paid", "기납부 지방소득세", MONEY, "right"),
        s("income_tax_refund", "차감징수 소득세", "template:-{{money.krw}}", "right"),
        s("local_income_tax_refund", "차감징수 지방소득세", "template:-{{money.krw}}", "right"),
        s("determined_income_tax_current", "결정세액 소득세 현재", MONEY, "right"),
        s("determined_income_tax_total", "결정세액 소득세 합계", MONEY, "right"),
        s("determined_local_tax_current", "결정세액 지방소득세 현재", MONEY, "right"),
        s("determined_local_tax_total", "결정세액 지방소득세 합계", MONEY, "right"),
        s("receipt_date", "영수일", "choice:2023 년 07월 31일|2024 년 02월 28일|2025 년 03월 31일", "center"),
        s("tax_due_income", "납부특례 소득세", MONEY, "right"),
        s("tax_due_total", "납부특례 합계", MONEY, "right"),
        s("withholding_agent_name", "원천징수의무자", COMPANIES, "center"),
        s("tax_office_recipient", "세무서장 귀하", "choice:서초세무서장귀하|삼성세무서장귀하|동대문세무서장귀하", "center"),
    ],
    "FIN-04": [
        s("header_document_confirmation", "상단 문서확인번호", "template:문서확인번호:{{pattern:####-####-####-####}}(신청인:{{person.name_ko}})"),
        s("print_date", "출력일자", "choice:2026/06/29|2025/09/19|2024/03/08", "center"),
        s("print_time", "출력시각", "pattern:##:##:##", "center"),
        s("application_number", "신청번호", "pattern:##############", "center"),
        s("application_datetime", "신청일시", DATETIME, "center"),
        s("applicant_rrn", "신청인 주민등록번호", RRN, "center"),
        s("applicant_name", "신청인 성명", NAME),
        s("page_number", "페이지", PAGE, "center"),
        s("np_acquisition_date", "국민연금 취득일", DATE_DOT, "center"),
        s("np_subscriber_name", "국민연금 가입자명", NAME),
        s("np_subscriber_type", "국민연금 가입자 구분", "choice:사업장가입자|지역가입자|임의가입자"),
        s("np_workplace_number", "국민연금 사업장관리번호", "pattern:###########", "center"),
        s("np_workplace_name", "국민연금 사업장명", COMPANIES),
        s("np_notice_date", "국민연금 기준일", "template:({{date.kr}})", "center"),
        s("hi_acquisition_date", "건강보험 취득일", DATE_DOT, "center"),
        s("hi_subscriber_name", "건강보험 가입자명", NAME),
        s("hi_subscriber_type", "건강보험 가입자 구분", "choice:직장가입자|지역가입자"),
        s("hi_workplace_number", "건강보험 사업장관리번호", "pattern:###########", "center"),
        s("hi_workplace_name", "건강보험 사업장명", COMPANIES),
        s("hi_notice_date", "건강보험 기준일", "template:({{date.kr}})", "center"),
        s("ei_acquisition_date", "고용보험 취득일", DATE_DOT, "center"),
        s("ei_subscriber_name", "고용보험 가입자명", NAME),
        s("ei_subscriber_type", "고용보험 가입자 구분", "choice:사업장가입자|피보험자"),
        s("ei_workplace_number", "고용보험 사업장관리번호", "pattern:###########", "center"),
        s("ei_workplace_name", "고용보험 사업장명", COMPANIES),
        s("ei_notice_date", "고용보험 기준일", "template:({{date.kr}})", "center"),
        s("wc_acquisition_date", "산재보험 취득일", DATE_DOT, "center"),
        s("wc_subscriber_name", "산재보험 가입자명", NAME),
        s("wc_subscriber_type", "산재보험 가입자 구분", "choice:사업장가입자|근로자"),
        s("wc_workplace_number", "산재보험 사업장관리번호", "pattern:###########", "center"),
        s("wc_workplace_name", "산재보험 사업장명", COMPANIES),
        s("wc_notice_date", "산재보험 기준일", "template:({{date.kr}})", "center"),
    ],
    "ID-05": [
        s("subject_registration_base", "등록기준지", ADDRESS),
        s("subject_relation", "본인 관계", "literal:본인", "center"),
        s("subject_name", "본인 성명", NAME),
        s("subject_birth_date", "본인 출생연월일", DATE_KR, "center"),
        s("subject_gender", "본인 성별", "choice:남|여", "center"),
        s("subject_rrn", "본인 주민등록번호", RRN, "center"),
        s("father_relation", "부 관계", "literal:부", "center"),
        s("father_birth_date", "부 출생연월일", DATE_KR, "center"),
        s("father_rrn", "부 주민등록번호", RRN, "center"),
        s("father_gender", "부 성별", "literal:남", "center"),
        s("father_registration_base", "부 등록기준지", ADDRESS),
        s("father_name", "부 성명", NAME),
        s("mother_relation", "모 관계", "literal:모", "center"),
        s("mother_name", "모 성명", NAME),
        s("mother_birth_date", "모 출생연월일", DATE_KR, "center"),
        s("mother_gender", "모 성별", "literal:여", "center"),
        s("mother_registration_base", "모 등록기준지", ADDRESS),
        s("mother_rrn", "모 주민등록번호", RRN, "center"),
        s("certificate_issue_date", "증명 발급일", DATE_KR, "center"),
        s("issuing_officer", "발급 책임관", "template:법원행정처 전산정보중앙관리소 전산운영책임관 {{person.name_ko}}", "center"),
        s("issue_time", "발급시각", "pattern:발급시각:##시##분", "center"),
        s("applicant_name", "신청인", "template:신청인: {{person.name_ko}}"),
        s("publication_number", "발행번호", "template:발행번호:{{pattern:####-####-####-####}}", "center"),
    ],
    "ID-02": [],
    "ID-03": [
        s("shareholder_list_date", "주주명부 기준일", "pool:id03_list_dates", "center"),
        s("shareholder_1_name", "주주 1 성명", "pool:id03_shareholder_names"),
        s("shareholder_1_share_count", "주주 1 소유주식수", "pool:id03_shareholder_share_counts", "right"),
        s("total_issued_shares", "총주식수", "pool:id03_total_issued_shares", "right"),
        s("par_value", "1주당 금액", "pool:id03_par_values", "right"),
        s("issue_date", "작성일", "pool:id03_issue_dates", "center"),
        s("company_name", "회사명", "pool:id03_company_names", "center"),
        s("company_address", "소재지", "pool:id03_company_addresses"),
        s("representative_name", "대표이사", "pool:id03_representative_names"),
        s("shareholder_list_date_suffix", "기준일 접미어", "literal:현재", "center"),
    ],
    "ID-04": [],
    "COL-01": [],
    "COL-03": [],
}


# Programmatic spec for ADM-04 estimate sheet; order follows review.json use-label order.
ADM04_HEADER_SPECS = [
    s("top_contact_line", "상단 담당자/연락처", "pool:adm04_top_contact_lines"),
    s("supplier_company_stamp_name", "공급자 상호 스탬프", "pool:adm04_supplier_company_stamp_names", "center"),
    s("recipient_title", "받으실 분", "pool:adm04_recipient_titles"),
    s("supplier_business_registration_number", "공급자 등록번호", "pool:adm04_supplier_business_registration_numbers", "center"),
    s("estimate_date_text", "견적일자", "pool:adm04_estimate_date_texts", "center"),
    s("supplier_company_name", "공급자 상호", "pool:adm04_supplier_company_names", "center"),
    s("payment_terms", "지불조건", "pool:adm04_payment_terms", "center"),
    s("supplier_representative_name", "대표자명", "pool:adm04_supplier_representative_names", "center"),
    s("delivery_period", "납품기간", "pool:adm04_delivery_periods"),
    s("supplier_address", "공급자 주소", "pool:adm04_supplier_addresses"),
    s("supplier_business_type_item", "업태/종목", "pool:adm04_supplier_business_type_items"),
    s("supplier_tel", "회사전화", "pool:adm04_supplier_tels", "center"),
    s("supplier_fax", "회사팩스", "pool:adm04_supplier_faxes", "center"),
    s("estimate_subject", "견적 제목", "pool:adm04_estimate_subjects"),
    s("estimate_total_text", "견적 합계 문구", "pool:adm04_estimate_total_texts"),
]
ADM04_LINE_SUFFIXES_FULL = [
    ("number", "번호", "numbers", "center"),
    ("item_name", "품목", "item_names", "left"),
    ("model", "모델", "models", "left"),
    ("unit", "단위", "units", "center"),
    ("quantity", "수량", "quantities", "center"),
    ("unit_price", "단가", "unit_prices", "right"),
    ("calibration_fee", "검교정", "calibration_fees", "right"),
    ("amount", "견적금액", "amounts", "right"),
]
ADM04_LINE_SUFFIXES_NOTE = [
    ("number", "번호", "numbers", "center"),
    ("item_name", "품목", "item_names", "left"),
    ("model", "모델", "models", "left"),
    ("unit", "단위", "units", "center"),
    ("quantity", "수량", "quantities", "center"),
    ("note", "비고", "notes", "left"),
]
ADM04_FOOTER_SPECS = [
    s("bank_account_kb", "국민은행 계좌", "pool:adm04_bank_account_kbs"),
    s("bank_account_holder", "예금주", "pool:adm04_bank_account_holders"),
    s("subtotal_amount", "소계", "pool:adm04_subtotal_amounts", "right"),
    s("bank_account_shinhan", "신한은행 계좌", "pool:adm04_bank_account_shinhans"),
    s("bank_account_woori", "우리은행 계좌", "pool:adm04_bank_account_wooris"),
    s("vat_amount", "부가세", "pool:adm04_vat_amounts", "right"),
    s("bank_account_enterprise_nonghyup", "기업/농협 계좌", "pool:adm04_bank_account_enterprise_nonghyups"),
    s("grand_total_amount", "합계", "pool:adm04_grand_total_amounts", "right"),
    s("company_description", "회사 설명", "pool:adm04_company_descriptions", "center"),
    s("homepage_url", "홈페이지", "pool:adm04_homepage_urls"),
    s("email_address", "이메일", "pool:adm04_email_addresses"),
    s("quote_validity_period", "견적유효기간", "pool:adm04_quote_validity_periods"),
    s("calibration_period", "검교정기간", "pool:adm04_calibration_periods"),
]
ADM04_SPECS = list(ADM04_HEADER_SPECS)
for _slot in range(1, 13):
    _suffixes = ADM04_LINE_SUFFIXES_NOTE if _slot in {2, 3} else ADM04_LINE_SUFFIXES_FULL
    for _suffix, _label, _pool_suffix, _align in _suffixes:
        ADM04_SPECS.append(s(f"line_{_slot}_{_suffix}", f"품목 {_slot} {_label}", f"pool:adm04_line_{_slot}_{_pool_suffix}", _align))
ADM04_SPECS.extend(ADM04_FOOTER_SPECS)
SPECS["ADM-04"] = ADM04_SPECS

# Programmatic specs for long register/resident/building documents.
SPECS["ID-02"] = [
    s("registry_serial_number", "등기부 일련번호", "pattern:######", "center"),
    s("corporate_registration_number", "법인등록번호", CORPNO, "center"),
    s("corporate_name", "상호", COMPANIES),
    s("head_office_address", "본점 소재지", ADDRESS),
    s("public_notice_line_1", "공고방법 1행", "template:당회사의 공고는 회사의 인터넷 홈페이지(www.{{company.name_ko}}.co.kr)에 한다."),
    s("public_notice_line_2", "공고방법 2행", "literal:다만 전산장애 또는 그 밖의 부득이한 사유로 회사의 인터넷 홈페이지에"),
    s("public_notice_line_3", "공고방법 3행", "literal:공고를 할 수 없을 때에는 서울특별시내에서 발행하는 일간"),
    s("public_notice_line_4", "공고방법 4행", "choice:한국경제신문에 게재한다|매일경제신문에 게재한다|서울경제신문에 게재한다"),
    s("par_value", "1주의 금액", "choice:금100원|금500원|금5,000원", "right"),
    s("authorized_shares", "발행할 주식의 총수", "choice:발행할주식의 총수2,000,000주|발행할주식의 총수1,000,000주", "right"),
    s("issued_shares_before", "발행주식수 변경전", "choice:512,112주|501,000주|532,597주", "right"),
    s("common_shares", "보통주식 수", "choice:501,000주|450,000주|300,000주", "right"),
    s("preferred_shares", "우선주식 수", "choice:11,112주|20,485주|32,000주", "right"),
    s("capital_amount", "자본금", MONEY, "right"),
    s("issued_shares_after", "변경 후 발행주식수", "choice:532,597주|600,000주|750,000주", "right"),
    s("change_registration_date", "변경일", "choice:2025.08.27변경|2024.06.21변경", "center"),
    s("common_shares_after", "변경 후 보통주식", "choice:501,000주|550,000주|700,000주", "right"),
    s("registration_date", "등기일", "choice:2025.09.05등기|2024.07.01등기", "center"),
    s("preferred_shares_after", "변경 후 우선주식", "choice:11,112주|20,485주|32,000주", "right"),
    s("other_shares", "기타 주식수", "choice:20,485 주|10,000 주|15,000 주", "right"),
    s("capital_increase_amount", "증가 자본금", MONEY, "right"),
] + [s(f"business_purpose_{i:02d}", f"사업목적 {i}", "choice:1.시스템 소프트웨어개발및 공급업|1.컴퓨터 시스템 통합 자문및구축서비스업|1.전문, 과학 및 기술 서비스업|1.전시 컨벤션 및 행사 대행업") for i in range(1, 13)] + [
    s("publication_number", "발행번호", "template:발행번호 {{pattern:################################****}}", "center"),
    s("verification_number", "발급확인번호", "pattern:발급확인번호 ####-AAAA-AAAA", "center"),
    s("registry_issue_date", "발행일", "choice:발행일2025/09/19|발행일2026/06/29", "center"),
    s("page_number", "페이지", "choice:1/8|2/8|1/3", "center"),
]

SPECS["ID-04"] = [
    s("document_confirmation_number", "문서확인번호", "template:문서확인번호:{{pattern:####-####-####-####}}", "center"),
    s("contact_phone", "전화번호", "template:전화:{{person.phone_kr}}", "center"),
    s("applicant_name", "신청인", "template:신청인:{{person.name_ko}}"),
    s("applicant_birth_date", "신청인 생년월일", "choice:(1997-08-04 )|(1989-01-31 )|(1970-06-28 )", "center"),
    s("certificate_issue_date", "발급일", DATE_KR, "center"),
    s("issuer", "발급기관", LOCAL_GOV, "center"),
    s("household_change_reason_1", "세대 변동사유 1", "choice:세대주변경|전입|거주지변경", "center"),
    s("household_head_name", "세대주 성명", NAME),
    s("household_head_name_hanja_open", "세대주 한자 괄호 시작", "literal:(", "center"),
    s("household_head_name_hanja_close", "세대주 한자 괄호 끝", "literal:)", "center"),
    s("household_change_date_1", "세대 변동일 1", DATE_ISO, "center"),
    s("address_line_1", "주소 1행", ADDRESS),
    s("address_change_date", "주소 변동일", DATE_ISO, "center"),
    s("address_line_2_building", "주소 2행 동", "choice:112동|101동|202동"),
    s("address_line_2_detail", "주소 2행 상세", "choice:2704호(고림동,힐스테이트용인 둔전역)|1607호(용산동5가, 파크타워)|505호(역삼동, 테헤란빌딩)"),
    s("address_change_reason", "주소 변동사유", "choice:행정구역변경|전입|세대주변경", "center"),
    s("member_1_name", "세대원 1 성명", NAME),
    s("member_1_hanja_open", "세대원 1 한자 괄호 시작", "literal:(", "center"),
    s("member_1_hanja_close", "세대원 1 한자 괄호 끝", "literal:)", "center"),
    s("member_1_change_date", "세대원 1 변동일", DATE_ISO, "center"),
    s("member_1_no", "세대원 1 번호", "literal:1", "center"),
    s("member_1_relation", "세대원 1 관계", "literal:본인", "center"),
    s("member_1_change_reason", "세대원 1 변동사유", "choice:세대주변경|전입", "center"),
    s("member_1_status", "세대원 1 등록상태", "literal:거주자", "center"),
    s("member_1_rrn", "세대원 1 주민등록번호", RRN, "center"),
    s("member_2_name", "세대원 2 성명", NAME),
    s("member_2_hanja_open", "세대원 2 한자 괄호 시작", "literal:(", "center"),
    s("member_2_hanja_close", "세대원 2 한자 괄호 끝", "literal:)", "center"),
    s("member_2_change_date", "세대원 2 변동일", DATE_ISO, "center"),
    s("member_2_relation", "세대원 2 관계", "literal:배우자", "center"),
    s("member_2_no", "세대원 2 번호", "literal:2", "center"),
    s("member_2_change_reason", "세대원 2 변동사유", "choice:세대주변경|전입", "center"),
    s("member_2_rrn", "세대원 2 주민등록번호", RRN, "center"),
    s("member_2_status", "세대원 2 등록상태", "literal:거주자", "center"),
    s("member_3_name", "세대원 3 성명", NAME),
    s("member_3_hanja_open", "세대원 3 한자 괄호 시작", "literal:(", "center"),
    s("member_3_hanja_close", "세대원 3 한자 괄호 끝", "literal:)", "center"),
    s("member_3_change_date", "세대원 3 변동일", DATE_ISO, "center"),
    s("member_3_no", "세대원 3 번호", "literal:3", "center"),
    s("member_3_relation", "세대원 3 관계", "literal:자녀", "center"),
    s("member_3_change_reason", "세대원 3 변동사유", "choice:세대주변경|전입", "center"),
    s("member_3_status", "세대원 3 등록상태", "literal:거주자", "center"),
    s("member_3_rrn", "세대원 3 주민등록번호", RRN, "center"),
    s("blank_line_marker", "이하여백", "literal:==이하여백==", "center"),
]

# Long real-estate register and building ledger specs: preserve row semantics while keeping 1-cycle manageable.
SPECS["COL-01"] = [s("unique_property_number", "부동산 고유번호", "template:고유번호 {{pattern:####-####-######}}", "center"), s("property_title", "부동산 표시 제목", "template:[건물] {{address.ko}} 르헤브빌딩")]
for i in range(1, 66):
    if i <= 29:
        label = f"표제부 항목 {i}"
        rule = "choice:서울특별시 서초구 반포동|르헤브빌딩|철골조,철근콘크리트조|제2종근린생활시설(학원)|114.11m²|5층|지1층 107.69m²"
    elif i <= 45:
        label = f"건물 표시 변경 항목 {i-29}"
        rule = "choice:2021년10월20일|서울특별시 서초구 반포동|709-7 르헤브빌딩|제2종근린생활시설(학원)|1층 59.17m2|2층 114.11m2|3층 114.11m2"
    else:
        label = f"갑구 권리사항 항목 {i-45}"
        rule = "choice:소유권보존|소유권이전|매매|소유자 김민준|소유자 주식회사엠케이컨텐츠|제230199호|서울특별시 강남구 도산대로70길 25"
    SPECS["COL-01"].append(s(f"real_estate_register_item_{i:02d}", label, rule, "center" if i in {1, 3, 4, 9, 20, 31, 48, 56, 66} else "left"))

# Narrow OCR boxes in the register template often represent row numbers,
# one-character marks, floor/page indicators, or tiny numeric cells rather than
# the long row text. Keep them synthetic but short enough to stay inside the
# captured bbox at the renderer's minimum font size.
COL01_NARROW_OVERRIDES: dict[str, Spec] = {
    "real_estate_register_item_01": s("real_estate_register_item_01", "표제부 순번 1", "choice:1|2|3", "center"),
    "real_estate_register_item_04": s("real_estate_register_item_04", "표제부 소형 기호 1", "choice:1|2|3", "center"),
    "real_estate_register_item_05": s("real_estate_register_item_05", "표제부 소형 기호 2", "choice:가|나|다", "center"),
    "real_estate_register_item_08": s("real_estate_register_item_08", "표제부 소형 텍스트", "choice:최고|등기|변경", "center"),
    "real_estate_register_item_10": s("real_estate_register_item_10", "표제부 층/기호", "choice:5층|4층|B1", "center"),
    "real_estate_register_item_12": s("real_estate_register_item_12", "표제부 순번 3", "choice:1|2|3", "center"),
    "real_estate_register_item_16": s("real_estate_register_item_16", "표제부 소형 기호 3", "choice:t|x|z", "center"),
    "real_estate_register_item_17": s("real_estate_register_item_17", "표제부 숫자", "choice:30|20|10", "center"),
    "real_estate_register_item_18": s("real_estate_register_item_18", "표제부 층수 2", "choice:2층|3층|4층", "center"),
    "real_estate_register_item_20": s("real_estate_register_item_20", "표제부 숫자 2", "choice:22|24|26", "center"),
    "real_estate_register_item_22": s("real_estate_register_item_22", "표제부 기호", "choice:X|O|-", "center"),
    "real_estate_register_item_24": s("real_estate_register_item_24", "표제부 층수", "choice:5층|4층|3층", "center"),
    "real_estate_register_item_25": s("real_estate_register_item_25", "표제부 숫자 3", "choice:40|30|20", "center"),
    "real_estate_register_item_28": s("real_estate_register_item_28", "표제부 층 기호 2", "choice:f1|f2|b1", "center"),
    "real_estate_register_item_29": s("real_estate_register_item_29", "표제부 순번 2", "choice:1|2|3", "center"),
    "real_estate_register_item_46": s("real_estate_register_item_46", "갑구 순번 1", "choice:1|2|3", "center"),
    "real_estate_register_item_54": s("real_estate_register_item_54", "갑구 순번 2", "choice:1|2|3", "center"),
    "real_estate_register_item_60": s("real_estate_register_item_60", "갑구 등기원인", "choice:매매|증여|상속", "center"),
    "real_estate_register_item_65": s("real_estate_register_item_65", "등기부 페이지", "choice:1/3|2/3|3/3", "center"),
}
SPECS["COL-01"] = [COL01_NARROW_OVERRIDES.get(spec[0], spec) for spec in SPECS["COL-01"]]

SPECS["COL-03"] = [
    s("document_confirmation_number", "문서확인번호", "template:문서확인번호:{{pattern:####-####-####-#####}}", "center"),
    s("print_date", "출력일자", "choice:2026/06/29|2025/09/19", "center"),
    s("print_time", "출력시각", "pattern:##:##:##", "center"),
    s("page_number", "페이지", "choice:(2쪽 중 제1쪽)|(1쪽 중 제1쪽)", "center"),
    s("building_management_number", "건축물관리번호", "pattern:##########-#-########", "center"),
    s("ledger_pk", "대장 고유번호", "pattern:################", "center"),
    s("building_name", "건물명", "choice:르헤브빌딩|테헤란빌딩|한빛타워"),
    s("household_summary", "호가구세대수", "choice:0호/0가구/0세대|12호/0가구/0세대", "center"),
    s("site_location", "대지위치", "choice:서울특별시서초구반포동|서울특별시강남구역삼동"),
    s("lot_number", "지번", "choice:709-7|123-45|30", "center"),
    s("road_address", "도로명주소", ADDRESS),
    s("site_area", "대지면적", "choice:220.2m²|537m2|122.44m2", "right"),
    s("building_area", "건축면적", "choice:537m2|429.31m²|194.96%", "right"),
    s("zoning", "지역지구", "choice:제2종일반주거지역 외1|상업지역|준주거지역"),
    s("restriction_zone", "제한구역", "choice:가축사육제한구역|상대보호구역|해당없음"),
]
for i in range(16, 56):
    label = f"건축물 현황 항목 {i-15}"
    if i in {16,17,21,22,23,29,38,46,51}:
        rule = "choice:55.6%|194.96%|14.5m|107.69|59.17|114.11"
        align = "right"
    elif i in {25,26,34,35,42,43,47,48}:
        rule = "choice:주1|지1층|1층|2층|3층|5층"
        align = "center"
    elif i in {31,32,39,40,41,52,53,54,55}:
        rule = "choice:주식회사엠케이컨텐츠|서울특별시용산구서빙고로 67,|2021.10.20.|소유권이전|발급일:2026년06월29일|담당자:오-케이민원센터|전화:02-2155-6306|서울특별시 서초구청장"
        align = "left"
    else:
        rule = "choice:철골조,철근콘크리트조|일반철골구조|제2종근린생활시설(학원)|제1종근린생활시설(소매점)|철골구조지붕"
        align = "left"
    SPECS["COL-03"].append(s(f"building_ledger_item_{i-15:02d}", label, rule, align))

COL03_NARROW_OVERRIDES: dict[str, Spec] = {
    "building_ledger_item_18": s("building_ledger_item_18", "건축물 현황 페이지 표기", "choice:1/1|1/2|2/2", "center"),
}
SPECS["COL-03"] = [COL03_NARROW_OVERRIDES.get(spec[0], spec) for spec in SPECS["COL-03"]]

MANUAL_SPECS: dict[str, list[ManualSpec]] = {
    "ID-11": [
        ms("writer_organization_name_top", "상단 작성인 기관명", "pool:id11_writer_organization_names", "left", [812, 524, 286, 30]),
        ms("writer_position_top", "상단 작성인 직책", "pool:id11_writer_positions", "left", [812, 557, 286, 30]),
        ms("writer_name_top", "상단 작성인 성명", "pool:id11_writer_names", "left", [812, 590, 246, 30]),
        ms("owner_path_25_percent_checkbox", "실소유자 확인 방법: 25% 이상 지분 소유자", "literal:✓", "center", [1005, 751, 54, 31]),
        ms("beneficial_owner_1_name_ko", "실소유자 1 국문 성명", "pool:id11_owner_1_names_ko", "left", [300, 1083, 185, 31]),
        ms("beneficial_owner_2_name_ko", "실소유자 2 국문 성명", "pool:id11_owner_2_names_ko", "left", [496, 1083, 214, 31]),
        ms("beneficial_owner_3_name_ko", "실소유자 3 국문 성명", "pool:id11_owner_3_names_ko", "left", [721, 1083, 204, 31]),
        ms("beneficial_owner_4_name_ko", "실소유자 4 국문 성명", "pool:id11_owner_4_names_ko", "left", [934, 1083, 179, 31]),
        ms("beneficial_owner_1_name_en", "실소유자 1 영문 성명", "pool:id11_owner_1_names_en", "left", [300, 1124, 185, 28]),
        ms("beneficial_owner_2_name_en", "실소유자 2 영문 성명", "pool:id11_owner_2_names_en", "left", [496, 1124, 214, 28]),
        ms("beneficial_owner_3_name_en", "실소유자 3 영문 성명", "pool:id11_owner_3_names_en", "left", [721, 1124, 204, 28]),
        ms("beneficial_owner_4_name_en", "실소유자 4 영문 성명", "pool:id11_owner_4_names_en", "left", [934, 1124, 179, 28]),
        ms("beneficial_owner_1_birth_date", "실소유자 1 생년월일", "pool:id11_owner_1_birth_dates", "center", [300, 1180, 185, 32]),
        ms("beneficial_owner_2_birth_date", "실소유자 2 생년월일", "pool:id11_owner_2_birth_dates", "center", [496, 1180, 214, 32]),
        ms("beneficial_owner_3_birth_date", "실소유자 3 생년월일", "pool:id11_owner_3_birth_dates", "center", [721, 1180, 204, 32]),
        ms("beneficial_owner_4_birth_date", "실소유자 4 생년월일", "pool:id11_owner_4_birth_dates", "center", [934, 1180, 179, 32]),
        ms("beneficial_owner_1_ownership_percent", "실소유자 1 지분율", "pool:id11_owner_1_ownership_percents", "right", [300, 1240, 176, 32]),
        ms("beneficial_owner_2_ownership_percent", "실소유자 2 지분율", "pool:id11_owner_2_ownership_percents", "right", [496, 1240, 204, 32]),
        ms("beneficial_owner_3_ownership_percent", "실소유자 3 지분율", "pool:id11_owner_3_ownership_percents", "right", [721, 1240, 195, 32]),
        ms("beneficial_owner_4_ownership_percent", "실소유자 4 지분율", "pool:id11_owner_4_ownership_percents", "right", [934, 1240, 169, 32]),
        ms("beneficial_owner_1_nationality", "실소유자 1 국적", "literal:대한민국", "center", [300, 1310, 185, 32]),
        ms("beneficial_owner_2_nationality", "실소유자 2 국적", "literal:대한민국", "center", [496, 1310, 214, 32]),
        ms("beneficial_owner_3_nationality", "실소유자 3 국적", "literal:대한민국", "center", [721, 1310, 204, 32]),
        ms("beneficial_owner_4_nationality", "실소유자 4 국적", "literal:대한민국", "center", [934, 1310, 179, 32]),
        ms("writer_organization_name_bottom", "하단 작성인 기관명", "pool:id11_writer_organization_names", "left", [502, 1397, 570, 30]),
        ms("writer_position_bottom", "하단 작성인 직책", "pool:id11_writer_positions", "left", [502, 1431, 570, 30]),
        ms("writer_name_bottom", "하단 작성인 성명", "pool:id11_writer_names", "left", [502, 1464, 530, 30]),
    ]
}





TRD02_MANUAL_SPECS = [
    ms("shipper_exporter_name", "Shipper/exporter name", "pool:trd02_shipper_exporter_names", "left", [40, 85, 160, 13], "ABC CORPORATION"),
    ms("packing_list_number_date", "Packing list number and date", "pool:trd02_packing_list_number_dates", "left", [346, 85, 210, 13], "ABCCI 2015-001 MAY 19, 2015"),
    ms("shipper_address_line1", "Shipper/exporter address line 1", "pool:trd02_shipper_address_line1s", "left", [40, 99, 230, 13], "120, SAMSUNG - DONG, GANGNAM - GU,"),
    ms("shipper_address_line2", "Shipper/exporter address line 2", "pool:trd02_shipper_address_line2s", "left", [39, 113, 150, 14], "SEOUL, SOUTH KOREA"),
    ms("shipper_tel", "Shipper telephone", "pool:trd02_shipper_tels", "left", [69, 128, 95, 13], "+82-2-000-0000"),
    ms("shipper_fax", "Shipper fax", "pool:trd02_shipper_faxs", "left", [188, 128, 95, 15], "+82-2-000-0000"),
    ms("buyer_importer_name", "Buyer/importer name", "pool:trd02_buyer_importer_names", "left", [39, 156, 160, 13], "DEF CORPORATION"),
    ms("buyer_address_line1", "Buyer/importer address line 1", "pool:trd02_buyer_address_line1s", "left", [38, 169, 140, 15], "110, FLOWER ROAD,"),
    ms("notify_party", "Notify party", "pool:trd02_notify_parties", "left", [349, 170, 180, 14], "SAME AS CONSIGNEE"),
    ms("buyer_address_line2", "Buyer/importer address line 2", "pool:trd02_buyer_address_line2s", "left", [37, 183, 140, 13], "NEW YORK, U.S.A"),
    ms("buyer_tel", "Buyer telephone", "pool:trd02_buyer_tels", "left", [68, 198, 110, 16], "+1-123-456789"),
    ms("consignee_name", "Consignee", "pool:trd02_consignee_names", "left", [39, 234, 120, 13], "SAME AS ABOVE"),
    ms("payment_delivery_1", "Terms/payment delivery line 1", "pool:trd02_payment_delivery_1s", "left", [349, 228, 190, 13], "1) FREIGHT COLLECT BY OCEAN"),
    ms("payment_delivery_2", "Terms/payment delivery line 2", "pool:trd02_payment_delivery_2s", "left", [348, 242, 205, 13], "2)H.S. CODE NO. : 1234-00-0000"),
    ms("payment_delivery_3", "Terms/payment delivery line 3", "pool:trd02_payment_delivery_3s", "left", [349, 256, 240, 13], "3) NO. OF BILL, OF LADING: ABC012345678"),
    ms("port_loading_city", "Port of loading city", "pool:trd02_port_loading_cities", "center", [69, 269, 60, 15], "BUSAN,"),
    ms("final_destination_city", "Final destination city", "pool:trd02_final_destination_cities", "center", [210, 269, 80, 15], "NEW YORK,"),
    ms("port_loading_country", "Port of loading country", "pool:trd02_port_loading_countries", "center", [52, 284, 95, 13], "SOUTH KOREA"),
    ms("final_destination_country", "Final destination country", "pool:trd02_final_destination_countries", "center", [223, 284, 55, 14], "U.S.A"),
    ms("carrier_vessel", "Carrier/vessel", "pool:trd02_carrier_vessels", "left", [32, 312, 135, 13], "HAPPY VESSEL V.50E"),
    ms("sailing_date", "Sailing on/about", "pool:trd02_sailing_dates", "center", [206, 311, 85, 14], "MAY 25, 2015"),
    ms("shipping_mark_buyer", "Shipping mark buyer", "pool:trd02_shipping_mark_buyers", "left", [37, 354, 85, 15], "DEF CORP."),
    ms("shipping_mark_destination", "Shipping mark destination", "pool:trd02_shipping_mark_destinations", "left", [37, 371, 80, 11], "NEW YORK"),
    ms("description_goods_header", "Goods/services header description", "pool:trd02_description_goods_headers", "left", [156, 371, 135, 10], "MOTORCYCLE GLOVES"),
    ms("shipping_mark_carton_range", "Shipping mark carton range", "pool:trd02_shipping_mark_carton_ranges", "left", [35, 383, 80, 14], "C/NO.1~2"),
    ms("shipping_mark_item_no", "Shipping mark item no", "pool:trd02_shipping_mark_item_nos", "left", [35, 397, 70, 14], "ITEM NO."),
    ms("box_1_title", "Box 1 title", "pool:trd02_box_1_titles", "left", [155, 426, 145, 14], "MOTORCYCLE GLOVES"),
    ms("box_1_net_weight", "Box 1 net weight", "pool:trd02_box_1_net_weights", "right", [525, 426, 45, 15], "420.000"),
    ms("box_1_gross_weight", "Box 1 gross weight", "pool:trd02_box_1_gross_weights", "right", [582, 426, 45, 15], "500.000"),
    ms("box_1_volume", "Box 1 volume", "pool:trd02_box_1_volumes", "right", [643, 427, 35, 14], "0.212"),
    ms("box_1_dimensions", "Box 1 dimensions", "pool:trd02_box_1_dimensionss", "center", [542, 441, 128, 13], "(1,200 X 420 X 420 MM)"),
    ms("box_1_item_code", "Box 1 item code", "pool:trd02_box_1_item_codes", "left", [155, 456, 70, 11], "(1) MG-001"),
    ms("box_1_quantity", "Box 1 quantity", "pool:trd02_box_1_quantities", "center", [230, 456, 80, 11], "X 1,000 PRS"),
    ms("box_1_carton_breakdown", "Box 1 carton breakdown", "pool:trd02_box_1_carton_breakdowns", "left", [330, 455, 130, 13], "(200 PRS X 5 CARTONS)"),
    ms("box_2_title", "Box 2 title", "pool:trd02_box_2_titles", "left", [156, 469, 145, 14], "MOTORCYCLE GLOVES"),
    ms("box_2_net_weight", "Box 2 net weight", "pool:trd02_box_2_net_weights", "right", [525, 469, 45, 14], "420.000"),
    ms("box_2_gross_weight", "Box 2 gross weight", "pool:trd02_box_2_gross_weights", "right", [583, 471, 45, 11], "500,000"),
    ms("box_2_volume", "Box 2 volume", "pool:trd02_box_2_volumes", "right", [642, 469, 35, 15], "0.212"),
    ms("box_2_dimensions", "Box 2 dimensions", "pool:trd02_box_2_dimensionss", "center", [543, 483, 128, 13], "(1,200 X 420 X 420 MM)"),
    ms("box_2_item_code", "Box 2 item code", "pool:trd02_box_2_item_codes", "left", [156, 498, 70, 11], "(1) MG-002"),
    ms("box_2_quantity", "Box 2 quantity", "pool:trd02_box_2_quantities", "center", [230, 498, 80, 11], "X 1.000 PRS"),
    ms("box_2_carton_breakdown", "Box 2 carton breakdown", "pool:trd02_box_2_carton_breakdowns", "left", [330, 497, 130, 13], "(200 PRS X 5 CARTONS )"),
    ms("total_trade_terms", "Total trade terms", "pool:trd02_total_trade_terms", "left", [200, 513, 150, 12], "FOB BUSAN, SOUTH KOREA"),
    ms("total_net_weight", "Total net weight", "pool:trd02_total_net_weights", "right", [526, 513, 45, 12], "840.000"),
    ms("total_gross_weight", "Total gross weight", "pool:trd02_total_gross_weights", "right", [579, 513, 50, 12], "1,000.000"),
    ms("total_volume", "Total volume", "pool:trd02_total_volumes", "right", [643, 512, 35, 14], "0.424"),
    ms("net_weight_unit", "Net weight unit", "pool:trd02_net_weight_units", "center", [531, 527, 26, 12], "KGS"),
    ms("gross_weight_unit", "Gross weight unit", "pool:trd02_gross_weight_units", "center", [588, 527, 26, 12], "KGS"),
    ms("volume_unit", "Volume unit", "pool:trd02_volume_units", "center", [644, 527, 25, 12], "KGS"),
    ms("package_summary", "Package summary", "pool:trd02_package_summaries", "center", [311, 555, 230, 12], "TWO (2) BOXES OF MOTORCYCLE GLOVES"),
    ms("say_package_only", "Say package only", "pool:trd02_say_package_onlies", "left", [154, 566, 180, 14], "*SAY: TWO (2) BOXES ONLY."),
    ms("container_seal_no", "Container and seal no", "pool:trd02_container_seal_nos", "left", [156, 581, 270, 12], "* CONTANER & SEAL NO. :ABCP1Z34567/EFB2IOOD"),
    ms("origin_country_statement", "Origin country statement", "pool:trd02_origin_country_statements", "left", [155, 594, 300, 16], "*ORIGIN OF COUNTRY: REFUBLIC OF KOREA (R. O.K)"),
    ms("footer_company_name", "Footer company name", "pool:trd02_footer_company_names", "center", [474, 741, 180, 21], "ABC CORPORATION"),
    ms("footer_tel", "Footer telephone", "pool:trd02_footer_tels", "left", [100, 765, 95, 14], "+ 82-2-000-0000"),
    ms("footer_fax", "Footer fax", "pool:trd02_footer_faxs", "left", [100, 781, 95, 14], "+82-2-000-0000"),
    ms("signed_by_name", "Signed by name and title", "pool:trd02_signed_by_names", "center", [471, 832, 210, 19], "K. D. HONG / MANAGING DIRECTOR"),
]
MANUAL_SPECS["TRD-02"] = TRD02_MANUAL_SPECS


TRD06_MANUAL_SPECS = [
    ms("exporter_name", "Exporter name", "pool:trd06_exporter_names", "left", [220, 206, 360, 20], "YesForm Co., Ltd."),
    ms("exporter_email", "Exporter e-mail", "pool:trd06_exporter_emails", "left", [754, 205, 265, 22], "export@yesform.co.kr"),
    ms("exporter_telephone", "Exporter telephone", "pool:trd06_exporter_telephones", "left", [218, 246, 180, 20], "+82-2-123-4567"),
    ms("exporter_fax", "Exporter fax", "pool:trd06_exporter_faxs", "left", [755, 246, 180, 20], "+82-2-123-4568"),
    ms("exporter_address", "Exporter address", "pool:trd06_exporter_addresss", "left", [221, 284, 430, 20], "123 Yes Street, Yes-gu, Yes, Republic of Korea"),
    ms("blanket_period_from", "Blanket period from", "pool:trd06_blanket_period_froms", "center", [168, 381, 118, 21], "____/__/__"),
    ms("blanket_period_to", "Blanket period to", "pool:trd06_blanket_period_tos", "center", [382, 380, 130, 24], "____/__/__"),
    ms("producer_name", "Producer name", "pool:trd06_producer_names", "left", [218, 489, 300, 19], "Yes Manufacturing Co."),
    ms("producer_email", "Producer e-mail", "pool:trd06_producer_emails", "left", [753, 488, 265, 21], "producer@yesmfg.co.kr"),
    ms("producer_telephone", "Producer telephone", "pool:trd06_producer_telephones", "left", [218, 527, 180, 20], "+82-32-456-7890"),
    ms("producer_fax", "Producer fax", "pool:trd06_producer_faxs", "left", [756, 529, 180, 17], "+82-32-456-7891"),
    ms("producer_address", "Producer address", "pool:trd06_producer_addresss", "left", [220, 569, 430, 17], "456 Yes Industrial Park, Yes, Republic of Korea"),
    ms("importer_name", "Importer name", "pool:trd06_importer_names", "left", [220, 663, 300, 20], "Nono Wholesale Inc."),
    ms("importer_email", "Importer e-mail", "pool:trd06_importer_emails", "left", [755, 664, 280, 17], "imports@nonowholesale.com"),
    ms("importer_telephone", "Importer telephone", "pool:trd06_importer_telephones", "left", [219, 704, 180, 17], "+1-213-987-6543"),
    ms("importer_fax", "Importer fax", "pool:trd06_importer_faxs", "left", [756, 704, 180, 17], "+1-213-987-6544"),
    ms("importer_address", "Importer address", "pool:trd06_importer_addresss", "left", [220, 741, 420, 20], "789 Trade Ave, Nono city, Nono, USA"),
]
for _slot, _y in [(1, 899), (2, 939), (3, 978)]:
    TRD06_MANUAL_SPECS.extend([
        ms(f"item_{_slot}_serial_no", f"Item {_slot} serial no", f"pool:trd06_item_{_slot}_serial_nos", "center", [96, _y, 60, 21], "0123"),
        ms(f"item_{_slot}_description", f"Item {_slot} description", f"pool:trd06_item_{_slot}_descriptions", "left", [184, _y - 1, 205, 23], "Plastic Office Supplies"),
        ms(f"item_{_slot}_quantity_unit", f"Item {_slot} quantity and unit", f"pool:trd06_item_{_slot}_quantity_units", "center", [399, _y - 2, 125, 26], "5,000 pcs"),
        ms(f"item_{_slot}_hs_no", f"Item {_slot} HS No.", f"pool:trd06_item_{_slot}_hs_nos", "center", [647, _y, 80, 20], "3926.90"),
        ms(f"item_{_slot}_preference_criterion", f"Item {_slot} preference criterion", f"pool:trd06_item_{_slot}_preference_criterions", "center", [770, _y, 135, 20], "CTC"),
        ms(f"item_{_slot}_country_of_origin", f"Item {_slot} country of origin", f"pool:trd06_item_{_slot}_country_of_origins", "center", [938, _y - 1, 165, 24], "Republic of Korea"),
    ])
TRD06_MANUAL_SPECS.extend([
    ms("certification_date", "Certification date", "pool:trd06_certification_dates", "center", [630, 1518, 150, 24], ""),
    ms("authorized_name", "Authorized name/signature", "pool:trd06_authorized_names", "center", [885, 1586, 150, 28], ""),
])
MANUAL_SPECS["TRD-06"] = TRD06_MANUAL_SPECS


TRD01_MANUAL_SPECS = [
    ms("invoice_number_date", "Invoice No. and date", "pool:trd01_invoice_number_dates", "left", [486, 130, 270, 21], "MK20211214, DEC 14. 2021"),
    ms("shipper_name", "Shipper/Seller name", "pool:trd01_shipper_names", "left", [62, 158, 255, 20], "MK GLOBAL CO., LTD."),
    ms("shipper_address", "Shipper/Seller address", "pool:trd01_shipper_addresses", "left", [62, 183, 320, 23], "HWASEONG-SI, GYEONGGI-DO,"),
    ms("shipper_country", "Shipper/Seller country", "pool:trd01_shipper_countries", "left", [63, 211, 230, 21], "REPUBLIC OF KOREA"),
    ms("lc_number_date", "L/C No. and date", "pool:trd01_lc_number_dates", "left", [485, 191, 330, 23], "M42JH912NS27501, DEC 16. 2021"),
    ms("buyer_reference", "Buyer(if other than consignee)", "pool:trd01_buyer_references", "left", [486, 289, 350, 21], "SAME AS CONSIGNEE"),
    ms("consignee_name", "Consignee name", "pool:trd01_consignee_names", "left", [63, 316, 300, 21], "GOSINARA CO., LTD."),
    ms("consignee_address_line1", "Consignee address line 1", "pool:trd01_consignee_address_line1s", "left", [63, 342, 330, 25], "14524 YUAN LAOSHAN QU,"),
    ms("consignee_address_line2", "Consignee address line 2", "pool:trd01_consignee_address_line2s", "left", [63, 371, 360, 23], "QINGDAO SHI, SHANDONG SHENG,"),
    ms("consignee_country", "Consignee country", "pool:trd01_consignee_countries", "left", [63, 398, 130, 21], "CHINA"),
    ms("country_of_origin", "Country of origin", "pool:trd01_country_of_origins", "left", [487, 477, 230, 21], "REPUBLIC OF KOREA"),
    ms("departure_date", "Departure date", "pool:trd01_departure_dates", "center", [80, 532, 150, 21], "DEC 16. 2021"),
    ms("vessel_flight", "Vessel/flight", "pool:trd01_vessel_flights", "center", [79, 608, 110, 24], "QCY123"),
    ms("loading_port", "From", "pool:trd01_loading_ports", "center", [266, 610, 175, 20], "INCHEON, KOREA"),
    ms("terms_of_delivery", "Terms of delivery", "pool:trd01_terms_of_deliveries", "left", [486, 609, 165, 20], "F.O.B INCHEON"),
    ms("payment_terms", "Terms of payment", "pool:trd01_payment_terms", "left", [486, 635, 160, 21], "L/C AT SIGHT"),
    ms("destination_port", "To", "pool:trd01_destination_ports", "left", [79, 658, 190, 26], "QINGDAO, CHINA"),
    ms("goods_description", "Goods description", "pool:trd01_goods_descriptions", "left", [355, 760, 170, 24], "GIRL'S SHIRTS"),
    ms("quantity", "Quantity", "pool:trd01_quantities", "center", [587, 762, 84, 21], "10,000 PC"),
    ms("unit_price", "Unit price", "pool:trd01_unit_prices", "center", [675, 762, 110, 21], "US$1.00/PC"),
    ms("amount", "Amount", "pool:trd01_amounts", "right", [800, 760, 91, 25], "US$10,000"),
    ms("shipping_mark_code", "Shipping marks code", "pool:trd01_shipping_mark_codes", "left", [62, 788, 95, 25], "CN-275"),
    ms("material_composition", "Material composition", "pool:trd01_material_compositions", "left", [230, 789, 360, 23], "(Cotton 40%, Nylon 30%, Rayon 30%)"),
    ms("shipping_mark_destination", "Shipping marks destination", "pool:trd01_shipping_mark_destinations", "left", [63, 816, 120, 24], "QINGDAO"),
    ms("lot_number", "Lot number", "pool:trd01_lot_numbers", "left", [61, 843, 120, 23], "LOT NO"),
    ms("carton_range", "Carton number range", "pool:trd01_carton_ranges", "left", [62, 870, 120, 24], "C/NO.1-25"),
    ms("origin_mark", "Origin mark", "pool:trd01_origin_marks", "left", [64, 899, 160, 20], "MADE IN KOREA"),
    ms("signed_by", "Signed by", "pool:trd01_signed_bies", "center", [682, 1196, 205, 42], ""),
]
MANUAL_SPECS["TRD-01"] = TRD01_MANUAL_SPECS


TRD05_MANUAL_SPECS = [
    ms("settlement_exchange_rate", "결재환율", "pool:trd05_settlement_exchange_rates", "center", [141, 115, 80, 23]),
    ms("usd_exchange_rate", "USD환율", "pool:trd05_usd_exchange_rates", "center", [316, 115, 89, 22]),
    ms("issue_number", "제출번호", "pool:trd05_issue_numbers", "left", [138, 148, 157, 24]),
    ms("customs_broker_office", "신고인 관세사무소", "pool:trd05_customs_broker_offices", "left", [208, 179, 141, 26]),
    ms("customs_broker_name", "신고인 관세사명", "pool:trd05_customs_broker_names", "center", [355, 178, 62, 25]),
    ms("declaration_number", "신고번호", "pool:trd05_declaration_numbers", "left", [471, 173, 179, 27]),
    ms("declaration_date", "신고일자", "pool:trd05_declaration_dates", "center", [739, 175, 103, 24]),
    ms("declaration_type_name", "신고구분", "pool:trd05_declaration_type_names", "center", [875, 176, 98, 21]),
    ms("exporter_name_top", "수출대행자명", "pool:trd05_exporter_name_tops", "left", [207, 213, 132, 26]),
    ms("exporter_trade_code_top", "수출대행자 통관고유부호", "pool:trd05_exporter_trade_code_tops", "left", [206, 239, 186, 27]),
    ms("exporter_category", "수출자구분", "pool:trd05_exporter_categories", "center", [581, 237, 22, 29]),
    ms("transaction_type", "거래구분", "pool:trd05_transaction_types", "center", [638, 230, 73, 21]),
    ms("export_type", "종류", "pool:trd05_export_types", "center", [803, 230, 71, 21]),
    ms("payment_method", "결제방법", "pool:trd05_payment_methods", "center", [938, 230, 104, 20]),
    ms("destination_code", "목적국 코드", "pool:trd05_destination_codes", "center", [636, 252, 60, 20]),
    ms("destination_country", "목적국명", "pool:trd05_destination_countries", "center", [636, 276, 60, 22]),
    ms("loading_port", "적재항", "pool:trd05_loading_ports", "center", [803, 276, 72, 22]),
    ms("carrier_name", "선박회사 항공사", "pool:trd05_carrier_names", "center", [938, 275, 71, 22]),
    ms("exporter_name", "수출화주명", "pool:trd05_exporter_names", "left", [208, 274, 128, 26]),
    ms("exporter_trade_code", "수출화주 통관고유부호", "pool:trd05_exporter_trade_codes", "left", [208, 305, 183, 25]),
    ms("exporter_address", "수출화주 주소", "pool:trd05_exporter_addresses", "left", [210, 335, 215, 26]),
    ms("exporter_representative_name", "대표자명", "pool:trd05_exporter_representative_names", "center", [208, 363, 59, 26]),
    ms("exporter_location_code", "수출화주 소재지", "pool:trd05_exporter_location_codes", "center", [566, 361, 36, 25]),
    ms("exporter_business_registration_number", "사업자등록번호", "pool:trd05_exporter_business_registration_numbers", "center", [208, 393, 113, 23]),
    ms("inspection_due_date", "검사희망일", "pool:trd05_inspection_due_dates", "center", [960, 354, 94, 26]),
    ms("transport_type", "운송형태", "pool:trd05_transport_types", "center", [721, 354, 64, 25]),
    ms("goods_location_code", "물품소재지 코드", "pool:trd05_goods_location_codes", "center", [763, 392, 34, 22]),
    ms("goods_location_address", "물품소재지 주소", "pool:trd05_goods_location_addresses", "left", [639, 413, 214, 20]),
    ms("manufacturer_name", "제조자명", "pool:trd05_manufacturer_names", "left", [208, 444, 128, 21]),
    ms("manufacturer_trade_code", "제조자 통관고유부호", "pool:trd05_manufacturer_trade_codes", "left", [208, 469, 184, 26]),
    ms("manufacture_place_code", "제조장소 코드", "pool:trd05_manufacture_place_codes", "center", [208, 498, 35, 25]),
    ms("industrial_zone_code", "산업단지부호", "pool:trd05_industrial_zone_codes", "center", [468, 495, 38, 27]),
    ms("buyer_name", "구매자명", "pool:trd05_buyer_names", "left", [209, 530, 106, 20]),
    ms("buyer_code", "구매자부호", "pool:trd05_buyer_codes", "left", [209, 554, 120, 22]),
    ms("refund_applicant_type", "환급신청인", "pool:trd05_refund_applicant_types", "center", [735, 532, 21, 21]),
    ms("refund_applicant_description", "간이환급", "pool:trd05_refund_applicant_descriptions", "center", [735, 553, 65, 22]),
    ms("item_count_text", "품목 총란수", "pool:trd05_item_count_texts", "center", [300, 583, 86, 20]),
    ms("goods_name", "품명", "pool:trd05_goods_names", "left", [171, 623, 165, 20]),
    ms("trade_goods_name", "거래품명", "pool:trd05_trade_goods_names", "left", [172, 645, 294, 22]),
    ms("model_specification", "모델규격", "pool:trd05_model_specifications", "left", [52, 713, 110, 21]),
    ms("item_quantity", "품목 수량", "pool:trd05_item_quantities", "center", [728, 710, 57, 27]),
    ms("unit_price_usd", "단가 USD", "pool:trd05_unit_price_usds", "right", [838, 711, 87, 25]),
    ms("amount_usd", "금액 USD", "pool:trd05_amount_usds", "right", [988, 711, 87, 24]),
    ms("hs_code", "세번부호", "pool:trd05_hs_codes", "center", [183, 900, 109, 21]),
    ms("net_weight", "순중량", "pool:trd05_net_weights", "center", [511, 898, 65, 24]),
    ms("empty_quantity_marker", "수량 공란표기", "pool:trd05_empty_quantity_markers", "center", [756, 897, 28, 29]),
    ms("reported_price_fob", "신고가격 FOB", "pool:trd05_reported_price_fobs", "right", [947, 908, 127, 44]),
    ms("export_goods_number", "수출품장부호", "pool:trd05_export_goods_numbers", "left", [190, 946, 101, 21]),
    ms("package_count_type", "포장갯수 종류", "pool:trd05_package_count_types", "center", [1026, 942, 52, 27]),
    ms("export_requirement_approval_number", "수출요건확인 번호", "pool:trd05_export_requirement_approval_numbers", "left", [229, 983, 164, 21]),
    ms("export_requirement_document_name", "발급서류명", "pool:trd05_export_requirement_document_names", "left", [223, 1007, 177, 21]),
    ms("total_gross_weight", "총중량", "pool:trd05_total_gross_weights", "center", [244, 1049, 63, 27]),
    ms("total_package_count", "총포장갯수", "pool:trd05_total_package_counts", "center", [582, 1046, 51, 27]),
    ms("total_reported_price_fob", "총신고가격 FOB", "pool:trd05_total_reported_price_fobs", "right", [982, 1035, 95, 44]),
    ms("freight_krw", "운임 원화", "pool:trd05_freight_krws", "right", [297, 1097, 84, 24]),
    ms("insurance_krw", "보험료 원화", "pool:trd05_insurance_krws", "right", [566, 1097, 67, 24]),
    ms("payment_amount_text", "결제금액", "pool:trd05_payment_amount_texts", "left", [803, 1096, 179, 21]),
    ms("container_flag", "컨테이너 여부", "pool:trd05_container_flags", "center", [1061, 1139, 18, 24]),
    ms("customs_chief_name", "신고수리 세관장", "pool:trd05_customs_chief_names", "center", [942, 1275, 89, 25]),
    ms("customs_officer_name", "관세사", "pool:trd05_customs_officer_names", "center", [959, 1308, 76, 30]),
    ms("period_start_date", "운송기간 시작", "literal:", "center", [116, 1424, 103, 24]),
    ms("period_end_date", "운송기간 종료", "literal:", "center", [265, 1424, 103, 26]),
    ms("loading_due_date", "적재의무기한", "pool:trd05_loading_due_dates", "center", [551, 1414, 97, 28]),
    ms("acceptance_date", "신고수리일자", "pool:trd05_acceptance_dates", "center", [975, 1411, 95, 24]),
]
MANUAL_SPECS["TRD-05"] = TRD05_MANUAL_SPECS


QC01_MANUAL_SPECS = [
    ms("sample_name_country", "시료명(생산국)", "pool:qc01_sample_name_countries", "left", [522, 469, 743, 57], "울트라 커플러(현장체결식철근커플러)(한국)"),
    ms("receipt_number", "접수번호", "pool:qc01_receipt_numbers", "center", [1566, 480, 230, 46], "230531-012"),
    ms("sampling_location", "시료채취 장소", "pool:qc01_sampling_locations", "left", [522, 530, 155, 51], "준성산업"),
    ms("receipt_date_text", "접수일자", "pool:qc01_receipt_date_texts", "center", [1566, 537, 250, 51], "2023.05. 31."),
    ms("intended_use", "성과 이용 목적", "pool:qc01_intended_uses", "left", [518, 586, 237, 55], "공급원승인용"),
    ms("sampling_date_text", "채취일", "pool:qc01_sampling_date_texts", "center", [1564, 595, 250, 54], "2023.05.30."),
    ms("project_name", "공사명", "pool:qc01_project_names", "left", [516, 651, 750, 50], "-"),
    ms("sampler_name", "채취자", "pool:qc01_sampler_names", "left", [1566, 656, 504, 53], "준성산업 품질관리자 박준우"),
    ms("ordering_client", "발주자", "pool:qc01_ordering_clients", "left", [516, 709, 750, 52], "-"),
    ms("observer_name", "참관자", "pool:qc01_observer_names", "left", [1566, 716, 430, 52], "-"),
    ms("contractor_name", "시공자", "pool:qc01_contractor_names", "left", [516, 769, 750, 51], "-"),
    ms("manufacturer_name", "생산자", "pool:qc01_manufacturer_names", "left", [1567, 776, 156, 51], "준성산업"),
    ms("requester_name", "의뢰인", "pool:qc01_requester_names", "left", [516, 825, 309, 56], "준성산업 박준우"),
    ms("inventory_quantity", "재고량", "pool:qc01_inventory_quantities", "left", [1566, 836, 250, 53], "-"),
    ms("national_critical_facility_status", "국가중요시설여부", "pool:qc01_national_critical_facility_statuses", "left", [515, 884, 234, 55], "해당사항없음"),
    ms("section_1_number", "결과 1 연번", "pool:qc01_section_1_numbers", "center", [153, 1410, 32, 42], "1"),
    ms("section_1_test_item_name", "결과 1 시험검사항목", "pool:qc01_section_1_test_item_names", "center", [268, 1403, 94, 56], "치수"),
    ms("section_1_inner_label", "결과 1 내경 라벨", "pool:qc01_section_1_inner_labels", "center", [463, 1329, 167, 58], "내경(D2)"),
    ms("section_1_outer_label", "결과 1 외경 라벨", "pool:qc01_section_1_outer_labels", "center", [465, 1406, 166, 53], "외경(D1)"),
    ms("section_1_length_label", "결과 1 길이 라벨", "pool:qc01_section_1_length_labels", "center", [463, 1475, 163, 63], "길이(L1)"),
    ms("section_1_test_method", "결과 1 시험검사방법", "pool:qc01_section_1_test_methods", "center", [705, 1406, 270, 54], "의뢰인제시방법"),
    ms("section_1_d19_inner_diameter", "D19 내경", "pool:qc01_section_1_d19_inner_diameters", "center", [1031, 1337, 143, 46], "22.3mm"),
    ms("section_1_d22_inner_diameter", "D22 내경", "pool:qc01_section_1_d22_inner_diameters", "center", [1229, 1341, 142, 45], "25.5mm"),
    ms("section_1_d25_inner_diameter", "D25 내경", "pool:qc01_section_1_d25_inner_diameters", "center", [1422, 1338, 149, 54], "28.7mm"),
    ms("section_1_d19_outer_diameter", "D19 외경", "pool:qc01_section_1_d19_outer_diameters", "center", [1031, 1412, 145, 50], "41.4mm"),
    ms("section_1_d22_outer_diameter", "D22 외경", "pool:qc01_section_1_d22_outer_diameters", "center", [1227, 1413, 144, 51], "47.7mm"),
    ms("section_1_d25_outer_diameter", "D25 외경", "pool:qc01_section_1_d25_outer_diameters", "center", [1422, 1415, 149, 52], "51.1mm"),
    ms("section_1_d19_length", "D19 길이", "pool:qc01_section_1_d19_lengths", "center", [1031, 1486, 143, 53], "63.4mm"),
    ms("section_1_d22_length", "D22 길이", "pool:qc01_section_1_d22_lengths", "center", [1226, 1488, 144, 54], "68.6mm"),
    ms("section_1_d25_length", "D25 길이", "pool:qc01_section_1_d25_lengths", "center", [1422, 1490, 147, 52], "74.9mm"),
    ms("section_1_responsible_qualification", "결과 1 책임기술인 자격", "pool:qc01_section_1_responsible_qualifications", "center", [1613, 1401, 238, 42], "건설재료시험기사"),
    ms("section_1_responsible_cert_number", "결과 1 책임기술인 자격번호", "pool:qc01_section_1_responsible_cert_numbers", "center", [1631, 1439, 203, 43], "062021411561"),
    ms("section_1_responsible_engineer_name", "결과 1 책임기술인 성명", "pool:qc01_section_1_responsible_engineer_names", "center", [1876, 1416, 89, 64], "곽재현"),
    ms("section_1_responsible_engineer_signature", "결과 1 책임기술인 서명", "pool:qc01_section_1_responsible_engineer_signatures", "center", [1965, 1401, 122, 83], "곽재현"),
    ms("section_1_examiner_name", "결과 1 시험검사자 성명", "pool:qc01_section_1_examiner_names", "center", [2109, 1418, 92, 64], "김현준"),
    ms("section_1_examiner_signature", "결과 1 시험검사자 서명", "pool:qc01_section_1_examiner_signatures", "center", [2204, 1407, 122, 77], "김현준"),
    ms("section_2_number", "결과 2 연번", "pool:qc01_section_2_numbers", "center", [146, 1841, 39, 46], "2"),
    ms("section_2_test_item_name", "결과 2 시험검사항목", "pool:qc01_section_2_test_item_names", "center", [263, 1831, 98, 64], "치수"),
    ms("section_2_inner_label", "결과 2 내경 라벨", "pool:qc01_section_2_inner_labels", "center", [457, 1759, 169, 63], "내경(D2)"),
    ms("section_2_outer_label", "결과 2 외경 라벨", "pool:qc01_section_2_outer_labels", "center", [459, 1835, 167, 60], "외경(D1)"),
    ms("section_2_length_label", "결과 2 길이 라벨", "pool:qc01_section_2_length_labels", "center", [463, 1914, 157, 53], "길이(L1)"),
    ms("section_2_test_method", "결과 2 시험검사방법", "pool:qc01_section_2_test_methods", "center", [699, 1837, 272, 58], "의뢰인제시방법"),
    ms("section_2_d29_inner_diameter", "D29 내경", "pool:qc01_section_2_d29_inner_diameters", "center", [1077, 1767, 143, 55], "32.6mm"),
    ms("section_2_d32_inner_diameter", "D32 내경", "pool:qc01_section_2_d32_inner_diameters", "center", [1370, 1769, 147, 55], "36.4mm"),
    ms("section_2_d29_outer_diameter", "D29 외경", "pool:qc01_section_2_d29_outer_diameters", "center", [1077, 1844, 143, 51], "58.2mm"),
    ms("section_2_d32_outer_diameter", "D32 외경", "pool:qc01_section_2_d32_outer_diameters", "center", [1370, 1846, 144, 54], "64.3mm"),
    ms("section_2_d29_length", "D29 길이", "pool:qc01_section_2_d29_lengths", "center", [1077, 1919, 141, 50], "83.6mm"),
    ms("section_2_d32_length", "D32 길이", "pool:qc01_section_2_d32_lengths", "center", [1369, 1923, 145, 50], "94.1mm"),
    ms("section_2_responsible_qualification", "결과 2 책임기술인 자격", "pool:qc01_section_2_responsible_qualifications", "center", [1609, 1834, 238, 42], "건설재료시험기사"),
    ms("section_2_responsible_cert_number", "결과 2 책임기술인 자격번호", "pool:qc01_section_2_responsible_cert_numbers", "center", [1627, 1870, 204, 43], "062021411561"),
    ms("section_2_responsible_engineer_name", "결과 2 책임기술인 성명", "pool:qc01_section_2_responsible_engineer_names", "center", [1864, 1846, 103, 62], "곽재현"),
    ms("section_2_responsible_engineer_signature", "결과 2 책임기술인 서명", "pool:qc01_section_2_responsible_engineer_signatures", "center", [1963, 1840, 129, 79], "곽재현"),
    ms("section_2_examiner_name", "결과 2 시험검사자 성명", "pool:qc01_section_2_examiner_names", "center", [2103, 1849, 96, 61], "김현준"),
    ms("section_2_examiner_signature", "결과 2 시험검사자 서명", "pool:qc01_section_2_examiner_signatures", "center", [2206, 1846, 122, 77], "김현준"),
    ms("issue_date_text", "발행일", "pool:qc01_issue_date_texts", "center", [1895, 2590, 379, 61], "2023년 06월 09일"),
    ms("representative_title_name", "대표자명", "pool:qc01_representative_title_names", "center", [1448, 2765, 418, 92], "대표 박동준"),
    ms("office_phone", "기관 전화번호", "pool:qc01_office_phones", "center", [343, 2914, 264, 48], "053-582-1070"),
    ms("office_fax", "기관 팩스번호", "pool:qc01_office_faxes", "center", [756, 2913, 273, 50], "053-582-1071"),
    ms("office_address", "기관 주소", "pool:qc01_office_addresses", "left", [265, 2971, 734, 59], "대구광역시 달성군 화원읍 비슬로530길 39"),
    ms("page_indicator", "페이지 표기", "pool:qc01_page_indicators", "center", [1031, 3359, 362, 55], "총2페이지중 1페이지"),
]
MANUAL_SPECS["QC-01"] = QC01_MANUAL_SPECS


QC02_MANUAL_SPECS = [
    ms("approval_owner_name", "담당 결재자", "pool:qc02_approval_owner_names", "center", [807, 122, 88, 32], "담당"),
    ms("approval_reviewer_name", "검토 결재자", "pool:qc02_approval_reviewer_names", "center", [896, 122, 88, 32], "검토"),
    ms("approval_manager_name", "승인 결재자", "pool:qc02_approval_manager_names", "center", [985, 122, 88, 32], "승인"),
    ms("supplier_company_name", "거래처", "pool:qc02_supplier_company_names", "left", [323, 272, 274, 42], "거래처"),
    ms("purchase_order_number", "발주번호", "pool:qc02_purchase_order_numbers", "center", [798, 272, 274, 42], "발주번호"),
    ms("purchase_order_year", "발주일자 연", "pool:qc02_purchase_order_years", "center", [323, 323, 34, 26], "발주 연"),
    ms("purchase_order_month", "발주일자 월", "pool:qc02_purchase_order_months", "center", [374, 323, 28, 26], "발주 월"),
    ms("purchase_order_day", "발주일자 일", "pool:qc02_purchase_order_days", "center", [426, 323, 28, 26], "발주 일"),
    ms("receiving_year", "입고일자 연", "pool:qc02_receiving_years", "center", [802, 323, 42, 26], "입고 연"),
    ms("receiving_month", "입고일자 월", "pool:qc02_receiving_months", "center", [854, 323, 28, 26], "입고 월"),
    ms("receiving_day", "입고일자 일", "pool:qc02_receiving_days", "center", [906, 323, 28, 26], "입고 일"),
    ms("inspection_manager_name", "검수담당자", "pool:qc02_inspection_manager_names", "left", [323, 361, 222, 43], "검수담당자"),
    ms("receiving_location", "입고장소", "pool:qc02_receiving_locations", "left", [798, 361, 274, 43], "입고장소"),
    ms("inspection_method", "검수방법", "pool:qc02_inspection_methods", "left", [323, 407, 748, 43], "검수방법"),
]
for _slot in range(1, 9):
    _y = 604 + (_slot - 1) * 45
    QC02_MANUAL_SPECS.extend([
        ms(f"line_{_slot}_number", f"검수 품목 {_slot} 번호", f"pool:qc02_line_{_slot}_numbers", "center", [116, _y, 83, 43], str(_slot)),
        ms(f"line_{_slot}_item_name", f"검수 품목 {_slot} 품명", f"pool:qc02_line_{_slot}_item_names", "left", [200, _y, 292, 43], "품명"),
        ms(f"line_{_slot}_specification", f"검수 품목 {_slot} 규격", f"pool:qc02_line_{_slot}_specifications", "left", [493, _y, 145, 43], "규격"),
        ms(f"line_{_slot}_received_quantity", f"검수 품목 {_slot} 수량", f"pool:qc02_line_{_slot}_received_quantities", "center", [639, _y, 103, 43], "수량"),
        ms(f"line_{_slot}_quality_result", f"검수 품목 {_slot} 품질결과", f"pool:qc02_line_{_slot}_quality_results", "center", [743, _y, 101, 43], "품질"),
        ms(f"line_{_slot}_other_result", f"검수 품목 {_slot} 기타결과", f"pool:qc02_line_{_slot}_other_results", "center", [845, _y, 101, 43], "기타"),
        ms(f"line_{_slot}_remark", f"검수 품목 {_slot} 비고", f"pool:qc02_line_{_slot}_remarks", "left", [947, _y, 127, 43], "비고"),
    ])
QC02_MANUAL_SPECS.extend([
    ms("inspector_opinion", "검수자 의견", "pool:qc02_inspector_opinions", "left", [200, 1415, 745, 130], "검수자 의견"),
    ms("department_head_confirmation", "부서장 확인", "pool:qc02_department_head_confirmations", "center", [947, 1415, 126, 130], "부서장 확인"),
])
MANUAL_SPECS["QC-02"] = QC02_MANUAL_SPECS


def base_value_type(rule: str) -> str:
    low = rule.lower()
    if rule in {NAME}: return "person.name_ko"
    if rule == RRN: return "person.rrn"
    if rule == PHONE: return "person.phone_kr"
    if rule == ADDRESS: return "address.ko"
    if rule == MONEY: return "money.krw"
    if rule == COMPANIES: return "company.name_ko"
    if "date.kr" in low or "년" in rule or "date" in low: return "date.kr"
    if "money.krw" in low or "원" in rule or "amount" in low: return "money.krw"
    if "address.ko" in low or "주소" in rule: return "address.ko"
    if "company.name_ko" in low or "주식회사" in rule or "회사" in rule: return "company.name_ko"
    if "person.rrn" in low or "rrn" in low: return "person.rrn"
    if "person.phone_kr" in low or "전화" in rule: return "person.phone_kr"
    if "person.name_ko" in low or "성명" in rule or "대표" in rule: return "person.name_ko"
    return "free_text.short"


def default_spec(doc_id: str, index: int, label: dict[str, Any]) -> Spec:
    text = str(label.get("text") or "").strip()
    field = re.sub(r"[^0-9a-zA-Z가-힣]+", "_", text).strip("_")[:24] or f"field_{index:03d}"
    return s(f"{doc_id.lower().replace('-', '_')}_{index:03d}_{field}", f"수동필드 {index:03d}", "free_text.short")


def profile_extras(doc_id: str) -> dict[str, Any]:
    if doc_id == "TRD-02":
        packing_profiles = trd02_packing_list_profiles()
        field_ids = [spec[0] for spec in MANUAL_SPECS["TRD-02"]]
        scalar_pools = {f"trd02_{field_id}s": [item[field_id] for item in packing_profiles] for field_id in field_ids}
        scalar_pools.update({
            "trd02_notify_parties": [item["notify_party"] for item in packing_profiles],
            "trd02_port_loading_cities": [item["port_loading_city"] for item in packing_profiles],
            "trd02_final_destination_cities": [item["final_destination_city"] for item in packing_profiles],
            "trd02_port_loading_countries": [item["port_loading_country"] for item in packing_profiles],
            "trd02_final_destination_countries": [item["final_destination_country"] for item in packing_profiles],
            "trd02_box_1_quantities": [item["box_1_quantity"] for item in packing_profiles],
            "trd02_box_2_quantities": [item["box_2_quantity"] for item in packing_profiles],
            "trd02_total_trade_terms": [item["total_trade_terms"] for item in packing_profiles],
            "trd02_package_summaries": [item["package_summary"] for item in packing_profiles],
            "trd02_say_package_onlies": [item["say_package_only"] for item in packing_profiles],
        })
        return {
            "data_pools": {"trd02_packing_list_profiles": packing_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "trd02_packing_list_profiles",
                    "targets": {field_id: field_id for field_id in field_ids},
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/포장명세서(Packing_List)__TRD-02/samples/original/포장명세서.jpg",
                    "note": "Packing List 원본 이미지의 shipper/exporter, buyer/importer, consignee, notify party, terms, port/destination, carrier, sailing date, shipping mark, 2개 box line, 중량/CBM 합계, container/seal, origin statement, signed by 영역을 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.trade.gov/export-solutions",
                    "note": "수출 문서와 해외 발송 업무 맥락 확인용. 포장명세서는 상업송장/선하증권과 함께 선적 물품, 포장 수량, 중량, 용적, 운송 정보를 대조하는 문서로 다룸.",
                },
                {
                    "source": "domain_reference",
                    "url": "https://www.trade.gov/commercial-invoice",
                    "note": "상업송장과 함께 수출 선적 문서에 등장하는 수출자, 수입자, 품목, 수량, 가격/운송 조건 맥락을 확인하고 packing list의 shipper/buyer/goods/terms 생성 정책에 반영함.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:TRD02_PACKING_LIST_PROFILES",
                    "note": "box별 quantity는 carton 수와 carton당 수량의 곱으로 만들고, net/gross/volume은 품목별 단위값과 수량/박스 수에서 계산한다. total_net/gross/volume은 box 1+box 2 합계와 일치한다.",
                },
            ],
        }
    if doc_id == "TRD-06":
        origin_profiles = trd06_certificate_origin_profiles()
        field_ids = [spec[0] for spec in MANUAL_SPECS["TRD-06"]]
        scalar_pools = {f"trd06_{field_id}s": [item[field_id] for item in origin_profiles] for field_id in field_ids}
        return {
            "data_pools": {"trd06_certificate_origin_profiles": origin_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "trd06_certificate_origin_profiles",
                    "targets": {field_id: field_id for field_id in field_ids},
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/원산지증명서(C_O)__TRD-06/samples/original/원산지증명서_page_001.jpg",
                    "note": "한미 FTA Certificate of Origin 원본 이미지의 Exporter, Blanket Period, Producer, Importer, Items eligible for proof of origin, Date, Authorized 영역을 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_site",
                    "url": "https://ustr.gov/trade-agreements/free-trade-agreements/korus-fta/final-text",
                    "note": "KORUS FTA 원문 중 원산지 규정과 원산지 증명 업무 맥락 확인용. 품목별 원산지 기준은 CTC/RVC/PE/WO 계열 값으로 제한하고 blanket period는 12개월 이내로 생성한다.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.cbp.gov/trade/free-trade-agreements/korea",
                    "note": "미국 CBP의 Korea Free Trade Agreement 수입·원산지 관련 업무 맥락 확인용. 수입자, 수출자, 생산자, HS 번호, 원산지 기준을 한 record 안에서 묶어 생성한다.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:TRD06_CERTIFICATE_ORIGIN_PROFILES",
                    "note": "blanket_period_to는 blanket_period_from 이후 330~359일로 두어 12개월을 넘지 않게 만들고, 각 품목 row의 description, quantity, HS No., preference criterion, country of origin을 하나의 profile record에서 선택한다.",
                },
            ],
        }
    if doc_id == "TRD-01":
        invoice_profiles = trd01_commercial_invoice_profiles()
        field_ids = [spec[0] for spec in MANUAL_SPECS["TRD-01"]]
        scalar_pools = {f"trd01_{field_id}s": [item[field_id] for item in invoice_profiles] for field_id in field_ids}
        scalar_pools.update({
            "trd01_shipper_addresses": [item["shipper_address"] for item in invoice_profiles],
            "trd01_shipper_countries": [item["shipper_country"] for item in invoice_profiles],
            "trd01_consignee_countries": [item["consignee_country"] for item in invoice_profiles],
            "trd01_terms_of_deliveries": [item["terms_of_delivery"] for item in invoice_profiles],
            "trd01_payment_terms": [item["payment_terms"] for item in invoice_profiles],
            "trd01_quantities": [item["quantity"] for item in invoice_profiles],
            "trd01_country_of_origins": [item["country_of_origin"] for item in invoice_profiles],
            "trd01_shipping_mark_destinations": [item["shipping_mark_destination"] for item in invoice_profiles],
            "trd01_signed_bies": [item["signed_by"] for item in invoice_profiles],
        })
        return {
            "data_pools": {"trd01_commercial_invoice_profiles": invoice_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "trd01_commercial_invoice_profiles",
                    "targets": {field_id: field_id for field_id in field_ids},
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/상업송장(Commercial_Invoice)__TRD-01/samples/original/상업송장.png",
                    "note": "상업송장 원본 이미지의 송장번호/일자, Shipper/Seller, Consignee, L/C, Buyer, 원산지, 출항일, 선박/항공편, 적재/도착항, 거래조건/결제조건, 품목·수량·단가·금액, Shipping Marks, 서명 영역을 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.trade.gov/commercial-invoice",
                    "note": "상업송장은 국제 거래에서 판매자, 구매자, 선적, 품목, 수량, 단가, 금액 등 핵심 거래 정보를 제시하는 문서라는 업무 맥락 확인용.",
                },
                {
                    "source": "official_site",
                    "url": "https://iccwbo.org/business-solutions/incoterms-rules/",
                    "note": "FOB/CIF/CFR/FCA/DAP 등 Incoterms 계열 거래조건을 faker profile의 terms_of_delivery 후보로 구성하기 위한 공식 ICC 맥락 확인용.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:TRD01_COMMERCIAL_INVOICE_PROFILES",
                    "note": "송장번호는 송장일 기반, L/C 일자는 송장일 이후, 출항일은 L/C 일자 이후로 생성한다. amount는 quantity*unit_price로 계산하고, 수출자/수입자/도착항/Shipping Mark를 하나의 record에서 함께 선택한다.",
                },
            ],
        }
    if doc_id == "TRD-05":
        export_profiles = trd05_export_declaration_profiles()
        field_ids = [spec[0] for spec in MANUAL_SPECS["TRD-05"]]
        scalar_pools = {f"trd05_{field_id}s": [item[field_id] for item in export_profiles] for field_id in field_ids}
        scalar_pools.update({
            "trd05_exporter_categories": [item["exporter_category"] for item in export_profiles],
            "trd05_destination_countries": [item["destination_country"] for item in export_profiles],
            "trd05_exporter_addresses": [item["exporter_address"] for item in export_profiles],
            "trd05_goods_location_addresses": [item["goods_location_address"] for item in export_profiles],
            "trd05_item_quantities": [item["item_quantity"] for item in export_profiles],
            "trd05_period_start_dates": ["" for _ in export_profiles],
            "trd05_period_end_dates": ["" for _ in export_profiles],
        })
        return {
            "data_pools": {"trd05_export_declaration_profiles": export_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "trd05_export_declaration_profiles",
                    "targets": {field_id: field_id for field_id in field_ids},
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/수출입신고필증__TRD-05/samples/original/수출신고필증.jpg",
                    "note": "수출신고필증 원본 이미지의 신고번호/신고일/수출자/구매자/목적국/적재항/품목/세번/중량/가격/운임/보험료/수리일자 영역을 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/관세법/제241조",
                    "note": "수출·수입 또는 반송 신고의 법적 맥락 확인용. 합성 profile은 신고번호, 신고일자, 수리일자, 적재의무기한, 품목 및 가격 정보를 하나의 record로 묶는다.",
                },
                {
                    "source": "official_site",
                    "url": "https://unipass.customs.go.kr/csp/index.do",
                    "note": "UNI-PASS 전자신고·수출신고서·수출신고필증 출력 업무 맥락 확인용.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:TRD05_EXPORT_DECLARATION_PROFILES",
                    "note": "신고번호는 신고일 기반으로 생성하고, 적재의무기한은 신고일+30일, 금액은 수량*단가, FOB 원화는 FOB USD*환율, 총중량은 순중량보다 크게 구성한다.",
                },
            ],
        }
    if doc_id == "QC-01":
        quality_profiles = qc01_quality_test_profiles()
        field_ids = [spec[0] for spec in MANUAL_SPECS["QC-01"]]
        scalar_pools = {f"qc01_{field_id}s": [item[field_id] for item in quality_profiles] for field_id in field_ids}
        scalar_pools.update({
            "qc01_sample_name_countries": [item["sample_name_country"] for item in quality_profiles],
            "qc01_inventory_quantities": [item["inventory_quantity"] for item in quality_profiles],
            "qc01_national_critical_facility_statuses": [item["national_critical_facility_status"] for item in quality_profiles],
            "qc01_office_faxes": [item["office_fax"] for item in quality_profiles],
            "qc01_office_addresses": [item["office_address"] for item in quality_profiles],
        })
        return {
            "data_pools": {"qc01_quality_test_profiles": quality_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "qc01_quality_test_profiles",
                    "targets": {field_id: field_id for field_id in field_ids},
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/품질·시험성적서__QC-01/samples/original/품질시험성적서.jpg",
                    "note": "품질검사 성적서 원본 이미지의 상단 접수/채취/의뢰 정보, 2개 시험결과 표, 발행일/대표/연락처/주소/페이지 표기를 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/건설기술%20진흥법%20시행규칙/제56조",
                    "note": "건설공사 품질시험·검사 결과 통보 및 성적서 업무 맥락 확인용. 합성 profile은 시료, 접수일, 채취일, 시험항목, 결과, 책임기술인/시험검사자 정보를 하나의 record로 묶는다.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.kicq.co.kr/",
                    "note": "원본 샘플 발행기관인 한국건설품질연구소의 시험·검사 기관 맥락 확인용.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:QC01_QUALITY_TEST_PROFILES",
                    "note": "접수일은 채취일 이후, 발행일은 접수일 이후가 되도록 생성하며, D19/D22/D25/D29/D32 치수 측정값은 규격별 기준 치수 주변의 mm 값으로 일관 생성한다.",
                },
            ],
        }
    if doc_id == "QC-02":
        inspection_profiles = qc02_inspection_profiles()
        scalar_pools: dict[str, list[str]] = {
            "qc02_approval_owner_names": [item["approval_owner_name"] for item in inspection_profiles],
            "qc02_approval_reviewer_names": [item["approval_reviewer_name"] for item in inspection_profiles],
            "qc02_approval_manager_names": [item["approval_manager_name"] for item in inspection_profiles],
            "qc02_supplier_company_names": [item["supplier_company_name"] for item in inspection_profiles],
            "qc02_purchase_order_numbers": [item["purchase_order_number"] for item in inspection_profiles],
            "qc02_purchase_order_dates": [item["purchase_order_date"] for item in inspection_profiles],
            "qc02_purchase_order_years": [item["purchase_order_year"] for item in inspection_profiles],
            "qc02_purchase_order_months": [item["purchase_order_month"] for item in inspection_profiles],
            "qc02_purchase_order_days": [item["purchase_order_day"] for item in inspection_profiles],
            "qc02_receiving_dates": [item["receiving_date"] for item in inspection_profiles],
            "qc02_receiving_years": [item["receiving_year"] for item in inspection_profiles],
            "qc02_receiving_months": [item["receiving_month"] for item in inspection_profiles],
            "qc02_receiving_days": [item["receiving_day"] for item in inspection_profiles],
            "qc02_inspection_manager_names": [item["inspection_manager_name"] for item in inspection_profiles],
            "qc02_receiving_locations": [item["receiving_location"] for item in inspection_profiles],
            "qc02_inspection_methods": [item["inspection_method"] for item in inspection_profiles],
            "qc02_inspector_opinions": [item["inspector_opinion"] for item in inspection_profiles],
            "qc02_department_head_confirmations": [item["department_head_confirmation"] for item in inspection_profiles],
        }
        targets = {
            "approval_owner_name": "approval_owner_name",
            "approval_reviewer_name": "approval_reviewer_name",
            "approval_manager_name": "approval_manager_name",
            "supplier_company_name": "supplier_company_name",
            "purchase_order_number": "purchase_order_number",
            "purchase_order_year": "purchase_order_year",
            "purchase_order_month": "purchase_order_month",
            "purchase_order_day": "purchase_order_day",
            "receiving_year": "receiving_year",
            "receiving_month": "receiving_month",
            "receiving_day": "receiving_day",
            "inspection_manager_name": "inspection_manager_name",
            "receiving_location": "receiving_location",
            "inspection_method": "inspection_method",
            "inspector_opinion": "inspector_opinion",
            "department_head_confirmation": "department_head_confirmation",
        }
        for slot in range(1, 9):
            for suffix, pool_suffix in [
                ("number", "numbers"),
                ("item_name", "item_names"),
                ("specification", "specifications"),
                ("received_quantity", "received_quantities"),
                ("quality_result", "quality_results"),
                ("other_result", "other_results"),
                ("remark", "remarks"),
            ]:
                field_id = f"line_{slot}_{suffix}"
                targets[field_id] = field_id
                scalar_pools[f"qc02_line_{slot}_{pool_suffix}"] = [item[field_id] for item in inspection_profiles]
        return {
            "data_pools": {"qc02_inspection_profiles": inspection_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "qc02_inspection_profiles",
                    "targets": targets,
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/입고·검수_보고서__QC-02/samples/original/검수보고서_page_001.jpg",
                    "note": "입고품 검수보고서 빈 양식의 결재란, 거래처/발주/입고/검수방법 영역, 검수내역 표 8개 행, 검수자 의견, 부서장 확인 영역을 수동 bbox로 정의함.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/국가를%20당사자로%20하는%20계약에%20관한%20법률%20시행령",
                    "note": "물품 납품 후 검사/검수 업무의 공식 계약관리 맥락 확인용. 실제 합성에서는 입고 수량, 품질 판정, 불량/격리 처리의 내부 정합성을 우선 적용.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.pps.go.kr/",
                    "note": "납품·검사·검수 및 조달 품질관리 업무 맥락 확인용 조달청 공식 사이트.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:QC02_INSPECTION_PROFILES",
                    "note": "품목별 입고수량, 합격/부분합격, 불량격리, 비고를 하나의 record에서 생성한다. defect_quantity가 0이면 합격/입고/정상입고, 0보다 크면 부분합격/불량격리/교환요청으로 묶는다.",
                },
            ],
        }
    if doc_id == "ADM-04":
        estimate_profiles = adm04_estimate_profiles()
        scalar_pools: dict[str, list[str]] = {
            "adm04_top_contact_lines": [item["top_contact_line"] for item in estimate_profiles],
            "adm04_supplier_company_stamp_names": [item["supplier_company_stamp_name"] for item in estimate_profiles],
            "adm04_recipient_titles": [item["recipient_title"] for item in estimate_profiles],
            "adm04_supplier_business_registration_numbers": [item["supplier_business_registration_number"] for item in estimate_profiles],
            "adm04_estimate_date_texts": [item["estimate_date_text"] for item in estimate_profiles],
            "adm04_supplier_company_names": [item["supplier_company_name"] for item in estimate_profiles],
            "adm04_payment_terms": [item["payment_terms"] for item in estimate_profiles],
            "adm04_supplier_representative_names": [item["supplier_representative_name"] for item in estimate_profiles],
            "adm04_delivery_periods": [item["delivery_period"] for item in estimate_profiles],
            "adm04_supplier_addresses": [item["supplier_address"] for item in estimate_profiles],
            "adm04_supplier_business_type_items": [item["supplier_business_type_item"] for item in estimate_profiles],
            "adm04_supplier_tels": [item["supplier_tel"] for item in estimate_profiles],
            "adm04_supplier_faxes": [item["supplier_fax"] for item in estimate_profiles],
            "adm04_estimate_subjects": [item["estimate_subject"] for item in estimate_profiles],
            "adm04_estimate_total_texts": [item["estimate_total_text"] for item in estimate_profiles],
            "adm04_bank_account_kbs": [item["bank_account_kb"] for item in estimate_profiles],
            "adm04_bank_account_holders": [item["bank_account_holder"] for item in estimate_profiles],
            "adm04_subtotal_amounts": [item["subtotal_amount"] for item in estimate_profiles],
            "adm04_bank_account_shinhans": [item["bank_account_shinhan"] for item in estimate_profiles],
            "adm04_bank_account_wooris": [item["bank_account_woori"] for item in estimate_profiles],
            "adm04_vat_amounts": [item["vat_amount"] for item in estimate_profiles],
            "adm04_bank_account_enterprise_nonghyups": [item["bank_account_enterprise_nonghyup"] for item in estimate_profiles],
            "adm04_grand_total_amounts": [item["grand_total_amount"] for item in estimate_profiles],
            "adm04_company_descriptions": [item["company_description"] for item in estimate_profiles],
            "adm04_homepage_urls": [item["homepage_url"] for item in estimate_profiles],
            "adm04_email_addresses": [item["email_address"] for item in estimate_profiles],
            "adm04_quote_validity_periods": [item["quote_validity_period"] for item in estimate_profiles],
            "adm04_calibration_periods": [item["calibration_period"] for item in estimate_profiles],
        }
        targets = {
            "top_contact_line": "top_contact_line",
            "supplier_company_stamp_name": "supplier_company_stamp_name",
            "recipient_title": "recipient_title",
            "supplier_business_registration_number": "supplier_business_registration_number",
            "estimate_date_text": "estimate_date_text",
            "supplier_company_name": "supplier_company_name",
            "payment_terms": "payment_terms",
            "supplier_representative_name": "supplier_representative_name",
            "delivery_period": "delivery_period",
            "supplier_address": "supplier_address",
            "supplier_business_type_item": "supplier_business_type_item",
            "supplier_tel": "supplier_tel",
            "supplier_fax": "supplier_fax",
            "estimate_subject": "estimate_subject",
            "estimate_total_text": "estimate_total_text",
            "bank_account_kb": "bank_account_kb",
            "bank_account_holder": "bank_account_holder",
            "subtotal_amount": "subtotal_amount",
            "bank_account_shinhan": "bank_account_shinhan",
            "bank_account_woori": "bank_account_woori",
            "vat_amount": "vat_amount",
            "bank_account_enterprise_nonghyup": "bank_account_enterprise_nonghyup",
            "grand_total_amount": "grand_total_amount",
            "company_description": "company_description",
            "homepage_url": "homepage_url",
            "email_address": "email_address",
            "quote_validity_period": "quote_validity_period",
            "calibration_period": "calibration_period",
        }
        for slot in range(1, 13):
            suffixes = [
                ("number", "numbers"),
                ("item_name", "item_names"),
                ("model", "models"),
                ("unit", "units"),
                ("quantity", "quantities"),
            ]
            if slot in {2, 3}:
                suffixes.append(("note", "notes"))
            else:
                suffixes.extend([
                    ("unit_price", "unit_prices"),
                    ("calibration_fee", "calibration_fees"),
                    ("amount", "amounts"),
                ])
            for suffix, pool_suffix in suffixes:
                field_id = f"line_{slot}_{suffix}"
                targets[field_id] = field_id
                scalar_pools[f"adm04_line_{slot}_{pool_suffix}"] = [item[field_id] for item in estimate_profiles]
        return {
            "data_pools": {"adm04_estimate_profiles": estimate_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "adm04_estimate_profiles",
                    "targets": targets,
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/산출내역서·견적서__ADM-04/samples/original/견적서_page_001.jpg",
                    "note": "전기제조 형식승인 법정장비 견적서 원본 이미지의 수신자, 견적일자, 지불/납품/유효/검교정기간, 공급자 정보, 품목 12행, 소계/부가세/합계를 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/부가가치세법/제32조",
                    "note": "견적서의 부가세 및 공급가액/세액 표기 맥락 확인. 산식은 품목별 금액 합계=소계, 소계*10%=부가세, 소계+부가세=합계로 구성.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.pps.go.kr/",
                    "note": "공공·제조 구매 업무에서 산출내역/견적 항목을 수량·단가·금액 중심으로 검토하는 조달 업무 맥락 확인용 조달청 공식 사이트.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:ADM04_ESTIMATE_PROFILES",
                    "note": "품목별 공급 단가와 검교정비를 합산한 금액을 만들고, 소계·VAT·합계를 같은 record 안에서 계산하여 선택하도록 구성.",
                },
            ],
        }
    if doc_id == "TRD-07":
        order_profiles = trd07_purchase_order_profiles()
        scalar_pools: dict[str, list[str]] = {
            "trd07_purchase_order_numbers": [item["purchase_order_number"] for item in order_profiles],
            "trd07_receiver_company_names": [item["receiver_company_name"] for item in order_profiles],
            "trd07_sender_company_names": [item["sender_company_name"] for item in order_profiles],
            "trd07_receiver_contact_titles": [item["receiver_contact_title"] for item in order_profiles],
            "trd07_sender_department_contacts": [item["sender_department_contact"] for item in order_profiles],
            "trd07_receiver_tels": [item["receiver_tel"] for item in order_profiles],
            "trd07_sender_tels": [item["sender_tel"] for item in order_profiles],
            "trd07_receiver_faxes": [item["receiver_fax"] for item in order_profiles],
            "trd07_sender_faxes": [item["sender_fax"] for item in order_profiles],
            "trd07_sender_emails": [item["sender_email"] for item in order_profiles],
            "trd07_receiver_addresses": [item["receiver_address"] for item in order_profiles],
            "trd07_sender_addresses": [item["sender_address"] for item in order_profiles],
            "trd07_prepared_dates": [item["prepared_date"] for item in order_profiles],
            "trd07_reviewed_dates": [item["reviewed_date"] for item in order_profiles],
            "trd07_approved_dates": [item["approved_date"] for item in order_profiles],
            "trd07_shipping_addresses": [item["shipping_address"] for item in order_profiles],
            "trd07_delivery_site_names": [item["delivery_site_name"] for item in order_profiles],
            "trd07_supply_total_amounts": [item["supply_total_amount"] for item in order_profiles],
            "trd07_form_codes": [item["form_code"] for item in order_profiles],
            "trd07_issuer_company_footers": [item["issuer_company_footer"] for item in order_profiles],
        }
        targets = {
            "purchase_order_number": "purchase_order_number",
            "receiver_company_name": "receiver_company_name",
            "sender_company_name": "sender_company_name",
            "receiver_contact_title": "receiver_contact_title",
            "sender_department_contact": "sender_department_contact",
            "receiver_tel": "receiver_tel",
            "sender_tel": "sender_tel",
            "receiver_fax": "receiver_fax",
            "sender_fax": "sender_fax",
            "sender_email": "sender_email",
            "receiver_address": "receiver_address",
            "sender_address": "sender_address",
            "prepared_date": "prepared_date",
            "reviewed_date": "reviewed_date",
            "approved_date": "approved_date",
            "shipping_address": "shipping_address",
            "delivery_site_name": "delivery_site_name",
            "supply_total_amount": "supply_total_amount",
            "form_code": "form_code",
            "issuer_company_footer": "issuer_company_footer",
        }
        for slot in range(1, 5):
            suffixes = [
                ("number", "numbers"),
                ("item_description", "item_descriptions"),
                ("quantity", "quantities"),
                ("unit_price", "unit_prices"),
                ("amount", "amounts"),
                ("due_date", "due_dates"),
            ]
            if slot == 2:
                suffixes.append(("remark", "remarks"))
            for suffix, pool_suffix in suffixes:
                field_id = f"line_{slot}_{suffix}"
                targets[field_id] = field_id
                scalar_pools[f"trd07_line_{slot}_{pool_suffix}"] = [item[field_id] for item in order_profiles]
        return {
            "data_pools": {"trd07_purchase_order_profiles": order_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "trd07_purchase_order_profiles",
                    "targets": targets,
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/발주서(PO)·거래명세서__TRD-07/samples/original/발주서_page_001.jpg",
                    "note": "가로형 A4 발주서 원본 이미지의 PO NO, 수신/발신 정보, 결재일, 품목 4행, 발송지, 공급가 합계를 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/부가가치세법/제32조",
                    "note": "발주서 자체는 회사 내부 구매문서이나, 원본 하단 조건에 세금계산서와 공급가/VAT 별도 표기가 있어 세금계산서 기재사항의 공급가액·부가가치세액 맥락을 확인함.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.nts.go.kr/",
                    "note": "세금계산서·전자세금계산서와 공급가액/세액 업무 맥락 확인용 국세청 공식 사이트.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:TRD07_PURCHASE_ORDER_PROFILES",
                    "note": "품목별 금액은 수량*단가, 공급가 합계는 4개 품목 금액 합계로 사전 계산하고, PO 번호/거래처/품목/금액/납기/발송지를 하나의 record로 묶어 선택함.",
                },
            ],
        }
    if doc_id == "SEC-01":
        fund_profiles = sec01_fund_profiles()
        return {
            "data_pools": {
                "sec01_fund_profiles": fund_profiles,
                "sec01_investment_risk_grade_labels": [item["investment_risk_grade_label"] for item in fund_profiles],
                "sec01_investment_risk_grades": sorted(set(item["investment_risk_grade"] for item in fund_profiles)),
                "sec01_fund_names": [item["fund_name"] for item in fund_profiles],
                "sec01_asset_manager_names": [item["asset_manager_name"] for item in fund_profiles],
                "sec01_disclosure_reference_texts": [item["disclosure_reference_text"] for item in fund_profiles],
                "sec01_prospectus_preparation_dates": [item["prospectus_preparation_date"] for item in fund_profiles],
                "sec01_effective_dates": [item["securities_registration_effective_date"] for item in fund_profiles],
                "sec01_offered_security_types": sorted(set(item["offered_security_type"] for item in fund_profiles)),
                "sec01_offering_total_amounts": [item["offering_total_amount"] for item in fund_profiles],
                "sec01_offering_period_descriptions": sorted(set(item["offering_period_description"] for item in fund_profiles)),
            },
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "sec01_fund_profiles",
                    "targets": {
                        "investment_risk_grade_label": "investment_risk_grade_label",
                        "investment_risk_grade": "investment_risk_grade",
                        "fund_name": "fund_name",
                        "asset_manager_name": "asset_manager_name",
                        "disclosure_reference_text": "disclosure_reference_text",
                        "prospectus_preparation_date": "prospectus_preparation_date",
                        "securities_registration_effective_date": "securities_registration_effective_date",
                        "offered_security_type": "offered_security_type",
                        "offering_total_amount": "offering_total_amount",
                        "offering_period_description": "offering_period_description",
                    },
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/투자설명서·증권신고서__SEC-01/samples/original/투자설명서_page_001.jpg",
                    "note": "67쪽 투자설명서 중 page 1 표지/요약 영역의 투자위험등급, 집합투자기구 명칭, 집합투자업자, 작성기준일, 효력발생일, 모집 증권 종류/총액/기간 bbox만 1-cycle 대상으로 정의함.",
                },
                {
                    "source": "official_disclosure_system",
                    "url": "https://dart.fss.or.kr/",
                    "note": "원본 하단 열람장소 안내에 전자문서 공시 경로로 금융감독원 DART가 표시되어 있어 투자설명서/증권신고서 공시 맥락 확인용으로 사용.",
                },
                {
                    "source": "official_association",
                    "url": "https://www.kofia.or.kr/",
                    "note": "원본 판매회사 참조 문구와 집합투자증권 관련 금융투자협회 열람/참조 맥락을 반영.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/자본시장과%20금융투자업에%20관한%20법률",
                    "note": "증권신고서/투자설명서의 법적 문서 유형 맥락 확인용. 이번 구현은 전체 67쪽이 아닌 표지 1쪽의 고정 bbox 주입에 한정.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:SEC01_FUND_PROFILES",
                    "note": "fund_name, asset_manager_name, manager URL, risk grade, 작성기준일, 효력발생일, 모집총액, 모집기간을 하나의 record에서 고르도록 구성해 문서 내부 정합성을 유지.",
                },
            ],
        }
    if doc_id == "ID-11":
        owner_profiles = id11_beneficial_owner_profiles()
        scalar_pools: dict[str, list[str]] = {
            "id11_writer_organization_names": [item["writer_organization_name_top"] for item in owner_profiles],
            "id11_writer_positions": [item["writer_position_top"] for item in owner_profiles],
            "id11_writer_names": [item["writer_name_top"] for item in owner_profiles],
        }
        targets = {
            "writer_organization_name_top": "writer_organization_name_top",
            "writer_position_top": "writer_position_top",
            "writer_name_top": "writer_name_top",
            "owner_path_25_percent_checkbox": "owner_path_25_percent_checkbox",
            "writer_organization_name_bottom": "writer_organization_name_bottom",
            "writer_position_bottom": "writer_position_bottom",
            "writer_name_bottom": "writer_name_bottom",
        }
        for slot in range(1, 5):
            for suffix, pool_suffix in [
                ("name_ko", "names_ko"),
                ("name_en", "names_en"),
                ("birth_date", "birth_dates"),
                ("ownership_percent", "ownership_percents"),
                ("nationality", "nationalities"),
            ]:
                field_id = f"beneficial_owner_{slot}_{suffix}"
                targets[field_id] = field_id
                scalar_pools[f"id11_owner_{slot}_{pool_suffix}"] = [item[field_id] for item in owner_profiles]
        return {
            "data_pools": {
                "id11_beneficial_owner_profiles": owner_profiles,
                **scalar_pools,
            },
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "id11_beneficial_owner_profiles",
                    "targets": targets,
                },
                {"type": "copy", "source": "writer_organization_name_top", "target": "writer_organization_name_bottom"},
                {"type": "copy", "source": "writer_position_top", "target": "writer_position_bottom"},
                {"type": "copy", "source": "writer_name_top", "target": "writer_name_bottom"},
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/실소유자_확인서(AML)__ID-11/samples/original/실소유자확인서_page_001.jpg",
                    "note": "미래에셋증권 실소유자확인서 page 1의 실제 소유자 확인 방법, 실소유자 최대 4명 작성사항, 작성인 정보 영역을 기준으로 수동 bbox schema를 정의함.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/특정%20금융거래정보의%20보고%20및%20이용%20등에%20관한%20법률%20시행령",
                    "note": "원본 문서에 표시된 특정 금융거래정보의 보고 및 이용 등에 관한 법률 시행령 제10조의5 실제 소유자 확인 맥락. 법인/단체의 실제 소유자 확인과 25% 이상 지분 보유자 판단 구조를 반영.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:ID11_BENEFICIAL_OWNER_PROFILES",
                    "note": "비대면 법인/단체 계좌개설용 양식이므로 외국인 포함 시 개설 불가 안내를 반영해 nationality는 대한민국으로 고정하고, 소유자 지분율은 한 record 안에서 합계 100%가 되도록 구성.",
                },
            ],
        }
    if doc_id == "CRD-02":
        credit_profiles = crd02_credit_profiles()
        return {
            "data_pools": {
                "crd02_credit_profiles": credit_profiles,
                "crd02_certificate_serial_numbers": [item["certificate_serial_number"] for item in credit_profiles],
                "crd02_issue_numbers": [item["issue_number"] for item in credit_profiles],
                "crd02_recipient_company_names": [item["recipient_company_name"] for item in credit_profiles],
                "crd02_evaluated_company_names": [item["evaluated_company_name"] for item in credit_profiles],
                "crd02_representative_names": [item["representative_name"] for item in credit_profiles],
                "crd02_corporate_registration_numbers": [item["corporate_registration_number"] for item in credit_profiles],
                "crd02_business_registration_numbers": [item["business_registration_number"] for item in credit_profiles],
                "crd02_headquarters_addresses": [item["headquarters_address"] for item in credit_profiles],
                "crd02_fiscal_year_ends": [item["fiscal_year_end"] for item in credit_profiles],
                "crd02_rating_evaluation_dates": [item["rating_evaluation_date"] for item in credit_profiles],
                "crd02_rating_valid_untils": [item["rating_valid_until"] for item in credit_profiles],
                "crd02_credit_ratings": CRD02_RATING_GRADES,
                "crd02_submission_purposes": CRD02_PURPOSES,
                "crd02_rating_descriptions": CRD02_RATING_DESCRIPTIONS,
            },
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "crd02_credit_profiles",
                    "targets": {
                        "certificate_serial_number": "certificate_serial_number",
                        "issue_number": "issue_number",
                        "recipient_company_name": "recipient_company_name",
                        "evaluated_company_name": "evaluated_company_name",
                        "representative_name": "representative_name",
                        "corporate_registration_number": "corporate_registration_number",
                        "business_registration_number": "business_registration_number",
                        "headquarters_address": "headquarters_address",
                        "fiscal_year_end": "fiscal_year_end",
                        "rating_evaluation_date": "rating_evaluation_date",
                        "rating_valid_until": "rating_valid_until",
                        "credit_rating": "credit_rating",
                        "rating_description_grade": "rating_description_grade",
                        "submission_purpose": "submission_purpose",
                    },
                },
                {"type": "copy", "source": "credit_rating", "target": "rating_description_grade"},
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/기업신용등급평가서__CRD-02/samples/original/기업신용평가서_page_001.jpg",
                    "note": "기업신용평가등급 확인서 원본 이미지의 일련번호, 교부번호, 기업체/대표자/등록번호/주소, 재무결산기준일, 등급평가일, 유효기한, 제출처 및 용도 구조를 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/신용정보의%20이용%20및%20보호에%20관한%20법률",
                    "note": "확인서 유의사항에 표시된 신용정보의 이용 및 보호에 관한 법률 맥락 확인. 기업신용등급은 기업이 제출한 자료와 평가회사 기준에 따라 평가된 값이며 지급보증 자체는 아님.",
                },
                {
                    "source": "domain_rule",
                    "url": "local:CRD02_RATING_GRADES",
                    "note": "기업신용평가 등급은 AAA부터 C/CC 계열까지의 등급 문자열을 사용하며, 확인서 본문 등급 설명에 등장하는 등급은 카드형 등급과 동일해야 하므로 copy constraint로 묶음.",
                },
            ],
        }
    if doc_id == "ID-01":
        registration_profiles = id01_registration_profiles()
        scalar_pools: dict[str, list[str]] = {
            "id01_business_registration_numbers": [item["business_registration_number"] for item in registration_profiles],
            "id01_corporate_names": [item["corporate_name"] for item in registration_profiles],
            "id01_representative_names": [item["representative_name"] for item in registration_profiles],
            "id01_opening_dates": [item["opening_date"] for item in registration_profiles],
            "id01_corporate_registration_numbers": [item["corporate_registration_number"] for item in registration_profiles],
            "id01_workplace_addresses": [item["workplace_address"] for item in registration_profiles],
            "id01_head_office_address_line1": [item["head_office_address_line1"] for item in registration_profiles],
            "id01_head_office_address_line2": [item["head_office_address_line2"] for item in registration_profiles],
            "id01_issue_reasons": [item["issue_reason"] for item in registration_profiles],
            "id01_issue_dates": [item["issue_date"] for item in registration_profiles],
            "id01_tax_office_chiefs": [item["tax_office_chief"] for item in registration_profiles],
        }
        for slot in range(1, 8):
            scalar_pools[f"id01_business_type_{slot}"] = [item[f"business_type_{slot}"] for item in registration_profiles]
        for slot in range(1, 7):
            scalar_pools[f"id01_business_item_{slot}"] = [item[f"business_item_{slot}"] for item in registration_profiles]
        targets = {
            "business_registration_number": "business_registration_number",
            "corporate_name": "corporate_name",
            "representative_name": "representative_name",
            "opening_date": "opening_date",
            "corporate_registration_number": "corporate_registration_number",
            "workplace_address": "workplace_address",
            "head_office_address_line1": "head_office_address_line1",
            "head_office_address_line2": "head_office_address_line2",
            "issue_reason": "issue_reason",
            "issue_date": "issue_date",
            "tax_office_chief": "tax_office_chief",
        }
        for slot in range(1, 8):
            targets[f"business_type_{slot}"] = f"business_type_{slot}"
        for slot in range(1, 7):
            targets[f"business_item_{slot}"] = f"business_item_{slot}"
        return {
            "data_pools": {"id01_registration_profiles": registration_profiles, **scalar_pools},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "id01_registration_profiles",
                    "targets": targets,
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/사업자등록증__ID-01/samples/original/15-4.jpg",
                    "note": "사업자등록증 원본 이미지의 등록번호, 법인명, 대표자, 개업연월일, 법인등록번호, 사업장/본점 소재지, 업태·종목, 발급사유, 발급일, 세무서장 구조를 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.hometax.go.kr/",
                    "note": "사업자등록증명·사업자등록 관련 민원/발급 맥락 확인용 홈택스 공식 사이트.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/부가가치세법%20시행령/제11조",
                    "note": "사업자등록 관련 신청·등록사항 맥락 확인용 국가법령정보센터 법령 페이지.",
                },
                {
                    "source": "official_site",
                    "url": "https://www.nts.go.kr/",
                    "note": "세무서장/국세청 발급기관 맥락 확인용 국세청 공식 사이트.",
                },
            ],
        }
    if doc_id == "ID-03":
        registry_profiles = id03_registry_profiles()
        return {
            "data_pools": {
                "id03_registry_profiles": registry_profiles,
                "id03_list_dates": [item["list_date"] for item in registry_profiles],
                "id03_shareholder_names": [item["shareholder_name"] for item in registry_profiles],
                "id03_shareholder_share_counts": [item["shareholder_share_count"] for item in registry_profiles],
                "id03_total_issued_shares": [item["total_issued_shares"] for item in registry_profiles],
                "id03_par_values": sorted(set(item["par_value"] for item in registry_profiles)),
                "id03_issue_dates": [item["issue_date"] for item in registry_profiles],
                "id03_company_names": [item["company_name"] for item in registry_profiles],
                "id03_company_addresses": [item["company_address"] for item in registry_profiles],
                "id03_representative_names": [item["representative_name"] for item in registry_profiles],
            },
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "id03_registry_profiles",
                    "targets": {
                        "shareholder_list_date": "list_date",
                        "shareholder_list_date_suffix": "list_date_suffix",
                        "shareholder_1_name": "shareholder_name",
                        "shareholder_1_share_count": "shareholder_share_count",
                        "total_issued_shares": "total_issued_shares",
                        "par_value": "par_value",
                        "issue_date": "issue_date",
                        "company_name": "company_name",
                        "company_address": "company_address",
                        "representative_name": "representative_name",
                    },
                }
            ],
            "source_notes": [
                {
                    "source": "source_image",
                    "url": "workbench/documents/주주명부__ID-03/samples/original/4_page_001.jpg",
                    "note": "재외공관 공증법 시행령 별지 제32호서식으로 표시된 주주명부 원본 이미지의 주주명, 소유주식수, 총주식수, 1주당 금액, 회사명, 소재지, 대표이사 구조를 기준으로 schema를 정의함.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/상법/제352조",
                    "note": "상법 제352조의 주주명부 기재사항 맥락 확인. 주주와 주식 수량을 핵심 관계로 둔다.",
                },
                {
                    "source": "official_law",
                    "url": "https://www.law.go.kr/법령/재외공관 공증법 시행령",
                    "note": "원본 상단에 표시된 재외공관 공증법 시행령 별지 서식 맥락 확인.",
                },
            ],
        }
    if doc_id != "FIN-01":
        return {}
    company_profiles = fin01_company_profiles()
    tax_office_profiles = fin01_tax_office_profiles()
    accounting_periods = fin01_accounting_periods()
    return {
        "data_pools": {
            "fin01_company_profiles": company_profiles,
            "fin01_company_names": [item["name"] for item in company_profiles],
            "fin01_business_types": sorted(set(item["business_type"] for item in company_profiles)),
            "fin01_business_items": sorted(set(item["business_item"] for item in company_profiles)),
            "fin01_accounting_periods": accounting_periods,
            "fin01_period_starts": [item["start"] for item in accounting_periods],
            "fin01_period_ends": [item["end"] for item in accounting_periods],
            "fin01_tax_office_profiles": tax_office_profiles,
            "fin01_tax_office_chiefs": [item["chief"] for item in tax_office_profiles],
            "fin01_tax_office_phones": [item["phone"] for item in tax_office_profiles],
            "fin01_service_counters": sorted(set(item["counter"] for item in tax_office_profiles)),
        },
        "constraints": [
            {
                "type": "pick_record",
                "pool": "fin01_company_profiles",
                "targets": {
                    "company_name": "name",
                    "business_registration_number": "biz_no",
                    "representative_name": "representative",
                    "corporate_registration_number_masked": "corp_no_masked",
                    "business_type": "business_type",
                    "business_item": "business_item",
                    "company_address": "address",
                },
            },
            {
                "type": "pick_record",
                "pool": "fin01_accounting_periods",
                "targets": {
                    "fiscal_period_start": "start",
                    "fiscal_period_end": "end",
                    "filing_type": "filing_type",
                    "filing_date": "filing_date",
                    "certificate_issue_date": "issue_date",
                },
            },
            {
                "type": "pick_record",
                "pool": "fin01_tax_office_profiles",
                "targets": {
                    "tax_office_chief": "chief",
                    "tax_office_phone": "phone",
                    "service_counter": "counter",
                },
            },
        ],
        "source_notes": [
            {
                "source": "source_image",
                "url": "workbench/documents/재무제표(재무상태표·손익계산서)__FIN-01/samples/original/표준재무제표증명원＿지엘-1_page_001.jpg",
                "note": "표준재무제표증명 페이지 1 원본 이미지의 발급번호, 사업자, 과세기간, 신고일, 접수번호, 세무서장, 연락처 필드 구조를 기준으로 schema를 정의함.",
            },
            {
                "source": "official_site",
                "url": "https://www.hometax.go.kr/",
                "note": "원본 문서 하단에 홈택스 발급/원본확인 안내가 표시되어 있어 국세청 홈택스 발급 문서로 간주.",
            },
            {
                "source": "official_site",
                "url": "https://www.nts.go.kr/",
                "note": "세무서장/세무서 연락처 계열 필드의 기관 맥락 확인용 국세청 공식 사이트.",
            },
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=payload, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def update_manifest(doc_dir: Path, artifacts: dict[str, Path]) -> None:
    path = doc_dir / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("artifacts", {})
    for key, value in artifacts.items():
        data["artifacts"][key] = str(value.relative_to(ROOT) if value.is_absolute() and value.is_relative_to(ROOT) else value)
    data["status"] = "authoring_done"
    data["updated_at"] = NOW
    write_json(path, data)


def pick_review_inpaint(doc_dir: Path) -> tuple[Path, Path] | None:
    inpaints = sorted(doc_dir.glob("inpaint/*/lama/inpainted_lama.png"))
    if not inpaints:
        return None
    inpaint = inpaints[-1]
    sample_key = inpaint.parents[1].name
    review = doc_dir / "review" / sample_key / "review.json"
    if not review.exists():
        reviews = sorted(doc_dir.glob("review/*/review.json"))
        if not reviews:
            return None
        review = reviews[-1]
    return review, inpaint


def build_doc(doc_dir: Path) -> dict[str, Any] | None:
    manifest = json.loads((doc_dir / "manifest.json").read_text(encoding="utf-8"))
    doc_id = manifest["doc_id"]
    title = manifest["title"]
    pair = pick_review_inpaint(doc_dir)
    if pair is None:
        return None
    review_path, inpaint_path = pair
    review = json.loads(review_path.read_text(encoding="utf-8"))
    manual_specs = MANUAL_SPECS.get(doc_id, [])
    labels = [item for item in review.get("labels", []) if item.get("status") == "use"]
    specs = SPECS.get(doc_id, [])
    if manual_specs:
        labels = [
            {
                "id": f"manual_{doc_id.lower().replace('-', '_')}_{index:03d}",
                "text": source_text,
                "bbox": bbox,
            }
            for index, (_field_id, _label, _rule, _align, bbox, source_text) in enumerate(manual_specs, start=1)
        ]
        specs = [(field_id, label, rule, align) for field_id, label, rule, align, _bbox, _source_text in manual_specs]
    if len(specs) != len(labels):
        print(f"WARN {doc_id}: specs={len(specs)} labels={len(labels)}; using fallback for missing/extra")
    fields = []
    style_classes = []
    generators = {}
    for i, label in enumerate(labels, 1):
        spec = specs[i - 1] if i - 1 < len(specs) else default_spec(doc_id, i, label)
        field_id, human_label, rule, align = spec
        bbox = [int(v) for v in label["bbox"]]
        font_size = max(10, int(round(bbox[3] * 0.72)))
        style_class = f"style_{field_id}"
        field = {
            "field_id": field_id,
            "label": human_label,
            "bbox": bbox,
            "bbox_format": "xywh",
            "source_detection_id": label.get("id"),
            "source_text": label.get("text", ""),
            "value_type": base_value_type(rule),
            "generator": rule,
            "style_class": style_class,
            "render_policy": {"align": align, "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
            "export": {"json_path": field_id.replace("_", "."), "csv_column": field_id},
            "required": True,
            "notes": "2026-07-02 수동 authoring: 원본/review/inpaint 시각 검수 기반으로 의미 key와 faker rule 지정",
        }
        fields.append(field)
        style_spec = {
            "style_class": style_class,
            "font_family": "default_korean",
            "font_path": default_font_path(),
            "font_size": font_size,
            "font_weight": "normal",
            "fill": [32, 32, 32],
            "opacity": 1.0,
            "align": align,
            "valign": "middle",
            "line_spacing": 1.0,
            "letter_spacing": 0,
            "baseline_shift": 0,
            "overflow": "shrink",
            "confidence": 0.55,
            "source_detection_ids": [label.get("id")],
        }
        if doc_id == "CRD-02" and field_id in {"credit_rating", "rating_description_grade"}:
            style_spec["fill"] = [0, 0, 128]
            if field_id == "credit_rating":
                style_spec["font_size"] = max(font_size, 64)
        if doc_id == "SEC-01":
            if field_id in {"investment_risk_grade_label", "investment_risk_grade"}:
                style_spec["fill"] = [0, 120, 0]
                style_spec["font_weight"] = "bold"
            if field_id == "offering_period_description":
                style_spec["valign"] = "top"
                style_spec["font_size"] = max(16, min(style_spec["font_size"], 28))
            if field_id == "disclosure_reference_text":
                style_spec["font_size"] = max(14, min(style_spec["font_size"], 26))
        if doc_id == "TRD-07":
            if field_id.endswith("_item_description") or field_id in {"shipping_address", "receiver_address", "sender_address"}:
                style_spec["font_size"] = max(12, min(style_spec["font_size"], 20))
            if field_id.endswith("_amount") or field_id.endswith("_unit_price") or field_id == "supply_total_amount":
                style_spec["font_size"] = max(14, min(style_spec["font_size"], 20))
            if field_id in {"purchase_order_number", "supply_total_amount"}:
                style_spec["font_weight"] = "bold"
        if doc_id == "TRD-02":
            style_spec["font_size"] = max(6, min(style_spec["font_size"], 9))
            if field_id in {"footer_company_name", "signed_by_name"}:
                style_spec["font_size"] = max(8, min(style_spec["font_size"], 13))
                style_spec["font_weight"] = "bold"
            if field_id.endswith("_weight") or field_id.endswith("_volume"):
                style_spec["font_size"] = max(6, min(style_spec["font_size"], 8))
            if field_id in {"container_seal_no", "origin_country_statement", "package_summary", "say_package_only", "payment_delivery_1", "payment_delivery_2", "payment_delivery_3"}:
                style_spec["font_size"] = max(6, min(style_spec["font_size"], 8))
        if doc_id == "TRD-06":
            style_spec["font_size"] = max(10, min(style_spec["font_size"], 17))
            if field_id.endswith("_address") or field_id.endswith("_email") or field_id.endswith("_description"):
                style_spec["font_size"] = max(9, min(style_spec["font_size"], 15))
            if field_id.startswith("item_"):
                style_spec["font_size"] = max(10, min(style_spec["font_size"], 16))
            if field_id in {"certification_date", "authorized_name"}:
                style_spec["font_size"] = max(12, min(style_spec["font_size"], 20))
                style_spec["font_weight"] = "bold"
        if doc_id == "TRD-01":
            style_spec["font_size"] = max(10, min(style_spec["font_size"], 17))
            if field_id in {"consignee_address_line1", "consignee_address_line2", "material_composition"}:
                style_spec["font_size"] = max(10, min(style_spec["font_size"], 15))
            if field_id in {"invoice_number_date", "lc_number_date", "terms_of_delivery", "payment_terms", "quantity", "unit_price", "amount"}:
                style_spec["font_size"] = max(10, min(style_spec["font_size"], 16))
            if field_id == "signed_by":
                style_spec["font_size"] = max(14, min(style_spec["font_size"], 24))
                style_spec["font_weight"] = "bold"
        if doc_id == "TRD-05":
            style_spec["font_size"] = max(8, min(style_spec["font_size"], 16))
            if field_id in {"goods_name", "trade_goods_name", "model_specification", "payment_amount_text", "export_requirement_approval_number", "export_requirement_document_name"}:
                style_spec["font_size"] = max(8, min(style_spec["font_size"], 14))
            if field_id in {"reported_price_fob", "total_reported_price_fob"}:
                style_spec["font_size"] = max(8, min(style_spec["font_size"], 13))
            if field_id.endswith("_address") or field_id == "goods_location_address":
                style_spec["font_size"] = max(8, min(style_spec["font_size"], 13))
            if field_id in {"period_start_date", "period_end_date"}:
                style_spec["font_size"] = max(8, min(style_spec["font_size"], 12))
        if doc_id == "QC-01":
            if field_id in {"sample_name_country", "sampler_name", "requester_name", "office_address"}:
                style_spec["font_size"] = max(18, min(style_spec["font_size"], 32))
            if field_id.startswith("section_"):
                style_spec["font_size"] = max(16, min(style_spec["font_size"], 28))
            if field_id.endswith("_signature"):
                style_spec["font_size"] = max(18, min(style_spec["font_size"], 34))
            if field_id in {"project_name", "ordering_client", "contractor_name", "observer_name", "inventory_quantity"}:
                style_spec["font_size"] = max(16, min(style_spec["font_size"], 26))
        if doc_id == "QC-02":
            if field_id in {"purchase_order_year", "purchase_order_month", "purchase_order_day", "receiving_year", "receiving_month", "receiving_day"}:
                style_spec["font_size"] = max(11, min(style_spec["font_size"], 15))
            if field_id.startswith("line_"):
                style_spec["font_size"] = max(11, min(style_spec["font_size"], 18))
            if field_id.endswith("_remark") or field_id in {"inspection_method", "inspector_opinion"}:
                style_spec["font_size"] = max(10, min(style_spec["font_size"], 16))
            if field_id in {"inspector_opinion", "department_head_confirmation"}:
                style_spec["valign"] = "top"
        style_classes.append(style_spec)
        generators[field_id] = rule
    authoring = doc_dir / "authoring"
    schema_path = authoring / "schema.json"
    stylesheet_path = authoring / "stylesheet.json"
    faker_path = authoring / "faker_profile.json"
    schema = {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": doc_id,
        "title": title,
        "source_review": str(review_path.resolve()),
        "source_image": str(Path(review.get("source_image", "")).resolve()) if review.get("source_image") else "",
        "source_inpainted": str(inpaint_path.resolve()),
        "image": {"width": review.get("image", {}).get("width"), "height": review.get("image", {}).get("height")},
        "fields": fields,
        "groups": [],
        "authoring_mode": "manual_20260702",
    }
    stylesheet = {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": doc_id,
        "source_image": schema["source_image"],
        "style_classes": style_classes,
        "notes": "font-size/font-family/font-weight는 사용자 최종 보정 대상. align/overflow는 수동 authoring에서 최소 동작값 지정.",
    }
    extras = profile_extras(doc_id)
    faker = {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": doc_id,
        "locale": "ko_KR",
        "field_generators": generators,
        "constraints": extras.get("constraints", []),
        "data_pools": extras.get("data_pools", []),
        "source_notes": extras.get("source_notes", []),
        "notes": "2026-07-02 수동 authoring. 기존 템플릿이 없는 값은 choice/literal/pattern/template 규칙으로 직접 구성.",
    }
    write_json(schema_path, schema)
    write_json(stylesheet_path, stylesheet)
    write_json(faker_path, faker)
    result = render_authoring_preview(schema_path, stylesheet_path, faker_path, out_dir=authoring / "render_preview", seed=1234)
    update_manifest(doc_dir, {
        "authoring": schema_path,
        "authoring_stylesheet": stylesheet_path,
        "authoring_faker_profile": faker_path,
        "authoring_preview": result.image,
        "authoring_overlay": result.overlay,
    })
    return {"doc_id": doc_id, "title": title, "fields": len(fields), "warnings": result.warning_count, "preview": str(result.image)}


def main() -> int:
    summaries=[]
    for doc_dir in sorted(WORKBENCH.glob("*")):
        if not doc_dir.is_dir() or doc_dir.name.startswith(".") or not (doc_dir / "manifest.json").exists():
            continue
        manifest = json.loads((doc_dir / "manifest.json").read_text(encoding="utf-8"))
        doc_id = manifest.get("doc_id", "")
        if doc_id not in FIRST_PRIORITY_DOC_IDS:
            print(f"SKIP {doc_id}: out of 2026-07-02 first-priority target scope")
            continue
        if not SPECS.get(doc_id) and not MANUAL_SPECS.get(doc_id):
            print(f"SKIP {doc_id}: manual authoring spec is not defined yet")
            continue
        summary = build_doc(doc_dir)
        if summary:
            summaries.append(summary)
            print(json.dumps(summary, ensure_ascii=False))
    write_json(ROOT / "outputs" / "manual_authoring_20260702_summary.json", {"generated_at": NOW, "documents": summaries})
    print(f"generated {len(summaries)} authoring bundles")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
