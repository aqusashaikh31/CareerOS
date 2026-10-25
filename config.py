"""Central configuration. All secrets come from environment / .env (never commit .env)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class Settings:
    # LLM: "anthropic" | "openai" | "none" (none = rule-based fallback, app still works)
    # "ollama" (default, open-source models running locally, no key) | "anthropic" | "openai" | "none"
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama").lower()
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    llm_model: str = os.getenv("LLM_MODEL", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    # Any OpenAI-compatible provider (Groq, OpenRouter, Gemini, Ollama...) via LLM_PROVIDER=openai
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")

    # Database: SQLite by default, PostgreSQL via DATABASE_URL
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'careeros.db'}")

    # Vector DB
    chroma_dir: str = os.getenv("CHROMA_DIR", str(DATA_DIR / "chroma"))

    # Job API (Adzuna). If keys are empty, bundled sample jobs are used.
    adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "")
    adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "")
    adzuna_country: str = os.getenv("ADZUNA_COUNTRY", "in")

    # Matching thresholds (cosine similarity)
    semantic_match_threshold: float = float(os.getenv("SEMANTIC_MATCH_THRESHOLD", "0.60"))
    semantic_weak_threshold: float = float(os.getenv("SEMANTIC_WEAK_THRESHOLD", "0.42"))


settings = Settings()
