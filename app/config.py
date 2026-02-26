from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    llm_provider: str = "gemini"  # "gemini" or "openai"

    gemini_api_keys: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    real_estate_api_key: str = ""
    kakao_api_key: str = ""

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_gemini_keys(self) -> list[str]:
        if self.gemini_api_keys:
            return [k.strip() for k in self.gemini_api_keys.split(",") if k.strip()]
        if self.gemini_api_key:
            return [self.gemini_api_key]
        return []


@lru_cache
def get_settings() -> Settings:
    return Settings()
