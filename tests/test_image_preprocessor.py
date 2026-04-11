import io
import pytest
from PIL import Image
from image_preprocessor import preprocess_image


def make_test_image(width=100, height=100, mode="RGB"):
    img = Image.new(mode, (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    # Convert to RGB before saving as JPEG (JPEG doesn't support RGBA)
    if img.mode != "RGB":
        img = img.convert("RGB")
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
