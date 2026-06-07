"""Check Langfuse infrastructure secrets in .env for unchanged defaults.

Usage:
    python scripts/check_secrets.py

First run: creates .env.backup, compares .env against known default values.
Subsequent runs: diffs .env vs .env.backup, then updates .env.backup.

Exits 0 if all secrets differ from defaults, 1 otherwise.
"""

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
BACKUP_PATH = REPO_ROOT / ".env.backup"

INFRA_VARS = [
    "LANGFUSE_POSTGRES_PASSWORD",
    "LANGFUSE_CLICKHOUSE_PASSWORD",
    "LANGFUSE_NEXTAUTH_SECRET",
    "LANGFUSE_SALT",
    "LANGFUSE_INIT_ORG_ID",
    "LANGFUSE_INIT_USER_EMAIL",
    "LANGFUSE_INIT_USER_PASSWORD",
    "LANGFUSE_INIT_USER_NAME",
]

# Known default values shipped with the Langfuse docker-compose template.
# If a .env value matches these, it hasn't been rotated.
KNOWN_DEFAULTS = {
    "LANGFUSE_POSTGRES_PASSWORD": "postgres",
    "LANGFUSE_CLICKHOUSE_PASSWORD": "langfuse",
    "LANGFUSE_NEXTAUTH_SECRET": "mysecret",
    "LANGFUSE_SALT": "mysalt",
    "LANGFUSE_INIT_ORG_ID": "default",
    "LANGFUSE_INIT_USER_EMAIL": "admin@example.com",
    "LANGFUSE_INIT_USER_PASSWORD": "password123",
    "LANGFUSE_INIT_USER_NAME": "Admin",
}


def parse_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in INFRA_VARS:
            continue
        value = value.strip().strip("\"'")
        result[key] = value
    return result


def print_table(rows: list[tuple[str, str, str]]) -> None:
    name_width = max(len(r[0]) for r in rows) + 2
    for name, icon, msg in rows:
        print(f"  {name:<{name_width}} {icon}  {msg}")


def main() -> int:
    if not ENV_PATH.exists():
        print("Error: .env not found. Copy .env.template to .env first.")
        return 1

    env = parse_env(ENV_PATH)
    missing = [v for v in INFRA_VARS if v not in env]
    if missing:
        print(f"Error: .env is missing these vars: {', '.join(missing)}")
        return 1

    if not BACKUP_PATH.exists():
        shutil.copy2(ENV_PATH, BACKUP_PATH)

        rows: list[tuple[str, str, str]] = []
        unchanged = 0
        for var in INFRA_VARS:
            val = env[var]
            if KNOWN_DEFAULTS.get(var) == val:
                rows.append((var, "!!", "still default - edit .env to change"))
                unchanged += 1
            else:
                rows.append((var, "OK", "already customized"))

        print("Created .env.backup snapshot.\n")
        print_table(rows)
        print()
        if unchanged:
            print(f"{unchanged} of {len(INFRA_VARS)} secrets still at defaults.")
            print("Edit .env, then re-run this script.")
            return 1
        print("All secrets customized. Ready for docker compose up -d.")
        return 0

    backup = parse_env(BACKUP_PATH)
    rows = []
    changed = 0
    for var in INFRA_VARS:
        current = env[var]
        previous = backup.get(var, "")
        if current != previous:
            rows.append((var, "OK", "changed"))
            changed += 1
        else:
            rows.append((var, "--", "unchanged"))

    shutil.copy2(ENV_PATH, BACKUP_PATH)

    print("Updated .env.backup to current .env.\n")
    print_table(rows)
    print()
    if changed:
        print(f"{changed} changed, {len(INFRA_VARS) - changed} unchanged.")
        print("Run docker compose up -d to apply.")
    else:
        print("All 8 secrets unchanged since last check. No restart needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
