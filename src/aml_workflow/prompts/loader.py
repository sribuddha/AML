from __future__ import annotations

import pathlib

_PROMPT_DIR = pathlib.Path(__file__).parent

_TRIAGE_SYSTEM = (_PROMPT_DIR / "triage_system.txt").read_text()
_TRIAGE_USER = (_PROMPT_DIR / "triage_user.txt").read_text()
_TRIAGE_STAGE2_SYSTEM = (_PROMPT_DIR / "triage_stage2_system.txt").read_text()
_TRIAGE_STAGE3_SYSTEM = (_PROMPT_DIR / "triage_stage3_system.txt").read_text()


def get_triage_system() -> str:
    return _TRIAGE_SYSTEM


def get_triage_stage2_system() -> str:
    return _TRIAGE_STAGE2_SYSTEM


def get_triage_stage3_system() -> str:
    return _TRIAGE_STAGE3_SYSTEM


def render_triage_user() -> str:
    return _TRIAGE_USER
