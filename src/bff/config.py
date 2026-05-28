import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _ensure_loaded() -> None:
    if not hasattr(_ensure_loaded, "_loaded"):
        _ensure_loaded._loaded = True
        load_dotenv()


def get_data_dir() -> Path:
    _ensure_loaded()
    d = Path(os.getenv("AML_DATA_DIR", str(BASE_DIR / "data")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_upload_dir() -> Path:
    _ensure_loaded()
    d = Path(os.getenv("AML_UPLOAD_DIR", str(get_data_dir() / "uploads")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_database_url() -> str:
    _ensure_loaded()
    return os.getenv("AML_DATABASE_URL", f"sqlite+aiosqlite:///{get_data_dir() / 'aml.db'}")

# ── Observability (Langfuse) ───────────────────────────────────

OBSERVABILITY_PROVIDER = os.getenv("OBSERVABILITY_PROVIDER", "none")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://127.0.0.1:3000")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# ── LLM Provider ────────────────────────────────────────────────

LLM_PROVIDER = os.getenv("AML_LLM_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("AML_OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("AML_GEMINI_API_KEY", "")
LLM_MODEL_TRIAGE = os.getenv("AML_LLM_MODEL_TRIAGE", "gpt-4o-mini")
LLM_MODEL_SAR = os.getenv("AML_LLM_MODEL_SAR", "gpt-4o")

# ── Batch Settings ──────────────────────────────────────────────

STAGE2_BATCH_SIZE = int(os.getenv("AML_STAGE2_BATCH_SIZE", "25"))
STAGE3_BATCH_SIZE = int(os.getenv("AML_STAGE3_BATCH_SIZE", "5"))
SAR_BATCH_SIZE = int(os.getenv("AML_SAR_BATCH_SIZE", "5"))
STAGE2_CONCURRENCY = int(os.getenv("AML_STAGE2_CONCURRENCY", "1"))
STAGE3_CONCURRENCY = int(os.getenv("AML_STAGE3_CONCURRENCY", "1"))
SAR_CONCURRENCY = int(os.getenv("AML_SAR_CONCURRENCY", "1"))

# ── Velocity / Structuring Thresholds ─────────────────────────────

VELOCITY_ZSCORE_THRESHOLD = float(os.getenv("AML_VELOCITY_ZSCORE_THRESHOLD", "2.0"))
STRUCTURING_24H_THRESHOLD = int(os.getenv("AML_STRUCTURING_24H_THRESHOLD", "3"))
