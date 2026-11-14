"""Resolve bundled project inputs independently of the launch directory."""

from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PRODUCTS = PROJECT_DIR / "data" / "products.csv"
DEFAULT_COMPETITORS = PROJECT_DIR / "data" / "competitors.csv"


def load_environment() -> None:
    load_dotenv(PROJECT_DIR / ".env")
