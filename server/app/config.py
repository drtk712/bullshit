"""Runtime configuration for the poster server."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    memefast_api_key: str
    memefast_api_url: str
    memefast_model: str
    poster_server_token: str

    def __init__(self) -> None:
        self.memefast_api_key = os.environ.get("MEMEFAST_API_KEY", "")
        self.memefast_api_url = os.environ.get("MEMEFAST_API_URL", "https://memefast.top/v1/chat/completions")
        self.memefast_model = os.environ.get("MEMEFAST_MODEL", "gpt-image-2-all")
        self.poster_server_token = os.environ.get("POSTER_SERVER_TOKEN", "")

        if not self.memefast_api_key:
            raise RuntimeError("MEMEFAST_API_KEY 环境变量未设置")
        if not self.poster_server_token:
            raise RuntimeError("POSTER_SERVER_TOKEN 环境变量未设置")


settings = Settings()
