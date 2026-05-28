from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://factroll:factroll@localhost/factroll"
    auth0_domain: str = ""
    auth0_audience: str = ""
    # Bypass token validation in local dev; never set in production
    auth_disabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
