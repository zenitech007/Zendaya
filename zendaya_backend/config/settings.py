from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Core app settings
    gemini_api_key: str
    app_env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")

    # Hologram mode: 'desktop' for Lottie animation, 'ar' for Unity client
    hologram_mode: str = Field(default="desktop", env="HOLOGRAM_MODE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# ✅ Create global instance
settings = Settings()
