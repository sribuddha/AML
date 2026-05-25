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
