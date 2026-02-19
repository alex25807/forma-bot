from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    WEBHOOK_SECRET: str = ""
    WEBHOOK_HOST: str = ""
    OPENAI_API_KEY: str = ""
    ADMIN_ID: int = 0
    VIP_CODE: str = "FORMA2026"
    PAYMENT_PROVIDER_TOKEN: str = ""
    STANDARD_PRICE: int = 29900
    PREMIUM_PRICE: int = 49900

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
