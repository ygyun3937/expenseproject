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
