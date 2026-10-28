"""Fetch NASA's article photograph and lay it out for preview frames."""

from __future__ import annotations

import io
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from studio_api.core.errors import ErrorCode, StudioError


async def fetch_nasa_source_image(image_url: str) -> tuple[bytes, str]:
    parsed = urlsplit(image_url)
    if parsed.scheme != "https" or parsed.netloc != "assets.science.nasa.gov":
        raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid NASA image URL")
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await client.get(image_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "NASA image is unavailable") from exc
    content = response.content
    mime_type = response.headers.get("content-type", "").split(";", 1)[0]
    if mime_type not in {"image/jpeg", "image/png"} or len(content) > 12_000_000:
        raise StudioError(ErrorCode.POLICY_REJECTED, "NASA image response is invalid")
    try:
        with Image.open(io.BytesIO(content)) as source:
            source.verify()
    except (OSError, ValueError) as exc:
        raise StudioError(ErrorCode.POLICY_REJECTED, "NASA image cannot be decoded") from exc
    return content, mime_type


def nasa_source_card(content: bytes, width: int, height: int) -> bytes:
    with Image.open(io.BytesIO(content)) as source:
        photo = source.convert("RGB")
    canvas = ImageOps.fit(photo, (width, height)).filter(ImageFilter.GaussianBlur(22))
    canvas = Image.blend(canvas, Image.new("RGB", canvas.size, (10, 24, 40)), 0.45)
    margin = max(16, round(min(width, height) * 0.035))
    foreground = ImageOps.contain(photo, (width - margin * 2, height - margin * 4))
    x = (width - foreground.width) // 2
    y = (height - foreground.height) // 2
    canvas.paste(foreground, (x, y))
    draw = ImageDraw.Draw(canvas)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    try:
        font = ImageFont.truetype(font_path, max(16, round(min(width, height) * 0.026)))
    except OSError:
        font = ImageFont.load_default()
    draw.text(
        (margin, margin),
        "Truyện hư cấu từ ảnh NASA",
        fill="white",
        font=font,
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )
    draw.text(
        (margin, margin + 25),
        "Ảnh: NASA Earth Observatory",
        fill="white",
        font=font,
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()
