from __future__ import annotations

import random
from datetime import date, timedelta

KOREAN_LAST_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권"]
KOREAN_GIVEN_NAMES = [
    "민준", "서준", "도윤", "예준", "시우", "하준", "주원", "지호", "지후", "준우",
    "서연", "서윤", "지우", "서현", "민서", "하은", "하윤", "윤서", "지유", "지민",
]
CITIES = ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "세종특별자치시"]
DISTRICTS = ["중구", "서구", "동구", "남구", "북구", "강남구", "서초구", "마포구", "송파구", "영등포구"]
ROADS = ["중앙로", "테헤란로", "세종대로", "충무로", "을지로", "한강대로", "삼성로", "월드컵북로"]
BANKS = ["국민은행", "신한은행", "우리은행", "하나은행", "농협은행", "기업은행", "카카오뱅크"]
COMPANY_SUFFIXES = ["상사", "산업", "테크", "유통", "건설", "파트너스", "솔루션", "에프앤비"]
TEXT_SNIPPETS = ["샘플값", "예시값", "더미값", "테스트값"]


def generate_value(field_type: str, rng: random.Random, *, choices: list[str] | None = None, fmt: str | None = None) -> str:
    if choices:
        return rng.choice(choices)

    normalized = field_type.lower().replace("-", "_")
    if normalized in {"name", "person_name", "korean_name"}:
        return _name(rng)
    if normalized in {"amount", "money", "price"}:
        return _amount(rng)
    if normalized in {"date", "issue_date", "birth_date"}:
        return _date(rng, fmt or "%Y-%m-%d")
    if normalized in {"account", "account_no", "account_number"}:
        return _account(rng)
    if normalized in {"address", "road_address"}:
        return _address(rng)
    if normalized in {"bank", "bank_name"}:
        return rng.choice(BANKS)
    if normalized in {"business", "business_name", "company"}:
        return _company(rng)
    if normalized in {"business_reg_no", "business_number"}:
        return f"{rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10000, 99999)}"
    if normalized in {"resident_reg_no", "rrn"}:
        return f"{rng.randint(700101, 991231)}-{rng.randint(1000000, 4999999)}"
    if normalized in {"phone", "mobile"}:
        return f"010-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
    return rng.choice(TEXT_SNIPPETS)


def _name(rng: random.Random) -> str:
    return rng.choice(KOREAN_LAST_NAMES) + rng.choice(KOREAN_GIVEN_NAMES)


def _amount(rng: random.Random) -> str:
    return f"{rng.randrange(10_000, 9_999_000, 100):,}"


def _date(rng: random.Random, fmt: str) -> str:
    start = date(2020, 1, 1)
    value = start + timedelta(days=rng.randint(0, 365 * 8))
    return value.strftime(fmt)


def _account(rng: random.Random) -> str:
    return f"{rng.randint(100, 999)}-{rng.randint(100000, 999999)}-{rng.randint(10, 99)}-{rng.randint(100, 999)}"


def _address(rng: random.Random) -> str:
    return f"{rng.choice(CITIES)} {rng.choice(DISTRICTS)} {rng.choice(ROADS)} {rng.randint(1, 299)}"


def _company(rng: random.Random) -> str:
    return f"{rng.choice(['한빛', '대한', '미래', '우리', '새롬', '제일', '금강'])}{rng.choice(COMPANY_SUFFIXES)}"
