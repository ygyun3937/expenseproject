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
                    results.append(data)
                except AllModelsFailedError as e:
                    return jsonify({"error": str(e)}), 503
                except Exception as e:
                    results.append({"filename": name, "error": str(e)})

        return jsonify(results)

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
