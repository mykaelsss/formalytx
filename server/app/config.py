from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    fastf1_cache_dir: str = 'cache'
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'

    cache_high_water: float = 0.85
    cache_low_water: float = 0.70
    cache_prune_interval_seconds: int = 600

    # FastF1 sets no timeout on its HTTP requests, so an unresponsive upstream
    # would otherwise block the calling thread forever.
    upstream_connect_timeout_seconds: float = 10
    upstream_read_timeout_seconds: float = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
