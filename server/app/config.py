from pydantic import SecretStr
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

    # Archive of exported sessions. Uses R2 when r2_bucket is set, otherwise a
    # local directory when archive_local_dir is set, otherwise it's disabled.
    r2_account_id: str = ''
    r2_access_key_id: str = ''
    r2_secret_access_key: SecretStr = SecretStr('')
    r2_bucket: str = ''
    archive_local_dir: str = ''

    # Sessions loaded through FastF1, for sessions not in the archive yet.
    # Each holds a few hundred MB.
    session_cache_size: int = 2
    session_cache_idle_seconds: int = 1800

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
