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
