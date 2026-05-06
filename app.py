import os
import socket
import webbrowser
import threading
import fitz  # PyMuPDF


def is_port_in_use(port: int) -> bool:
    """지정 포트가 이미 사용 중인지 확인 (중복 실행 방지용)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def notify_already_running(port: int):
    """이미 실행 중이면 알림 후 기존 창 열기."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(
            "경비정산서 - 알림",
            "이미 실행 중입니다.\n기존 창을 다시 열어드립니다."
        )
        root.destroy()
    except Exception:
        pass
    webbrowser.open(f"http://localhost:{port}")
from flask import Flask, request, jsonify, render_template
from config import Config, ConfigError
from image_preprocessor import preprocess_image
from receipt_processor import ReceiptProcessor, AllModelsFailedError
from exchange_rate import fetch_rates, fetch_latest
# 유가는 이제 관리자 설정값(settings.json)에 직접 저장 · KNOC 외부 연동 제거
from excel_export import build_workbook as _build_xlsx
from settings_store import get_settings, save_settings, ADMIN_PASSWORD
import category_learner
from datetime import date as _date


def pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    """PDF bytes를 페이지별 PNG 이미지 bytes 리스트로 변환한다."""
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            images.append(pix.tobytes("png"))
    return images


def create_app(testing=False):
    app = Flask(__name__)
    app.config["TESTING"] = testing
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32MB

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/guide")
    def guide():
        return render_template("guide.html")

    @app.route("/vendor/tailwind.js")
    def tailwind_js():
        """Tailwind CDN을 서버에서 1회 캐싱 후 제공 (페이지 로드 속도 ↑)."""
        from flask import Response
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "tailwind_cached.js")
        if not os.path.exists(cache_path):
            try:
                import urllib.request
                urllib.request.urlretrieve("https://cdn.tailwindcss.com/3.4.17", cache_path)
            except Exception:
                # 다운로드 실패 시 원본 CDN으로 리다이렉트
                from flask import redirect
                return redirect("https://cdn.tailwindcss.com/3.4.17")
        with open(cache_path, "rb") as f:
            data = f.read()
        return Response(data, mimetype="application/javascript",
                        headers={"Cache-Control": "public, max-age=86400"})

    @app.route("/process", methods=["POST"])
    def process():
        files = request.files.getlist("files")
        tab = request.form.get("tab", "domestic")
        if tab not in ("domestic", "overseas"):
            tab = "domestic"
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
                raw_bytes = file.read()
                is_pdf = file.filename.lower().endswith(".pdf")
                if is_pdf:
                    pages = pdf_to_images(raw_bytes)
                    page_items = [
                        (f"{file.filename} ({i+1}페이지)", img)
                        for i, img in enumerate(pages)
                    ]
                else:
                    page_items = [(file.filename, raw_bytes)]
            except Exception as e:
                results.append({"filename": file.filename, "error": f"파일을 열 수 없습니다: {e}"})
                continue

            for name, image_bytes in page_items:
                try:
                    processed = preprocess_image(image_bytes)
                    data = processor.process(processed, tab=tab)
                    data["filename"] = name
                    # 학습된 (상점 → 카테고리) 매핑이 있으면 덮어쓰기 (사용자 수정 이력 반영)
                    learned = category_learner.lookup(data.get("store_name", ""))
                    if learned:
                        data["category"] = learned
                        data["_learned"] = True
                    results.append(data)
                except AllModelsFailedError as e:
                    return jsonify({"error": str(e)}), 503
                except Exception as e:
                    results.append({"filename": name, "error": str(e)})

        return jsonify(results)

    @app.route("/api/config", methods=["GET"])
    def api_config():
        """프론트가 사용하는 회사 규정 설정 (settings.json 우선, 없으면 env)."""
        return jsonify(get_settings())

    @app.route("/api/learn-category", methods=["POST"])
    def api_learn_category():
        """사용자가 카테고리 수정 시 (상점명→카테고리) 매핑 학습."""
        body = request.get_json(silent=True) or {}
        merchant = (body.get("merchant") or "").strip()
        category = (body.get("category") or "").strip()
        if not merchant or not category:
            return jsonify({"error": "merchant, category 필수"}), 400
        category_learner.learn(merchant, category)
        return jsonify({"ok": True})

    @app.route("/api/learned-categories", methods=["GET"])
    def api_learned_categories():
        return jsonify({"items": category_learner.list_all()})

    @app.route("/api/learn-category/delete", methods=["POST"])
    def api_learn_delete():
        body = request.get_json(silent=True) or {}
        merchant = (body.get("merchant") or "").strip()
        if not merchant:
            return jsonify({"error": "merchant 필수"}), 400
        category_learner.delete(merchant)
        return jsonify({"ok": True})

    @app.route("/api/admin/settings", methods=["POST"])
    def api_admin_settings():
        """관리자용 설정 업데이트. 비밀번호 필요."""
        body = request.get_json(silent=True) or {}
        if body.get("password") != ADMIN_PASSWORD:
            return jsonify({"error": "비밀번호가 올바르지 않습니다."}), 401
        try:
            updated = save_settings(body.get("settings") or {})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"ok": True, "settings": updated})

    @app.route("/api/admin/verify-password", methods=["POST"])
    def api_verify_password():
        """관리자 비밀번호 검증만 수행 (저장 동작 없음).

        클라이언트가 localStorage 에 저장하는 항목(예: 일비 기준액)을
        쓰기 전에 비밀번호를 검증하는 용도.
        """
        body = request.get_json(silent=True) or {}
        if body.get("password") != ADMIN_PASSWORD:
            return jsonify({"ok": False, "error": "비밀번호가 올바르지 않습니다."}), 401
        return jsonify({"ok": True})

    @app.route("/api/export-excel", methods=["POST"])
    def api_export_excel():
        """현재 정산 상태를 엑셀(.xlsx)로 변환."""
        from flask import Response
        data = request.get_json(silent=True) or {}
        try:
            xlsx_bytes = _build_xlsx(data)
        except Exception as e:
            return jsonify({"error": f"엑셀 생성 실패: {e}"}), 500
        name = (data.get("common") or {}).get("userName") or "expense"
        filename = f"{name}_경비정산_{_date.today().isoformat()}.xlsx"
        # ASCII-safe 파일명 인코딩
        import urllib.parse
        safe = urllib.parse.quote(filename)
        return Response(
            xlsx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe}"},
        )

    @app.route("/api/fuel-price", methods=["GET"])
    def api_fuel_price():
        """유가(원/L) — 관리자 설정값 반환.

        Query: ?type=gasoline|diesel|lpg (미지정 시 전체 반환)
        """
        s = get_settings()
        prices = {
            "gasoline": s.get("fuel_price_gasoline") or 0,
            "diesel": s.get("fuel_price_diesel") or 0,
            "lpg": s.get("fuel_price_lpg") or 0,
        }
        typ = (request.args.get("type") or "").lower()
        if typ in prices:
            price = prices[typ]
            if price <= 0:
                return jsonify({"error": "관리자 설정에 유가가 등록되지 않았습니다. ⚙️ 설정에서 입력해 주세요.", "unavailable": True}), 404
            return jsonify({"price": price, "source": "관리자 설정"})
        return jsonify({**prices, "source": "관리자 설정"})

    @app.route("/api/exchange-rate", methods=["GET"])
    def api_exchange_rate():
        """서울외국환중개 매매기준율 조회.

        Query params:
            currency (required): ISO 통화코드 (USD, JPY 등). KRW는 {rate: 1}.
            start, end (optional): YYYY-MM-DD. 둘 다 있으면 기간 평균.
                                   없으면 최근 영업일 단건.
        """
        currency = (request.args.get("currency") or "").strip().upper()
        if not currency:
            return jsonify({"error": "currency 파라미터가 필요합니다."}), 400
        if currency == "KRW":
            return jsonify({
                "currency": "KRW", "rate": 1, "source": "KRW",
                "business_days": 0, "daily": [],
            })
        start = request.args.get("start")
        end = request.args.get("end")
        try:
            res = fetch_rates(currency, start, end) if (start and end) else fetch_latest(currency)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            return jsonify({"error": f"서울외국환중개 조회 실패: {e}"}), 502
        return jsonify(res._asdict())

    return app


def open_browser(port):
    webbrowser.open(f"http://localhost:{port}")


def run_with_splash(port):
    """tkinter 스플래시 + 상시 실행 컨트롤 창. 창 닫으면 프로세스 완전 종료."""
    import sys
    try:
        import tkinter as tk
    except Exception:
        # tkinter 못 쓰면 그냥 서버 실행
        threading.Timer(1.5, lambda: open_browser(port)).start()
        create_app().run(host="127.0.0.1", port=port, debug=False)
        return

    # Flask를 백그라운드 데몬 스레드에서 실행
    app = create_app()
    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    # 루트 창 (스플래시 → 컨트롤 창으로 전환)
    root = tk.Tk()
    root.title("경비정산서 실행 중")
    root.configure(bg="#1e3a8a")
    root.attributes("-topmost", True)

    # 초기 스플래시 모드
    root.overrideredirect(True)
    w, h = 400, 160
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    title_lbl = tk.Label(root, text="MAK 경비정산서",
                         font=("Malgun Gothic", 16, "bold"),
                         fg="white", bg="#1e3a8a")
    title_lbl.pack(pady=(24, 6))
    status = tk.Label(root, text="프로그램을 시작하고 있습니다...",
                      font=("Malgun Gothic", 10), fg="#cbd5e1", bg="#1e3a8a")
    status.pack()
    hint = tk.Label(root, text="브라우저가 자동으로 열립니다",
                    font=("Malgun Gothic", 9), fg="#94a3b8", bg="#1e3a8a")
    hint.pack(pady=(4, 0))

    def force_exit():
        try:
            root.destroy()
        except Exception:
            pass
        os._exit(0)  # Flask 포함 모두 강제 종료

    def to_control_mode():
        # 스플래시 → 컨트롤 창으로 전환
        status.config(text="✅ 실행 중")
        hint.config(text=f"http://localhost:{port}")
        root.update()
        open_browser(port)

        # 창을 작은 컨트롤 창으로 변환
        root.overrideredirect(False)  # 타이틀바 다시 표시
        root.attributes("-topmost", False)
        w2, h2 = 340, 200
        root.geometry(f"{w2}x{h2}+{sw - w2 - 20}+{sh - h2 - 80}")  # 우하단

        # 종료 버튼 추가
        exit_btn = tk.Button(root, text="🛑 프로그램 종료",
                             font=("Malgun Gothic", 10, "bold"),
                             bg="#ef4444", fg="white", bd=0,
                             activebackground="#dc2626", activeforeground="white",
                             cursor="hand2", command=force_exit)
        exit_btn.pack(pady=(10, 14), padx=20, fill="x", ipady=8)

        # 창 X 버튼 클릭 시에도 완전 종료
        root.protocol("WM_DELETE_WINDOW", force_exit)

    root.after(2000, to_control_mode)
    root.mainloop()
    # mainloop 빠져나오면 안전하게 종료
    os._exit(0)


if __name__ == "__main__":
    import sys
    import traceback
    try:
        port = int(os.getenv("PORT", 5000))
        print(f"[경비정산서] 시작 포트: {port}")
        if is_port_in_use(port):
            print("[경비정산서] 이미 실행 중 - 브라우저로 전환")
            notify_already_running(port)
        else:
            print("[경비정산서] 서버 시작 중...")
            run_with_splash(port)
    except Exception:
        # 에러를 파일로도 기록
        try:
            log_path = os.path.join(os.path.dirname(sys.executable), "경비정산서_error.log")
            with open(log_path, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
            print(f"[경비정산서] 에러 발생. 로그 저장됨: {log_path}")
        except Exception:
            pass
        traceback.print_exc()
        input("\n엔터를 누르면 종료됩니다...")
