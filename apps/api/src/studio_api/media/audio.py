from __future__ import annotations

import io
import math
import struct
import wave


def fake_narration_wav(duration_ms: int) -> bytes:
    """Audible fixture tone; never presented as Vietnamese speech or publishable narration."""
    sample_rate = 16_000
    frames = round(sample_rate * duration_ms / 1000)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        samples = bytearray()
        for index in range(frames):
            envelope = min(1.0, index / 1600, (frames - index) / 1600)
            sample = round(1200 * envelope * math.sin(2 * math.pi * 330 * index / sample_rate))
            samples.extend(struct.pack("<h", sample))
        wav.writeframes(samples)
    return output.getvalue()
