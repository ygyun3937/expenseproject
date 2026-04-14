import os
from dotenv import load_dotenv

load_dotenv()

FALLBACK_MODELS = [
    "gemini-2.0-flash-001",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
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
        try:
            self.meal_limit_per_person = int(os.getenv("MEAL_LIMIT_PER_PERSON", "12000"))
        except ValueError:
            self.meal_limit_per_person = 12000
        try:
            self.lodging_limit_per_night = int(os.getenv("LODGING_LIMIT_PER_NIGHT", "70000"))
        except ValueError:
            self.lodging_limit_per_night = 70000
