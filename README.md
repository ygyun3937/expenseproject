# 경비정산서 자동화

영수증 이미지를 업로드하면 AI가 자동으로 항목을 인식하고 경비정산서를 출력해주는 프로그램입니다.

---

## 실행 방법

### 방법 1: .exe 실행 (직원용 — Python 설치 불필요)

1. `경비정산서.exe`와 `.env` 파일을 같은 폴더에 놓습니다
2. `.env` 파일 안에 API 키가 설정되어 있는지 확인합니다
3. `경비정산서.exe`를 더블클릭합니다
4. 브라우저가 자동으로 열리면 영수증을 업로드합니다

### 방법 2: Python으로 직접 실행 (개발용)

```bash
# 1. 저장소 클론
git clone https://github.com/ygyun3937/expenseproject.git
cd expenseproject

# 2. 의존성 설치
pip install -r requirements.txt

# 3. API 키 설정
cp .env.example .env
# .env 파일을 열어서 GEMINI_API_KEY에 실제 키 입력

# 4. 실행
python app.py
```

브라우저에서 `http://localhost:5000` 접속

---

## Windows에서 .exe 빌드하기

> ⚠️ .exe는 반드시 **Windows PC**에서 빌드해야 합니다.

```bash
# 1. 저장소 클론
git clone https://github.com/ygyun3937/expenseproject.git
cd expenseproject

# 2. 의존성 설치
pip install -r requirements.txt
pip install pyinstaller

# 3. .exe 빌드 (5~10분 소요)
pyinstaller expense.spec
```

빌드 완료 후 `dist\경비정산서.exe` 파일이 생성됩니다.

직원들에게 배포할 때는 다음 두 파일을 같은 폴더에 전달하세요:
- `dist\경비정산서.exe`
- `.env` (API 키 포함)

---

## API 키 발급

1. [Google AI Studio](https://aistudio.google.com) 접속
2. 우측 상단 **Get API key** 클릭
3. **Create API key** 후 복사
4. `.env` 파일에 붙여넣기:
   ```
   GEMINI_API_KEY=여기에키입력
   ```

---

## 사용 방법

1. 영수증 이미지를 드래그&드롭하거나 클릭해서 업로드 (여러 장 동시 가능)
2. AI가 자동으로 가게명, 날짜, 항목, 금액을 인식
3. 인식 결과를 화면에서 직접 수정 가능
4. **정산서 인쇄** 버튼 클릭 → 인쇄 미리보기 → 출력

---

## 지원 파일 형식

- JPG, PNG 등 이미지 파일

---

## 문의

API 연결 오류 발생 시 API 키를 구매하신 담당자에게 문의하세요.
