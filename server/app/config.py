from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    fastf1_cache_dir: str = 'cache'
    cors_origins: str = 'http://localhost:3000'
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
