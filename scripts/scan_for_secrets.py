"""Pre-commit hook: scan staged files for secrets and API keys.

Exits 1 if any secrets are found, causing the commit to abort.
"""

import re
import sys
from pathlib import Path

SECRET_PATTERNS: list[tuple[str, str]] = [
    ("OpenAI API Key", r"(?i)sk-[A-Za-z0-9]{20,}"),
    ("Gemini API Key", r"(?i)AIza[0-9A-Za-z_-]{35}"),
    ("AWS Access Key", r"(?i)AKIA[0-9A-Z]{16}"),
    ("Generic Private Key", r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
    ("Generic API Key (env var in code)", r"""(?i)(?:api_key|apikey|secret|token)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]"""),
]

FALSE_POSITIVE_PATTERNS = [
    r"VITE_AML_API_KEY",
    r"AML_OPENAI_API_KEY",
    r"AML_GEMINI_API_KEY",
    r"AML_API_KEY",
    r"LANGFUSE_",
]


def _is_false_positive(line: str) -> bool:
    return any(re.search(p, line) for p in FALSE_POSITIVE_PATTERNS)


SKIP_DIRS = {".venv", "work", "__pycache__", ".git", "node_modules", "dist", "build"}


def main() -> int:
    if len(sys.argv) > 1:
        files = [Path(p) for p in sys.argv[1:]]
    else:
        files = [p for p in Path(".").rglob("*") if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)]

    exit_code = 0
    for filepath in files:
        if not filepath.is_file():
            continue
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue

        for line_idx, line in enumerate(text.splitlines(), 1):
            if _is_false_positive(line):
                continue
            for name, pattern in SECRET_PATTERNS:
                if re.search(pattern, line):
                    print(
                        f"SECURITY: {name} found in {filepath}:{line_idx}",
                        file=sys.stderr,
                    )
                    exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
