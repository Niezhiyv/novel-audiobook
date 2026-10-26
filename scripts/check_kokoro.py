from __future__ import annotations

import argparse
import json
from pathlib import Path

import soundfile as sf

from app.tts.config import DEFAULT_VOICES, VOICE_LABELS, build_default_engine


def main() -> int:
    parser = argparse.ArgumentParser(description="验证本地 Kokoro 中文音色")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/kokoro/previews"),
        help="试听 WAV 输出目录",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    engine = build_default_engine()
    manifest: list[dict[str, object]] = []
    for voice_id in DEFAULT_VOICES:
        text = f"这是{VOICE_LABELS[voice_id]}的离线试听。"
        clip = engine.synthesize(text, voice_id, 1.0)
        output = args.output / f"{voice_id}.wav"
        sf.write(output, clip.samples, clip.sample_rate)
        duration = round(clip.samples.size / clip.sample_rate, 2)
        manifest.append(
            {
                "voice_id": voice_id,
                "label": VOICE_LABELS[voice_id],
                "file": output.name,
                "sample_rate": clip.sample_rate,
                "duration_seconds": duration,
            }
        )
        print(f"{voice_id}: {duration:.2f}s -> {output}")

    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已验证 {len(manifest)} 个中文音色。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
