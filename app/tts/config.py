from __future__ import annotations

import os
from pathlib import Path

from app.tts.kokoro_engine import KokoroTTSEngine

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = REPOSITORY_ROOT / "models" / "kokoro"

DEFAULT_VOICES = {
    "zf_001": "zf_001",
    "zf_002": "zf_002",
    "zf_003": "zf_003",
    "zm_009": "zm_009",
    "zm_010": "zm_010",
    "zm_011": "zm_011",
}

VOICE_LABELS = {
    "zf_001": "中文女声 1",
    "zf_002": "中文女声 2",
    "zf_003": "中文女声 3",
    "zm_009": "中文男声 1",
    "zm_010": "中文男声 2",
    "zm_011": "中文男声 3",
}

KOKORO_MODEL_VERSION = "kokoro-v1.1-zh-int8"


def build_default_engine() -> KokoroTTSEngine:
    model_path = Path(
        os.getenv(
            "KOKORO_MODEL_PATH",
            str(DEFAULT_MODEL_DIR / "kokoro-v1.1-zh.int8.onnx"),
        )
    )
    voices_path = Path(
        os.getenv(
            "KOKORO_VOICES_PATH",
            str(DEFAULT_MODEL_DIR / "voices-v1.1-zh.bin"),
        )
    )
    vocab_value = os.getenv("KOKORO_VOCAB_PATH")
    vocab_path = Path(vocab_value) if vocab_value else None
    return KokoroTTSEngine(
        model_path,
        voices_path,
        DEFAULT_VOICES,
        language=os.getenv("KOKORO_LANGUAGE", "cmn"),
        vocab_path=vocab_path,
    )
