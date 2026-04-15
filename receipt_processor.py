import json
import re
import google.generativeai as genai
from PIL import Image
import io

OVERSEAS_PROMPT = """이것은 해외 경비 증빙 이미지입니다. 영수증/인보이스/카드결제내역 등 다양한 형식이 있을 수 있습니다.
다음 항목을 반드시 JSON 형식으로만 반환해 주세요 (```json 마크다운 없이 순수 JSON만):
{
  "store_name": "가게명/업체명 (영문 또는 현지어 그대로)",
  "date": "날짜 YYYY-MM-DD 형식",
  "category": "카테고리 (아래 목록 중 하나)",
  "currency": "통화 ISO 코드 (예: USD, EUR, JPY, CNY, VND)",
  "items": [
    {"name": "품목명", "quantity": 수량, "unit_price": 단가, "amount": 금액}
  ],
  "subtotal": 소계,
  "tax": 세금(없으면 0),
  "total": 합계
}

카테고리 분류 (반드시 이 중 하나):
- 식비: Meal, Restaurant, Cafe, F&B
- 교통비: Transport, Taxi, Uber, Metro, Train, Flight, Rental car
- 숙박비: Hotel, Accommodation, Airbnb
- 접대비: Entertainment (거래처 접대용)
- 소모품: Supplies, Office supplies, Stationery
- 운반비: Delivery, Shipping, Courier
- 수수료: Fee, Bank charges, Service charge
- 로밍: Roaming, Telecom
- 기타: 위 분류에 해당되지 않는 모든 것

규칙:
- 모든 금액은 **양수**(절댓값). total/subtotal은 숫자만 반환 (통화 기호 없이).
- currency는 화폐 기호(₩, $, €, ¥)로만 나와 있어도 ISO 코드로 변환 ($→USD, €→EUR, ¥→JPY, ₩→KRW).
- 판단 애매하면 category="기타".
- 반드시 JSON만 반환."""

PROMPT = """이것은 한국어 경비 증빙 이미지입니다. 일반 영수증일 수도 있고, 카드 결제/계좌이체/송금 내역 스크린샷일 수도 있습니다.
다음 항목을 반드시 JSON 형식으로만 반환해 주세요 (```json 마크다운 없이 순수 JSON만):
{
  "store_name": "가게명 또는 송금/이체 수취인명",
  "date": "날짜 YYYY-MM-DD 형식",
  "category": "카테고리 (아래 목록 중 하나)",
  "headcount": 인원수(영수증에 "N명", "N인", "N인분", "인원: N" 등이 인쇄/손글씨로 적혀있으면 숫자만. 없으면 null),
  "nights": 숙박일수(숙박 영수증에 "N박", "N일", "체크인/체크아웃"으로 계산 가능한 일수. 숙박 영수증이 아니면 null),
  "items": [
    {"name": "품목명", "quantity": 수량, "unit_price": 단가, "amount": 금액}
  ],
  "subtotal": 소계,
  "tax": 부가세(없으면 0),
  "total": 합계
}

카테고리 분류 (반드시 이 중 하나) — 상점명 매핑이 있으면 **품목과 무관하게 상점명 기준 우선**:

- 식비:
  - 식당(한식·양식·중식·일식·분식·치킨·피자·패스트푸드·뷔페 등)
  - 카페: 스타벅스, 이디야, 투썸, 메가커피, 공차, 컴포즈, 빽다방, 폴바셋 등
  - 편의점 **식품만**: GS25, CU, 세븐일레븐, 이마트24, 미니스톱 등 (편의점은 식품/음료만 식비, 생필품은 소모품)
  - 베이커리: 파리바게뜨, 뚜레쥬르, 성심당 등

- 유류비: 주유소 (자동차 주유) — GS칼텍스, SK에너지, 현대오일뱅크, S-OIL, 알뜰주유소 등

- 교통비: 택시, 버스, 지하철, KTX, SRT, 기차, 항공, 하이패스, 카카오T, 우버, 티머니

- 주차비: 주차장, 주차요금, 파킹, 주차타워

- 숙박비: 호텔, 모텔, 펜션, 리조트, 에어비앤비

- 접대비: **거래처 접대용**이 명확히 표기된 경우만 (영수증에 "거래처", "접대" 손글씨 표기 등)

- 소모품 — **잡화·생활·사무용품 전문점은 품목 무관하게 소모품**:
  - 잡화·생활용품: **다이소, 모던하우스, 이케아, 자주, 무인양품(MUJI), 플라잉타이거**
  - 사무용품: 알파문구, 모닝글로리, 교보핫트랙스, 오피스디포
  - 대형마트 생필품: 이마트, 홈플러스, 롯데마트, 코스트코 (단, 식품만 있으면 식비)
  - 문구, 건전지, 프린터 토너, 배터리, 케이블 등

- 운반비: 택배, 퀵서비스, 화물, 배송비, CJ대한통운, 한진택배, 우체국택배, 쿠팡배송

- 기타: 위 분류에 명확히 들지 않는 모든 것 (송금/이체 포함)

**분류 규칙 우선순위**:
1. 위에 명시된 **상점명이 일치하면 그 카테고리로 확정** (품목 무관)
2. 상점명 매칭 없으면 주요 품목 기반 판단
3. 애매하면 category="기타"

규칙:
- 모든 금액은 **양의 정수**로 반환하세요. '-20,000원'처럼 음수/마이너스 기호가 있어도 절댓값(20000)으로 기록합니다.
- 송금/이체 화면은 category="기타", items는 [{"name": "송금" 또는 "이체", "quantity": 1, "unit_price": 금액, "amount": 금액}] 한 줄로 채우세요.
- 판단이 애매하면 category="기타"로 하세요.
- 인식할 수 없는 항목은 null로 표시합니다.
- 반드시 JSON만 반환하고 다른 설명은 포함하지 마세요."""


class AllModelsFailedError(Exception):
    pass


class ReceiptProcessor:
    def __init__(self, config):
        self.config = config
        genai.configure(api_key=config.api_key)

    def process(self, image_bytes: bytes, tab: str = "domestic") -> dict:
        """이미지 bytes를 받아 인식 결과 dict를 반환한다."""
        image = Image.open(io.BytesIO(image_bytes))
        prompt = OVERSEAS_PROMPT if tab == "overseas" else PROMPT
        last_error = None

        for model_name in self.config.fallback_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    [prompt, image],
                    generation_config={"temperature": 0},
                )
                return self._parse_response(response.text)
            except AllModelsFailedError:
                raise
            except Exception as e:
                print(f"[{model_name}] 실패: {type(e).__name__}: {e}")
                last_error = e
                continue

        raise AllModelsFailedError(
            "AI 서비스 연결에 문제가 발생했습니다.\nAPI 키를 구매하신 담당자에게 문의해 주세요."
        )

    def _parse_response(self, text: str) -> dict:
        """응답 텍스트에서 JSON을 추출해 파싱한다."""
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()
        return json.loads(text)
