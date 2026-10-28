from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from studio_api.core.errors import ErrorCode, StudioError


class FFmpegAdapter:
    backend_id = "ffmpeg"

    @staticmethod
    def available() -> bool:
        return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

    async def probe_file(self, path: Path) -> dict[str, Any]:
        if not self.available():
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "FFmpeg and ffprobe are not installed")
        process = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode:
            raise StudioError(ErrorCode.POLICY_REJECTED, stderr.decode(errors="replace"))
        return json.loads(stdout)

    async def create_scene_clip(
        self,
        image_path: Path,
        output_path: Path,
        duration_seconds: float,
        width: int,
        height: int,
    ) -> Path:
        if not self.available():
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "FFmpeg and ffprobe are not installed")
        frames = max(1, round(duration_seconds * 30))
        filter_graph = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"zoompan=z='min(zoom+0.0003,1.08)':d={frames}:s={width}x{height}:fps=30,"
            "format=yuv420p"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            str(duration_seconds),
            "-vf",
            filter_graph,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise StudioError(ErrorCode.POLICY_REJECTED, stderr.decode(errors="replace"))
        return output_path

    async def assemble_episode(
        self,
        scenes: list[tuple[Path, Path, Path, int]],
        output_path: Path,
        width: int,
        height: int,
    ) -> dict[str, Any]:
        if not self.available():
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "FFmpeg and ffprobe are not installed")
        if not scenes:
            raise StudioError(ErrorCode.POLICY_REJECTED, "No scenes to assemble")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clip_paths: list[Path] = []
        for index, (image_path, audio_path, caption_path, duration_ms) in enumerate(scenes):
            clip_path = output_path.parent / f"scene-{index:02}.mp4"
            seconds = duration_ms / 1000
            frames = round(seconds * 30)
            zoom_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                f"zoompan=z='min(zoom+0.0003,1.08)':d={frames}:s={width}x{height}:fps=30,"
                "format=yuv420p"
            )
            filter_graph = f"[0:v]{zoom_filter}[v];[v][2:v]overlay=0:0:shortest=1[out]"
            await self._run(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-framerate",
                "1",
                "-i",
                str(image_path),
                "-i",
                str(audio_path),
                "-loop",
                "1",
                "-framerate",
                "30",
                "-i",
                str(caption_path),
                "-filter_complex",
                filter_graph,
                "-map",
                "[out]",
                "-map",
                "1:a",
                "-frames:v",
                str(frames),
                "-af",
                f"apad,atrim=duration={seconds}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "24",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-shortest",
                str(clip_path),
            )
            clip_paths.append(clip_path)
        concat_file = output_path.parent / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{path.name}'\n" for path in clip_paths), encoding="utf-8"
        )
        await self._run(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        )
        metadata = await self.probe_file(output_path)
        expected_seconds = sum(item[3] for item in scenes) / 1000
        actual_seconds = float(metadata["format"]["duration"])
        codecs = {stream["codec_type"]: stream["codec_name"] for stream in metadata["streams"]}
        if codecs.get("video") != "h264" or codecs.get("audio") != "aac":
            raise StudioError(ErrorCode.POLICY_REJECTED, "Rendered media codecs are invalid")
        if abs(actual_seconds - expected_seconds) > expected_seconds * 0.05:
            raise StudioError(ErrorCode.POLICY_REJECTED, "Rendered duration drift exceeds 5%")
        await self._run(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(output_path),
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        )
        return metadata

    @staticmethod
    async def _run(*args: str) -> None:
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise StudioError(
                ErrorCode.POLICY_REJECTED,
                f"Media operation failed: {stderr.decode(errors='replace')[:500]}",
            )
