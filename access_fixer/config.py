"""Settings read from the environment (and .env in development)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-3.6-flash"


@dataclass(frozen=True)
class Settings:
    model: str
    allow_local: bool


def load_settings() -> Settings:
    return Settings(
        model=os.getenv("ACCESS_FIXER_MODEL", DEFAULT_MODEL),
        allow_local=os.getenv("ACCESS_FIXER_ALLOW_LOCAL", "0") == "1",
    )
