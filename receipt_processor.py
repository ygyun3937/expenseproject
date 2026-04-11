import json
import re
import google.generativeai as genai
from PIL import Image
import io

PROMPT = """이것은 한국어 영수증 이미지입니다.
다음 항목을 반드시 JSON 형식으로만 반환해 주세요 (```json 마크다운 없이 순수 JSON만):
{
  "store_name": "가게명",
  "date": "날짜 YYYY-MM-DD 형식",
  "items": [
    {"name": "품목명", "quantity": 수량, "unit_price": 단가, "amount": 금액}
  ],
  "subtotal": 소계,
  "tax": 부가세(없으면 0),
  "total": 합계
}
인식할 수 없는 항목은 null로 표시해 주세요.
반드시 JSON만 반환하고 다른 설명은 포함하지 마세요."""


class AllModelsFailedError(Exception):
    pass


class ReceiptProcessor:
    def __init__(self, config):
        self.config = config
        genai.configure(api_key=config.api_key)

    def _prepare_image(self, image_bytes: bytes):
        """이미지 bytes를 Gemini API에 전달할 형식으로 변환한다."""
        try:
            return Image.open(io.BytesIO(image_bytes))
        except Exception:
            # 유효하지 않은 이미지 포맷이면 inline data로 전달
            return {"mime_type": "image/jpeg", "data": image_bytes}

    def process(self, image_bytes: bytes) -> dict:
        """이미지 bytes를 받아 인식 결과 dict를 반환한다."""
        image = self._prepare_image(image_bytes)
        last_error = None

        for model_name in self.config.fallback_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([PROMPT, image])
                return self._parse_response(response.text)
            except AllModelsFailedError:
                raise
            except Exception as e:
                last_error = e
                continue

        raise AllModelsFailedError(
            f"AI 서비스 연결에 문제가 발생했습니다. API 키를 구매하신 담당자에게 문의해 주세요. (오류: {last_error})"
        )

    def _parse_response(self, text: str) -> dict:
        """응답 텍스트에서 JSON을 추출해 파싱한다."""
        # ```json ... ``` 마크다운 제거
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()
        return json.loads(text)
