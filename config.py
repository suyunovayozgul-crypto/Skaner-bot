from pydantic_settings import BaseSettings

class Config(BaseSettings):
    # Telegram credentials
    api_id: int = 0
    api_hash: str = ""
    session_name: str = "userbot"

    # Ownership
    owner_id: int = 0
    admin_ids: str = "123456789"
    sudo_id: int = 123456789

    # Bot settings
    command_prefix: str = "."
    download_folder: str = "downloads"

    # AI settings
    openai_key: str = ""
    ai_provider: str = "openai"

    # Defaults
    default_emoji: str = "👍"
    default_purge_limit: int = 100
    db_path: str = "userbot.db"
    timezone: str = "UTC"
    font_default: str = "bold"
    cooldown_default: int = 5  # seconds

    # Other
    bot_token: str = None
    log_level: str = "INFO"
    max_retries: int = 3
    timeout: int = 30

    class Config:
        env_file = ".env"

config = Config()