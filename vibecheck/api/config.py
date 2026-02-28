from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./vibecheck.db"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    CLONE_DIR: str = "/tmp/vibecheck-repos"
    DEBUG: bool = False


settings = Settings()
