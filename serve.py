import os
from waitress import serve
from app import create_app

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    threads = int(os.getenv("THREADS", 16))
    app = create_app()
    print(f"[경비정산서] 서버 시작: http://{host}:{port} (threads={threads})")
    serve(app, host=host, port=port, threads=threads)
