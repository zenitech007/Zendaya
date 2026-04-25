"""
Configuration management for Zendaya AI Backend
"""
import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # === Core App Settings ===
    app_name: str = Field(default="Zendaya AI Assistant", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")

    # === Security ===
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # === CORS ===
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="ALLOWED_ORIGINS"
    )

    # === AI Services ===
    gemini_api_key: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    elevenlabs_api_key: Optional[str] = Field(default=None, env="ELEVENLABS_API_KEY")
    default_voice_id: str = Field(default="mxTlDrtKZzOqgjtBw4hM", env="DEFAULT_VOICE_ID")

    # === Voice & Hologram Settings ===
    enable_voice_wake: bool = Field(default=True, env="ENABLE_VOICE_WAKE")
    hologram_mode: str = Field(default="desktop", env="HOLOGRAM_MODE")  # or "ar"

    # === Knowledge & Search ===
    pinecone_api_key: Optional[str] = Field(default=None, env="PINECONE_API_KEY")
    pinecone_environment: str = Field(default="us-east-1", env="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field(default="zendaya-knowledge", env="PINECONE_INDEX_NAME")
    tavily_api_key: Optional[str] = Field(default=None, env="TAVILY_API_KEY")

    # === Cybersecurity Tools ===
    abuseipdb_api_key: Optional[str] = Field(default=None, env="ABUSEIPDB_API_KEY")
    google_safe_browsing_api_key: Optional[str] = Field(default=None, env="GOOGLE_SAFE_BROWSING_API_KEY")

    # === Google Services ===
    google_application_credentials: Optional[str] = Field(
        default=None, env="GOOGLE_APPLICATION_CREDENTIALS"
    )

    # === Database ===
    database_url: str = Field(default="sqlite:///./zendaya.db", env="DATABASE_URL")
    supabase_db_url: Optional[str] = Field(default=None, env="SUPABASE_DB_URL")

    # === Supabase ===
    supabase_url: Optional[str] = Field(default=None, env="SUPABASE_URL")
    supabase_anon_key: Optional[str] = Field(default=None, env="SUPABASE_ANON_KEY")
    supabase_service_role_key: Optional[str] = Field(default=None, env="SUPABASE_SERVICE_ROLE_KEY")

    # === Voice Processing ===
    audio_sample_rate: int = Field(default=16000, env="AUDIO_SAMPLE_RATE")
    audio_chunk_duration: int = Field(default=30, env="AUDIO_CHUNK_DURATION")
    noise_reduction_strength: float = Field(default=0.8, env="NOISE_REDUCTION_STRENGTH")

    # === Smart Home ===
    device_discovery_timeout: int = Field(default=30, env="DEVICE_DISCOVERY_TIMEOUT")
    device_control_timeout: int = Field(default=10, env="DEVICE_CONTROL_TIMEOUT")

    # === Smart Home API Keys ===
    philips_hue_api_key: Optional[str] = Field(default=None, env="PHILIPS_HUE_API_KEY")
    tp_link_username: Optional[str] = Field(default=None, env="TP_LINK_USERNAME")
    tp_link_password: Optional[str] = Field(default=None, env="TP_LINK_PASSWORD")
    samsung_smartthings_token: Optional[str] = Field(default=None, env="SAMSUNG_SMARTTHINGS_TOKEN")

    # === Offline Intelligence ===
    offline_data_dir: str = Field(default="offline_data", env="OFFLINE_DATA_DIR")
    cache_expiry_hours: int = Field(default=24, env="CACHE_EXPIRY_HOURS")

    # === WebSocket ===
    websocket_heartbeat_interval: int = Field(default=30, env="WEBSOCKET_HEARTBEAT_INTERVAL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # ✅ Prevents crashes from unknown env vars

    @property
    def async_database_url(self) -> str:
        """Return the async version of the database URL."""
        url = self.supabase_db_url or self.database_url

        if url.startswith("sqlite:///"):
            return url.replace("sqlite:///", "sqlite+aiosqlite:///")
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://")
        return url


# ✅ Global instance
settings = Settings()
