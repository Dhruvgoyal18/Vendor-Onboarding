from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    database_url: str
    anthropic_api_key: str
    groq_api_key: str = ""
    llm_provider: str = "anthropic"
    resend_api_key: str = ""
    from_email: str = "onboarding@vendoronboarding.com"
    frontend_url: str = "http://localhost:3000"
    environment: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
