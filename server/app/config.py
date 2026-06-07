from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    fastf1_cache_dir: str = 'cache'
    cors_origins: str = 'http://localhost:3000'

    # Upper bound on the *processed* session cache (the per-session .ff1pkl dirs,
    # not the sqlite http cache). When exceeded, the oldest-accessed session dirs
    # are evicted down to cache_prune_target_mb. 0 disables pruning.
    cache_max_mb: int = 2048
    cache_prune_target_mb: int = 1536
    cache_prune_interval_seconds: int = 600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
