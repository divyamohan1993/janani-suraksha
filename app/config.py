"""Application configuration with defense-in-depth defaults."""
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "JananiSuraksha"
    app_version: str = "1.0.0"
    debug: bool = False

    # Security
    allowed_origins: list[str] = ["https://jananisuraksha.dmj.one"]
    rate_limit_per_minute: int = 100
    api_key_header: str = "X-API-Key"
    api_keys: list[str] = []  # Empty = no auth required (demo mode)

    # Risk thresholds (from spec)
    risk_threshold_low: float = 0.01
    risk_threshold_medium: float = 0.05
    risk_threshold_high: float = 0.15

    # Engine paths
    risk_table_path: str = "data/risk_table.json"
    facility_graph_path: str = "data/facility_graph.json"
    hb_trajectories_path: str = "data/hb_trajectories.json"

    # External API keys (loaded from .env)
    google_maps_api_key: str = ""
    data_gov_api_key: str = ""

    # Telegram alerts
    telegram_bot_token: str = ""  # From @BotFather
    telegram_chat_id: str = ""    # Target chat/group ID

    # Gemini API (for conversational assessment)
    gemini_api_key: str = ""  # Google AI Studio key

    model_config = {"env_prefix": "JANANI_", "env_file": ".env"}

@lru_cache
def get_settings() -> Settings:
    return Settings()
