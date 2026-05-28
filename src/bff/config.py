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

def get_observability_provider() -> str:
    _ensure_loaded()
    return os.getenv("OBSERVABILITY_PROVIDER", "none")

def get_langfuse_host() -> str:
    _ensure_loaded()
    return os.getenv("LANGFUSE_HOST", "http://127.0.0.1:3000")

def get_langfuse_public_key() -> str:
    _ensure_loaded()
    return os.getenv("LANGFUSE_PUBLIC_KEY", "")

def get_langfuse_secret_key() -> str:
    _ensure_loaded()
    return os.getenv("LANGFUSE_SECRET_KEY", "")

# ── LLM Provider ────────────────────────────────────────────────

def get_llm_provider() -> str:
    _ensure_loaded()
    return os.getenv("AML_LLM_PROVIDER", "openai")

def get_openai_api_key() -> str:
    _ensure_loaded()
    return os.getenv("AML_OPENAI_API_KEY", "")

def get_gemini_api_key() -> str:
    _ensure_loaded()
    return os.getenv("AML_GEMINI_API_KEY", "")

def get_llm_model_triage() -> str:
    _ensure_loaded()
    return os.getenv("AML_LLM_MODEL_TRIAGE", "gpt-4o-mini")

def get_llm_model_sar() -> str:
    _ensure_loaded()
    return os.getenv("AML_LLM_MODEL_SAR", "gpt-4o")

# ── Batch Settings ──────────────────────────────────────────────

def get_stage2_batch_size() -> int:
    _ensure_loaded()
    return int(os.getenv("AML_STAGE2_BATCH_SIZE", "25"))

def get_stage3_batch_size() -> int:
    _ensure_loaded()
    return int(os.getenv("AML_STAGE3_BATCH_SIZE", "5"))

def get_sar_batch_size() -> int:
    _ensure_loaded()
    return int(os.getenv("AML_SAR_BATCH_SIZE", "5"))

def get_stage2_concurrency() -> int:
    _ensure_loaded()
    return int(os.getenv("AML_STAGE2_CONCURRENCY", "1"))

def get_stage3_concurrency() -> int:
    _ensure_loaded()
    return int(os.getenv("AML_STAGE3_CONCURRENCY", "1"))

def get_sar_concurrency() -> int:
    _ensure_loaded()
    return int(os.getenv("AML_SAR_CONCURRENCY", "1"))

# ── Batch / Chunk Settings ────────────────────────────────────────

def get_chunk_size() -> int:
    _ensure_loaded()
    return int(os.getenv("AML_CHUNK_SIZE", "10000"))

# ── Velocity / Structuring Thresholds ─────────────────────────────

def get_velocity_zscore_threshold() -> float:
    _ensure_loaded()
    return float(os.getenv("AML_VELOCITY_ZSCORE_THRESHOLD", "2.0"))

def get_structuring_24h_threshold() -> int:
    _ensure_loaded()
    return int(os.getenv("AML_STRUCTURING_24H_THRESHOLD", "3"))
