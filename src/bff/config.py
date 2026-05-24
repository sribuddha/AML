import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("AML_DATA_DIR", str(BASE_DIR / "data")))
UPLOAD_DIR = Path(os.getenv("AML_UPLOAD_DIR", str(DATA_DIR / "uploads")))

DATABASE_URL = os.getenv("AML_DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR / 'aml.db'}")

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── LLM Provider ────────────────────────────────────────────────

LLM_PROVIDER = os.getenv("AML_LLM_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("AML_OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("AML_GEMINI_API_KEY", "")
LLM_MODEL_TRIAGE = os.getenv("AML_LLM_MODEL_TRIAGE", "gpt-4o-mini")
LLM_MODEL_SAR = os.getenv("AML_LLM_MODEL_SAR", "gpt-4o")
