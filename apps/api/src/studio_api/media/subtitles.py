from __future__ import annotations


def millis_to_srt(value: int) -> str:
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def build_srt(segments: list[tuple[str, int]]) -> str:
    cursor = 0
    blocks: list[str] = []
    for index, (text, duration_ms) in enumerate(segments, start=1):
        end = cursor + duration_ms
        blocks.append(f"{index}\n{millis_to_srt(cursor)} --> {millis_to_srt(end)}\n{text}")
        cursor = end
    return "\n\n".join(blocks) + "\n"
