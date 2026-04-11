# 영수증 경비정산서 자동화 시스템 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 영수증 이미지를 업로드하면 Gemini AI가 항목을 자동 인식하고, 검토 후 회사 양식으로 인쇄할 수 있는 Python Flask 로컬 웹 앱을 구축한다.

**Architecture:** Flask 로컬 서버가 이미지를 받아 Pillow로 전처리 후 Gemini 2.0 Flash API에 구조화 프롬프트로 전송, JSON 결과를 단일 HTML 페이지에 테이블로 표시한다. 사용자가 인라인 편집 후 인쇄 버튼을 누르면 브라우저 인쇄 기능으로 회사 양식 PDF를 출력한다. Gemini 모델 폴백 목록을 내장해 모델 deprecated 시 자동 대응한다.

**Tech Stack:** Python 3.10+, Flask, Pillow, google-generativeai, pytest, PyInstaller

---

## Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `tests/conftest.py`

- [ ] **Step 1: requirements.txt 작성**

```
flask==3.0.3
pillow==10.3.0
google-generativeai==0.7.2
python-dotenv==1.0.1
pytest==8.2.0
```

- [ ] **Step 2: .env.example 작성**

```
GEMINI_API_KEY=your-api-key-here
```

- [ ] **Step 3: tests/conftest.py 작성**

```python
# 공유 픽스처는 각 테스트 파일에 정의.
# 이 파일은 pytest가 tests/ 디렉토리를 패키지로 인식하게 한다.
```

- [ ] **Step 4: 의존성 설치**

```bash
pip install -r requirements.txt
```

Expected: 에러 없이 설치 완료

- [ ] **Step 5: 커밋**

```bash
git add requirements.txt .env.example tests/conftest.py
git commit -m "chore: project scaffolding"
```

---

## Task 2: Config 모듈

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_config.py
import os
import pytest
from unittest.mock import patch
from config import Config, ConfigError

def test_loads_api_key_from_env():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
        config = Config()
        assert config.api_key == "test-key-123"

def test_raises_when_api_key_missing():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
            Config()

def test_fallback_models_order():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        config = Config()
        assert config.fallback_models[0] == "gemini-2.0-flash"
        assert len(config.fallback_models) >= 2
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'config'"

- [ ] **Step 3: config.py 구현**

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

class ConfigError(Exception):
    pass

class Config:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ConfigError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.")
        self.api_key = api_key
        self.fallback_models = FALLBACK_MODELS
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_config.py -v
```

Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config module with model fallback list"
```

---

## Task 3: 이미지 전처리 모듈

**Files:**
- Create: `image_preprocessor.py`
- Create: `tests/test_image_preprocessor.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_image_preprocessor.py
import io
import pytest
from PIL import Image
from image_preprocessor import preprocess_image

def make_test_image(width=100, height=100, mode="RGB"):
    img = Image.new(mode, (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def test_returns_bytes():
    result = preprocess_image(make_test_image())
    assert isinstance(result, bytes)

def test_resizes_large_image():
    # 4000x3000 이미지 → 장변 2048px 이하로 축소
    large_image = make_test_image(4000, 3000)
    result = preprocess_image(large_image)
    img = Image.open(io.BytesIO(result))
    assert max(img.size) <= 2048

def test_small_image_not_upscaled():
    # 500x400 이미지는 그대로
    small_image = make_test_image(500, 400)
    result = preprocess_image(small_image)
    img = Image.open(io.BytesIO(result))
    assert img.size == (500, 400)

def test_converts_to_rgb():
    # RGBA 이미지도 RGB로 변환
    rgba_image = make_test_image(100, 100, mode="RGBA")
    result = preprocess_image(rgba_image)
    img = Image.open(io.BytesIO(result))
    assert img.mode == "RGB"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_image_preprocessor.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'image_preprocessor'"

- [ ] **Step 3: image_preprocessor.py 구현**

```python
# image_preprocessor.py
import io
from PIL import Image, ImageEnhance, ImageOps

MAX_SIZE = 2048

def preprocess_image(image_bytes: bytes) -> bytes:
    """
    영수증 이미지를 Gemini API 전송 전에 전처리한다.
    - EXIF 회전 정보 반영
    - 장변 2048px 이하로 리사이즈
    - RGBA → RGB 변환
    - 밝기/대비 자동 보정
    """
    img = Image.open(io.BytesIO(image_bytes))

    # EXIF 회전 반영 (스마트폰 사진 대응)
    img = ImageOps.exif_transpose(img)

    # RGBA, P 모드 → RGB 변환
    if img.mode != "RGB":
        img = img.convert("RGB")

    # 장변 기준 리사이즈
    w, h = img.size
    if max(w, h) > MAX_SIZE:
        ratio = MAX_SIZE / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # 밝기/대비 보정 (영수증은 보통 어둡거나 저대비)
    img = ImageEnhance.Brightness(img).enhance(1.1)
    img = ImageEnhance.Contrast(img).enhance(1.2)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_image_preprocessor.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add image_preprocessor.py tests/test_image_preprocessor.py
git commit -m "feat: image preprocessor with resize/rotation/brightness"
```

---

## Task 4: 영수증 인식 모듈 (Gemini API + 폴백)

**Files:**
- Create: `receipt_processor.py`
- Create: `tests/test_receipt_processor.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_receipt_processor.py
import pytest
from unittest.mock import MagicMock, patch, call
from receipt_processor import ReceiptProcessor, AllModelsFailedError

SAMPLE_JSON_RESPONSE = """
{
  "store_name": "스타벅스 강남점",
  "date": "2026-04-10",
  "items": [
    {"name": "아메리카노", "quantity": 2, "unit_price": 4500, "amount": 9000},
    {"name": "케이크", "quantity": 1, "unit_price": 6500, "amount": 6500}
  ],
  "subtotal": 15500,
  "tax": 1409,
  "total": 15500
}
"""

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.api_key = "test-key"
    config.fallback_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    return config

def test_parses_valid_response(mock_config):
    with patch("receipt_processor.genai") as mock_genai:
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = SAMPLE_JSON_RESPONSE
        mock_genai.GenerativeModel.return_value = mock_model

        processor = ReceiptProcessor(mock_config)
        result = processor.process(b"fake-image-bytes")

        assert result["store_name"] == "스타벅스 강남점"
        assert result["total"] == 15500
        assert len(result["items"]) == 2

def test_falls_back_to_next_model_on_failure(mock_config):
    with patch("receipt_processor.genai") as mock_genai:
        first_model = MagicMock()
        first_model.generate_content.side_effect = Exception("Model deprecated")
        second_model = MagicMock()
        second_model.generate_content.return_value.text = SAMPLE_JSON_RESPONSE
        mock_genai.GenerativeModel.side_effect = [first_model, second_model]

        processor = ReceiptProcessor(mock_config)
        result = processor.process(b"fake-image-bytes")

        assert result["store_name"] == "스타벅스 강남점"
        assert mock_genai.GenerativeModel.call_count == 2

def test_raises_when_all_models_fail(mock_config):
    with patch("receipt_processor.genai") as mock_genai:
        failing_model = MagicMock()
        failing_model.generate_content.side_effect = Exception("All failed")
        mock_genai.GenerativeModel.return_value = failing_model

        processor = ReceiptProcessor(mock_config)
        with pytest.raises(AllModelsFailedError):
            processor.process(b"fake-image-bytes")

def test_handles_json_wrapped_in_markdown(mock_config):
    wrapped = f"```json\n{SAMPLE_JSON_RESPONSE}\n```"
    with patch("receipt_processor.genai") as mock_genai:
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = wrapped
        mock_genai.GenerativeModel.return_value = mock_model

        processor = ReceiptProcessor(mock_config)
        result = processor.process(b"fake-image-bytes")
        assert result["store_name"] == "스타벅스 강남점"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_receipt_processor.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'receipt_processor'"

- [ ] **Step 3: receipt_processor.py 구현**

```python
# receipt_processor.py
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

    def process(self, image_bytes: bytes) -> dict:
        """이미지 bytes를 받아 인식 결과 dict를 반환한다."""
        image = Image.open(io.BytesIO(image_bytes))
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_receipt_processor.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add receipt_processor.py tests/test_receipt_processor.py
git commit -m "feat: receipt processor with Gemini fallback and JSON parsing"
```

---

## Task 5: Flask 서버

**Files:**
- Create: `app.py`

- [ ] **Step 1: 테스트 작성 (conftest.py 업데이트)**

```python
# tests/test_app.py
import io
import json
import pytest
from unittest.mock import patch, MagicMock
from app import create_app

@pytest.fixture
def client():
    app = create_app(testing=True)
    return app.test_client()

def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200

def test_process_requires_files(client):
    with patch("app.Config"):
        with patch("app.ReceiptProcessor"):
            response = client.post("/process", data={})
            assert response.status_code == 400
            data = json.loads(response.data)
            assert "error" in data

def test_process_returns_receipt_data(client):
    mock_result = {
        "store_name": "스타벅스",
        "date": "2026-04-10",
        "items": [{"name": "아메리카노", "quantity": 1, "unit_price": 4500, "amount": 4500}],
        "subtotal": 4500,
        "tax": 409,
        "total": 4500
    }
    with patch("app.Config"):
        with patch("app.ReceiptProcessor") as MockProcessor:
            with patch("app.preprocess_image", return_value=b"processed"):
                instance = MockProcessor.return_value
                instance.process.return_value = mock_result

                fake_file = (io.BytesIO(b"fake-image"), "receipt.jpg")
                response = client.post(
                    "/process",
                    data={"files": fake_file},
                    content_type="multipart/form-data"
                )
                assert response.status_code == 200
                results = json.loads(response.data)
                assert len(results) == 1
                assert results[0]["store_name"] == "스타벅스"

def test_process_returns_error_on_all_models_failed(client):
    from receipt_processor import AllModelsFailedError
    with patch("app.Config"):
        with patch("app.ReceiptProcessor") as MockProcessor:
            with patch("app.preprocess_image", return_value=b"processed"):
                instance = MockProcessor.return_value
                instance.process.side_effect = AllModelsFailedError("all failed")

                fake_file = (io.BytesIO(b"fake-image"), "receipt.jpg")
                response = client.post(
                    "/process",
                    data={"files": fake_file},
                    content_type="multipart/form-data"
                )
                assert response.status_code == 503
                data = json.loads(response.data)
                assert "error" in data
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_app.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app'"

- [ ] **Step 3: app.py 구현**

```python
# app.py
import os
import webbrowser
import threading
from flask import Flask, request, jsonify, render_template
from config import Config, ConfigError
from image_preprocessor import preprocess_image
from receipt_processor import ReceiptProcessor, AllModelsFailedError

def create_app(testing=False):
    app = Flask(__name__)
    app.config["TESTING"] = testing
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB 최대

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/process", methods=["POST"])
    def process():
        files = request.files.getlist("files")
        if not files or all(f.filename == "" for f in files):
            return jsonify({"error": "파일을 선택해 주세요."}), 400

        try:
            config = Config()
            processor = ReceiptProcessor(config)
        except ConfigError as e:
            return jsonify({"error": str(e)}), 500

        results = []

        for file in files:
            if file.filename == "":
                continue
            try:
                image_bytes = file.read()
                processed = preprocess_image(image_bytes)
                data = processor.process(processed)
                data["filename"] = file.filename
                results.append(data)
            except AllModelsFailedError as e:
                return jsonify({"error": str(e)}), 503
            except Exception as e:
                results.append({"filename": file.filename, "error": str(e)})

        return jsonify(results)

    return app


def open_browser(port):
    webbrowser.open(f"http://localhost:{port}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    threading.Timer(1.0, open_browser, args=[port]).start()
    app = create_app()
    app.run(host="127.0.0.1", port=port, debug=False)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_app.py -v
```

Expected: 4 passed

- [ ] **Step 5: 전체 테스트 실행**

```bash
pytest -v
```

Expected: 모든 테스트 통과

- [ ] **Step 6: 커밋**

```bash
git add app.py tests/test_app.py
git commit -m "feat: Flask server with process endpoint and browser auto-open"
```

---

## Task 6: 프론트엔드 (HTML/CSS/JS)

**Files:**
- Create: `templates/index.html`
- Create: `static/style.css`
- Create: `static/app.js`

- [ ] **Step 1: templates/index.html 작성**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>경비정산서 자동화</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div id="app" class="container">

    <!-- 헤더 (화면용, 인쇄 시 숨김) -->
    <header class="no-print">
      <h1>경비정산서 자동화</h1>
    </header>

    <!-- 업로드 영역 (인쇄 시 숨김) -->
    <section id="upload-section" class="no-print">
      <div id="drop-zone" class="drop-zone">
        <div class="drop-zone-icon">📎</div>
        <p>영수증 이미지를 여기에 드래그하거나<br><strong>클릭해서 선택</strong>하세요</p>
        <p class="hint">JPG, PNG, PDF 지원 · 여러 파일 동시 업로드 가능</p>
        <input type="file" id="file-input" accept="image/*,.pdf" multiple hidden>
      </div>
      <div id="status-message" class="status hidden"></div>
    </section>

    <!-- 결과 영역 -->
    <section id="result-section" class="hidden">

      <!-- 인쇄 헤더 (인쇄 시에만 표시) -->
      <div class="print-header print-only">
        <h2>경비정산서</h2>
        <div class="print-meta">
          <span>작성일: <span id="print-date"></span></span>
        </div>
      </div>

      <!-- 결과 테이블 -->
      <table id="result-table">
        <thead>
          <tr>
            <th>가게명</th>
            <th>날짜</th>
            <th>항목</th>
            <th>금액 (원)</th>
            <th class="no-print">삭제</th>
          </tr>
        </thead>
        <tbody id="result-body">
        </tbody>
        <tfoot>
          <tr>
            <td colspan="3" class="total-label">합계</td>
            <td id="total-amount" class="total-value">0</td>
            <td class="no-print"></td>
          </tr>
        </tfoot>
      </table>

      <!-- 행 추가 / 인쇄 버튼 (인쇄 시 숨김) -->
      <div class="actions no-print">
        <button id="add-row-btn" class="btn-secondary">+ 행 추가</button>
        <button id="reset-btn" class="btn-secondary">초기화</button>
        <button id="print-btn" class="btn-primary">🖨️ 정산서 인쇄</button>
      </div>
    </section>

  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: static/style.css 작성**

```css
/* ===== 기본 ===== */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
  background: #f5f6fa;
  color: #2d3436;
}

.container {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px;
}

header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 24px;
  color: #2d3436;
}

/* ===== 업로드 ===== */
.drop-zone {
  border: 2px dashed #b2bec3;
  border-radius: 12px;
  padding: 48px 24px;
  text-align: center;
  background: white;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.drop-zone:hover, .drop-zone.drag-over {
  border-color: #0984e3;
  background: #f0f8ff;
}

.drop-zone-icon { font-size: 2.5rem; margin-bottom: 12px; }
.drop-zone p { color: #636e72; line-height: 1.6; }
.drop-zone .hint { font-size: 0.85rem; margin-top: 8px; color: #b2bec3; }

/* ===== 상태 메시지 ===== */
.status {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.9rem;
}
.status.loading { background: #dfe6e9; color: #2d3436; }
.status.error   { background: #ffeaa7; color: #d35400; border: 1px solid #fdcb6e; }
.hidden { display: none !important; }

/* ===== 테이블 ===== */
#result-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  margin-top: 20px;
}

#result-table th {
  background: #0984e3;
  color: white;
  padding: 12px 10px;
  text-align: left;
  font-size: 0.9rem;
}

#result-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 0.9rem;
}

#result-table td input {
  border: 1px solid transparent;
  padding: 4px 6px;
  width: 100%;
  border-radius: 4px;
  font-family: inherit;
  font-size: 0.9rem;
  background: transparent;
}

#result-table td input:focus {
  border-color: #0984e3;
  outline: none;
  background: white;
}

.delete-btn {
  background: #ff7675;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 3px 8px;
  cursor: pointer;
  font-size: 0.8rem;
}

.total-label { text-align: right; font-weight: 600; padding-right: 16px; }
.total-value { font-weight: 700; font-size: 1.05rem; color: #0984e3; }

/* ===== 버튼 ===== */
.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
}

.btn-primary {
  background: #0984e3;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 10px 24px;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-primary:hover { background: #0773c5; }

.btn-secondary {
  background: white;
  color: #2d3436;
  border: 1px solid #dfe6e9;
  border-radius: 8px;
  padding: 10px 18px;
  font-size: 0.9rem;
  cursor: pointer;
}
.btn-secondary:hover { background: #f5f6fa; }

/* ===== 인쇄 ===== */
.print-only { display: none; }

@media print {
  body { background: white; }
  .no-print { display: none !important; }
  .print-only { display: block !important; }

  .print-header {
    text-align: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 2px solid #2d3436;
  }

  .print-header h2 { font-size: 1.8rem; margin-bottom: 8px; }
  .print-meta { font-size: 0.9rem; color: #636e72; }

  #result-table {
    box-shadow: none;
    border: 1px solid #ddd;
  }

  #result-table th { background: #2d3436!important; -webkit-print-color-adjust: exact; }
}
```

- [ ] **Step 3: static/app.js 작성**

```javascript
// static/app.js

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const statusMsg = document.getElementById('status-message');
const resultSection = document.getElementById('result-section');
const resultBody = document.getElementById('result-body');
const totalAmount = document.getElementById('total-amount');

// ===== 업로드 이벤트 =====

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', () => handleFiles(fileInput.files));

document.getElementById('print-btn').addEventListener('click', () => {
  document.getElementById('print-date').textContent = new Date().toLocaleDateString('ko-KR');
  window.print();
});

document.getElementById('add-row-btn').addEventListener('click', addEmptyRow);

document.getElementById('reset-btn').addEventListener('click', () => {
  resultBody.innerHTML = '';
  resultSection.classList.add('hidden');
  fileInput.value = '';
  updateTotal();
});

// ===== 파일 처리 =====

async function handleFiles(files) {
  if (!files || files.length === 0) return;

  showStatus('처리 중입니다...', 'loading');

  const formData = new FormData();
  for (const file of files) formData.append('files', file);

  try {
    const res = await fetch('/process', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok) {
      showStatus(data.error || '오류가 발생했습니다.', 'error');
      return;
    }

    hideStatus();
    renderResults(data);
  } catch (err) {
    showStatus('서버 연결에 실패했습니다. 앱이 실행 중인지 확인해 주세요.', 'error');
  }
}

// ===== 결과 렌더링 =====

function renderResults(receipts) {
  resultSection.classList.remove('hidden');

  for (const receipt of receipts) {
    const items = receipt.items || [];

    if (items.length === 0) {
      addRow(receipt.store_name || '', receipt.date || '', '(항목 없음)', receipt.total || 0);
    } else {
      for (const item of items) {
        addRow(
          receipt.store_name || '',
          receipt.date || '',
          item.name || '',
          item.amount ?? receipt.total ?? 0
        );
      }
    }
  }

  updateTotal();
}

function addRow(storeName, date, itemName, amount) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="text" value="${esc(storeName)}" placeholder="가게명"></td>
    <td><input type="text" value="${esc(date)}" placeholder="YYYY-MM-DD"></td>
    <td><input type="text" value="${esc(itemName)}" placeholder="항목"></td>
    <td><input type="number" value="${amount}" placeholder="0" class="amount-input"></td>
    <td class="no-print"><button class="delete-btn" onclick="deleteRow(this)">✕</button></td>
  `;
  tr.querySelectorAll('.amount-input').forEach(el => el.addEventListener('input', updateTotal));
  resultBody.appendChild(tr);
}

function addEmptyRow() {
  resultSection.classList.remove('hidden');
  addRow('', '', '', 0);
  updateTotal();
}

function deleteRow(btn) {
  btn.closest('tr').remove();
  updateTotal();
}

function updateTotal() {
  const inputs = resultBody.querySelectorAll('.amount-input');
  const sum = Array.from(inputs).reduce((acc, el) => acc + (parseFloat(el.value) || 0), 0);
  totalAmount.textContent = sum.toLocaleString('ko-KR');
}

// ===== 유틸 =====

function showStatus(msg, type) {
  statusMsg.textContent = msg;
  statusMsg.className = `status ${type}`;
}

function hideStatus() {
  statusMsg.className = 'status hidden';
}

function esc(str) {
  return String(str ?? '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}
```

- [ ] **Step 4: 앱 실행 확인**

```bash
# .env 파일 생성
cp .env.example .env
# GEMINI_API_KEY에 실제 키 입력 후
python app.py
```

Expected: 브라우저가 자동으로 `http://localhost:5000` 열림, 업로드 화면 표시

- [ ] **Step 5: 커밋**

```bash
git add templates/ static/
git commit -m "feat: single-page frontend with drag-drop upload and editable table"
```

---

## Task 7: PyInstaller 빌드

**Files:**
- Create: `expense.spec`

- [ ] **Step 1: PyInstaller 설치**

```bash
pip install pyinstaller
```

- [ ] **Step 2: expense.spec 작성**

```python
# expense.spec
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'flask',
        'google.generativeai',
        'PIL',
        'dotenv',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='경비정산서',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # 콘솔 창 숨김
    icon=None,
)
```

- [ ] **Step 3: 빌드 실행**

```bash
pyinstaller expense.spec
```

Expected: `dist/경비정산서.exe` 생성 (약 50~80MB)

- [ ] **Step 4: 빌드 결과물 .gitignore에 추가**

`.gitignore`에 다음 추가:
```
dist/
build/
*.spec.bak
```

- [ ] **Step 5: 커밋**

```bash
git add expense.spec .gitignore
git commit -m "build: add PyInstaller spec for exe packaging"
```

---

## 미결 사항 (추후 작업)

다음은 회사 양식 확인 후 별도로 작업:

1. **인쇄 CSS 커스텀** — `static/style.css`의 `@media print` 섹션을 회사 양식에 맞게 수정
2. **인쇄 헤더 정보** — `templates/index.html`의 `print-header`에 회사명, 부서, 결재란 등 추가
3. **API 키 초기 설정 UI** — `.env` 파일이 없을 때 앱 첫 실행 시 키 입력 화면 (선택)
