"""Core configuration and shared utilities."""

from dotenv import load_dotenv

from .config import Settings, get_settings

load_dotenv()

__all__ = ["Settings", "get_settings"]
