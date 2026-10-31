"""Settings read from the environment (and .env in development)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_FALLBACK_MODEL = "gemini-3.5-flash-lite"


@dataclass(frozen=True)
class Settings:
    model: str
    fallback_model: str
    allow_local: bool


def load_settings() -> Settings:
    return Settings(
        model=os.getenv("ACCESS_FIXER_MODEL", DEFAULT_MODEL),
        fallback_model=os.getenv("ACCESS_FIXER_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL),
        allow_local=os.getenv("ACCESS_FIXER_ALLOW_LOCAL", "0") == "1",
    )
