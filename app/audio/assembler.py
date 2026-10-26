from __future__ import annotations

import os
import re
import subprocess
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf

from app.domain.models import Chapter, ChapterStatus, Role, Segment
from app.tts.base import TTSEngine
from app.tts.cache import AudioCache, chunk_text


class MissingVoiceError(ValueError):
    pass


class ChapterAssembler:
    def __init__(
        self,
        engine: TTSEngine,
        cache: AudioCache,
        *,
        chunk_chars: int = 180,
        pause_ms: int = 350,
    ) -> None:
        self.engine = engine
        self.cache = cache
        self.chunk_chars = chunk_chars
        self.pause_ms = pause_ms

    def render(
        self,
        chapters: Sequence[Chapter],
        segments: Sequence[Segment],
        roles: Mapping[int, Role],
        output_dir: Path,
    ) -> list[Path]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        rendered: list[Path] = []
        for chapter in chapters:
            chapter_segments = sorted(
                (segment for segment in segments if segment.chapter_id == chapter.id),
                key=lambda segment: segment.position,
            )
            if not chapter_segments:
                raise ValueError(f"章节没有可生成的片段: {chapter.title}")
            samples, sample_rate = self._render_chapter_samples(chapter_segments, roles)
            path = output_dir / _output_filename(chapter)
            self._encode_mp3(samples, sample_rate, path)
            chapter.status = ChapterStatus.COMPLETED
            chapter.error = None
            chapter.output_path = str(path)
            rendered.append(path)
        return rendered

    def _render_chapter_samples(
        self,
        segments: Sequence[Segment],
        roles: Mapping[int, Role],
    ) -> tuple[np.ndarray, int]:
        pieces: list[np.ndarray] = []
        sample_rate: int | None = None
        for segment_index, segment in enumerate(segments):
            role = roles.get(segment.role_id) if segment.role_id is not None else None
            if role is None:
                raise MissingVoiceError(f"片段没有分配角色: {segment.text[:20]}")
            if not role.voice_id:
                raise MissingVoiceError(f"角色尚未分配音色: {role.name}")

            for chunk in chunk_text(segment.text, self.chunk_chars):
                wav_path = self.cache.get_or_create(
                    chunk,
                    role.voice_id,
                    role.speed,
                    self.engine,
                )
                clip, clip_rate = sf.read(
                    wav_path,
                    dtype="float32",
                    always_2d=False,
                )
                if sample_rate is None:
                    sample_rate = int(clip_rate)
                elif int(clip_rate) != sample_rate:
                    raise ValueError("同一章节的音频采样率不一致")
                pieces.append(np.asarray(clip, dtype=np.float32))
            if segment_index + 1 < len(segments):
                pieces.append(self._pause(sample_rate))

        if not pieces or sample_rate is None:
            raise ValueError("章节没有可拼接的音频")
        return np.concatenate(pieces), sample_rate

    def _pause(self, sample_rate: int) -> np.ndarray:
        count = round(sample_rate * self.pause_ms / 1000)
        return np.zeros(max(1, count), dtype=np.float32)

    def _encode_mp3(self, samples: np.ndarray, sample_rate: int, destination: Path) -> None:
        temporary_wav = destination.with_name(f".{destination.stem}.{uuid.uuid4().hex}.tmp.wav")
        temporary_mp3 = destination.with_name(f".{destination.stem}.{uuid.uuid4().hex}.tmp.mp3")
        try:
            sf.write(
                temporary_wav,
                samples,
                sample_rate,
                format="WAV",
                subtype="FLOAT",
            )
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(temporary_wav),
                    "-codec:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                    str(temporary_mp3),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"FFmpeg 编码失败: {completed.stderr.strip()}")
            os.replace(temporary_mp3, destination)
        finally:
            temporary_wav.unlink(missing_ok=True)
            temporary_mp3.unlink(missing_ok=True)


def _output_filename(chapter: Chapter) -> str:
    safe_title = re.sub(r'[<>:"/\\|?*]', "_", chapter.title).strip(" .")
    if not safe_title:
        safe_title = "未命名章节"
    return f"{chapter.index:03d} - {safe_title}.mp3"
