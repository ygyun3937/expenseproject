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
