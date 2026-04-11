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
