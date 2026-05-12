"""Runtime configuration for the Wantuju CloudRun service."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cloudbase_env_id: str | None = os.getenv("CLOUDBASE_ENV_ID")
    cloudbase_apikey: str | None = os.getenv("CLOUDBASE_APIKEY")
    cloudbase_db_instance: str = os.getenv("CLOUDBASE_DB_INSTANCE", "flexdb")
    cloudbase_db_name: str = os.getenv("CLOUDBASE_DB_NAME", "tnt-gizs5ya5s")
    cloudbase_command_db_instance: str | None = os.getenv("CLOUDBASE_COMMAND_DB_INSTANCE")
    cloudbase_command_db_name: str | None = os.getenv("CLOUDBASE_COMMAND_DB_NAME")
    memefast_api_key: str = os.getenv("MEMEFAST_API_KEY", "")
    memefast_api_url: str = os.getenv("MEMEFAST_API_URL", "https://memefast.top/v1/chat/completions")
    memefast_model: str = os.getenv("MEMEFAST_MODEL", "gpt-image-2-all")
    run_env: str = os.getenv("TENCENTCLOUD_RUNENV", "")


settings = Settings()
