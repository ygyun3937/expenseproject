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
